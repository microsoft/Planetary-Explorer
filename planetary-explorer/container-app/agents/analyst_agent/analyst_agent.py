"""AnalystAgent — single Azure AI Agent Service agent for all Layer-2 analysis.

This replaces the AnalysisRouter + Orchestrator + Synthesizer + 9-analyzer
registry with one ReAct agent that picks tools from the catalog in
``tools.py``.

Public API
----------
* ``AnalystAgent`` — class with ``async run(request) -> SynthesizedResponse``
* ``get_analyst_agent()`` — module-level singleton accessor

Architecture
------------
* Lazy initialization (no Agent Service calls at import time)
* One agent definition; per-session thread (mirrors EnhancedVisionAgent
  pattern)
* Tools read shared state via the session ContextVar in
  ``session_context.py``
* Fail-open: any uncaught exception returns a SynthesizedResponse with
  ``success=False`` and a graceful error message — never crashes the
  dispatch caller.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextvars import Context
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    from pipeline.contracts import SynthesizedResponse

logger = logging.getLogger(__name__)


def _serialize_tool_result_for_model(result: Any) -> str:
    from mcp_runtime import redact_sensitive_value

    return json.dumps(redact_sensitive_value(result), default=str)


# ---------------------------------------------------------------------------
# Lazy import of Azure SDK — keep dev environments without Azure usable.
# ---------------------------------------------------------------------------

try:
    from azure.identity.aio import DefaultAzureCredential  # type: ignore

    _AZURE_AVAILABLE = True
except Exception as _az_exc:  # pragma: no cover
    logger.warning(
        "azure.identity not available (%s); AnalystAgent will fail-open with a fallback response.",
        _az_exc,
    )
    _AZURE_AVAILABLE = False
    DefaultAzureCredential = None  # type: ignore


# ---------------------------------------------------------------------------
# Per-session thread tracking
# ---------------------------------------------------------------------------


@dataclass
class AnalystThread:
    session_id: str
    thread_id: Optional[str] = None


@dataclass
class AnalystInvocation:
    session_id: str
    thread: Optional[AnalystThread] = None
    owned_threads: List[AnalystThread] = field(default_factory=list)
    stop_requested: bool = False
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    provider_task: Optional[asyncio.Task] = None


# ---------------------------------------------------------------------------
# AnalystAgent
# ---------------------------------------------------------------------------


class AnalystAgent:
    """Single ReAct agent that owns all of Layer 2."""

    def __init__(self) -> None:
        self._agents_client = None
        self._agent_id: Optional[str] = None
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._threads: Dict[str, AnalystThread] = {}
        self._session_locks: WeakValueDictionary[str, asyncio.Lock] = (
            WeakValueDictionary()
        )
        self._background_tasks: set[asyncio.Task] = set()
        self._max_init_retries = 2
        self._run_timeout_seconds = max(
            1.0,
            float(os.getenv("ANALYST_AGENT_TIMEOUT_SECONDS", "60")),
        )
        logger.info("AnalystAgent created (lazy init on first use)")

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            last_error: Optional[Exception] = None
            for attempt in range(self._max_init_retries + 1):
                try:
                    if attempt > 0:
                        wait = 2**attempt
                        logger.info(
                            "[ANALYST] init retry %d/%d after %ds",
                            attempt + 1,
                            self._max_init_retries + 1,
                            wait,
                        )
                        await asyncio.sleep(wait)
                    await self._do_initialize()
                    return
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "[ANALYST] init attempt %d failed: %s", attempt + 1, e
                    )
                    self._agents_client = None
                    self._agent_id = None
                    self._initialized = False
            assert last_error is not None
            raise last_error

    async def _do_initialize(self) -> None:
        if not _AZURE_AVAILABLE:
            raise RuntimeError("azure.identity not installed")

        from azure.ai.agents.aio import AgentsClient  # type: ignore
        from azure.ai.agents.models import AsyncFunctionTool, AsyncToolSet  # type: ignore

        endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5")
        if not endpoint:
            raise ValueError(
                "AZURE_AI_PROJECT_ENDPOINT or AZURE_OPENAI_ENDPOINT must be set"
            )

        from .analyst_prompt import ANALYST_AGENT_INSTRUCTIONS
        from .tools import create_analyst_functions

        credential = DefaultAzureCredential()
        self._agents_client = AgentsClient(endpoint=endpoint, credential=credential)

        functions = AsyncFunctionTool(create_analyst_functions())
        toolset = AsyncToolSet()
        toolset.add(functions)
        self._agents_client.enable_auto_function_calls(toolset)

        agent = await self._agents_client.create_agent(
            model=deployment,
            name="PlanetaryExplorerAnalyst",
            instructions=ANALYST_AGENT_INSTRUCTIONS,
            toolset=toolset,
        )
        self._agent_id = agent.id
        self._initialized = True
        logger.info(
            "AnalystAgent initialized: agent_id=%s model=%s", agent.id, deployment
        )

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    async def _get_or_create_thread(
        self,
        session_id: str,
        invocation: AnalystInvocation,
    ) -> AnalystThread:
        existing = self._threads.get(session_id)
        if existing and existing.thread_id:
            invocation.thread = existing
            invocation.owned_threads.append(existing)
            return existing
        await self._ensure_initialized()
        thread = await self._agents_client.threads.create()  # type: ignore[union-attr]
        rec = AnalystThread(session_id=session_id, thread_id=thread.id)
        invocation.thread = rec
        invocation.owned_threads.append(rec)
        if not invocation.stop_requested:
            self._threads[session_id] = rec
        logger.info("[ANALYST] thread %s -> %s", session_id, thread.id)
        return rec

    async def reset_session(self, session_id: str) -> None:
        """Forget one scoped conversation and delete its remote thread."""
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            thread = self._threads.pop(session_id, None)
            if (
                thread is None
                or not thread.thread_id
                or self._agents_client is None
            ):
                return
            await self._delete_remote_thread(thread)

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    async def run(self, request) -> "SynthesizedResponse":
        """Run analysis and always clear caller-visible session context."""
        from .session_context import clear_session

        try:
            return await self._run_with_session(request)
        finally:
            clear_session()

    async def _run_with_session(self, request) -> "SynthesizedResponse":
        """Run the ReAct loop for a single AnalysisRequest.

        Returns a SynthesizedResponse that's drop-in compatible with the
        old Orchestrator + Synthesizer output (so layer1_agents.AnalyzeAgent
        doesn't need to change its caller contract).
        """
        from pipeline.contracts import (
            AnalysisPlan,
            SynthesizedResponse,
            Source,
            Visualization,
        )
        from .session_context import AnalystSession, set_session

        started = time.time()

        # Populate the ContextVar so tools see the session.
        # ``use_graphrag`` / ``stac_mode`` ride on the request via the
        # request.options dict-style attributes when present (set by
        # AnalyzeAgent before delegation). Default to permissive "on".
        _use_graphrag = bool(getattr(request, "use_graphrag", True))
        _stac_mode = str(getattr(request, "stac_mode", "public") or "public")
        sess = AnalystSession(
            question=request.question,
            session_id=request.session_id,
            authenticated_user_id=request.authenticated_user_id,
            pin=request.pin,
            pins=list(request.pins),
            bbox=request.bbox,
            location_name=request.location_name,
            time_range=request.time_range,
            loaded_collections=list(request.loaded_collections),
            loaded_collections_meta=list(request.loaded_collections_meta),
            screenshot_b64=request.screenshot_b64,
            screenshot_url=request.screenshot_url,
            has_screenshot=request.has_screenshot,
            stac_items=list(request.stac_items),
            tile_urls=list(request.tile_urls),
            history=list(request.history),
            hint=request.hint,
            use_graphrag=_use_graphrag,
            stac_mode=_stac_mode,
        )
        set_session(sess)

        analyst_status: Optional[Dict[str, Any]] = None
        if request.analysis_type == "screenshot":
            answer, evidence, analyst_status = await self._run_explicit_screenshot(
                request
            )
        else:
            invocation = AnalystInvocation(session_id=request.session_id)
            invocation_task = asyncio.create_task(
                self._invoke_serialized(request, invocation)
            )
            try:
                done, _pending = await asyncio.wait(
                    {invocation_task},
                    timeout=self._run_timeout_seconds,
                )
            except asyncio.CancelledError:
                invocation.stop_requested = True
                invocation.stop_event.set()
                self._abandon_invocation_threads(invocation)
                self._track_background_task(invocation_task, "cancelled invocation")
                self._schedule_invocation_cleanup(invocation, invocation_task)
                raise

            if invocation_task not in done:
                logger.warning(
                    "[ANALYST] run timed out after %.1fs, returning fallback response",
                    self._run_timeout_seconds,
                )
                invocation.stop_requested = True
                invocation.stop_event.set()
                self._abandon_invocation_threads(invocation)
                self._track_background_task(invocation_task, "timed-out invocation")
                self._schedule_invocation_cleanup(invocation, invocation_task)
                answer = self._fallback_answer(
                    request,
                    f"timed out after {self._run_timeout_seconds:.1f}s",
                )
                evidence = []
                analyst_status = {
                    "status": "timeout",
                    "timeout_seconds": self._run_timeout_seconds,
                }
            else:
                if invocation_task.cancelled():
                    answer = self._fallback_answer(request, "analysis was cancelled")
                    evidence = []
                    analyst_status = {
                        "status": "error",
                        "error_type": "CancelledError",
                    }
                else:
                    try:
                        answer, _tool_calls, evidence = invocation_task.result()
                    except Exception as e:
                        logger.exception("[ANALYST] run failed, returning fallback response")
                        answer = self._fallback_answer(request, str(e))
                        evidence = []
                        analyst_status = {
                            "status": "error",
                            "error_type": type(e).__name__,
                        }

        # Aggregate sources from tool evidence
        sources: List[Source] = []
        visualizations: List[Visualization] = []
        seen = set()
        for ev in evidence:
            payload = ev.get("payload") or {}
            for src in payload.get("sources", []) or []:
                key = (src.get("title"), src.get("uri"))
                if key in seen:
                    continue
                seen.add(key)
                try:
                    sources.append(Source(**src))
                except Exception:
                    pass
            for visualization in payload.get("visualizations", []) or []:
                try:
                    visualizations.append(Visualization(**visualization))
                except Exception:
                    pass

        # Detect a clarify short-circuit
        structured_by_tool: Dict[str, Any] = {}
        clarify_payload: Optional[Dict[str, Any]] = None
        for ev in evidence:
            tool_name = ev.get("tool")
            payload = ev.get("payload") or {}
            if tool_name == "ask_user_to_clarify":
                clarify_payload = payload
            if tool_name:
                structured_by_tool[tool_name] = payload

        if clarify_payload:
            structured_by_tool["clarify"] = clarify_payload
        if analyst_status:
            structured_by_tool["analyst_status"] = analyst_status

        # Build a degenerate plan record for back-compat with callers that
        # still serialize ``plan``. The plan is just the sequence of tools
        # that actually ran.
        try:
            from pipeline.contracts import AnalysisStep
            plan_steps = [
                AnalysisStep(
                    analyzer=ev.get("tool", "unknown"),
                    hint=None,
                    rationale="ReAct tool call",
                    parallel_with_previous=False,
                )
                for ev in evidence
                if ev.get("tool")
            ]
            plan = AnalysisPlan(steps=plan_steps, reasoning="AnalystAgent ReAct", confidence=0.9)
        except Exception:
            plan = None  # type: ignore

        elapsed_ms = int((time.time() - started) * 1000)
        return SynthesizedResponse(
            answer=answer,
            sources=sources,
            visualizations=visualizations,
            structured=structured_by_tool,
            plan=plan,
            elapsed_ms=elapsed_ms,
        )

    async def _run_explicit_screenshot(self, request):
        """Execute a Get Started Image Analysis request without an LLM routing round."""
        from .session_context import get_session
        from .tools import describe_map_screenshot

        try:
            payload = await asyncio.wait_for(
                describe_map_screenshot(request.question),
                timeout=self._run_timeout_seconds,
            )
        except asyncio.TimeoutError:
            payload = {
                "success": False,
                "error": f"timed out after {self._run_timeout_seconds:.1f}s",
            }
        except Exception as error:
            logger.exception("[ANALYST] explicit screenshot analysis failed")
            payload = {"success": False, "error": str(error)}

        evidence = list(get_session().evidence)
        if not evidence:
            evidence = [{"tool": "describe_map_screenshot", "payload": payload}]
        if payload.get("success") and payload.get("answer"):
            return str(payload["answer"]), evidence, None

        error = str(payload.get("error") or "vision analysis failed")
        return self._fallback_answer(request, error), evidence, {
            "status": "timeout" if "timed out" in error else "error",
            "error_type": "VisionTimeout" if "timed out" in error else "VisionError",
        }

    def _track_background_task(self, task: asyncio.Task, label: str) -> None:
        """Keep detached cleanup alive and consume its terminal result."""
        if task in self._background_tasks:
            return
        self._background_tasks.add(task)

        def finish(completed: asyncio.Task) -> None:
            self._background_tasks.discard(completed)
            try:
                completed.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("[ANALYST] background %s failed", label)

        task.add_done_callback(finish)

    async def _invoke_serialized(self, request, invocation: AnalystInvocation):
        """Allow at most one remote Agent run per user session."""
        lock = self._session_locks.setdefault(request.session_id, asyncio.Lock())
        async with lock:
            if invocation.stop_requested:
                raise asyncio.CancelledError
            if request.geoint_module == "foundation_change":
                provider_task = asyncio.create_task(
                    self._invoke_with_preflight(request, invocation)
                )
            else:
                provider = (
                    self._invoke_responses_api
                    if str(request.model or "").casefold().startswith("gpt-5.6")
                    else self._invoke_agent_service
                )
                provider_task = asyncio.create_task(provider(request, invocation))
            invocation.provider_task = provider_task
            stop_task = asyncio.create_task(
                invocation.stop_event.wait(),
                context=Context(),
            )
            try:
                done, _pending = await asyncio.wait(
                    {provider_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if provider_task in done:
                    if provider_task.cancelled():
                        raise asyncio.CancelledError
                    return provider_task.result()

                provider_task.cancel()
                self._track_background_task(provider_task, "stopped provider")
                raise asyncio.CancelledError
            finally:
                stop_task.cancel()
                self._track_background_task(stop_task, "stop waiter")
                if invocation.stop_requested:
                    self._abandon_invocation_threads(invocation)

    async def _invoke_with_preflight(self, request, invocation: AnalystInvocation):
        """Run mandatory module preflight and the selected model provider."""
        if request.geoint_module == "foundation_change":
            from .tools import list_geofm_models

            geofm_context = await list_geofm_models()
            request = request.model_copy(
                update={
                    "geofm_context": geofm_context,
                    "hint": "foundation_change",
                }
            )
        if invocation.stop_requested:
            raise asyncio.CancelledError
        provider = (
            self._invoke_responses_api
            if str(request.model or "").casefold().startswith("gpt-5.6")
            else self._invoke_agent_service
        )
        return await provider(request, invocation)

    def _schedule_invocation_cleanup(
        self,
        invocation: AnalystInvocation,
        invocation_task: asyncio.Task,
    ) -> None:
        """Cancel only the remote thread owned by one timed-out invocation."""
        cleanup_task = asyncio.create_task(
            self._cleanup_invocation(invocation, invocation_task),
            context=Context(),
        )
        self._track_background_task(cleanup_task, "remote run cleanup")

    async def _cleanup_invocation(
        self,
        invocation: AnalystInvocation,
        invocation_task: asyncio.Task,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + 10.0
        scanned_after_completion = False
        cancelled_run_ids: set[str] = set()
        while asyncio.get_running_loop().time() < deadline:
            provider_task = invocation.provider_task
            if provider_task is not None and not provider_task.done():
                provider_task.cancel()
                self._track_background_task(provider_task, "late provider")

            threads = list(invocation.owned_threads)
            if self._agents_client is not None:
                for thread in threads:
                    if thread.thread_id:
                        await self._cancel_thread_runs(thread, cancelled_run_ids)

            provider_done = provider_task is None or provider_task.done()
            invocation_done = invocation_task.done()
            if provider_done and invocation_done:
                if scanned_after_completion:
                    break
                scanned_after_completion = True
            await asyncio.sleep(0.1)

        if not invocation_task.done():
            invocation_task.cancel()
            self._track_background_task(invocation_task, "late invocation")
        deleted_thread_ids: set[str] = set()
        for thread in invocation.owned_threads:
            if thread.thread_id and thread.thread_id not in deleted_thread_ids:
                await self._delete_remote_thread(thread)
                deleted_thread_ids.add(thread.thread_id)
        self._abandon_invocation_threads(invocation)

    def _abandon_invocation_threads(self, invocation: AnalystInvocation) -> None:
        for thread in invocation.owned_threads:
            if self._threads.get(invocation.session_id) is thread:
                self._threads.pop(invocation.session_id, None)

    async def _cancel_thread_runs(
        self,
        thread: AnalystThread,
        cancelled_run_ids: Optional[set[str]] = None,
    ) -> None:
        """Best-effort bounded cancellation for one detached remote thread."""

        active_statuses = {"queued", "in_progress", "requires_action"}

        async def cancel_runs() -> None:
            runs = self._agents_client.runs.list(
                thread_id=thread.thread_id,
                limit=10,
                order="desc",
            )
            async for run in runs:
                run_id = str(run.id)
                if cancelled_run_ids is not None and run_id in cancelled_run_ids:
                    continue
                raw_status = getattr(run, "status", "")
                status = str(getattr(raw_status, "value", raw_status)).lower()
                if status not in active_statuses:
                    continue
                await self._agents_client.runs.cancel(
                    thread_id=thread.thread_id,
                    run_id=run.id,
                )
                if cancelled_run_ids is not None:
                    cancelled_run_ids.add(run_id)
                logger.info(
                    "[ANALYST] cancelled timed-out remote run %s on thread %s",
                    run.id,
                    thread.thread_id,
                )

        cleanup_task = asyncio.create_task(cancel_runs(), context=Context())
        done, _pending = await asyncio.wait({cleanup_task}, timeout=5.0)
        if cleanup_task not in done:
            cleanup_task.cancel()
            self._track_background_task(cleanup_task, "late remote cleanup")
            logger.warning(
                "[ANALYST] remote run cleanup timed out for thread %s",
                thread.thread_id,
            )
            return
        try:
            cleanup_task.result()
        except Exception as exc:
            logger.warning(
                "[ANALYST] remote run cleanup failed for thread %s: %s",
                thread.thread_id,
                exc,
            )

    async def _delete_remote_thread(self, thread: AnalystThread) -> None:
        """Best-effort bounded deletion for an invocation-owned thread."""
        threads = getattr(self._agents_client, "threads", None)
        if threads is None or not thread.thread_id:
            return
        try:
            async with asyncio.timeout(5.0):
                await threads.delete(thread.thread_id)
        except Exception:
            logger.warning(
                "[ANALYST] failed to delete remote thread %s",
                thread.thread_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Agent Service invocation
    # ------------------------------------------------------------------

    async def _create_responses_client(self):
        """Create an Azure OpenAI Responses client and optional credential."""
        from openai import AsyncOpenAI

        endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT must be set for GPT-5.6")
        api_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
        if api_key:
            return AsyncOpenAI(
                api_key=api_key,
                base_url=f"{endpoint}/openai/v1/",
            ), None

        credential = DefaultAzureCredential()
        token = await credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        return AsyncOpenAI(
            api_key=token.token,
            base_url=f"{endpoint}/openai/v1/",
        ), credential

    async def _invoke_responses_api(
        self,
        request,
        invocation: AnalystInvocation,
    ):
        """Run GPT-5.6 with tools and the requested reasoning effort."""
        from azure.ai.agents.models import AsyncFunctionTool  # type: ignore

        from .analyst_prompt import ANALYST_AGENT_INSTRUCTIONS
        from .session_context import get_session
        from .tools import create_analyst_functions

        if invocation.stop_requested:
            raise asyncio.CancelledError

        functions = create_analyst_functions()
        functions_by_name = {function.__name__: function for function in functions}
        function_tool = AsyncFunctionTool(functions)
        response_tools = []
        for definition in function_tool.definitions:
            function_definition = definition.as_dict()["function"]
            response_tools.append({"type": "function", **function_definition})

        input_items: List[Dict[str, Any]] = []
        for turn in request.history[-4:]:
            role = str(turn.get("role") or "user")
            content = turn.get("content") or turn.get("text")
            if role in {"user", "assistant"} and content:
                input_items.append({"role": role, "content": str(content)[:2000]})
        input_items.append({"role": "user", "content": self._build_message(request)})

        client, credential = await self._create_responses_client()
        tool_calls: List[str] = []
        try:
            response = await client.responses.create(
                model=request.model,
                instructions=ANALYST_AGENT_INSTRUCTIONS,
                input=input_items,
                tools=response_tools,
                reasoning={"effort": request.reasoning_effort},
                parallel_tool_calls=False,
                max_output_tokens=16000,
            )
            tool_rounds = 0
            while True:
                if invocation.stop_requested:
                    raise asyncio.CancelledError
                calls = [
                    item
                    for item in response.output
                    if getattr(item, "type", None) == "function_call"
                ]
                if not calls:
                    return response.output_text or "", tool_calls, list(get_session().evidence)
                if tool_rounds >= 8:
                    raise RuntimeError("GPT-5.6 exceeded the eight-step tool-call limit")
                tool_rounds += 1

                outputs = []
                for call in calls:
                    name = str(call.name)
                    tool_calls.append(name)
                    function = functions_by_name.get(name)
                    if function is None:
                        result = {"success": False, "error": f"Unknown tool: {name}"}
                    else:
                        try:
                            arguments = json.loads(call.arguments or "{}")
                            result = await function(**arguments)
                        except Exception as error:
                            logger.exception("[ANALYST] Responses tool %s failed", name)
                            result = {"success": False, "error": str(error)}
                    outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": _serialize_tool_result_for_model(result),
                        }
                    )

                response = await client.responses.create(
                    model=request.model,
                    instructions=ANALYST_AGENT_INSTRUCTIONS,
                    previous_response_id=response.id,
                    input=outputs,
                    tools=response_tools,
                    reasoning={"effort": request.reasoning_effort},
                    parallel_tool_calls=False,
                    max_output_tokens=16000,
                )
        finally:
            await client.close()
            if credential is not None:
                await credential.close()

    async def _invoke_agent_service(
        self,
        request,
        invocation: AnalystInvocation,
    ):
        """Send message, run, collect assistant text + tool-call evidence."""
        from azure.ai.agents.models import ListSortOrder  # type: ignore
        from geoint.agent_retry import (
            agent_retry_delay_seconds,
            is_retryable_agent_error,
        )

        await self._ensure_initialized()
        assert self._agents_client is not None and self._agent_id is not None

        thread = await self._get_or_create_thread(request.session_id, invocation)
        if invocation.stop_requested:
            raise asyncio.CancelledError

        augmented = self._build_message(request)

        run = None
        for attempt in range(3):
            run_dispatch_started = False
            try:
                if attempt > 0:
                    await asyncio.sleep(agent_retry_delay_seconds(attempt))
                    if invocation.stop_requested:
                        raise asyncio.CancelledError
                    new_thread = await self._agents_client.threads.create()
                    new_record = AnalystThread(
                        session_id=request.session_id, thread_id=new_thread.id
                    )
                    invocation.thread = new_record
                    invocation.owned_threads.append(new_record)
                    if invocation.stop_requested:
                        raise asyncio.CancelledError
                    self._threads[request.session_id] = new_record
                    thread = new_record

                if invocation.stop_requested:
                    raise asyncio.CancelledError

                await self._agents_client.messages.create(
                    thread_id=thread.thread_id,
                    role="user",
                    content=augmented,
                )
                if invocation.stop_requested:
                    raise asyncio.CancelledError
                run_dispatch_started = True
                run = await self._agents_client.runs.create_and_process(
                    thread_id=thread.thread_id,
                    agent_id=self._agent_id,
                    model=request.model,
                )
                if invocation.stop_requested:
                    raise asyncio.CancelledError
                if (
                    run.status == "failed"
                    and is_retryable_agent_error(run.last_error)
                    and attempt < 2
                ):
                    if await self._run_has_tool_calls(thread.thread_id, run.id):
                        logger.warning(
                            "[ANALYST] transient run failure occurred after tool "
                            "dispatch; automatic retry suppressed"
                        )
                        break
                    logger.warning(
                        "[ANALYST] run attempt %d returned transient failure: %s",
                        attempt + 1,
                        run.last_error,
                    )
                    continue
                break
            except Exception as e:
                if invocation.stop_requested:
                    raise asyncio.CancelledError from e
                logger.warning("[ANALYST] run attempt %d failed: %s", attempt + 1, e)
                if run_dispatch_started:
                    raise RuntimeError(
                        "Agent Service transport failed after run dispatch; "
                        "automatic retry suppressed"
                    ) from e
                if attempt == 2:
                    raise

        if run is None:
            raise RuntimeError("Agent Service run returned None")
        if run.status == "failed":
            raise RuntimeError(f"Agent Service run failed: {run.last_error}")

        # Extract assistant response
        answer = ""
        messages = self._agents_client.messages.list(
            thread_id=thread.thread_id,
            order=ListSortOrder.DESCENDING,
        )
        async for msg in messages:
            if msg.run_id != run.id:
                continue
            if msg.role == "assistant" and msg.text_messages:
                answer = msg.text_messages[-1].text.value
                break

        # Extract tool-call names (evidence shape comes from the ContextVar)
        tool_calls: List[str] = []
        run_steps = self._agents_client.run_steps.list(
            thread_id=thread.thread_id,
            run_id=run.id,
        )
        async for step in run_steps:
            details = getattr(step, "step_details", None)
            if details and hasattr(details, "tool_calls"):
                for tc in details.tool_calls or []:
                    fn = getattr(tc, "function", None)
                    if fn and getattr(fn, "name", None):
                        tool_calls.append(fn.name)

        # Tools recorded their results on the session ContextVar
        from .session_context import get_session
        evidence = list(get_session().evidence)
        return answer, tool_calls, evidence

    async def _run_has_tool_calls(self, thread_id: str, run_id: str) -> bool:
        """Return whether a remote run dispatched any function tool."""
        assert self._agents_client is not None
        try:
            run_steps = self._agents_client.run_steps.list(
                thread_id=thread_id,
                run_id=run_id,
            )
            async for step in run_steps:
                details = getattr(step, "step_details", None)
                if details and getattr(details, "tool_calls", None):
                    return True
            return False
        except Exception:
            logger.warning(
                "[ANALYST] could not inspect failed run %s; automatic retry suppressed",
                run_id,
                exc_info=True,
            )
            return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_message(self, request) -> str:
        ctx_lines: List[str] = []
        if request.location_name:
            ctx_lines.append(f"- location_name: {request.location_name}")
        if request.pin:
            ctx_lines.append(f"- pin: lat={request.pin[0]:.5f}, lng={request.pin[1]:.5f}")
        if request.bbox:
            ctx_lines.append(f"- bbox: {request.bbox}")
        if request.loaded_collections:
            ctx_lines.append(
                f"- loaded_collections: {', '.join(request.loaded_collections)}"
            )
        if request.has_screenshot or request.screenshot_b64:
            ctx_lines.append("- screenshot: available")
        if request.time_range:
            ctx_lines.append(
                f"- time_range: {request.time_range} "
                f"(window of data already LOADED on the map — samplable, "
                f"not a hard constraint)"
            )
        if request.history:
            # Last 3 turns max, condensed
            tail = request.history[-3:]
            ctx_lines.append(f"- recent_history: {len(tail)} turn(s)")
        if request.geofm_context is not None:
            ctx_lines.append(
                "- geospatial_foundation_models_preflight: "
                f"{request.geofm_context}"
            )

        ctx_block = "\n".join(ctx_lines) if ctx_lines else "- (no map state)"

        module_instruction = ""
        if request.geoint_module == "foundation_change":
            module_instruction = (
                "\n\n[Foundation Change Module]\n"
                "The Geospatial Foundation Models registry was already queried for "
                "this turn. Use that preflight result and prioritize PlanAura "
                "contextual-change tools. When the user supplies two dates and one "
                "HLS view is loaded, submit compare_with_geofm with that collection "
                "and the two ISO dates; the tool resolves the scene pair. Billed GPU "
                "work still requires the user's approval."
            )

        return (
            f"[Session Context]\n{ctx_block}\n\n"
            f"[User Question]\n{request.question}{module_instruction}"
        )

    def _fallback_answer(self, request, err: str) -> str:
        # Last-resort message when Agent Service is unreachable.
        return (
            "I couldn't complete the analysis right now — the Planetary Explorer "
            f"analyst service was unavailable ({err[:120]}). Please retry; "
            "if the problem persists, check the AZURE_AI_PROJECT_ENDPOINT and "
            "managed-identity configuration."
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


_SINGLETON: Optional[AnalystAgent] = None


def get_analyst_agent() -> AnalystAgent:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = AnalystAgent()
    return _SINGLETON

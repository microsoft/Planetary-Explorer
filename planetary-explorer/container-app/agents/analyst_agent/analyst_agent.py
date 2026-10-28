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
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# AnalystAgent
# ---------------------------------------------------------------------------


class AnalystAgent:
    """Single ReAct agent that owns all of Layer 2."""

    def __init__(self) -> None:
        self._agents_client = None
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._model_lock = asyncio.Lock()
        self._threads: Dict[str, AnalystThread] = {}
        # Per-model agent cache. Previously a single mutable self._agent_id /
        # self._current_model pair was shared across all concurrent requests
        # -- if user A selected gpt-5 and user B selected gpt-4o-mini at
        # nearly the same time, the model-switch code could swap the shared
        # agent_id out from under user A's in-flight run (PR #31 review
        # finding). Caching one agent per model, and resolving the agent_id
        # to a local variable per request instead of reading shared mutable
        # state, removes the race entirely and also avoids leaking a new
        # Agent Service agent definition on every back-and-forth switch.
        self._agents_by_model: Dict[str, str] = {}
        self._default_model: Optional[str] = None
        self._max_init_retries = 2
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
                    self._agents_by_model.clear()
                    self._initialized = False
            assert last_error is not None
            raise last_error

    async def _do_initialize(self, model: Optional[str] = None) -> None:
        if not _AZURE_AVAILABLE:
            raise RuntimeError("azure.identity not installed")

        from azure.ai.agents.aio import AgentsClient  # type: ignore
        from azure.ai.agents.models import AsyncFunctionTool, AsyncToolSet  # type: ignore

        endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )
        # `model` is the user-selected deployment (from the frontend's model
        # selector, threaded in via AnalyzeAgent.run -> AnalystAgent.run).
        # Falls back to the env-configured default when no selection was
        # made, preserving prior behavior for callers that don't pass one.
        deployment = model or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5")
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

        agent = await self._create_agent_capped(deployment, ANALYST_AGENT_INSTRUCTIONS, toolset)
        self._agents_by_model[deployment] = agent.id
        self._default_model = deployment
        self._initialized = True
        logger.info(
            "AnalystAgent initialized: agent_id=%s model=%s", agent.id, deployment
        )

    async def _get_or_create_agent_for_model(self, model: Optional[str]) -> str:
        """Return the Agent Service agent_id for ``model``, creating and
        caching it if needed.

        Resolves to a return value the caller stores locally, rather than
        mutating shared instance state read later by a different request --
        see the race-condition note on ``self._agents_by_model`` in
        ``__init__`` for why that distinction matters.

        Falsy ``model`` resolves to the default deployment set up at first
        initialization. No-op fast path (plain dict read, no lock) when the
        agent for this model is already cached, so the common case (no
        selection made, or same model as last turn) costs nothing.
        """
        await self._ensure_initialized()
        resolved_model = model or self._default_model
        cached = self._agents_by_model.get(resolved_model)
        if cached:
            return cached
        async with self._model_lock:
            cached = self._agents_by_model.get(resolved_model)
            if cached:
                return cached
            from .analyst_prompt import ANALYST_AGENT_INSTRUCTIONS
            from .tools import create_analyst_functions
            from azure.ai.agents.models import AsyncFunctionTool, AsyncToolSet  # type: ignore

            logger.info(
                "[ANALYST] No cached agent for model=%s -- creating one (%d cached so far)",
                resolved_model, len(self._agents_by_model),
            )
            functions = AsyncFunctionTool(create_analyst_functions())
            toolset = AsyncToolSet()
            toolset.add(functions)
            self._agents_client.enable_auto_function_calls(toolset)  # type: ignore[union-attr]
            agent = await self._create_agent_capped(resolved_model, ANALYST_AGENT_INSTRUCTIONS, toolset)
            self._agents_by_model[resolved_model] = agent.id
            return agent.id

    async def _create_agent_capped(self, model: str, instructions: str, toolset):
        """Create an Agent Service agent, capping reasoning effort for
        reasoning-family models when possible.

        The Agents SDK's ``create_agent`` does not document a
        ``reasoning_effort`` parameter the way the plain chat.completions
        API does (see ContextualAgent/LoadAgent/etc., which already cap
        this on gpt-5 for latency). Since the underlying REST API is built
        on the same schema family as the Assistants/Responses API, it may
        still accept the field as an undocumented passthrough -- but this
        is unverified, so we try it and transparently fall back to
        creating the agent without it if the service/SDK rejects the
        extra kwarg. Never raises solely because of this attempt.

        Per-family effort value: gpt-5-family models accept "minimal" (and
        higher); o-series (o1/o3/o4) models only accept "low"/"medium"/
        "high" and reject "minimal" with an HTTP 400 -- using the same
        value for both families was a real bug (PR #31 review finding).
        """
        from model_family import reasoning_effort_for_model
        effort = reasoning_effort_for_model(model)
        if effort:
            try:
                return await self._agents_client.create_agent(  # type: ignore[union-attr]
                    model=model,
                    name="PlanetaryExplorerAnalyst",
                    instructions=instructions,
                    toolset=toolset,
                    reasoning_effort=effort,
                )
            except TypeError:
                # SDK's typed signature rejects the kwarg outright (no
                # passthrough support at all in this SDK version).
                logger.info(
                    "[ANALYST] reasoning_effort not supported by installed "
                    "azure-ai-agents SDK version -- creating agent without it"
                )
            except Exception as exc:
                # Service-side rejection (e.g. unknown field in request
                # body) surfaces as an HTTP error from the SDK, not a
                # TypeError -- catch broadly here so a latency-cap attempt
                # never breaks agent creation.
                logger.info(
                    "[ANALYST] reasoning_effort=%s rejected by service (%s) -- "
                    "creating agent without it", effort, exc,
                )
        return await self._agents_client.create_agent(  # type: ignore[union-attr]
            model=model,
            name="PlanetaryExplorerAnalyst",
            instructions=instructions,
            toolset=toolset,
        )

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    async def _get_or_create_thread(self, session_id: str) -> AnalystThread:
        existing = self._threads.get(session_id)
        if existing and existing.thread_id:
            return existing
        await self._ensure_initialized()
        thread = await self._agents_client.threads.create()  # type: ignore[union-attr]
        rec = AnalystThread(session_id=session_id, thread_id=thread.id)
        self._threads[session_id] = rec
        logger.info("[ANALYST] thread %s -> %s", session_id, thread.id)
        return rec

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    async def run(self, request, model: Optional[str] = None) -> "SynthesizedResponse":
        """Run the ReAct loop for a single AnalysisRequest.

        Returns a SynthesizedResponse that's drop-in compatible with the
        old Orchestrator + Synthesizer output (so layer1_agents.AnalyzeAgent
        doesn't need to change its caller contract).

        Args:
            model: Optional user-selected deployment name (from the
                frontend model selector). Resolved to a cached (or newly
                created) Agent Service agent for that model -- see
                ``_get_or_create_agent_for_model``.
        """
        from pipeline.contracts import (
            AnalysisPlan,
            SynthesizedResponse,
            Source,
            Visualization,
        )
        from .session_context import AnalystSession, clear_session, get_session, set_session

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

        try:
            # Resolved inside the try so a bad/unavailable deployment (e.g.
            # Agent Service rejects the model, transient failure) degrades
            # to _fallback_answer below instead of raising out of run() as
            # an uncaught 500 (PR #41 review finding: this previously ran
            # before the try: block).
            agent_id = await self._get_or_create_agent_for_model(model)
            answer, tool_calls, evidence, skill_pack_id = await self._invoke_agent_service(request, agent_id)
        except Exception as e:
            logger.exception("[ANALYST] run failed, returning fallback response")
            answer = self._fallback_answer(request, str(e))
            tool_calls = []
            evidence = []
            skill_pack_id = None

        # Aggregate sources from tool evidence
        sources: List[Source] = []
        seen = set()
        for ev in evidence:
            for src in (ev.get("payload") or {}).get("sources", []) or []:
                key = (src.get("title"), src.get("uri"))
                if key in seen:
                    continue
                seen.add(key)
                try:
                    sources.append(Source(**src))
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

        if skill_pack_id:
            structured_by_tool["skill_pack"] = {"id": skill_pack_id}

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

        clear_session()

        elapsed_ms = int((time.time() - started) * 1000)
        return SynthesizedResponse(
            answer=answer,
            sources=sources,
            visualizations=[],  # tools currently don't emit visualizations
            structured=structured_by_tool,
            plan=plan,
            elapsed_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Agent Service invocation
    # ------------------------------------------------------------------

    async def _invoke_agent_service(self, request, agent_id: str):
        """Send message, run, collect assistant text + tool-call evidence.

        ``agent_id`` is resolved by the caller (``run()``) via
        ``_get_or_create_agent_for_model`` into a local value, not shared
        mutable instance state -- so concurrent requests on different
        models can't race each other (see the note in ``__init__``).
        """
        from azure.ai.agents.models import ListSortOrder  # type: ignore

        await self._ensure_initialized()
        assert self._agents_client is not None

        thread = await self._get_or_create_thread(request.session_id)

        augmented = self._build_message(request)

        # Skill pack: pick 0-1 domain guidance packs matching this question
        # and inject as additional_instructions for this run only -- pure
        # prompt augmentation, no new tools, no model change. Mirrors the
        # identical mechanism in EnhancedVisionAgent.analyze().
        skill_instructions = None
        skill_pack_id = None
        try:
            from skills.skill_selector import select_skill_pack, render_skill_block
            pack = select_skill_pack(request.question, applies_to="analyst_agent")
            if pack:
                skill_instructions = render_skill_block(pack)
                skill_pack_id = pack.id
        except Exception as skill_exc:
            logger.warning("[SKILLS] Selection failed (continuing without): %s", skill_exc)

        run = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    await asyncio.sleep(2**attempt)
                    new_thread = await self._agents_client.threads.create()
                    self._threads[request.session_id] = AnalystThread(
                        session_id=request.session_id, thread_id=new_thread.id
                    )
                    thread = self._threads[request.session_id]

                await self._agents_client.messages.create(
                    thread_id=thread.thread_id,
                    role="user",
                    content=augmented,
                )
                run = await self._agents_client.runs.create_and_process(
                    thread_id=thread.thread_id,
                    agent_id=agent_id,
                    additional_instructions=skill_instructions,
                )
                break
            except Exception as e:
                logger.warning("[ANALYST] run attempt %d failed: %s", attempt + 1, e)
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
        return answer, tool_calls, evidence, skill_pack_id

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

        ctx_block = "\n".join(ctx_lines) if ctx_lines else "- (no map state)"

        return (
            f"[Session Context]\n{ctx_block}\n\n"
            f"[User Question]\n{request.question}"
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

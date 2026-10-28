"""Shared helper for mapping a model/deployment name to the correct
``reasoning_effort`` (or ``temperature``) kwargs.

Extracted from 4 near-identical copy-pasted if/elif blocks in
analyst_agent.py, contextual_agent.py, clarifier_agent.py, and
semantic_translator.py (PR #41 review: "a single reasoning_kwargs(model)
helper would stop it drifting"). Centralizing this also makes the
per-family mapping independently unit-testable without needing to mock
any Azure client.

Per-family effort value: gpt-5-family models accept "minimal" (and
higher); o-series (o1/o3/o4) models only accept "low"/"medium"/"high"
and reject "minimal" with an HTTP 400 -- using the same value for both
families was the original bug (PR #31 review finding).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def reasoning_effort_for_model(model: Optional[str]) -> Optional[str]:
    """Return the ``reasoning_effort`` value for ``model``, or ``None`` if
    the model family doesn't support/need the parameter (callers should
    use ``temperature`` instead in that case).
    """
    model_lc = (model or "").lower()
    if model_lc.startswith("gpt-5"):
        return "minimal"
    if model_lc.startswith(("o1", "o3", "o4")):
        return "low"
    return None


def is_reasoning_family(model: Optional[str]) -> bool:
    """True if ``model`` is a reasoning-family model (gpt-5*/o1*/o3*/o4*)
    that accepts ``reasoning_effort`` instead of ``temperature``.
    """
    return reasoning_effort_for_model(model) is not None


def resolve_fallback_model_id(
    models: List[Dict[str, Any]], *, hard_default: str = "gpt-4o-mini"
) -> str:
    """Pick the model id to rewrite an invalid/missing selection to.

    Extracted from /api/query's model-validation block (fastapi_app.py)
    so the fallback-selection logic is independently unit-testable without
    importing fastapi_app (which has heavy module-level Azure client
    initialization side effects).

    Precedence: whichever entry is marked isDefault=True (both the ARM
    discovery path and the static fallback list always set exactly one),
    else the first entry in the list, else ``hard_default`` if the list
    is empty (PR #41 review finding: a hardcoded fallback id may not exist
    in every tenant/mode, so prefer the live list's own notion of default).
    """
    default_entry = next((m for m in models if m.get("isDefault")), None)
    if default_entry is not None:
        return default_entry["id"]
    if models:
        return models[0]["id"]
    return hard_default


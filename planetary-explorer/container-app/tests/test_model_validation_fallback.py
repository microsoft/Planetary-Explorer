"""Unit tests for model_family.resolve_fallback_model_id -- the
model-validation fallback-selection logic used by /api/query to decide
what to rewrite an invalid/unknown client-supplied model id to.

Extracted from fastapi_app.py so it's testable without importing that
module (which has heavy side effects at import time). PR #41 review
findings this locks in:
  - the fallback must not be a hardcoded id that may not exist in this
    tenant/mode -- it must come from whatever the live list marks
    isDefault=True.
  - when a models list is empty, fall back to the caller-supplied
    hard_default rather than raising.
"""

from __future__ import annotations

from model_family import resolve_fallback_model_id


def test_resolve_fallback_prefers_is_default_entry():
    models = [
        {"id": "gpt-4o", "isDefault": False},
        {"id": "gpt-4o-mini", "isDefault": True},
        {"id": "gpt-5", "isDefault": False},
    ]
    assert resolve_fallback_model_id(models) == "gpt-4o-mini"


def test_resolve_fallback_respects_custom_configured_default():
    # Mirrors _fallback_models_with_configured_deployment(): when a custom
    # AZURE_OPENAI_DEPLOYMENT_NAME is configured, it is marked isDefault,
    # demoting the static gpt-4o-mini entry.
    models = [
        {"id": "gpt-4o-mini", "isDefault": False},
        {"id": "gpt-4o", "isDefault": False},
        {"id": "gpt-5", "isDefault": False},
        {"id": "my-custom-deployment", "isDefault": True},
    ]
    assert resolve_fallback_model_id(models) == "my-custom-deployment"


def test_resolve_fallback_falls_back_to_first_entry_if_no_default():
    models = [{"id": "only-model", "isDefault": False}]
    assert resolve_fallback_model_id(models) == "only-model"


def test_resolve_fallback_hard_default_when_list_empty():
    assert resolve_fallback_model_id([]) == "gpt-4o-mini"
    assert resolve_fallback_model_id([], hard_default="custom-default") == "custom-default"

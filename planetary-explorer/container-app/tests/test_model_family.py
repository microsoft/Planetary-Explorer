"""Unit tests for model_family.reasoning_effort_for_model -- the per-model-
family mapping used by AnalystAgent, ContextualAgent, ClarifierAgent, and
semantic_translator.tile_selector_agent to decide between
``reasoning_effort`` and ``temperature`` kwargs.

gpt-5-family models accept "minimal" (and higher); o-series (o1/o3/o4)
models only accept "low"/"medium"/"high" and reject "minimal" with an
HTTP 400 -- using the same value for both families was the original bug
(PR #31 review finding). These tests lock in the per-family mapping so a
future refactor can't silently reintroduce that regression.
"""

from __future__ import annotations

import pytest

from model_family import is_reasoning_family, reasoning_effort_for_model


@pytest.mark.parametrize(
    "model,expected",
    [
        ("gpt-5", "minimal"),
        ("gpt-5.5", "minimal"),
        ("gpt-5-chat", "minimal"),
        ("GPT-5", "minimal"),  # case-insensitive
        ("o1", "low"),
        ("o3", "low"),
        ("o3-mini", "low"),
        ("o4", "low"),
        ("o4-mini", "low"),
        ("O1-PREVIEW", "low"),  # case-insensitive
    ],
)
def test_reasoning_effort_for_reasoning_family_models(model, expected):
    assert reasoning_effort_for_model(model) == expected


@pytest.mark.parametrize(
    "model",
    [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "",
        None,
    ],
)
def test_reasoning_effort_none_for_non_reasoning_models(model):
    assert reasoning_effort_for_model(model) is None


def test_is_reasoning_family_matches_reasoning_effort_result():
    assert is_reasoning_family("gpt-5") is True
    assert is_reasoning_family("o3") is True
    assert is_reasoning_family("gpt-4o-mini") is False
    assert is_reasoning_family(None) is False

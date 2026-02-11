"""Tests for services.api.llm_routing_resolver — pure routing resolution logic."""
from __future__ import annotations

import pytest

from services.api.llm_routing_resolver import (
    CompiledRouting,
    RouteCandidate,
    RoutingContext,
    RoutingDecision,
    _as_bool,
    _as_float_opt,
    _as_int_opt,
    _as_str,
    _as_str_list,
    _kind_matches,
    resolve_routing,
    simulate_routing,
)

# ---------------------------------------------------------------------------
# Helpers: _as_bool
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,default,expected", [
    (True, False, True),
    (False, True, False),
    (None, True, True),
    (None, False, False),
    ("1", False, True),
    ("true", False, True),
    ("YES", False, True),
    ("on", False, True),
    ("0", True, False),
    ("false", True, False),
    ("NO", True, False),
    ("off", True, False),
    ("maybe", True, True),
    ("maybe", False, False),
])
def test_as_bool(value, default, expected):
    assert _as_bool(value, default) is expected

# ---------------------------------------------------------------------------
# Helpers: _as_str
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, ""),
    ("hello", "hello"),
    ("  spaced  ", "spaced"),
    (42, "42"),
])
def test_as_str(value, expected):
    assert _as_str(value) == expected

# ---------------------------------------------------------------------------
# Helpers: _as_str_list
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, []),
    ("single", ["single"]),
    ("  ", []),
    (["a", "b"], ["a", "b"]),
    (["a", None, "", "  ", "b"], ["a", "b"]),
    (42, []),
])
def test_as_str_list(value, expected):
    assert _as_str_list(value) == expected

# ---------------------------------------------------------------------------
# Helpers: _as_float_opt / _as_int_opt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, None),
    (0.7, 0.7),
    ("1.5", 1.5),
    ("bad", None),
])
def test_as_float_opt(value, expected):
    assert _as_float_opt(value) == expected


@pytest.mark.parametrize("value,expected", [
    (None, None),
    (100, 100),
    ("200", 200),
    ("nope", None),
])
def test_as_int_opt(value, expected):
    assert _as_int_opt(value) == expected

# ---------------------------------------------------------------------------
# _kind_matches
# ---------------------------------------------------------------------------

def test_kind_matches_empty_set():
    assert _kind_matches(set(), "anything") is True


def test_kind_matches_exact():
    assert _kind_matches({"chat"}, "chat") is True


def test_kind_matches_prefix():
    assert _kind_matches({"chat"}, "chat.stream") is True


def test_kind_matches_no_match():
    assert _kind_matches({"exam"}, "chat") is False


def test_kind_matches_empty_context():
    assert _kind_matches({"chat"}, "") is False

# ---------------------------------------------------------------------------
# Dataclass basics
# ---------------------------------------------------------------------------

def test_routing_context_defaults():
    ctx = RoutingContext()
    assert ctx.role is None
    assert ctx.needs_tools is False
    assert ctx.needs_json is False


def test_route_candidate_as_dict():
    rc = RouteCandidate(
        channel_id="ch1", provider="openai", mode="chat",
        model="gpt-4", temperature=0.5, max_tokens=1024,
        capabilities={"tools": True, "json": False},
    )
    d = rc.as_dict()
    assert d["channel_id"] == "ch1"
    assert d["temperature"] == 0.5
    assert d["max_tokens"] == 1024
    assert d["capabilities"] == {"tools": True, "json": False}


def test_routing_decision_selected_true():
    rc = RouteCandidate("ch1", "p", "m", "model")
    dec = RoutingDecision(enabled=True, matched_rule_id="r1", candidates=[rc], reason="matched")
    assert dec.selected is True


def test_routing_decision_selected_false():
    dec = RoutingDecision(enabled=True, matched_rule_id=None, candidates=[], reason="no_rule_matched")
    assert dec.selected is False


def test_routing_decision_as_dict():
    dec = RoutingDecision(enabled=False, matched_rule_id=None, candidates=[], reason="routing_disabled")
    d = dec.as_dict()
    assert d["enabled"] is False
    assert d["selected"] is False
    assert d["candidates"] == []

# ---------------------------------------------------------------------------
# resolve_routing
# ---------------------------------------------------------------------------

def _compiled(*, enabled=True, errors=None, warnings=None, channels=None, rules=None):
    return CompiledRouting(
        config={"enabled": enabled},
        errors=errors or [],
        warnings=warnings or [],
        channels_by_id=channels or {},
        rules=rules or [],
    )


def test_resolve_disabled():
    dec = resolve_routing(_compiled(enabled=False), RoutingContext())
    assert dec.enabled is False
    assert dec.reason == "routing_disabled"


def test_resolve_with_errors():
    dec = resolve_routing(_compiled(errors=["bad config"]), RoutingContext())
    assert dec.enabled is True
    assert dec.reason == "routing_invalid"


def test_resolve_no_rule_matched():
    rules = [{"id": "r1", "match": {"roles": ["admin"]}, "route": {"channel_id": "ch1"}}]
    channels = {"ch1": {"target": {"provider": "x", "mode": "chat", "model": "m"}}}
    dec = resolve_routing(_compiled(rules=rules, channels=channels), RoutingContext(role="student"))
    assert dec.reason == "no_rule_matched"
    assert dec.selected is False


def test_resolve_rule_matched_with_channel():
    channels = {
        "ch1": {
            "target": {"provider": "openai", "mode": "chat", "model": "gpt-4"},
            "params": {"temperature": 0.3, "max_tokens": 512},
            "capabilities": {"tools": True, "json": True},
        },
    }
    rules = [{"id": "r1", "match": {"roles": ["teacher"]}, "route": {"channel_id": "ch1"}}]
    dec = resolve_routing(_compiled(rules=rules, channels=channels), RoutingContext(role="teacher"))
    assert dec.reason == "matched"
    assert dec.matched_rule_id == "r1"
    assert len(dec.candidates) == 1
    assert dec.candidates[0].provider == "openai"
    assert dec.candidates[0].temperature == 0.3


def test_resolve_fallback_chain():
    channels = {
        "primary": {
            "target": {"provider": "a", "mode": "chat", "model": "m1"},
            "capabilities": {"tools": False},
            "fallback_channels": ["secondary"],
        },
        "secondary": {
            "target": {"provider": "b", "mode": "chat", "model": "m2"},
            "capabilities": {"tools": True},
        },
    }
    rules = [{"id": "r1", "match": {}, "route": {"channel_id": "primary"}}]
    ctx = RoutingContext(needs_tools=True)
    dec = resolve_routing(_compiled(rules=rules, channels=channels), ctx)
    assert dec.reason == "matched"
    # primary filtered out (tools=False), secondary kept
    assert len(dec.candidates) == 1
    assert dec.candidates[0].channel_id == "secondary"

# ---------------------------------------------------------------------------
# simulate_routing
# ---------------------------------------------------------------------------

def test_simulate_routing_structure():
    ctx = RoutingContext(role="student", kind="chat", needs_json=True)
    result = simulate_routing(_compiled(enabled=False), ctx)
    assert "context" in result
    assert result["context"]["role"] == "student"
    assert result["context"]["needs_json"] is True
    assert "decision" in result
    assert result["decision"]["reason"] == "routing_disabled"
    assert "validation" in result
    assert isinstance(result["validation"]["errors"], list)

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path("scripts/admin_auth_tui.py").resolve()
    spec = importlib.util.spec_from_file_location("admin_auth_tui", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_bool_or_any() -> None:
    mod = _load_module()
    assert mod._parse_bool_or_any("true") is True
    assert mod._parse_bool_or_any("false") is False
    assert mod._parse_bool_or_any("any") is None


def test_parse_selection_expr_by_indices_and_id() -> None:
    mod = _load_module()
    page_items = [
        {"teacher_id": "t1"},
        {"teacher_id": "t2"},
        {"teacher_id": "t3"},
        {"teacher_id": "t4"},
    ]
    picked = mod._parse_selection_expr("1,3-4,id:t2,t99", page_items)
    assert picked == {"t1", "t2", "t3", "t4", "t99"}


def test_apply_filters_and_sort() -> None:
    mod = _load_module()
    state = mod.ViewState(
        filter_query="zhang",
        filter_disabled=False,
        filter_password_set=True,
        sort_field="teacher_name",
        sort_desc=False,
    )
    items = [
        {
            "teacher_id": "b",
            "teacher_name": "张三",
            "email": "a@example.com",
            "is_disabled": False,
            "password_set": True,
            "token_version": 1,
        },
        {
            "teacher_id": "a",
            "teacher_name": "Li",
            "email": "b@example.com",
            "is_disabled": False,
            "password_set": True,
            "token_version": 2,
        },
        {
            "teacher_id": "c",
            "teacher_name": "张老师",
            "email": "zhang@example.com",
            "is_disabled": False,
            "password_set": True,
            "token_version": 3,
        },
    ]
    # Query works on id/name/email; only zhang@example.com should match.
    out = mod._apply_filters(items, state)
    assert [row["teacher_id"] for row in out] == ["c"]

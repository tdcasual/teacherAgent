from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, List

import pytest

from services.api.upload_llm_service import (
    UploadLlmDeps,
    llm_autofill_requirements,
    llm_parse_assignment_payload,
    parse_llm_json,
    truncate_text,
    xls_to_table_preview,
    xlsx_to_table_preview,
)


def _deps(call_llm):
    logs: List[Any] = []
    deps = UploadLlmDeps(
        app_root=Path("."),
        call_llm=call_llm,
        diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        parse_list_value=lambda value: [x.strip() for x in str(value or "").split(",") if x.strip()],
        compute_requirements_missing=lambda req: [k for k in ("subject", "topic") if not str(req.get(k) or "").strip()],
        merge_requirements=lambda base, update, overwrite=False: {**dict(base), **dict(update)},
        normalize_excel_cell=lambda value: str(value or ""),
    )
    return deps, logs


def test_truncate_text_and_parse_llm_json_branches() -> None:
    assert truncate_text("abc", 3) == "abc"
    assert truncate_text("abcd", 3).endswith("…")

    assert parse_llm_json("") is None
    assert parse_llm_json("no braces at all") is None
    assert parse_llm_json("prefix {\"ok\":1} suffix") == {"ok": 1}
    assert parse_llm_json("prefix {bad json} suffix") is None


def test_llm_parse_assignment_payload_success() -> None:
    deps, _ = _deps(
        call_llm=lambda *_args, **_kwargs: {
            "choices": [{"message": {"content": json.dumps({"questions": [], "requirements": {}})}}]
        },
    )
    out = llm_parse_assignment_payload("source", "answer", deps=deps)
    assert isinstance(out, dict)
    assert "requirements" in out


def test_llm_autofill_requirements_paths() -> None:
    deps, logs = _deps(call_llm=lambda *_args, **_kwargs: {})

    # no missing early return
    req, missing, ok = llm_autofill_requirements("s", "a", [], {"subject": "ok"}, [], deps=deps)
    assert ok is False
    assert missing == []
    assert req["subject"] == "ok"

    # parse failed branch
    deps_parse_fail, logs_parse_fail = _deps(
        call_llm=lambda *_args, **_kwargs: {"choices": [{"message": {"content": "not-json"}}]},
    )
    _, missing2, ok2 = llm_autofill_requirements(
        "s",
        "a",
        [{"stem": "Q1"}],
        {"subject": "", "topic": ""},
        ["subject", "topic"],
        deps=deps_parse_fail,
    )
    assert ok2 is False
    assert missing2 == ["subject", "topic"]
    assert logs_parse_fail and logs_parse_fail[-1][0] == "upload.autofill.failed"

    # uncertain as string path + non-dict requirements path
    deps_uncertain, _ = _deps(
        call_llm=lambda *_args, **_kwargs: {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "requirements": "bad-obj",
                                "uncertain": "topic,grade_level",
                            }
                        )
                    }
                }
            ]
        }
    )
    merged, missing3, ok3 = llm_autofill_requirements(
        "s",
        "a",
        [{"stem": "Q1"}],
        {"subject": "", "topic": ""},
        ["subject", "topic"],
        deps=deps_uncertain,
    )
    assert ok3 is True
    assert merged == {"subject": "", "topic": ""}
    assert "topic" in missing3
    assert "grade_level" in missing3

    # uncertain non-list path
    deps_uncertain_obj, _ = _deps(
        call_llm=lambda *_args, **_kwargs: {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "requirements": {"subject": "physics"},
                                "uncertain": 123,
                            }
                        )
                    }
                }
            ]
        }
    )
    merged_obj, missing_obj, ok_obj = llm_autofill_requirements(
        "s",
        "a",
        [{"stem": "Q1"}],
        {"subject": "", "topic": ""},
        ["subject", "topic"],
        deps=deps_uncertain_obj,
    )
    assert ok_obj is True
    assert merged_obj["subject"] == "physics"
    assert "topic" in missing_obj

    # exception branch
    deps_exc, logs_exc = _deps(call_llm=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("llm boom")))
    _, _, ok4 = llm_autofill_requirements("s", "a", [], {"subject": ""}, ["subject"], deps=deps_exc)
    assert ok4 is False
    assert logs_exc and logs_exc[-1][0] == "upload.autofill.error"

    # avoid unused warning
    assert isinstance(logs, list)


def test_xlsx_to_table_preview_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_file = tmp_path / "scores.xlsx"
    fake_file.write_text("x", encoding="utf-8")

    deps, _ = _deps(call_llm=lambda *_args, **_kwargs: {})
    deps = UploadLlmDeps(
        app_root=tmp_path,
        call_llm=deps.call_llm,
        diag_log=deps.diag_log,
        parse_list_value=deps.parse_list_value,
        compute_requirements_missing=deps.compute_requirements_missing,
        merge_requirements=deps.merge_requirements,
        normalize_excel_cell=deps.normalize_excel_cell,
    )

    monkeypatch.setattr("services.api.xlsx_rows.iter_rows", lambda *_args, **_kwargs: [])
    assert xlsx_to_table_preview(fake_file, deps=deps) == ""

    monkeypatch.setattr(
        "services.api.xlsx_rows.iter_rows",
        lambda *_args, **_kwargs: [
            (1, {1: " 张三 ", 2: "80"}),
            (2, {1: "李四", 2: "90"}),
        ],
    )
    preview = xlsx_to_table_preview(fake_file, deps=deps)
    assert "row\tC1\tC2" in preview
    assert "1\t张三\t80" in preview

    monkeypatch.setattr(
        "services.api.xlsx_rows.iter_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("rows boom")),
    )
    assert xlsx_to_table_preview(fake_file, deps=deps) == ""


def test_xlsx_to_table_preview_includes_compact_students_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_file = tmp_path / "scores.xlsx"
    fake_file.write_text("x", encoding="utf-8")

    deps, _ = _deps(call_llm=lambda *_args, **_kwargs: {})
    deps = UploadLlmDeps(
        app_root=tmp_path,
        call_llm=deps.call_llm,
        diag_log=deps.diag_log,
        parse_list_value=deps.parse_list_value,
        compute_requirements_missing=deps.compute_requirements_missing,
        merge_requirements=deps.merge_requirements,
        normalize_excel_cell=deps.normalize_excel_cell,
    )

    rows = [(1, {1: "班级", 2: "姓名", 30: "总分"})]
    for i in range(2, 82):
        rows.append((i, {1: "2401班", 2: "张三", 30: str(300 + i)}))
    monkeypatch.setattr("services.api.xlsx_rows.iter_rows", lambda *_args, **_kwargs: rows)

    preview = xlsx_to_table_preview(fake_file, deps=deps)
    assert "[students_compact] total=80" in preview
    assert "[raw_preview]" in preview
    assert "row\tC1\tC2\tC30" in preview


def test_xls_to_table_preview_success_and_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    deps, _ = _deps(call_llm=lambda *_args, **_kwargs: {})

    class _Sheet:
        nrows = 2
        ncols = 2

        @staticmethod
        def cell_value(r, c):
            return [["name", "score"], ["张三", 88]][r][c]

    class _Book:
        @staticmethod
        def sheet_by_index(_idx):
            return _Sheet()

    fake_xlrd = types.ModuleType("xlrd")
    fake_xlrd.open_workbook = lambda _path: _Book()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xlrd", fake_xlrd)

    preview = xls_to_table_preview(tmp_path / "x.xls", deps=deps)
    assert "row\tC1\tC2" in preview
    assert "2\t张三\t88" in preview

    monkeypatch.setattr(fake_xlrd, "open_workbook", lambda _path: (_ for _ in ()).throw(RuntimeError("bad xls")))
    assert xls_to_table_preview(tmp_path / "x.xls", deps=deps) == ""




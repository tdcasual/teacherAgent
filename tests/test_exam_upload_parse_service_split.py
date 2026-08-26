from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SERVICE_PATH = Path("services/api/exam_upload_parse_service.py")
_PARSER_DIR = Path("services/api/exam_upload_parse")
_PARSER_MODULES = {
    "xlsx": _PARSER_DIR / "xlsx_parser.py",
    "xls": _PARSER_DIR / "xls_parser.py",
    "pdf": _PARSER_DIR / "pdf_parser.py",
    "image": _PARSER_DIR / "image_parser.py",
}


def _issues(path: str) -> list[dict]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            path,
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=10",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else []


def test_exam_upload_parse_service_scoring_outputs_hotspot_removed() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    assert "def _write_scoring_outputs(" in source
    issues = _issues(str(_SERVICE_PATH))
    assert not issues, f"C901 issues still present: {issues}"


def test_exam_upload_parse_service_delegates_score_parsers_by_file_type() -> None:
    source = _SERVICE_PATH.read_text(encoding="utf-8")
    assert (
        "from .exam_upload_parse.score_file import parse_score_rows_for_file as "
        "_parse_score_rows_for_file"
    ) in source
    assert 'suffix == ".xlsx"' not in source
    assert 'suffix == ".xls"' not in source
    assert 'suffix == ".pdf"' not in source
    for name, path in _PARSER_MODULES.items():
        assert path.is_file(), f"missing parser module: {path}"
        text = path.read_text(encoding="utf-8")
        assert f"def parse_{name}_score_file(" in text
        issues = _issues(str(path))
        assert not issues, f"C901 issues still present in {path}: {issues}"


def test_exam_upload_parse_service_line_budget() -> None:
    lines = len(_SERVICE_PATH.read_text(encoding="utf-8").splitlines())
    assert lines < 1040, (
        f"exam_upload_parse_service.py is {lines} lines (limit 1040). "
        "Keep per-format score parsers in services/api/exam_upload_parse/."
    )


def test_parse_score_rows_for_file_dispatches_by_suffix(monkeypatch: Any, tmp_path: Path) -> None:
    from services.api.exam_upload_parse import score_file

    calls: List[str] = []

    def _record(label: str):
        def _parser(
            **_kwargs: Any,
        ) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict[str, Any]]]:
            calls.append(label)
            return [{"file_type": label}], [], {"file": label}

        return _parser

    monkeypatch.setattr(score_file, "parse_xlsx_score_file", _record("xlsx"))
    monkeypatch.setattr(score_file, "parse_xls_score_file", _record("xls"))
    monkeypatch.setattr(score_file, "parse_pdf_score_file", _record("pdf"))
    monkeypatch.setattr(score_file, "parse_image_score_file", _record("image"))

    common = {
        "exam_id": "EX1",
        "idx": 0,
        "derived_dir": tmp_path,
        "class_name_hint": "",
        "selected_candidate_id": None,
        "language": "zh",
        "ocr_mode": "FREE_OCR",
        "deps": object(),
    }
    cases = [
        ("scores.xlsx", "xlsx"),
        ("scores.xls", "xls"),
        ("scores.pdf", "pdf"),
        ("scores.png", "image"),
    ]
    for fname, expected in cases:
        calls.clear()
        rows, warnings, schema = score_file.parse_score_rows_for_file(
            fname=fname,
            score_path=tmp_path / fname,
            **common,
        )
        assert calls == [expected], fname
        assert rows == [{"file_type": expected}]
        assert warnings == []
        assert schema == {"file": expected}


def test_xlsx_preview_raise_keeps_script_schema_source(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from services.api.exam_upload_parse.xlsx_parser import parse_xlsx_score_file

    script_schema = {
        "mode": "subject",
        "confidence": 0.91,
        "needs_confirm": False,
        "subject": {"candidate_columns": [{"candidate_id": "pair:4:5"}]},
        "summary": {"data_rows": 2, "parsed_rows": 0},
    }
    score_path = tmp_path / "empty.xlsx"
    score_path.write_text("empty", encoding="utf-8")

    def _raise_preview(_path: Path) -> str:
        raise RuntimeError("preview exploded")

    deps = SimpleNamespace(
        parse_xlsx_with_script=lambda *_args, **_kwargs: ([], script_schema),
        xlsx_to_table_preview=_raise_preview,
    )

    file_rows, warnings, schema_source = parse_xlsx_score_file(
        exam_id="EX1",
        idx=0,
        fname="empty.xlsx",
        score_path=score_path,
        derived_dir=tmp_path,
        class_name_hint="",
        selected_candidate_id=None,
        deps=deps,
    )

    assert file_rows == []
    assert schema_source is not None
    assert schema_source.get("file") == "empty.xlsx"
    assert schema_source.get("mode") == "subject"
    assert schema_source.get("confidence") == 0.91
    assert any("empty.xlsx" in item and "解析异常" in item for item in warnings)

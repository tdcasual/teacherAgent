from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def test_without_generate_flag_does_not_make_generated(tmp_path: Path, monkeypatch) -> None:
    repo = Path(__file__).resolve().parent.parent
    script = repo / "skills" / "student-coach" / "scripts" / "select_practice.py"
    spec = importlib.util.spec_from_file_location("select_practice_cli", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    data = tmp_path / "data"
    bank = data / "question_bank"
    bank.mkdir(parents=True)
    (bank / "questions.csv").write_text(
        "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "select_practice.py",
            "--assignment-id",
            "HW_CLI",
            "--kp",
            "力学",
            "--per-kp",
            "2",
            "--teacher-id",
            "t_zhang",
            "--subject-id",
            "physics",
            "--question-bank",
            str(bank / "questions.csv"),
        ],
    )
    try:
        mod.main()
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "question_bank_insufficient" in str(exc)
    generated = data / "assignments" / "HW_CLI" / "generated_stems"
    assert not generated.exists()

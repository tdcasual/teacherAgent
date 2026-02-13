from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (_ROOT / rel_path).read_text(encoding="utf-8")


def test_student_app_types_include_verify_candidates_contract() -> None:
    source = _read("frontend/apps/student/src/appTypes.ts")
    assert "export type StudentVerifyCandidate" in source
    assert "candidates?: StudentVerifyCandidate[]" in source


def test_use_verification_surfaces_candidates_hint_for_multiple_name_conflict() -> None:
    source = _read("frontend/apps/student/src/hooks/useVerification.ts")
    assert "buildCandidateHint" in source
    assert "候选班级：" in source
    assert "identifyData.error === 'multiple'" in source

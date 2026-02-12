from pathlib import Path

import pytest


def _student_main_chunk_size_kb(dist_assets_dir: Path) -> float:
    candidates = sorted(dist_assets_dir.glob("index-*.js"))
    assert candidates, f"No student main chunk found in {dist_assets_dir}"
    return candidates[0].stat().st_size / 1024.0


def test_student_main_chunk_under_budget() -> None:
    assets_dir = Path("frontend/dist-student/assets")
    if not assets_dir.exists():
        pytest.skip(
            "Missing frontend/dist-student/assets. Build student frontend bundle before budget check."
        )
    size_kb = _student_main_chunk_size_kb(assets_dir)
    assert size_kb < 550, f"Student main chunk too large: {size_kb:.2f} kB (budget < 550 kB)"

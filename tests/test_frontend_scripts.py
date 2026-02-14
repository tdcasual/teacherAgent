import json
import re
from pathlib import Path


def test_frontend_has_lint_script() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    scripts = pkg.get("scripts", {})
    assert "lint" in scripts
    assert "format:check" in scripts


def _extract_output_dir(config_path: Path) -> str:
    source = config_path.read_text(encoding="utf-8")
    match = re.search(r"outputDir:\s*['\"]([^'\"]+)['\"]", source)
    assert match, (
        f"{config_path.name} should declare an explicit outputDir so "
        "parallel Playwright invocations do not overwrite each other's artifacts."
    )
    return match.group(1)


def test_playwright_configs_use_distinct_output_directories() -> None:
    teacher_config = Path("frontend/playwright.teacher.config.ts")
    student_config = Path("frontend/playwright.student.config.ts")

    teacher_output_dir = _extract_output_dir(teacher_config)
    student_output_dir = _extract_output_dir(student_config)

    assert teacher_output_dir != student_output_dir, (
        "Teacher and student Playwright configs must not share outputDir; "
        "shared artifacts can cause flaky parallel E2E runs."
    )
    assert teacher_output_dir.startswith("./test-results/")
    assert student_output_dir.startswith("./test-results/")

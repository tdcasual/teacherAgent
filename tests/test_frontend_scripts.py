import json
import re
from pathlib import Path


def test_frontend_has_lint_script() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    scripts = pkg.get("scripts", {})
    assert "lint" in scripts
    assert "format:check" in scripts


def test_frontend_smoke_runs_mocked_assignment_how_to_loop() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    scripts = pkg.get("scripts", {})
    assert "e2e:assignment-loop" in scripts
    assert "playwright.assignment.config.ts" in str(scripts.get("e2e:assignment-loop", ""))
    smoke = str(scripts.get("e2e:smoke", ""))
    assert "e2e:assignment-loop" in smoke
    assert "E2E_REAL" not in smoke


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


def test_playwright_configs_use_shared_base_factory() -> None:
    shared_config = Path("frontend/playwright.shared.ts")
    teacher_config = Path("frontend/playwright.teacher.config.ts")
    student_config = Path("frontend/playwright.student.config.ts")
    assignment_config = Path("frontend/playwright.assignment.config.ts")

    assert (
        shared_config.exists()
    ), "Playwright shared config module should exist at frontend/playwright.shared.ts."

    shared_source = shared_config.read_text(encoding="utf-8")
    assert "createAppPlaywrightConfig" in shared_source

    teacher_source = teacher_config.read_text(encoding="utf-8")
    student_source = student_config.read_text(encoding="utf-8")
    assignment_source = assignment_config.read_text(encoding="utf-8")

    assert "createAppPlaywrightConfig" in teacher_source
    assert "createAppPlaywrightConfig" in student_source
    assert assignment_config.exists()
    assert "createAppPlaywrightConfig" in assignment_source
    assert "assignment-core-loop.spec.ts" in assignment_source


def test_assignment_playwright_config_uses_distinct_output_directory() -> None:
    assignment_output_dir = _extract_output_dir(Path("frontend/playwright.assignment.config.ts"))
    teacher_output_dir = _extract_output_dir(Path("frontend/playwright.teacher.config.ts"))
    student_output_dir = _extract_output_dir(Path("frontend/playwright.student.config.ts"))

    assert assignment_output_dir.startswith("./test-results/")
    assert assignment_output_dir != teacher_output_dir
    assert assignment_output_dir != student_output_dir

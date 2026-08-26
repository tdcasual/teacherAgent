from pathlib import Path


def _docker_workflow() -> str:
    return Path(".github/workflows/docker.yml").read_text(encoding="utf-8")


def test_docker_workflow_does_not_publish_on_raw_v_star_tags() -> None:
    text = _docker_workflow()
    assert 'tags: ["v*"]' not in text
    assert "refs/tags/v" not in text


def test_docker_workflow_keeps_ci_workflow_run_and_manual_dispatch() -> None:
    text = _docker_workflow()
    assert "workflow_run:" in text
    assert 'workflows: ["CI"]' in text
    assert "types: [completed]" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "workflow_dispatch:" in text


def test_docker_workflow_does_not_use_combined_commit_status_api() -> None:
    text = _docker_workflow()
    assert "/status" not in text
    assert "combined" not in text.lower()

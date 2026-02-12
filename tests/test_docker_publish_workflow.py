from pathlib import Path


def test_docker_publish_is_gated_by_ci_success_on_main() -> None:
    text = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in text
    assert 'workflows: ["CI"]' in text
    assert "types: [completed]" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text


def test_docker_publish_keeps_release_tag_automation() -> None:
    text = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")
    assert "push:" in text
    assert 'tags: ["v*"]' in text
    assert 'startsWith(github.ref, \'refs/tags/v\')' in text
    assert 'branches: ["main"]' not in text


def test_docker_publish_emits_image_digest_summary() -> None:
    text = Path(".github/workflows/docker.yml").read_text(encoding="utf-8")
    assert "Summarize published image" in text
    assert "steps.build.outputs.digest" in text
    assert "GITHUB_STEP_SUMMARY" in text

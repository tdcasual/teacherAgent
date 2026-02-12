from __future__ import annotations

import textwrap
from pathlib import Path

from services.api.skills.loader import clear_cache, load_skills
from services.api.skills.runtime import compile_skill_runtime


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_markdown_skill_supports_advanced_frontmatter_and_includes(tmp_path: Path) -> None:
    clear_cache()
    system_skills = tmp_path / "system_skills"
    system_skills.mkdir(parents=True, exist_ok=True)

    teacher_skill_dir = tmp_path / "teacher_skills" / "advanced"
    _write_text(teacher_skill_dir / "references" / "guardrails.md", "必须输出三段式。")
    _write_text(
        teacher_skill_dir / "SKILL.md",
        textwrap.dedent(
            """\
            ---
            title: Advanced Skill
            description: short desc
            allowed_roles:
              - teacher
            keywords:
              - 小测
            ui:
              prompts:
                - 生成小测
              examples:
                - 给我十道题
            routing:
              keywords:
                - 小测
                - 课堂
              intents:
                - teacher_ops
              negative_keywords:
                - 路由
              keyword_weights:
                小测: 9
              min_score: 5
              min_margin: 2
              confidence_floor: 0.41
              match_mode: word_boundary
            agent:
              tools:
                allow:
                  - exam.list
                  - chart.exec
                deny:
                  - chart.exec
              budgets:
                max_tool_rounds: 2
                max_tool_calls: 3
              model_policy:
                enabled: true
                default:
                  provider: openai
                  mode: openai-chat
                  model: gpt-4.1-mini
                  temperature: 0.2
            includes:
              - references/guardrails.md
            ---
            主指令：先分析再输出。
            """
        ),
    )

    loaded = load_skills(system_skills, teacher_skills_dir=tmp_path / "teacher_skills")
    spec = loaded.skills["advanced"]

    assert spec.source_type == "teacher"
    assert spec.allowed_roles == ["teacher"]
    assert spec.ui.prompts == ["生成小测"]
    assert spec.ui.examples == ["给我十道题"]

    assert spec.routing.keywords == ["小测", "课堂"]
    assert spec.routing.intents == ["teacher_ops"]
    assert spec.routing.negative_keywords == ["路由"]
    assert spec.routing.keyword_weights.get("小测") == 9
    assert spec.routing.min_score == 5
    assert spec.routing.min_margin == 2
    assert spec.routing.confidence_floor == 0.41
    assert spec.routing.match_mode == "word_boundary"

    assert spec.agent.tools.allow == ["exam.list", "chart.exec"]
    assert spec.agent.tools.deny == ["chart.exec"]
    assert spec.agent.budgets.max_tool_rounds == 2
    assert spec.agent.budgets.max_tool_calls == 3
    assert spec.agent.model_policy.enabled is True
    assert spec.agent.model_policy.default is not None
    assert spec.agent.model_policy.default.model == "gpt-4.1-mini"

    assert "主指令：先分析再输出。" in spec.instructions
    assert "[Reference: references/guardrails.md]" in spec.instructions
    assert "必须输出三段式。" in spec.instructions
    clear_cache()


def test_markdown_skill_can_load_local_prompt_module(tmp_path: Path) -> None:
    clear_cache()
    system_skills = tmp_path / "system_skills"
    system_skills.mkdir(parents=True, exist_ok=True)

    teacher_skill_dir = tmp_path / "teacher_skills" / "local-module-skill"
    _write_text(teacher_skill_dir / "references" / "module.md", "LOCAL MODULE CONTENT")
    _write_text(
        teacher_skill_dir / "SKILL.md",
        textwrap.dedent(
            """\
            ---
            title: Local Module Skill
            agent:
              prompt_modules:
                - references/module.md
            ---
            主体说明
            """
        ),
    )

    loaded = load_skills(system_skills, teacher_skills_dir=tmp_path / "teacher_skills")
    spec = loaded.skills["local-module-skill"]
    runtime = compile_skill_runtime(spec)

    assert "主体说明" in runtime.system_prompt
    assert "LOCAL MODULE CONTENT" in runtime.system_prompt
    clear_cache()

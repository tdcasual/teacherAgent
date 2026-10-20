from pathlib import Path

_SKILL_MD = Path("skills/teacher-assignment-ops/SKILL.md")


def test_skill_md_has_no_score_or_rank_band() -> None:
    text = _SKILL_MD.read_text(encoding="utf-8")
    assert "ScoreBand" not in text
    assert "RankBand" not in text
    assert "未交=3; 逾期=1; 已交=28" in text

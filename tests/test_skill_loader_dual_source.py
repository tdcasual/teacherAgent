from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.skills.loader import load_skills


class SkillLoaderDualSourceTest(unittest.TestCase):
    def _write_skill_yaml(self, skill_dir: Path, *, title: str, desc: str = "") -> None:
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "skill.yaml").write_text(
            "\n".join(
                [
                    "schema_version: 1",
                    f"title: {title}",
                    f"description: {desc or title}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_dual_source_merges_and_claude_overrides_project(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            project_skills = root / "project" / "skills"
            self._write_skill_yaml(project_skills / "alpha", title="project-alpha")
            self._write_skill_yaml(project_skills / "beta", title="project-beta")

            fake_home = root / "home"
            claude_skills = fake_home / ".claude" / "skills"
            self._write_skill_yaml(claude_skills / "alpha", title="claude-alpha")
            self._write_skill_yaml(claude_skills / "gamma", title="claude-gamma")

            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(fake_home)
            try:
                loaded = load_skills(project_skills)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

            self.assertIn("alpha", loaded.skills)
            self.assertIn("beta", loaded.skills)
            self.assertIn("gamma", loaded.skills)
            self.assertEqual(loaded.skills["alpha"].title, "claude-alpha")
            self.assertEqual(loaded.skills["alpha"].source_type, "claude")
            self.assertEqual(loaded.skills["gamma"].source_type, "claude")
            self.assertEqual(loaded.skills["beta"].source_type, "system")
            self.assertIn(str(claude_skills / "alpha" / "skill.yaml"), loaded.skills["alpha"].source_path)

    def test_claude_skill_md_is_accepted_without_skill_yaml(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            project_skills = root / "project" / "skills"
            project_skills.mkdir(parents=True, exist_ok=True)

            fake_home = root / "home"
            skill_dir = fake_home / ".claude" / "skills" / "claude-notes"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "# Claude Notes\\n\\nYou are a specialized helper for Claude-style skills.",
                encoding="utf-8",
            )

            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(fake_home)
            try:
                loaded = load_skills(project_skills)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

            self.assertIn("claude-notes", loaded.skills)
            self.assertEqual(loaded.skills["claude-notes"].title, "Claude Notes")
            self.assertIn("specialized helper", loaded.skills["claude-notes"].desc)
            self.assertEqual(loaded.skills["claude-notes"].source_type, "claude")

    def test_invalid_claude_override_keeps_project_skill(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            project_skills = root / "project" / "skills"
            self._write_skill_yaml(project_skills / "alpha", title="project-alpha")

            fake_home = root / "home"
            bad_dir = fake_home / ".claude" / "skills" / "alpha"
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "skill.yaml").write_text("title: [broken", encoding="utf-8")

            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(fake_home)
            try:
                loaded = load_skills(project_skills)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

            self.assertIn("alpha", loaded.skills)
            self.assertEqual(loaded.skills["alpha"].title, "project-alpha")
            self.assertTrue(
                any((err.skill_id == "alpha") and ("YAML parse failed" in err.message) for err in loaded.errors),
                msg="expected YAML parse error for invalid .claude override",
            )


if __name__ == "__main__":
    unittest.main()

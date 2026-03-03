from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.skills.loader import clear_cache, load_skills


class SkillLoaderSingleSourceTest(unittest.TestCase):
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

    def test_loader_reads_project_skills_only(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            project_skills = root / "project" / "skills"
            self._write_skill_yaml(project_skills / "alpha", title="project-alpha")
            self._write_skill_yaml(project_skills / "beta", title="project-beta")

            fake_home = root / "home"
            home_skills = fake_home / ".claude" / "skills"
            self._write_skill_yaml(home_skills / "alpha", title="home-alpha")
            self._write_skill_yaml(home_skills / "gamma", title="home-gamma")

            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(fake_home)
            try:
                clear_cache()
                loaded = load_skills(project_skills)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

            self.assertIn("alpha", loaded.skills)
            self.assertIn("beta", loaded.skills)
            self.assertNotIn("gamma", loaded.skills)
            self.assertEqual(loaded.skills["alpha"].title, "project-alpha")
            self.assertEqual(loaded.skills["alpha"].source_type, "system")
            self.assertEqual(loaded.skills["beta"].source_type, "system")

    def test_home_skill_markdown_is_ignored(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            project_skills = root / "project" / "skills"
            project_skills.mkdir(parents=True, exist_ok=True)

            fake_home = root / "home"
            skill_dir = fake_home / ".claude" / "skills" / "home-notes"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "# Home Notes\n\nThis should be ignored by project loader.",
                encoding="utf-8",
            )

            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(fake_home)
            try:
                clear_cache()
                loaded = load_skills(project_skills)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

            self.assertNotIn("home-notes", loaded.skills)

    def test_invalid_home_overlay_does_not_affect_project_skill(self):
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
                clear_cache()
                loaded = load_skills(project_skills)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

            self.assertIn("alpha", loaded.skills)
            self.assertEqual(loaded.skills["alpha"].title, "project-alpha")
            self.assertFalse(any(err.skill_id == "alpha" for err in loaded.errors))


if __name__ == "__main__":
    unittest.main()

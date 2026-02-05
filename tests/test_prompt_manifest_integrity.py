import json
import unittest
from pathlib import Path


class TestPromptManifestIntegrity(unittest.TestCase):
    def test_manifest_paths_exist(self):
        repo = Path(__file__).resolve().parents[1]
        manifest_path = repo / "prompts" / "v1" / "manifest.json"
        self.assertTrue(manifest_path.exists(), "prompts/v1/manifest.json must exist")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIsInstance(manifest, dict)

        base = (repo / "prompts" / "v1").resolve()
        for role, modules in manifest.items():
            self.assertIsInstance(modules, list, f"manifest role {role} must map to list")
            self.assertTrue(modules, f"manifest role {role} must not be empty")
            for rel in modules:
                self.assertIsInstance(rel, str)
                path = (base / rel).resolve()
                self.assertTrue(path.exists(), f"module missing: {rel}")
                self.assertTrue(base in path.parents or path == base, f"path traversal detected: {rel}")

    def test_manifest_has_required_roles(self):
        repo = Path(__file__).resolve().parents[1]
        manifest_path = repo / "prompts" / "v1" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for role in ("teacher", "student", "unknown"):
            self.assertIn(role, manifest)

    def test_manifest_common_guardrails_first(self):
        repo = Path(__file__).resolve().parents[1]
        manifest_path = repo / "prompts" / "v1" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for role in ("teacher", "student", "unknown"):
            first = (manifest.get(role) or [""])[0]
            self.assertEqual(first, "common/00_guardrails.md", f"{role} should start with guardrails")


if __name__ == "__main__":
    unittest.main()


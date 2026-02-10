from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_provider_registry_service import (
    TeacherProviderRegistryDeps,
    merged_model_registry,
    resolve_provider_target,
    teacher_provider_registry_create,
    teacher_provider_registry_delete,
    teacher_provider_registry_get,
    teacher_provider_registry_probe_models,
    teacher_provider_registry_update,
    validate_master_key_policy,
)


def _base_registry() -> dict:
    return {
        "defaults": {"provider": "openai", "mode": "openai-chat", "timeout_sec": 120, "retry": 1},
        "providers": {
            "openai": {
                "api_key_envs": ["OPENAI_API_KEY"],
                "base_url": "https://api.openai.com/v1",
                "auth": {"type": "bearer"},
                "modes": {"openai-chat": {"endpoint": "/chat/completions", "model_env": "OPENAI_CHAT_MODEL", "default_model": "gpt-4.1-mini"}},
            }
        },
        "routing": {"fallback_chain": ["openai-chat"]},
    }


class TeacherProviderRegistryServiceTest(unittest.TestCase):
    def _deps(self, base: Path, env: dict[str, str]) -> TeacherProviderRegistryDeps:
        return TeacherProviderRegistryDeps(
            model_registry=_base_registry(),
            resolve_teacher_id=lambda teacher_id: str(teacher_id or "teacher_default"),
            teacher_workspace_dir=lambda teacher_id: base / "teacher_workspaces" / teacher_id,
            atomic_write_json=lambda path, payload: path.parent.mkdir(parents=True, exist_ok=True) or path.write_text(
                __import__("json").dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            ),
            now_iso=lambda: "2026-02-07T22:00:00",
            getenv=lambda name, default=None: env.get(name, default),
        )

    def test_master_key_policy_production_requires_key(self):
        with self.assertRaises(RuntimeError):
            validate_master_key_policy(getenv=lambda name, default=None: {"ENV": "production"}.get(name, default))

        ok = validate_master_key_policy(getenv=lambda name, default=None: {"ENV": "development"}.get(name, default))
        self.assertTrue(ok.get("ok"))

    def test_private_provider_crud_and_merge(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, {"ENV": "development", "MASTER_KEY_DEV_DEFAULT": "dev-key"})

            created = teacher_provider_registry_create(
                {
                    "teacher_id": "t01",
                    "provider_id": "tprv_proxy_a",
                    "display_name": "Proxy A",
                    "base_url": "https://proxy.example.com/v1",
                    "api_key": "sk-test-12345678",
                    "default_model": "gpt-4.1-mini",
                },
                deps=deps,
            )
            self.assertTrue(created.get("ok"))
            self.assertEqual((created.get("provider") or {}).get("provider"), "tprv_proxy_a")

            overview = teacher_provider_registry_get({"teacher_id": "t01"}, deps=deps)
            self.assertTrue(overview.get("ok"))
            providers = overview.get("providers") or []
            self.assertEqual(len(providers), 1)
            self.assertEqual((providers[0] or {}).get("api_key_masked", "")[:4], "sk-t")

            # Verify catalog includes base_url
            catalog_providers = (overview.get("catalog") or {}).get("providers") or []
            openai_cat = next((p for p in catalog_providers if p["provider"] == "openai"), None)
            self.assertIsNotNone(openai_cat)
            self.assertEqual(openai_cat["base_url"], "https://api.openai.com/v1")
            private_cat = next((p for p in catalog_providers if p["provider"] == "tprv_proxy_a"), None)
            self.assertIsNotNone(private_cat)
            self.assertEqual(private_cat["base_url"], "https://proxy.example.com/v1")

            # Verify shared_catalog also includes base_url
            shared_cat_providers = (overview.get("shared_catalog") or {}).get("providers") or []
            shared_openai = next((p for p in shared_cat_providers if p["provider"] == "openai"), None)
            self.assertIsNotNone(shared_openai)
            self.assertEqual(shared_openai["base_url"], "https://api.openai.com/v1")

            merged = merged_model_registry("t01", deps=deps)
            self.assertIn("tprv_proxy_a", ((merged.get("providers") or {})))

            resolved = resolve_provider_target("t01", "tprv_proxy_a", "openai-chat", "gpt-4.1", deps=deps)
            self.assertIsNotNone(resolved)
            self.assertEqual((resolved or {}).get("base_url"), "https://proxy.example.com/v1")
            self.assertIn("Authorization", ((resolved or {}).get("headers") or {}))

            updated = teacher_provider_registry_update(
                {"teacher_id": "t01", "provider_id": "tprv_proxy_a", "default_model": "gpt-4.1-nano"},
                deps=deps,
            )
            self.assertTrue(updated.get("ok"))
            self.assertEqual(((updated.get("provider") or {}).get("default_model")), "gpt-4.1-nano")

            deleted = teacher_provider_registry_delete({"teacher_id": "t01", "provider_id": "tprv_proxy_a"}, deps=deps)
            self.assertTrue(deleted.get("ok"))

            resolved_after = resolve_provider_target("t01", "tprv_proxy_a", "openai-chat", "", deps=deps)
            self.assertIsNone(resolved_after)

    def test_probe_models_not_ready_returns_error(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, {"ENV": "development", "MASTER_KEY_DEV_DEFAULT": "dev-key"})
            result = teacher_provider_registry_probe_models({"teacher_id": "t01", "provider_id": "tprv_missing"}, deps=deps)
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("error"), "provider_not_found")

    def test_create_allows_overriding_shared_provider(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, {"ENV": "development", "MASTER_KEY_DEV_DEFAULT": "dev-key"})
            result = teacher_provider_registry_create(
                {
                    "teacher_id": "t01",
                    "provider_id": "openai",
                    "display_name": "Override OpenAI",
                    "base_url": "https://proxy.example.com/v1",
                    "api_key": "sk-test-12345678",
                },
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result["provider"]["provider"], "openai")

    def test_update_allows_clearing_base_url_to_registry_default(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, {"ENV": "development", "MASTER_KEY_DEV_DEFAULT": "dev-key"})

            created = teacher_provider_registry_create(
                {
                    "teacher_id": "t01",
                    "provider_id": "openai",
                    "display_name": "OpenAI 覆盖",
                    "base_url": "https://proxy.example.com/v1",
                    "api_key": "sk-test-12345678",
                },
                deps=deps,
            )
            self.assertTrue(created.get("ok"))

            updated = teacher_provider_registry_update(
                {
                    "teacher_id": "t01",
                    "provider_id": "openai",
                    "base_url": "",
                },
                deps=deps,
            )
            self.assertTrue(updated.get("ok"))
            self.assertEqual((updated.get("provider") or {}).get("base_url"), "")

            merged = merged_model_registry("t01", deps=deps)
            private_cfg = ((merged.get("providers") or {}).get("openai") or {})
            self.assertEqual(private_cfg.get("base_url"), "https://api.openai.com/v1")


if __name__ == "__main__":
    unittest.main()

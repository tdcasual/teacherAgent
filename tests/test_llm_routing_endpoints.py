import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def pick_gateway_target(app_mod, prefer_provider: Optional[str] = None):
    providers = app_mod.LLM_GATEWAY.registry.get("providers") if isinstance(app_mod.LLM_GATEWAY.registry.get("providers"), dict) else {}
    best = None
    for provider in sorted(providers.keys()):
        modes = providers.get(provider).get("modes") if isinstance(providers.get(provider), dict) and isinstance(providers.get(provider).get("modes"), dict) else {}
        for mode in sorted(modes.keys()):
            mode_cfg = modes.get(mode) if isinstance(modes.get(mode), dict) else {}
            model = str(mode_cfg.get("default_model") or "").strip()
            if not model:
                continue
            candidate = {"provider": provider, "mode": mode, "model": model}
            if prefer_provider and provider == prefer_provider:
                return candidate
            if best is None:
                best = candidate
    if best is None:
        return {"provider": "openai", "mode": "openai-chat", "model": "gpt-4.1-mini"}
    return best


class LLMRoutingEndpointsTest(unittest.TestCase):
    def test_get_endpoint_uses_teacher_routing_api_deps(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)
            sentinel = object()
            captured = {}

            def fake_get(args, *, deps):  # type: ignore[no-untyped-def]
                captured["args"] = dict(args)
                captured["deps"] = deps
                return {"ok": True, "catalog": {"providers": {}}, "routing": {"rules": []}}

            app_mod._get_routing_api_impl = fake_get  # type: ignore[attr-defined]
            app_mod._teacher_routing_api_deps = lambda: sentinel  # type: ignore[attr-defined]

            res = client.get(
                "/teacher/llm-routing",
                params={"teacher_id": "t01", "history_limit": 7, "proposal_limit": 9, "proposal_status": "active"},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual((captured.get("args") or {}).get("teacher_id"), "t01")
            self.assertEqual((captured.get("args") or {}).get("history_limit"), 7)
            self.assertEqual((captured.get("args") or {}).get("proposal_limit"), 9)
            self.assertEqual((captured.get("args") or {}).get("proposal_status"), "active")
            self.assertIs(captured.get("deps"), sentinel)

    def test_get_endpoint_returns_catalog(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)
            res = client.get("/teacher/llm-routing")
            self.assertEqual(res.status_code, 200)
            payload = res.json()
            self.assertTrue(payload.get("ok"))
            self.assertIn("catalog", payload)
            self.assertIn("providers", payload["catalog"])
            self.assertIn("routing", payload)

    def test_simulate_accepts_config_override(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)
            target = pick_gateway_target(app_mod)
            config = {
                "enabled": True,
                "channels": [
                    {
                        "id": "teacher_fast",
                        "target": target,
                        "capabilities": {"tools": True, "json": True},
                    }
                ],
                "rules": [
                    {
                        "id": "rule_chat",
                        "priority": 200,
                        "match": {"roles": ["teacher"], "kinds": ["chat.agent"]},
                        "route": {"channel_id": "teacher_fast"},
                    }
                ],
            }
            res = client.post(
                "/teacher/llm-routing/simulate",
                json={
                    "role": "teacher",
                    "skill_id": "physics-teacher-ops",
                    "kind": "chat.agent",
                    "needs_tools": True,
                    "config": config,
                },
            )
            self.assertEqual(res.status_code, 200)
            payload = res.json()
            self.assertTrue(payload.get("ok"))
            self.assertTrue(payload.get("config_override"))
            self.assertTrue(payload.get("override_validation", {}).get("ok"))
            decision = payload.get("decision") or {}
            self.assertTrue(decision.get("selected"))
            self.assertEqual(decision.get("matched_rule_id"), "rule_chat")
            candidates = decision.get("candidates") or []
            self.assertEqual((candidates[0] or {}).get("channel_id"), "teacher_fast")

    def test_proposal_review_and_rollback_flow(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)
            target_a = pick_gateway_target(app_mod)
            target_b = pick_gateway_target(app_mod, prefer_provider="openai")

            config_a = {
                "enabled": True,
                "channels": [
                    {
                        "id": "channel_a",
                        "target": target_a,
                    }
                ],
                "rules": [{"id": "rule_a", "priority": 100, "match": {"roles": ["teacher"]}, "route": {"channel_id": "channel_a"}}],
            }
            create_a = client.post("/teacher/llm-routing/proposals", json={"note": "v1", "config": config_a})
            self.assertEqual(create_a.status_code, 200)
            proposal_a = create_a.json().get("proposal_id")
            self.assertTrue(proposal_a)
            apply_a = client.post(f"/teacher/llm-routing/proposals/{proposal_a}/review", json={"approve": True})
            self.assertEqual(apply_a.status_code, 200)
            version_a = int(apply_a.json().get("version") or 0)
            self.assertGreater(version_a, 0)

            config_b = {
                "enabled": True,
                "channels": [
                    {
                        "id": "channel_b",
                        "target": target_b,
                    }
                ],
                "rules": [{"id": "rule_b", "priority": 100, "match": {"roles": ["teacher"]}, "route": {"channel_id": "channel_b"}}],
            }
            create_b = client.post("/teacher/llm-routing/proposals", json={"note": "v2", "config": config_b})
            self.assertEqual(create_b.status_code, 200)
            proposal_b = create_b.json().get("proposal_id")
            self.assertTrue(proposal_b)
            apply_b = client.post(f"/teacher/llm-routing/proposals/{proposal_b}/review", json={"approve": True})
            self.assertEqual(apply_b.status_code, 200)
            self.assertGreater(int(apply_b.json().get("version") or 0), version_a)

            rolled = client.post("/teacher/llm-routing/rollback", json={"target_version": version_a, "note": "rollback test"})
            self.assertEqual(rolled.status_code, 200)

            overview = client.get("/teacher/llm-routing")
            self.assertEqual(overview.status_code, 200)
            rules = (overview.json().get("routing") or {}).get("rules") or []
            self.assertEqual(((rules[0] or {}).get("route") or {}).get("channel_id"), "channel_a")


    def test_history_keeps_latest_ten_versions(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)
            target = pick_gateway_target(app_mod)

            for idx in range(12):
                channel_id = f"channel_{idx}"
                config = {
                    "enabled": True,
                    "channels": [{"id": channel_id, "target": target}],
                    "rules": [
                        {
                            "id": f"rule_{idx}",
                            "priority": 100,
                            "match": {"roles": ["teacher"]},
                            "route": {"channel_id": channel_id},
                        }
                    ],
                }
                created = client.post("/teacher/llm-routing/proposals", json={"note": f"v{idx + 1}", "config": config})
                self.assertEqual(created.status_code, 200)
                proposal_id = created.json().get("proposal_id")
                self.assertTrue(proposal_id)

                applied = client.post(f"/teacher/llm-routing/proposals/{proposal_id}/review", json={"approve": True})
                self.assertEqual(applied.status_code, 200)

            overview = client.get("/teacher/llm-routing", params={"history_limit": 50})
            self.assertEqual(overview.status_code, 200)
            history = overview.json().get("history") or []
            self.assertEqual(len(history), 10)

            versions = [int(item.get("version") or 0) for item in history]
            self.assertTrue(all(v > 0 for v in versions))
            latest = max(versions)
            self.assertEqual(min(versions), latest - 9)

    def test_proposal_detail_endpoint_and_teacher_isolation(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)
            target_a = pick_gateway_target(app_mod)
            target_b = pick_gateway_target(app_mod, prefer_provider="openai")

            teacher_a = "teacher_alpha"
            teacher_b = "teacher_beta"

            config_a = {
                "enabled": True,
                "channels": [{"id": "channel_a", "target": target_a}],
                "rules": [{"id": "rule_a", "priority": 100, "match": {"roles": ["teacher"]}, "route": {"channel_id": "channel_a"}}],
            }
            create_a = client.post("/teacher/llm-routing/proposals", json={"teacher_id": teacher_a, "note": "a", "config": config_a})
            self.assertEqual(create_a.status_code, 200)
            proposal_a = create_a.json().get("proposal_id")
            self.assertTrue(proposal_a)

            detail_a = client.get(f"/teacher/llm-routing/proposals/{proposal_a}", params={"teacher_id": teacher_a})
            self.assertEqual(detail_a.status_code, 200)
            self.assertTrue(detail_a.json().get("ok"))
            self.assertEqual((detail_a.json().get("proposal") or {}).get("proposal_id"), proposal_a)

            apply_a = client.post(
                f"/teacher/llm-routing/proposals/{proposal_a}/review",
                json={"teacher_id": teacher_a, "approve": True},
            )
            self.assertEqual(apply_a.status_code, 200)

            config_b = {
                "enabled": True,
                "channels": [{"id": "channel_b", "target": target_b}],
                "rules": [{"id": "rule_b", "priority": 100, "match": {"roles": ["teacher"]}, "route": {"channel_id": "channel_b"}}],
            }
            create_b = client.post("/teacher/llm-routing/proposals", json={"teacher_id": teacher_b, "note": "b", "config": config_b})
            self.assertEqual(create_b.status_code, 200)
            proposal_b = create_b.json().get("proposal_id")
            self.assertTrue(proposal_b)
            apply_b = client.post(
                f"/teacher/llm-routing/proposals/{proposal_b}/review",
                json={"teacher_id": teacher_b, "approve": True},
            )
            self.assertEqual(apply_b.status_code, 200)

            overview_a = client.get("/teacher/llm-routing", params={"teacher_id": teacher_a})
            overview_b = client.get("/teacher/llm-routing", params={"teacher_id": teacher_b})
            self.assertEqual(overview_a.status_code, 200)
            self.assertEqual(overview_b.status_code, 200)
            rule_a = ((overview_a.json().get("routing") or {}).get("rules") or [])[0]
            rule_b = ((overview_b.json().get("routing") or {}).get("rules") or [])[0]
            self.assertEqual(((rule_a or {}).get("route") or {}).get("channel_id"), "channel_a")
            self.assertEqual(((rule_b or {}).get("route") or {}).get("channel_id"), "channel_b")

            simulate_a = client.post(
                "/teacher/llm-routing/simulate",
                json={"teacher_id": teacher_a, "role": "teacher", "kind": "chat.agent", "needs_tools": True},
            )
            simulate_b = client.post(
                "/teacher/llm-routing/simulate",
                json={"teacher_id": teacher_b, "role": "teacher", "kind": "chat.agent", "needs_tools": True},
            )
            self.assertEqual(simulate_a.status_code, 200)
            self.assertEqual(simulate_b.status_code, 200)
            candidate_a = (((simulate_a.json().get("decision") or {}).get("candidates") or [])[0] or {}).get("channel_id")
            candidate_b = (((simulate_b.json().get("decision") or {}).get("candidates") or [])[0] or {}).get("channel_id")
            self.assertEqual(candidate_a, "channel_a")
            self.assertEqual(candidate_b, "channel_b")

    def test_proposal_review_conflict_and_rollback_missing_target(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            client = TestClient(app_mod.app)
            target = pick_gateway_target(app_mod)
            config = {
                "enabled": True,
                "channels": [{"id": "channel_main", "target": target}],
                "rules": [{"id": "rule_main", "priority": 100, "match": {"roles": ["teacher"]}, "route": {"channel_id": "channel_main"}}],
            }

            created = client.post("/teacher/llm-routing/proposals", json={"note": "v-main", "config": config})
            self.assertEqual(created.status_code, 200)
            proposal_id = created.json().get("proposal_id")
            self.assertTrue(proposal_id)

            apply_once = client.post(f"/teacher/llm-routing/proposals/{proposal_id}/review", json={"approve": True})
            self.assertEqual(apply_once.status_code, 200)

            apply_twice = client.post(f"/teacher/llm-routing/proposals/{proposal_id}/review", json={"approve": True})
            self.assertEqual(apply_twice.status_code, 400)
            detail = apply_twice.json().get("detail") or {}
            self.assertEqual(detail.get("error"), "proposal_already_reviewed")

            rollback_missing = client.post("/teacher/llm-routing/rollback", json={"target_version": 99999})
            self.assertEqual(rollback_missing.status_code, 404)
            rollback_detail = rollback_missing.json().get("detail") or {}
            self.assertEqual(rollback_detail.get("error"), "target_version_not_found")


if __name__ == "__main__":
    unittest.main()

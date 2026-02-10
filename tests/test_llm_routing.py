import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


MODEL_REGISTRY = {
    "providers": {
        "siliconflow": {"modes": {"openai-chat": {}}},
        "openai": {"modes": {"openai-chat": {}, "openai-response": {}}},
    }
}


class LLMRoutingTest(unittest.TestCase):
    def test_resolve_with_fallback_chain(self):
        from services.api.llm_routing import RoutingContext, apply_routing_config, get_compiled_routing, resolve_routing

        with TemporaryDirectory() as td:
            config_path = Path(td) / "llm_routing.json"
            payload = {
                "enabled": True,
                "channels": [
                    {
                        "id": "teacher-fast",
                        "title": "教师快速",
                        "target": {
                            "provider": "siliconflow",
                            "mode": "openai-chat",
                            "model": "deepseek-ai/DeepSeek-V3.2",
                        },
                        "fallback_channels": ["teacher-safe"],
                        "capabilities": {"tools": True, "json": True},
                    },
                    {
                        "id": "teacher-safe",
                        "title": "教师稳妥",
                        "target": {
                            "provider": "openai",
                            "mode": "openai-chat",
                            "model": "gpt-4.1-mini",
                        },
                        "capabilities": {"tools": True, "json": True},
                    },
                ],
                "rules": [
                    {
                        "id": "teacher-agent",
                        "priority": 200,
                        "match": {"roles": ["teacher"], "kinds": ["chat.skill"]},
                        "route": {"channel_id": "teacher-fast"},
                    }
                ],
            }
            applied = apply_routing_config(config_path, MODEL_REGISTRY, payload, actor="teacher", source="test")
            self.assertTrue(applied.get("ok"))

            compiled = get_compiled_routing(config_path, MODEL_REGISTRY)
            decision = resolve_routing(
                compiled,
                RoutingContext(role="teacher", skill_id="physics-teacher-ops", kind="chat.skill", needs_tools=True),
            )
            self.assertTrue(decision.selected)
            self.assertEqual(decision.matched_rule_id, "teacher-agent")
            self.assertEqual([c.channel_id for c in decision.candidates], ["teacher-fast", "teacher-safe"])

    def test_kind_prefix_matching_supports_agent_specific_chat_kind(self):
        from services.api.llm_routing import RoutingContext, apply_routing_config, get_compiled_routing, resolve_routing

        with TemporaryDirectory() as td:
            config_path = Path(td) / "llm_routing.json"
            payload = {
                "enabled": True,
                "channels": [
                    {
                        "id": "teacher-fast",
                        "target": {
                            "provider": "openai",
                            "mode": "openai-chat",
                            "model": "gpt-4.1-mini",
                        },
                    }
                ],
                "rules": [
                    {
                        "id": "teacher-agent",
                        "priority": 200,
                        "match": {"roles": ["teacher"], "kinds": ["chat.skill"]},
                        "route": {"channel_id": "teacher-fast"},
                    }
                ],
            }
            applied = apply_routing_config(config_path, MODEL_REGISTRY, payload, actor="teacher", source="test")
            self.assertTrue(applied.get("ok"))

            compiled = get_compiled_routing(config_path, MODEL_REGISTRY)
            decision = resolve_routing(
                compiled,
                RoutingContext(role="teacher", kind="chat.skill", needs_tools=True),
            )
            self.assertTrue(decision.selected)
            self.assertEqual(decision.matched_rule_id, "teacher-agent")
            self.assertEqual(decision.candidates[0].channel_id, "teacher-fast")

    def test_capability_filter_falls_to_next_rule(self):
        from services.api.llm_routing import RoutingContext, apply_routing_config, get_compiled_routing, resolve_routing

        with TemporaryDirectory() as td:
            config_path = Path(td) / "llm_routing.json"
            payload = {
                "enabled": True,
                "channels": [
                    {
                        "id": "text-only",
                        "target": {
                            "provider": "siliconflow",
                            "mode": "openai-chat",
                            "model": "deepseek-ai/DeepSeek-V3.2",
                        },
                        "capabilities": {"tools": False, "json": True},
                    },
                    {
                        "id": "tool-ready",
                        "target": {"provider": "openai", "mode": "openai-chat", "model": "gpt-4.1-mini"},
                        "capabilities": {"tools": True, "json": True},
                    },
                ],
                "rules": [
                    {
                        "id": "prefer-text",
                        "priority": 200,
                        "match": {"roles": ["teacher"]},
                        "route": {"channel_id": "text-only"},
                    },
                    {
                        "id": "tool-fallback-rule",
                        "priority": 100,
                        "match": {"roles": ["teacher"], "needs_tools": True},
                        "route": {"channel_id": "tool-ready"},
                    },
                ],
            }
            applied = apply_routing_config(config_path, MODEL_REGISTRY, payload, actor="teacher", source="test")
            self.assertTrue(applied.get("ok"))

            compiled = get_compiled_routing(config_path, MODEL_REGISTRY)
            decision_tools = resolve_routing(compiled, RoutingContext(role="teacher", kind="chat.agent", needs_tools=True))
            self.assertTrue(decision_tools.selected)
            self.assertEqual(decision_tools.matched_rule_id, "tool-fallback-rule")
            self.assertEqual(decision_tools.candidates[0].channel_id, "tool-ready")

            decision_tools = resolve_routing(compiled, RoutingContext(role="teacher", kind="chat.skill", needs_tools=True))
            self.assertTrue(decision_tools.selected)
            self.assertEqual(decision_tools.matched_rule_id, "tool-fallback-rule")
            self.assertEqual(decision_tools.candidates[0].channel_id, "tool-ready")

            decision_no_tools = resolve_routing(compiled, RoutingContext(role="teacher", kind="chat.skill", needs_tools=False))
            self.assertTrue(decision_no_tools.selected)
            self.assertEqual(decision_no_tools.matched_rule_id, "prefer-text")
            self.assertEqual(decision_no_tools.candidates[0].channel_id, "text-only")

    def test_proposal_apply_and_rollback(self):
        from services.api.llm_routing import (
            apply_routing_config,
            apply_routing_proposal,
            create_routing_proposal,
            get_active_routing,
            rollback_routing_config,
        )

        with TemporaryDirectory() as td:
            config_path = Path(td) / "llm_routing.json"
            config_a = {
                "enabled": True,
                "channels": [
                    {
                        "id": "ch_a",
                        "target": {
                            "provider": "siliconflow",
                            "mode": "openai-chat",
                            "model": "deepseek-ai/DeepSeek-V3.2",
                        },
                    }
                ],
                "rules": [{"id": "r1", "priority": 100, "match": {"roles": ["teacher"]}, "route": {"channel_id": "ch_a"}}],
            }
            proposal = create_routing_proposal(config_path, MODEL_REGISTRY, config_a, actor="teacher", note="config a")
            self.assertTrue(proposal.get("ok"))
            proposal_id = proposal.get("proposal_id")
            apply_result = apply_routing_proposal(config_path, MODEL_REGISTRY, proposal_id=proposal_id, approve=True, actor="teacher")
            self.assertTrue(apply_result.get("ok"))
            applied_version = int(apply_result.get("version") or 0)
            self.assertGreater(applied_version, 0)

            config_b = {
                "enabled": True,
                "channels": [
                    {
                        "id": "ch_b",
                        "target": {"provider": "openai", "mode": "openai-chat", "model": "gpt-4.1-mini"},
                    }
                ],
                "rules": [{"id": "r2", "priority": 100, "match": {"roles": ["teacher"]}, "route": {"channel_id": "ch_b"}}],
            }
            direct = apply_routing_config(config_path, MODEL_REGISTRY, config_b, actor="teacher", source="test")
            self.assertTrue(direct.get("ok"))
            self.assertGreater(int(direct.get("version") or 0), applied_version)

            rolled = rollback_routing_config(config_path, MODEL_REGISTRY, target_version=applied_version, actor="teacher")
            self.assertTrue(rolled.get("ok"))

            active = get_active_routing(config_path, MODEL_REGISTRY)
            self.assertTrue(active.get("config", {}).get("enabled"))
            rules = active.get("config", {}).get("rules") or []
            self.assertEqual((rules[0].get("route") or {}).get("channel_id"), "ch_a")


if __name__ == "__main__":
    unittest.main()

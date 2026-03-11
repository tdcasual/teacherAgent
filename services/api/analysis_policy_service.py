from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_POLICY_PATH = REPO_ROOT / 'config' / 'analysis_policy.json'

_BUILTIN_ANALYSIS_POLICY: Dict[str, Any] = {
    'release_readiness': {
        'thresholds': {
            'max_changed_ratio': 0.2,
            'max_invalid_output_count': 0,
            'max_timeout_count': 0,
            'max_timeout_rate': 0.05,
            'max_invalid_output_rate': 0.05,
            'max_budget_rejection_rate': 0.02,
            'max_fallback_rate': 0.1,
            'window_sec': 3600,
        }
    },
    'review_feedback': {
        'reason_recommendation_specs': {
            'invalid_output': {
                'action_type': 'harden_output_schema',
                'default_priority': 'high',
                'recommended_action': 'Tighten specialist output schema and add contract regression fixtures.',
                'owner_hint': 'runtime_and_prompt',
            },
            'missing_fields': {
                'action_type': 'harden_artifact_adapter',
                'default_priority': 'high',
                'recommended_action': 'Backfill required artifact fields or route incomplete inputs to review earlier.',
                'owner_hint': 'artifact_adapter',
            },
            'low_confidence': {
                'action_type': 'tune_selector_thresholds',
                'default_priority': 'medium',
                'recommended_action': 'Revisit confidence thresholds, prompt grounding, and review routing policy.',
                'owner_hint': 'selector_and_prompt',
            },
            'missing_evidence_clips': {
                'action_type': 'improve_evidence_grounding',
                'default_priority': 'high',
                'recommended_action': 'Strengthen evidence grounding so report sections carry traceable evidence refs.',
                'owner_hint': 'prompt_and_runtime',
            },
            'signal_missing_evidence_refs': {
                'action_type': 'improve_evidence_grounding',
                'default_priority': 'medium',
                'recommended_action': 'Require evidence refs on key signals or suppress unsupported signals.',
                'owner_hint': 'prompt_and_runtime',
            },
            'timeout': {
                'action_type': 'reduce_runtime_cost',
                'default_priority': 'high',
                'recommended_action': 'Reduce runtime complexity or increase timeout budget with evidence.',
                'owner_hint': 'runtime',
            },
            'budget_exceeded': {
                'action_type': 'rebalance_budget',
                'default_priority': 'medium',
                'recommended_action': 'Rebalance token/step budgets or simplify the strategy path.',
                'owner_hint': 'runtime',
            },
            'specialist_execution_failed': {
                'action_type': 'stabilize_specialist_runner',
                'default_priority': 'high',
                'recommended_action': 'Stabilize specialist runner failure paths and add regression coverage.',
                'owner_hint': 'runtime',
            },
        },
        'fallback_recommendation': {
            'action_type': 'investigate_review_feedback',
            'default_priority': 'medium',
            'recommended_action': 'Inspect review feedback samples and convert them into explicit strategy fixes.',
            'owner_hint': 'strategy_owner',
        },
        'priority_rules': {
            'high_if_rejected_count_at_least': 1,
            'medium_if_retry_count_at_least': 1,
            'medium_if_item_count_at_least': 2,
        },
        'high_impact_dispositions': ['rejected', 'escalated'],
        'retry_dispositions': ['retry_requested'],
    },
    'strategy_eval': {
        'minimum_fixture_count_by_domain': {
            'survey': 3,
            'class_report': 3,
            'video_homework': 3,
        },
        'required_edge_case_tags': [
            'provider_attachment_noise',
            'long_duration_submission',
            'low_confidence_parse',
            'ocr_noise',
            'web_export_complex',
        ],
        'closed_loop_recommendations': {
            'expectation_failures': {
                'action_type': 'fix_eval_expectations',
                'priority': 'high',
                'recommended_action': 'Investigate failing fixtures and convert failures into explicit strategy fixes.',
                'owner_hint': 'evaluation',
            },
            'missing_edge_case_coverage': {
                'action_type': 'expand_edge_case_fixtures',
                'priority': 'medium',
                'recommended_action': 'Add fixtures for uncovered edge cases before expanding rollout.',
                'owner_hint': 'evaluation',
            },
        },
    },
}


def get_default_analysis_policy() -> Dict[str, Any]:
    return load_analysis_policy()



def load_analysis_policy_from_path(path: Path) -> Dict[str, Any]:
    return load_analysis_policy(path=path)



def load_analysis_policy(*, policy: Dict[str, Any] | None = None, path: Path | None = None) -> Dict[str, Any]:
    merged = copy.deepcopy(_BUILTIN_ANALYSIS_POLICY)
    source_path = path or DEFAULT_ANALYSIS_POLICY_PATH
    if source_path.exists():
        merged = merge_analysis_policy(merged, _read_policy_file(source_path))
    if isinstance(policy, dict) and policy:
        merged = merge_analysis_policy(merged, policy)
    return merged



def merge_analysis_policy(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in dict(override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_analysis_policy(dict(merged.get(key) or {}), value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged



def _read_policy_file(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'analysis policy must be a JSON object: {path}')
    return payload

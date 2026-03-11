from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.api.analysis_policy_service import (
    get_default_analysis_policy,
    load_analysis_policy,
    load_analysis_policy_from_path,
)


def test_analysis_policy_service_returns_default_policy_shape() -> None:
    policy = get_default_analysis_policy()

    assert policy['release_readiness']['thresholds']['max_timeout_rate'] == 0.05
    assert policy['release_readiness']['thresholds']['window_sec'] == 3600
    assert policy['review_feedback']['reason_recommendation_specs']['invalid_output']['action_type'] == 'harden_output_schema'
    assert policy['strategy_eval']['minimum_fixture_count_by_domain']['survey'] == 3
    assert 'provider_attachment_noise' in policy['strategy_eval']['required_edge_case_tags']



def test_analysis_policy_service_merges_partial_override_file(tmp_path: Path) -> None:
    policy_path = tmp_path / 'analysis_policy.json'
    policy_path.write_text(
        json.dumps(
            {
                'release_readiness': {
                    'thresholds': {
                        'max_timeout_rate': 0.2,
                    }
                },
                'review_feedback': {
                    'reason_recommendation_specs': {
                        'invalid_output': {
                            'action_type': 'custom_invalid_output_fix',
                        }
                    }
                },
                'strategy_eval': {
                    'required_edge_case_tags': ['provider_attachment_noise', 'brand_new_edge_case'],
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    policy = load_analysis_policy_from_path(policy_path)

    assert policy['release_readiness']['thresholds']['max_timeout_rate'] == 0.2
    assert policy['release_readiness']['thresholds']['max_invalid_output_rate'] == 0.05
    assert policy['review_feedback']['reason_recommendation_specs']['invalid_output']['action_type'] == 'custom_invalid_output_fix'
    assert policy['review_feedback']['reason_recommendation_specs']['invalid_output']['owner_hint'] == 'runtime_and_prompt'
    assert policy['strategy_eval']['required_edge_case_tags'] == ['provider_attachment_noise', 'brand_new_edge_case']
    assert policy['strategy_eval']['minimum_fixture_count_by_domain']['video_homework'] == 3



def test_analysis_policy_service_rejects_invalid_threshold_ranges() -> None:
    with pytest.raises(ValueError):
        load_analysis_policy(
            policy={
                'release_readiness': {
                    'thresholds': {
                        'max_timeout_rate': 1.2,
                    }
                }
            }
        )



def test_analysis_policy_service_rejects_invalid_priority_and_blank_edge_case() -> None:
    with pytest.raises(ValueError):
        load_analysis_policy(
            policy={
                'review_feedback': {
                    'reason_recommendation_specs': {
                        'invalid_output': {
                            'default_priority': 'urgent',
                        }
                    }
                },
                'strategy_eval': {
                    'required_edge_case_tags': ['provider_attachment_noise', ''],
                },
            }
        )



def test_analysis_policy_service_rejects_non_positive_window_and_negative_counts() -> None:
    with pytest.raises(ValueError):
        load_analysis_policy(
            policy={
                'release_readiness': {
                    'thresholds': {
                        'window_sec': 0,
                        'max_timeout_count': -1,
                    }
                }
            }
        )

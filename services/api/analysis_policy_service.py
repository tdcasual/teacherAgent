from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Annotated, Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_POLICY_PATH = REPO_ROOT / 'config' / 'analysis_policy.json'

PriorityLevel = Literal['high', 'medium', 'low']
NonNegativeInt = Annotated[int, Field(ge=0)]
RateValue = Annotated[float, Field(ge=0.0, le=1.0)]

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


class RecommendationSpecModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    action_type: str
    default_priority: PriorityLevel
    recommended_action: str
    owner_hint: str

    @field_validator('action_type', 'recommended_action', 'owner_hint')
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        normalized = str(value or '').strip()
        if not normalized:
            raise ValueError('must be a non-empty string')
        return normalized


class ClosedLoopRecommendationSpecModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    action_type: str
    priority: PriorityLevel
    recommended_action: str
    owner_hint: str

    @field_validator('action_type', 'recommended_action', 'owner_hint')
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        normalized = str(value or '').strip()
        if not normalized:
            raise ValueError('must be a non-empty string')
        return normalized


class ReleaseReadinessThresholdsModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    max_changed_ratio: RateValue
    max_invalid_output_count: NonNegativeInt
    max_timeout_count: NonNegativeInt
    max_timeout_rate: RateValue
    max_invalid_output_rate: RateValue
    max_budget_rejection_rate: RateValue
    max_fallback_rate: RateValue
    window_sec: Annotated[int, Field(gt=0)]


class ReleaseReadinessPolicyModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    thresholds: ReleaseReadinessThresholdsModel


class PriorityRulesModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    high_if_rejected_count_at_least: Annotated[int, Field(ge=1)]
    medium_if_retry_count_at_least: Annotated[int, Field(ge=1)]
    medium_if_item_count_at_least: Annotated[int, Field(ge=1)]


class ReviewFeedbackPolicyModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    reason_recommendation_specs: dict[str, RecommendationSpecModel]
    fallback_recommendation: RecommendationSpecModel
    priority_rules: PriorityRulesModel
    high_impact_dispositions: list[str]
    retry_dispositions: list[str]

    @field_validator('reason_recommendation_specs')
    @classmethod
    def _validate_reason_specs(cls, value: dict[str, RecommendationSpecModel]) -> dict[str, RecommendationSpecModel]:
        if not value:
            raise ValueError('reason_recommendation_specs must not be empty')
        normalized: dict[str, RecommendationSpecModel] = {}
        for key, item in value.items():
            name = str(key or '').strip()
            if not name:
                raise ValueError('reason_recommendation_specs keys must be non-empty')
            normalized[name] = item
        return normalized

    @field_validator('high_impact_dispositions', 'retry_dispositions')
    @classmethod
    def _validate_disposition_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            item = str(raw or '').strip()
            if not item:
                raise ValueError('disposition lists must not contain blank values')
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        if not normalized:
            raise ValueError('disposition lists must not be empty')
        return normalized


class StrategyEvalPolicyModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    minimum_fixture_count_by_domain: dict[str, NonNegativeInt]
    required_edge_case_tags: list[str]
    closed_loop_recommendations: dict[str, ClosedLoopRecommendationSpecModel]

    @field_validator('minimum_fixture_count_by_domain')
    @classmethod
    def _validate_minimum_fixture_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if not value:
            raise ValueError('minimum_fixture_count_by_domain must not be empty')
        normalized: dict[str, int] = {}
        for key, item in value.items():
            name = str(key or '').strip()
            if not name:
                raise ValueError('minimum_fixture_count_by_domain keys must be non-empty')
            normalized[name] = int(item)
        return normalized

    @field_validator('required_edge_case_tags')
    @classmethod
    def _validate_edge_case_tags(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            item = str(raw or '').strip()
            if not item:
                raise ValueError('required_edge_case_tags must not contain blank values')
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        if not normalized:
            raise ValueError('required_edge_case_tags must not be empty')
        return normalized

    @field_validator('closed_loop_recommendations')
    @classmethod
    def _validate_closed_loop_templates(
        cls, value: dict[str, ClosedLoopRecommendationSpecModel]
    ) -> dict[str, ClosedLoopRecommendationSpecModel]:
        if not value:
            raise ValueError('closed_loop_recommendations must not be empty')
        normalized: dict[str, ClosedLoopRecommendationSpecModel] = {}
        for key, item in value.items():
            name = str(key or '').strip()
            if not name:
                raise ValueError('closed_loop_recommendations keys must be non-empty')
            normalized[name] = item
        return normalized


class AnalysisPolicyModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    release_readiness: ReleaseReadinessPolicyModel
    review_feedback: ReviewFeedbackPolicyModel
    strategy_eval: StrategyEvalPolicyModel



def get_default_analysis_policy() -> Dict[str, Any]:
    return load_analysis_policy()



def load_analysis_policy_from_path(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return load_analysis_policy(path=path)



def load_analysis_policy(*, policy: Dict[str, Any] | None = None, path: Path | None = None) -> Dict[str, Any]:
    merged = copy.deepcopy(_BUILTIN_ANALYSIS_POLICY)
    source_path = path or DEFAULT_ANALYSIS_POLICY_PATH
    if source_path.exists():
        merged = merge_analysis_policy(merged, _read_policy_file(source_path))
    if isinstance(policy, dict) and policy:
        merged = merge_analysis_policy(merged, policy)
    return validate_analysis_policy(merged)



def validate_analysis_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validated = AnalysisPolicyModel.model_validate(policy)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return validated.model_dump(mode='python')



def build_analysis_policy_summary(policy: Dict[str, Any]) -> Dict[str, Any]:
    validated = validate_analysis_policy(policy)
    release_thresholds = dict((validated.get('release_readiness') or {}).get('thresholds') or {})
    review_feedback = dict(validated.get('review_feedback') or {})
    strategy_eval = dict(validated.get('strategy_eval') or {})
    return {
        'thresholds': release_thresholds,
        'reason_recommendation_spec_count': len(dict(review_feedback.get('reason_recommendation_specs') or {})),
        'high_impact_disposition_count': len(list(review_feedback.get('high_impact_dispositions') or [])),
        'retry_disposition_count': len(list(review_feedback.get('retry_dispositions') or [])),
        'required_edge_case_count': len(list(strategy_eval.get('required_edge_case_tags') or [])),
        'closed_loop_template_count': len(dict(strategy_eval.get('closed_loop_recommendations') or {})),
        'strategy_domain_count': len(dict(strategy_eval.get('minimum_fixture_count_by_domain') or {})),
    }



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

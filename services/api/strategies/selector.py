from __future__ import annotations

from typing import Iterable, List, Optional

from ..artifacts.contracts import ArtifactEnvelope
from .contracts import StrategyDecision, StrategySpec


class StrategySelectionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class StrategySelector:
    def __init__(self, specs: Iterable[StrategySpec]):
        self._specs = list(specs)

    def select(
        self,
        *,
        role: str,
        artifact: ArtifactEnvelope,
        task_kind: str,
        target_scope: Optional[str] = None,
    ) -> StrategyDecision:
        role_final = str(role or '').strip()
        task_kind_final = str(task_kind or '').strip()
        target_scope_final = str(target_scope or '').strip() or None
        matches: List[StrategySpec] = []
        for spec in self._specs:
            if spec.roles and role_final not in spec.roles:
                continue
            if artifact.artifact_type not in spec.accepted_artifacts:
                continue
            if task_kind_final not in spec.task_kinds:
                continue
            if spec.target_scopes and target_scope_final not in spec.target_scopes:
                continue
            matches.append(spec)

        if not matches:
            raise StrategySelectionError(
                'unsupported_strategy',
                f'No strategy for {artifact.artifact_type}:{task_kind_final}:{role_final}',
            )

        spec = sorted(
            matches,
            key=lambda item: (
                1 if item.target_scopes else 0,
                len(item.task_kinds),
                1 if item.confidence_floor is not None else 0,
            ),
            reverse=True,
        )[0]
        confidence = artifact.confidence
        review_required = spec.review_policy == 'always_review'
        delivery_mode = spec.delivery_mode
        reason = 'selected'
        if (
            spec.review_policy == 'auto_on_low_confidence'
            and spec.confidence_floor is not None
            and confidence is not None
            and float(confidence) < float(spec.confidence_floor)
        ):
            review_required = True
            delivery_mode = 'review_queue'
            reason = 'low_confidence_review'

        return StrategyDecision(
            strategy_id=spec.strategy_id,
            specialist_agent=spec.specialist_agent,
            task_kind=task_kind_final,
            review_policy=spec.review_policy,
            delivery_mode=delivery_mode,
            review_required=review_required,
            reason=reason,
            budget=dict(spec.budget or {}),
            return_schema=dict(spec.return_schema or {}),
        )



def build_default_strategy_selector(review_confidence_floor: float = 0.7) -> StrategySelector:
    return StrategySelector(
        [
            StrategySpec(
                strategy_id='survey.teacher.report',
                accepted_artifacts=['survey_evidence_bundle'],
                task_kinds=['survey.analysis'],
                specialist_agent='survey_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='teacher_report',
                roles=['teacher'],
                target_scopes=['class'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
            StrategySpec(
                strategy_id='survey.chat.followup',
                accepted_artifacts=['survey_evidence_bundle'],
                task_kinds=['survey.chat_followup'],
                specialist_agent='survey_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='chat_reply',
                roles=['teacher'],
                target_scopes=['class'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
            StrategySpec(
                strategy_id='class_signal.teacher.report',
                accepted_artifacts=['class_signal_bundle'],
                task_kinds=['class_report.analysis'],
                specialist_agent='class_signal_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='teacher_report',
                roles=['teacher'],
                target_scopes=['class'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
            StrategySpec(
                strategy_id='video_homework.teacher.report',
                accepted_artifacts=['multimodal_submission_bundle'],
                task_kinds=['video_homework.analysis'],
                specialist_agent='video_homework_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='teacher_report',
                roles=['teacher'],
                target_scopes=['student'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
        ]
    )

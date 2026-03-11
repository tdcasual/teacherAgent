from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

SCRIPT_PATH = Path('scripts/quality/check_analysis_preflight.py')
FIXTURES_DIR = Path('tests/fixtures')



def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location('analysis_preflight_gate', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def _detail_payload(*, report_id: str, summary: str = '班级对实验设计的理解偏弱', confidence: float = 0.73) -> dict:
    return {
        'report': {
            'report_id': report_id,
            'analysis_type': 'survey',
            'target_type': 'report',
            'target_id': report_id,
            'strategy_id': 'survey.teacher.report',
            'strategy_version': 'v1',
            'prompt_version': 'v1',
            'adapter_version': 'v1',
            'runtime_version': 'v1',
        },
        'analysis_artifact': {
            'executive_summary': summary,
            'teaching_recommendations': ['补充实验设计例题讲解'],
            'confidence_and_gaps': {'confidence': confidence},
        },
        'artifact_meta': {
            'parse_confidence': confidence,
            'missing_fields': ['question_summaries'],
            'review_reason': 'low_confidence',
        },
        'replay_context': {
            'artifact_payload': {
                'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider'},
                'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高二2403班', 'sample_size': 35},
                'question_summaries': [],
                'group_breakdowns': [],
                'free_text_signals': [],
                'attachments': [],
                'parse_confidence': confidence,
                'missing_fields': ['question_summaries'],
                'provenance': {'source': 'structured'},
            }
        },
    }



def _write_shadow_dirs(root: Path, *, changed: bool = False) -> tuple[Path, Path]:
    baseline_dir = root / 'baseline'
    candidate_dir = root / 'candidate'
    baseline_dir.mkdir()
    candidate_dir.mkdir()
    (baseline_dir / 'report_1.json').write_text(json.dumps(_detail_payload(report_id='report_1'), ensure_ascii=False), encoding='utf-8')
    candidate_payload = _detail_payload(report_id='report_1', summary='新的总结' if changed else '班级对实验设计的理解偏弱')
    (candidate_dir / 'report_1.json').write_text(json.dumps(candidate_payload, ensure_ascii=False), encoding='utf-8')
    return baseline_dir, candidate_dir



def test_analysis_preflight_gate_builds_passing_report(tmp_path: Path) -> None:
    module = _load_module()
    metrics_path = tmp_path / 'metrics.json'
    review_feedback_path = tmp_path / 'review_feedback.jsonl'
    metrics_path.write_text(json.dumps({'counters': {'invalid_output_count': 0, 'timeout_count': 0, 'review_downgrade_count': 0}}, ensure_ascii=False), encoding='utf-8')
    review_feedback_path.write_text('', encoding='utf-8')
    baseline_dir, candidate_dir = _write_shadow_dirs(tmp_path)

    payload = module.build_analysis_preflight_report(
        fixtures_dir=FIXTURES_DIR,
        review_feedback_path=review_feedback_path,
        metrics_path=metrics_path,
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
        policy_config_path=None,
    )

    assert payload['ok'] is True
    assert payload['policy_check']['valid'] is True
    assert payload['contract_check']['ok'] is True
    assert payload['release_readiness']['ready_for_release'] is True
    assert payload['strategy_eval']['rollout_recommendations']['ready_for_expansion'] is True
    assert payload['blocking_issues'] == []



def test_analysis_preflight_gate_blocks_on_release_readiness(tmp_path: Path) -> None:
    module = _load_module()
    metrics_path = tmp_path / 'metrics.json'
    review_feedback_path = tmp_path / 'review_feedback.jsonl'
    metrics_path.write_text(
        json.dumps({'counters': {'invalid_output_count': 1, 'timeout_count': 0, 'review_downgrade_count': 0}}, ensure_ascii=False),
        encoding='utf-8',
    )
    review_feedback_path.write_text('', encoding='utf-8')
    baseline_dir, candidate_dir = _write_shadow_dirs(tmp_path)

    payload = module.build_analysis_preflight_report(
        fixtures_dir=FIXTURES_DIR,
        review_feedback_path=review_feedback_path,
        metrics_path=metrics_path,
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
        policy_config_path=None,
    )

    assert payload['ok'] is False
    assert any(issue['code'] == 'invalid_output_count_exceeded' for issue in payload['blocking_issues'])



def test_analysis_preflight_gate_cli_accepts_policy_config_and_blocks_on_eval(tmp_path: Path) -> None:
    metrics_path = tmp_path / 'metrics.json'
    review_feedback_path = tmp_path / 'review_feedback.jsonl'
    policy_path = tmp_path / 'analysis_policy.json'
    metrics_path.write_text(json.dumps({'counters': {'invalid_output_count': 0, 'timeout_count': 0, 'review_downgrade_count': 0}}, ensure_ascii=False), encoding='utf-8')
    review_feedback_path.write_text('', encoding='utf-8')
    baseline_dir, candidate_dir = _write_shadow_dirs(tmp_path)
    policy_path.write_text(
        json.dumps(
            {
                'strategy_eval': {
                    'required_edge_case_tags': ['provider_attachment_noise', 'brand_new_edge_case'],
                }
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            '--fixtures',
            str(FIXTURES_DIR),
            '--review-feedback',
            str(review_feedback_path),
            '--metrics',
            str(metrics_path),
            '--baseline-dir',
            str(baseline_dir),
            '--candidate-dir',
            str(candidate_dir),
            '--policy-config',
            str(policy_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout.splitlines()[0])
    assert payload['ok'] is False
    assert any(issue['code'] == 'strategy_eval_not_ready_for_expansion' for issue in payload['blocking_issues'])

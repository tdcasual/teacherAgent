from __future__ import annotations

from pathlib import Path

from services.api.survey_report_parse_service import SurveyReportParseDeps, parse_survey_report_payload
from services.api.upload_text_service import UploadTextDeps, extract_text_from_file, extract_text_from_html


class _NoopLimit:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False



def _upload_text_deps() -> UploadTextDeps:
    return UploadTextDeps(
        diag_log=lambda *_args, **_kwargs: None,
        limit=lambda _sem: _NoopLimit(),
        ocr_semaphore=object(),
    )



def _parse_deps() -> SurveyReportParseDeps:
    text_deps = _upload_text_deps()
    return SurveyReportParseDeps(
        extract_text_from_file=lambda path, **kwargs: extract_text_from_file(Path(path), deps=text_deps, **kwargs),
        extract_text_from_html=extract_text_from_html,
    )



def test_parse_survey_report_payload_builds_bundle_from_mixed_unstructured_sources(tmp_path: Path) -> None:
    html_path = tmp_path / "export.html"
    html_path.write_text(
        """
        <html>
          <body>
            <h1>问卷标题: 课堂反馈问卷</h1>
            <p>样本量: 35</p>
            <p>主题: 公式推导 | count=5 | excerpts=推导太快了；例题太少</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    payload = {
        "submission_id": "sub-1",
        "teacher_id": "teacher_1",
        "class_name": "高二2403班",
        "attachments": [
            {
                "name": "report.pdf",
                "kind": "pdf",
                "text": "Q1: 本节课难度如何？\n偏难=12\n适中=20\n偏易=3\n分组: 实验班 | sample_size=20 | 偏难=10",
            },
            {
                "name": "shot.png",
                "kind": "image",
                "text": "Q2: 节奏是否合适？\n偏快=8\n适中=24\n偏慢=3",
            },
            {
                "name": "export.html",
                "kind": "web",
                "path": str(html_path),
            },
        ],
    }

    bundle = parse_survey_report_payload(provider="provider", payload=payload, deps=_parse_deps())

    assert bundle.survey_meta.title == "课堂反馈问卷"
    assert bundle.survey_meta.submission_id == "sub-1"
    assert bundle.audience_scope.teacher_id == "teacher_1"
    assert bundle.audience_scope.class_name == "高二2403班"
    assert bundle.audience_scope.sample_size == 35
    assert {item.question_id for item in bundle.question_summaries} == {"Q1", "Q2"}
    assert bundle.group_breakdowns[0].group_name == "实验班"
    assert bundle.group_breakdowns[0].sample_size == 20
    assert bundle.free_text_signals[0].theme == "公式推导"
    assert bundle.free_text_signals[0].evidence_count == 5
    assert len(bundle.attachments) == 3
    assert bundle.parse_confidence < 1.0
    assert bundle.provenance["source"] == "unstructured"
    assert bundle.missing_fields == []



def test_parse_survey_report_payload_keeps_partial_bundle_for_noisy_image_text() -> None:
    payload = {
        "attachments": [
            {
                "name": "ocr-shot.png",
                "kind": "image",
                "text": "### 班 级 : 高二2403班\n?? 样 本 量 : 41\nQ1 : 听懂程度\n听懂=21\n一般=15\n没听懂=5",
            }
        ]
    }

    bundle = parse_survey_report_payload(provider="provider", payload=payload, deps=_parse_deps())

    assert bundle.audience_scope.class_name == "高二2403班"
    assert bundle.audience_scope.sample_size == 41
    assert bundle.question_summaries[0].question_id == "Q1"
    assert bundle.question_summaries[0].stats["听懂"] == 21
    assert "teacher_id" in bundle.missing_fields
    assert "title" in bundle.missing_fields
    assert bundle.parse_confidence < 0.8

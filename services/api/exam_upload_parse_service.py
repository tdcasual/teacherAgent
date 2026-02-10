from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


def _candidate_source_rank(candidate_id: str) -> int:
    cid = str(candidate_id or "").strip()
    if cid.startswith("pair:"):
        return 1
    if cid.startswith("direct:"):
        return 2
    if cid == "chaos:text":
        return 3
    if cid == "chaos:sheet_text":
        return 4
    return 9


@dataclass(frozen=True)
class ExamUploadParseDeps:
    app_root: Path
    now_iso: Callable[[], str]
    now_date_compact: Callable[[], str]
    load_exam_job: Callable[[str], Dict[str, Any]]
    exam_job_path: Callable[[str], Path]
    write_exam_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    extract_text_from_file: Callable[..., str]
    extract_text_from_pdf: Callable[..., str]
    extract_text_from_image: Callable[..., str]
    parse_xlsx_with_script: Callable[[Path, Path, str, str, Optional[str]], Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]]
    xlsx_to_table_preview: Callable[[Path], str]
    xls_to_table_preview: Callable[[Path], str]
    llm_parse_exam_scores: Callable[[str], Dict[str, Any]]
    build_exam_rows_from_parsed_scores: Callable[[str, Dict[str, Any]], Tuple[List[Dict[str, Any]], Any, List[str]]]
    parse_score_value: Callable[[Any], Optional[float]]
    write_exam_responses_csv: Callable[[Path, List[Dict[str, Any]]], None]
    parse_exam_answer_key_text: Callable[[str], Tuple[List[Dict[str, Any]], List[str]]]
    write_exam_answers_csv: Callable[[Path, List[Dict[str, Any]]], None]
    compute_max_scores_from_rows: Callable[[List[Dict[str, Any]]], Dict[str, float]]
    write_exam_questions_csv: Callable[[Path, List[Dict[str, Any]], Optional[Dict[str, float]]], None]
    apply_answer_key_to_responses_csv: Callable[[Path, Path, Path, Path], Dict[str, Any]]
    compute_exam_totals: Callable[[Path], Dict[str, Any]]
    copy2: Callable[[Path, Path], Any]
    diag_log: Callable[[str, Dict[str, Any]], None]
    parse_date_str: Callable[[Any], str]


def process_exam_upload_job(job_id: str, deps: ExamUploadParseDeps) -> None:
    job = deps.load_exam_job(job_id)
    job_dir = deps.exam_job_path(job_id)
    paper_dir = job_dir / "paper"
    scores_dir = job_dir / "scores"
    answers_dir = job_dir / "answers"
    derived_dir = job_dir / "derived"

    exam_id = str(job.get("exam_id") or "").strip()
    if not exam_id:
        exam_id = f"EX{deps.now_date_compact()}_{job_id[-6:]}"
    language = job.get("language") or "zh"
    ocr_mode = job.get("ocr_mode") or "FREE_OCR"

    paper_files = job.get("paper_files") or []
    score_files = job.get("score_files") or []
    answer_files = job.get("answer_files") or []

    deps.write_exam_job(job_id, {"status": "processing", "step": "extract_paper", "progress": 10, "error": ""})

    if not paper_files:
        deps.write_exam_job(job_id, {"status": "failed", "error": "no_paper_files", "progress": 100})
        return
    if not score_files:
        deps.write_exam_job(job_id, {"status": "failed", "error": "no_score_files", "progress": 100})
        return

    ocr_hints = [
        "如果是图片/PDF 扫描件，请确保 OCR 可用，并上传清晰的 JPG/PNG/PDF（避免 HEIC）。",
        "如果是成绩表（PDF/图片），尽量上传原始 Excel（xls/xlsx）可获得更稳定解析。",
    ]

    paper_text_parts: List[str] = []
    for fname in paper_files:
        path = paper_dir / fname
        try:
            paper_text_parts.append(deps.extract_text_from_file(path, language=language, ocr_mode=ocr_mode))
        except Exception as exc:
            deps.write_exam_job(
                job_id,
                {
                    "status": "failed",
                    "step": "extract_paper",
                    "progress": 100,
                    "error": "paper_extract_failed",
                    "error_detail": str(exc)[:200],
                    "hints": ocr_hints,
                },
            )
            return
    paper_text = "\n\n".join([text for text in paper_text_parts if text])
    (job_dir / "paper_text.txt").write_text(paper_text or "", encoding="utf-8")

    deps.write_exam_job(job_id, {"step": "parse_scores", "progress": 35})

    all_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    score_schema: Dict[str, Any] = {}
    score_schema_sources: List[Dict[str, Any]] = []
    class_name_hint = str(job.get("class_name") or "").strip()
    score_schema_override = job.get("score_schema") if isinstance(job.get("score_schema"), dict) else {}
    override_subject = score_schema_override.get("subject") if isinstance(score_schema_override.get("subject"), dict) else {}
    selected_candidate_id = str(
        override_subject.get("selected_candidate_id")
        or score_schema_override.get("selected_candidate_id")
        or ""
    ).strip() or None

    for idx, fname in enumerate(score_files):
        score_path = scores_dir / str(fname)
        file_rows: List[Dict[str, Any]] = []
        try:
            if score_path.suffix.lower() == ".xlsx":
                tmp_csv = derived_dir / f"responses_part_{idx}.csv"
                parsed_rows, parsed_score_schema = deps.parse_xlsx_with_script(
                    score_path,
                    tmp_csv,
                    exam_id,
                    class_name_hint,
                    selected_candidate_id,
                )
                file_rows = parsed_rows or []
                if isinstance(parsed_score_schema, dict) and parsed_score_schema:
                    source_item = {
                        "file": str(fname),
                        "path": str(score_path),
                        **parsed_score_schema,
                    }
                    score_schema_sources.append(source_item)
                if not file_rows:
                    table_preview = deps.xlsx_to_table_preview(score_path)
                    if table_preview.strip():
                        parsed_scores = deps.llm_parse_exam_scores(table_preview)
                        if parsed_scores.get("error"):
                            warnings.append(f"成绩文件 {fname} LLM解析失败：{parsed_scores.get('error')}")
                        else:
                            file_rows, _, file_warnings = deps.build_exam_rows_from_parsed_scores(exam_id, parsed_scores)
                            warnings.extend(file_warnings)
            elif score_path.suffix.lower() == ".xls":
                table_preview = deps.xls_to_table_preview(score_path)
                if table_preview.strip():
                    parsed_scores = deps.llm_parse_exam_scores(table_preview)
                    if parsed_scores.get("error"):
                        warnings.append(f"成绩文件 {fname} LLM解析失败：{parsed_scores.get('error')}")
                    else:
                        file_rows, _, file_warnings = deps.build_exam_rows_from_parsed_scores(exam_id, parsed_scores)
                        warnings.extend(file_warnings)
            else:
                score_text_parts: List[str] = []
                if score_path.suffix.lower() == ".pdf":
                    score_text_parts.append(deps.extract_text_from_pdf(score_path, language=language, ocr_mode=ocr_mode))
                else:
                    score_text_parts.append(
                        deps.extract_text_from_image(score_path, language=language, ocr_mode=ocr_mode)
                    )
                table_preview = "\n\n".join([text for text in score_text_parts if text])
                if table_preview.strip():
                    parsed_scores = deps.llm_parse_exam_scores(table_preview)
                    if parsed_scores.get("error"):
                        warnings.append(f"成绩文件 {fname} LLM解析失败：{parsed_scores.get('error')}")
                    else:
                        file_rows, _, file_warnings = deps.build_exam_rows_from_parsed_scores(exam_id, parsed_scores)
                        warnings.extend(file_warnings)
        except Exception as exc:
            warnings.append(f"成绩文件 {fname} 解析异常：{str(exc)[:120]}")
            continue

        if file_rows:
            all_rows.extend(file_rows)

    if not all_rows:
        deps.write_exam_job(
            job_id,
            {
                "status": "failed",
                "step": "parse_scores",
                "progress": 100,
                "error": "scores_parsed_empty",
                "hints": ["未能从成绩文件解析出有效得分行。请优先上传 xlsx/xls，或更清晰的 PDF/图片。"] + ocr_hints,
            },
        )
        return

    dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in all_rows:
        sid = str(row.get("student_id") or "").strip()
        qid = str(row.get("question_id") or "").strip()
        if not sid or not qid:
            continue
        key = (sid, qid)
        try:
            score_val = float(row.get("score")) if row.get("score") is not None else None
        except Exception:
            score_val = None
        prev = dedup.get(key)
        if not prev:
            dedup[key] = row
            continue
        try:
            prev_score = float(prev.get("score")) if prev.get("score") is not None else None
        except Exception:
            prev_score = None
        if score_val is not None and (prev_score is None or score_val > prev_score):
            dedup[key] = row

    rows = list(dedup.values())

    q_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        qid = str(row.get("question_id") or "").strip()
        if not qid:
            continue
        if qid not in q_map:
            q_map[qid] = {
                "question_id": qid,
                "question_no": str(row.get("question_no") or "").strip(),
                "sub_no": str(row.get("sub_no") or "").strip(),
            }
    questions = list(q_map.values())
    questions.sort(
        key=lambda q: int(q.get("question_no") or "0") if str(q.get("question_no") or "").isdigit() else 9999
    )

    derived_dir.mkdir(parents=True, exist_ok=True)
    responses_unscored_csv = derived_dir / "responses_unscored.csv"
    responses_scored_csv = derived_dir / "responses_scored.csv"
    deps.write_exam_responses_csv(responses_unscored_csv, rows)

    answer_text = ""
    answers: List[Dict[str, Any]] = []
    answer_parse_warnings: List[str] = []
    if answer_files:
        deps.write_exam_job(job_id, {"step": "extract_answers", "progress": 45})
        answer_ocr_prompt = "请做OCR，只返回题号与选择题答案，不要解释。推荐每行一个：`1 A`、`2 C`、`12(1) B`。"
        answer_text_parts: List[str] = []
        for fname in answer_files:
            path = answers_dir / str(fname)
            if not path.exists():
                continue
            try:
                answer_text_parts.append(
                    deps.extract_text_from_file(path, language=language, ocr_mode=ocr_mode, prompt=answer_ocr_prompt)
                )
            except Exception as exc:
                warnings.append(f"答案文件 {fname} 解析失败：{str(exc)[:120]}")
        answer_text = "\n\n".join([text for text in answer_text_parts if text])
        (job_dir / "answer_text.txt").write_text(answer_text or "", encoding="utf-8")
        answers, answer_parse_warnings = deps.parse_exam_answer_key_text(answer_text)
        if answer_parse_warnings:
            warnings.extend([f"答案解析提示：{warn}" for warn in answer_parse_warnings])

    answers_csv = derived_dir / "answers.csv"
    if answers:
        deps.write_exam_answers_csv(answers_csv, answers)

    max_scores = deps.compute_max_scores_from_rows(rows)
    needs_answer_scoring = any((row.get("score") is None) and str(row.get("raw_answer") or "").strip() for row in rows)
    qids_need: set[str] = set()
    defaulted_max_score_qids: List[str] = []
    if needs_answer_scoring and answers:
        qids_need = {
            str(row.get("question_id") or "").strip()
            for row in rows
            if (row.get("score") is None) and str(row.get("raw_answer") or "").strip()
        }
        for qid in sorted(qids_need):
            if not qid:
                continue
            if qid not in max_scores:
                max_scores[qid] = 1.0
                defaulted_max_score_qids.append(qid)

    questions_csv = derived_dir / "questions.csv"
    deps.write_exam_questions_csv(questions_csv, questions, max_scores=max_scores)

    answer_apply_stats: Dict[str, Any] = {}
    if needs_answer_scoring and answers and answers_csv.exists():
        try:
            answer_apply_stats = deps.apply_answer_key_to_responses_csv(
                responses_unscored_csv,
                answers_csv,
                questions_csv,
                responses_scored_csv,
            )
            if answer_apply_stats.get("updated_rows"):
                deps.diag_log(
                    "exam_upload.answer_key.applied",
                    {
                        "job_id": job_id,
                        "updated_rows": answer_apply_stats.get("updated_rows"),
                        "total_rows": answer_apply_stats.get("total_rows"),
                    },
                )
            missing_ans = answer_apply_stats.get("missing_answer_qids") or []
            missing_max = answer_apply_stats.get("missing_max_score_qids") or []
            if missing_ans:
                preview = "，".join(missing_ans[:8])
                more = f" 等{len(missing_ans)}题" if len(missing_ans) > 8 else ""
                warnings.append(f"标准答案缺少题号：{preview}{more}（这些题无法自动评分）")
            if missing_max:
                preview = "，".join(missing_max[:8])
                more = f" 等{len(missing_max)}题" if len(missing_max) > 8 else ""
                warnings.append(f"题目满分缺失：{preview}{more}（这些题无法自动评分）")
        except Exception as exc:
            warnings.append(f"未能根据标准答案自动补齐客观题得分：{str(exc)[:120]}")
            deps.copy2(responses_unscored_csv, responses_scored_csv)
    else:
        deps.copy2(responses_unscored_csv, responses_scored_csv)

    raw_students: set[str] = set()
    scored_students: set[str] = set()
    responses_total = 0
    responses_scored = 0
    try:
        with responses_scored_csv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                responses_total += 1
                sid = str(row.get("student_id") or row.get("student_name") or "").strip()
                if sid:
                    raw_students.add(sid)
                if deps.parse_score_value(row.get("score")) is not None:
                    responses_scored += 1
                    if sid:
                        scored_students.add(sid)
    except Exception:
        pass

    scoring_status = "unscored"
    if responses_scored <= 0:
        scoring_status = "unscored"
    elif responses_total and responses_scored >= responses_total:
        scoring_status = "scored"
    else:
        scoring_status = "partial"

    totals_result = deps.compute_exam_totals(responses_scored_csv)
    totals = sorted(totals_result["totals"].values())
    avg_total = sum(totals) / len(totals) if totals else 0.0
    median_total = totals[len(totals) // 2] if totals else 0.0

    questions_for_draft: List[Dict[str, Any]] = []
    for question in questions:
        qid = str(question.get("question_id") or "").strip()
        if not qid:
            continue
        questions_for_draft.append(
            {
                "question_id": qid,
                "question_no": str(question.get("question_no") or "").strip(),
                "sub_no": str(question.get("sub_no") or "").strip(),
                "max_score": max_scores.get(qid),
            }
        )
    score_qids = [str(item.get("question_id") or "").strip() for item in questions_for_draft if item.get("question_id")]
    if len(score_qids) == 1 and score_qids[0] == "TOTAL":
        score_mode = "total"
    elif score_qids and all(qid.startswith("SUBJECT_") for qid in score_qids):
        score_mode = "subject"
    else:
        score_mode = "question"

    aggregated_data_rows = 0
    aggregated_parsed_rows = 0
    aggregated_unresolved: List[str] = []
    aggregated_candidates: List[Dict[str, Any]] = []
    confidence_values: List[float] = []
    selected_candidate_invalid = False
    for source in score_schema_sources:
        summary = source.get("summary") if isinstance(source.get("summary"), dict) else {}
        aggregated_data_rows += int(summary.get("data_rows") or 0)
        aggregated_parsed_rows += int(summary.get("parsed_rows") or 0)
        try:
            confidence_values.append(float(source.get("confidence")))
        except Exception:
            pass
        subject_info = source.get("subject") if isinstance(source.get("subject"), dict) else {}
        unresolved = subject_info.get("unresolved_students") if isinstance(subject_info.get("unresolved_students"), list) else []
        aggregated_unresolved.extend([str(x) for x in unresolved if str(x or "").strip()])
        candidates = subject_info.get("candidate_columns") if isinstance(subject_info.get("candidate_columns"), list) else []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get("candidate_id") or "").strip()
            if not candidate_id:
                continue
            aggregated_candidates.append({"candidate_id": candidate_id, **item, "file": source.get("file")})

    if score_schema_sources:
        modes = [str(source.get("mode") or "") for source in score_schema_sources if str(source.get("mode") or "")]
        overall_mode = "question" if "question" in modes else (modes[0] if modes else "")
        coverage = (aggregated_parsed_rows / aggregated_data_rows) if aggregated_data_rows > 0 else 0.0
        confidence = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0
        seen_candidate_ids: set[str] = set()
        dedup_candidates: List[Dict[str, Any]] = []
        for item in aggregated_candidates:
            candidate_id = str(item.get("candidate_id") or "").strip()
            if not candidate_id or candidate_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate_id)
            dedup_candidates.append(item)

        candidate_stats: Dict[str, Dict[str, Any]] = {}
        for item in aggregated_candidates:
            candidate_id = str(item.get("candidate_id") or "").strip()
            if not candidate_id:
                continue
            bucket = candidate_stats.setdefault(
                candidate_id,
                {
                    "candidate_id": candidate_id,
                    "rows_considered": 0,
                    "rows_parsed": 0,
                    "rows_invalid": 0,
                    "files": set(),
                    "types": set(),
                },
            )
            bucket["rows_considered"] = int(bucket.get("rows_considered") or 0) + int(item.get("rows_considered") or 0)
            bucket["rows_parsed"] = int(bucket.get("rows_parsed") or 0) + int(item.get("rows_parsed") or 0)
            bucket["rows_invalid"] = int(bucket.get("rows_invalid") or 0) + int(item.get("rows_invalid") or 0)
            file_name = str(item.get("file") or "").strip()
            if file_name:
                bucket_files = bucket.get("files")
                if isinstance(bucket_files, set):
                    bucket_files.add(file_name)
            candidate_type = str(item.get("type") or "").strip()
            if candidate_type:
                bucket_types = bucket.get("types")
                if isinstance(bucket_types, set):
                    bucket_types.add(candidate_type)

        candidate_summaries: List[Dict[str, Any]] = []
        for candidate_id, bucket in candidate_stats.items():
            rows_considered = int(bucket.get("rows_considered") or 0)
            rows_parsed = int(bucket.get("rows_parsed") or 0)
            rows_invalid = int(bucket.get("rows_invalid") or 0)
            parsed_rate = (rows_parsed / rows_considered) if rows_considered > 0 else 0.0
            quality_score = (rows_parsed * 1.0) + (parsed_rate * 100.0) - (rows_invalid * 0.2) - (
                _candidate_source_rank(candidate_id) * 2.0
            )
            files = bucket.get("files") if isinstance(bucket.get("files"), set) else set()
            types = bucket.get("types") if isinstance(bucket.get("types"), set) else set()
            candidate_summaries.append(
                {
                    "candidate_id": candidate_id,
                    "rows_considered": rows_considered,
                    "rows_parsed": rows_parsed,
                    "rows_invalid": rows_invalid,
                    "parsed_rate": round(float(parsed_rate), 4),
                    "source_rank": _candidate_source_rank(candidate_id),
                    "files": sorted([str(x) for x in files]),
                    "types": sorted([str(x) for x in types]),
                    "quality_score": round(float(quality_score), 4),
                }
            )
        candidate_summaries.sort(
            key=lambda item: (
                -float(item.get("quality_score") or 0.0),
                int(item.get("source_rank") or 99),
                str(item.get("candidate_id") or ""),
            )
        )
        recommended_candidate_id = str((candidate_summaries[0].get("candidate_id") if candidate_summaries else "") or "")
        recommended_candidate_reason = ""
        if candidate_summaries:
            top = candidate_summaries[0]
            recommended_candidate_reason = (
                f"rows_parsed={int(top.get('rows_parsed') or 0)}, "
                f"parsed_rate={float(top.get('parsed_rate') or 0.0):.2f}, "
                f"source_rank={int(top.get('source_rank') or 99)}"
            )

        selected_candidate_available = True
        if overall_mode == "subject" and selected_candidate_id:
            subject_sources = [
                source for source in score_schema_sources if str(source.get("mode") or "") == "subject"
            ]
            candidate_present = any(
                str(item.get("candidate_id") or "").strip() == selected_candidate_id for item in dedup_candidates
            )
            availability_flags: List[bool] = []
            for source in subject_sources:
                subject_info = source.get("subject") if isinstance(source.get("subject"), dict) else {}
                if "selected_candidate_available" in subject_info:
                    availability_flags.append(bool(subject_info.get("selected_candidate_available")))
            selected_candidate_available = bool(candidate_present and (not availability_flags or all(availability_flags)))
            selected_candidate_invalid = not selected_candidate_available

        needs_confirm = bool((coverage < 0.85) or (confidence < 0.82) or selected_candidate_invalid)

        score_schema = {
            "mode": overall_mode,
            "confidence": round(float(confidence), 4),
            "needs_confirm": needs_confirm,
            "sources": score_schema_sources,
            "subject": {
                "target": "physics",
                "selected_candidate_id": selected_candidate_id,
                "selected_candidate_available": selected_candidate_available,
                "recommended_candidate_id": recommended_candidate_id,
                "recommended_candidate_reason": recommended_candidate_reason,
                "candidate_summaries": candidate_summaries,
                "coverage": round(float(coverage), 4),
                "data_rows": aggregated_data_rows,
                "parsed_rows": aggregated_parsed_rows,
                "unresolved_students": sorted(set(aggregated_unresolved)),
                "candidate_columns": dedup_candidates,
                "thresholds": {"coverage": 0.85, "confidence": 0.82},
            },
        }
        if selected_candidate_id and selected_candidate_available:
            score_schema["confirm"] = True
            score_schema["needs_confirm"] = False
        elif selected_candidate_id and selected_candidate_invalid:
            score_schema["subject"]["selection_error"] = "selected_candidate_not_found"

    parsed_payload = {
        "exam_id": exam_id,
        "generated_at": deps.now_iso(),
        "meta": {
            "date": deps.parse_date_str(job.get("date")),
            "class_name": str(job.get("class_name") or ""),
            "language": language,
            "score_mode": score_mode,
        },
        "paper_files": paper_files,
        "score_files": score_files,
        "answer_files": answer_files,
        "derived": {
            "responses_unscored": "derived/responses_unscored.csv",
            "responses_scored": "derived/responses_scored.csv",
            "questions": "derived/questions.csv",
            "answers": "derived/answers.csv" if answers else "",
        },
        "questions": questions_for_draft,
        "answer_key": {"count": len(answers), "source_files": answer_files}
        if answers
        else {"count": 0, "source_files": answer_files},
        "scoring": {
            "status": scoring_status,
            "responses_total": responses_total,
            "responses_scored": responses_scored,
            "students_total": len(raw_students),
            "students_scored": len(scored_students),
            "default_max_score_qids": defaulted_max_score_qids,
        },
        "counts": {
            "students": len(raw_students),
            "responses": responses_total or len(rows),
            "questions": len(questions),
        },
        "counts_scored": {
            "students": len(scored_students),
            "responses": responses_scored,
        },
        "totals_summary": {
            "avg_total": round(avg_total, 3),
            "median_total": round(median_total, 3),
            "max_total_observed": max(totals) if totals else 0.0,
        },
        "score_schema": score_schema,
        "warnings": warnings,
        "notes": "paper_text_empty" if not paper_text.strip() else "",
    }

    needs_confirm = bool(score_schema.get("needs_confirm")) if isinstance(score_schema, dict) else False
    if needs_confirm:
        selection_error = ""
        if isinstance(score_schema, dict):
            subject_info = score_schema.get("subject") if isinstance(score_schema.get("subject"), dict) else {}
            selection_error = str(subject_info.get("selection_error") or "").strip()
        if selection_error == "selected_candidate_not_found":
            recommended_id = ""
            if isinstance(score_schema, dict):
                subject_info = score_schema.get("subject") if isinstance(score_schema.get("subject"), dict) else {}
                recommended_id = str(subject_info.get("recommended_candidate_id") or "").strip()
            if recommended_id:
                warnings.append(
                    f"所选物理分映射在当前成绩表中不可用，已回退自动匹配，建议改用 {recommended_id} 并重新确认。"
                )
            else:
                warnings.append("所选物理分映射在当前成绩表中不可用，已回退自动匹配，请重新确认映射。")
        unresolved = ((score_schema.get("subject") or {}).get("unresolved_students") or []) if isinstance(score_schema, dict) else []
        unresolved_count = len(unresolved) if isinstance(unresolved, list) else 0
        if unresolved_count > 0:
            preview = "，".join([str(x) for x in unresolved[:5]])
            more = f" 等{unresolved_count}人" if unresolved_count > 5 else ""
            warnings.append(f"物理成绩解析置信度不足：{preview}{more} 未能自动识别，请在草稿中确认物理分映射。")
        else:
            warnings.append("物理成绩解析置信度不足，请在草稿中确认物理分映射。")
        parsed_payload["warnings"] = warnings
    parsed_payload["needs_confirm"] = needs_confirm
    (job_dir / "parsed.json").write_text(json.dumps(parsed_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    deps.write_exam_job(
        job_id,
        {
            "status": "done",
            "step": "done",
            "progress": 100,
            "exam_id": exam_id,
            "counts": parsed_payload.get("counts"),
            "counts_scored": parsed_payload.get("counts_scored"),
            "totals_summary": parsed_payload.get("totals_summary"),
            "scoring": parsed_payload.get("scoring"),
            "answer_key": parsed_payload.get("answer_key"),
            "warnings": warnings,
            "draft_version": 1,
            "needs_confirm": needs_confirm,
            "score_schema": score_schema,
        },
    )

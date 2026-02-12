from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_EXAM_CHART_DEFAULT_TYPES = ["score_distribution", "knowledge_radar", "class_compare", "question_discrimination"]
_EXAM_CHART_TYPE_ALIASES = {
    "score_distribution": "score_distribution",
    "distribution": "score_distribution",
    "histogram": "score_distribution",
    "成绩分布": "score_distribution",
    "分布": "score_distribution",
    "knowledge_radar": "knowledge_radar",
    "radar": "knowledge_radar",
    "knowledge": "knowledge_radar",
    "知识点雷达": "knowledge_radar",
    "雷达图": "knowledge_radar",
    "class_compare": "class_compare",
    "class": "class_compare",
    "group_compare": "class_compare",
    "班级对比": "class_compare",
    "对比": "class_compare",
    "question_discrimination": "question_discrimination",
    "discrimination": "question_discrimination",
    "区分度": "question_discrimination",
    "题目区分度": "question_discrimination",
}


@dataclass(frozen=True)
class ExamAnalysisChartsDeps:
    app_root: Path
    uploads_dir: Path
    safe_int_arg: Callable[[Any, int, int, int], int]
    load_exam_manifest: Callable[[str], Dict[str, Any]]
    exam_responses_path: Callable[[Dict[str, Any]], Optional[Path]]
    compute_exam_totals: Callable[[Path], Dict[str, Any]]
    exam_analysis_get: Callable[[str], Dict[str, Any]]
    parse_score_value: Callable[[Any], Optional[float]]
    exam_questions_path: Callable[[Dict[str, Any]], Optional[Path]]
    read_questions_csv: Callable[[Path], Dict[str, Dict[str, Any]]]
    execute_chart_exec: Callable[..., Dict[str, Any]]


def normalize_exam_chart_types(value: Any) -> List[str]:
    raw_items: List[str] = []
    if isinstance(value, list):
        raw_items = [str(v or "").strip() for v in value]
    elif isinstance(value, str):
        raw_items = [x.strip() for x in re.split(r"[,\s，;；]+", value) if x.strip()]
    normalized: List[str] = []
    for item in raw_items:
        key = _EXAM_CHART_TYPE_ALIASES.get(item.lower()) or _EXAM_CHART_TYPE_ALIASES.get(item)
        if not key:
            continue
        if key not in normalized:
            normalized.append(key)
    return normalized or list(_EXAM_CHART_DEFAULT_TYPES)


def build_exam_chart_bundle_input(exam_id: str, top_n: int, deps: ExamAnalysisChartsDeps) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    responses_path = deps.exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}

    totals_result = deps.compute_exam_totals(responses_path)
    totals: Dict[str, float] = totals_result.get("totals") or {}
    students_meta: Dict[str, Dict[str, str]] = totals_result.get("students") or {}
    if not totals:
        return {"error": "no_scored_responses", "exam_id": exam_id}

    score_values = [float(v) for v in totals.values()]
    student_count = len(score_values)
    warnings: List[str] = []

    class_scores: Dict[str, List[float]] = {}
    for sid, total in totals.items():
        cls = str((students_meta.get(sid) or {}).get("class_name") or "").strip() or "未分班"
        class_scores.setdefault(cls, []).append(float(total))

    class_compare_mode = "class"
    class_compare: List[Dict[str, Any]] = []
    if len(class_scores) >= 2:
        for cls, vals in class_scores.items():
            class_compare.append(
                {
                    "label": cls,
                    "avg_total": round(sum(vals) / len(vals), 3),
                    "student_count": len(vals),
                }
            )
        class_compare.sort(key=lambda x: x.get("avg_total") or 0, reverse=True)
    else:
        class_compare_mode = "tier"
        ranked_scores = [float(v) for _, v in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)]
        if ranked_scores:
            n = len(ranked_scores)
            idx1 = max(1, n // 3)
            idx2 = n if n < 3 else min(n, max(idx1 + 1, (2 * n) // 3))
            segments = [
                ("Top 33%", ranked_scores[:idx1]),
                ("Middle 34%", ranked_scores[idx1:idx2]),
                ("Bottom 33%", ranked_scores[idx2:]),
            ]
            for label, vals in segments:
                if not vals:
                    continue
                class_compare.append(
                    {
                        "label": label,
                        "avg_total": round(sum(vals) / len(vals), 3),
                        "student_count": len(vals),
                    }
                )

    analysis_res = deps.exam_analysis_get(exam_id)
    kp_items: List[Dict[str, Any]] = []
    if analysis_res.get("ok"):
        analysis = analysis_res.get("analysis") if isinstance(analysis_res.get("analysis"), dict) else {}
        raw_kps = analysis.get("knowledge_points") if isinstance(analysis, dict) else None
        if isinstance(raw_kps, list):
            for row in raw_kps:
                if not isinstance(row, dict):
                    continue
                label = str(row.get("kp_id") or row.get("name") or row.get("kp") or "").strip()
                if not label:
                    continue
                mastery: Optional[float] = None
                loss_rate = deps.parse_score_value(row.get("loss_rate"))
                if loss_rate is not None:
                    mastery = 1.0 - float(loss_rate)
                if mastery is None:
                    avg_score = deps.parse_score_value(row.get("avg_score"))
                    coverage_score = deps.parse_score_value(row.get("coverage_score"))
                    if (avg_score is not None) and (coverage_score is not None) and coverage_score > 0:
                        mastery = float(avg_score) / float(coverage_score)
                if mastery is None:
                    mastery = deps.parse_score_value(row.get("mastery"))
                if mastery is None:
                    continue
                mastery = max(0.0, min(1.0, float(mastery)))
                kp_items.append(
                    {
                        "label": label,
                        "mastery": round(mastery, 4),
                        "loss_rate": round(1.0 - mastery, 4),
                        "coverage_count": int(row.get("coverage_count") or 0),
                    }
                )
    if kp_items:
        kp_items.sort(key=lambda x: x.get("mastery") or 0)
        kp_limit = deps.safe_int_arg(top_n, 8, 3, 12)
        kp_items = kp_items[:kp_limit]
    else:
        warnings.append("知识点雷达图数据不足（analysis.knowledge_points 缺失或为空）。")

    questions_path = deps.exam_questions_path(manifest)
    questions = deps.read_questions_csv(questions_path) if questions_path else {}
    question_scores: Dict[str, Dict[str, float]] = {}
    question_meta: Dict[str, Dict[str, Any]] = {}
    observed_max: Dict[str, float] = {}
    with responses_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sid = str(row.get("student_id") or row.get("student_name") or "").strip()
            qid = str(row.get("question_id") or "").strip()
            score = deps.parse_score_value(row.get("score"))
            if not sid or not qid or score is None:
                continue
            per_q = question_scores.setdefault(qid, {})
            prev = per_q.get(sid)
            if (prev is None) or (score > prev):
                per_q[sid] = float(score)
            prev_max = observed_max.get(qid)
            observed_max[qid] = float(score) if prev_max is None else max(prev_max, float(score))
            if qid not in question_meta:
                question_meta[qid] = {
                    "question_no": str(row.get("question_no") or "").strip(),
                    "question_id": qid,
                }

    question_discrimination: List[Dict[str, Any]] = []
    ranked_students = [sid for sid, _ in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)]
    if len(ranked_students) >= 4:
        group_size = max(1, int(len(ranked_students) * 0.27))
        group_size = min(group_size, len(ranked_students) // 2)
        top_ids = ranked_students[:group_size]
        bottom_ids = ranked_students[-group_size:]
        for qid, per_student in question_scores.items():
            q_meta = questions.get(qid) or question_meta.get(qid) or {}
            max_score = deps.parse_score_value(q_meta.get("max_score"))
            if (max_score is None) or (max_score <= 0):
                max_score = observed_max.get(qid)
            if (max_score is None) or (max_score <= 0):
                continue
            top_vals = [float(per_student[sid]) / float(max_score) for sid in top_ids if sid in per_student]
            bottom_vals = [float(per_student[sid]) / float(max_score) for sid in bottom_ids if sid in per_student]
            if (not top_vals) or (not bottom_vals):
                continue
            disc = (sum(top_vals) / len(top_vals)) - (sum(bottom_vals) / len(bottom_vals))
            avg_score = sum(per_student.values()) / len(per_student) if per_student else 0.0
            q_no = str(q_meta.get("question_no") or "").strip()
            label = q_no if q_no.upper().startswith("Q") else (f"Q{q_no}" if q_no else qid)
            question_discrimination.append(
                {
                    "question_id": qid,
                    "label": label,
                    "discrimination": round(float(disc), 4),
                    "avg_score": round(float(avg_score), 4),
                    "max_score": float(max_score),
                    "response_count": len(per_student),
                }
            )
        question_discrimination.sort(key=lambda x: x.get("discrimination") or 0)
        question_discrimination = question_discrimination[: deps.safe_int_arg(top_n, 12, 3, 30)]
    else:
        warnings.append("题目区分度图数据不足（学生数至少需要 4 人）。")

    return {
        "ok": True,
        "exam_id": exam_id,
        "student_count": student_count,
        "scores": score_values,
        "knowledge_points": kp_items,
        "class_compare": class_compare,
        "class_compare_mode": class_compare_mode,
        "question_discrimination": question_discrimination,
        "warnings": warnings,
    }


def chart_code_score_distribution() -> str:
    return (
        "import matplotlib.pyplot as plt\n"
        "import numpy as np\n"
        "scores = [float(x) for x in (input_data.get('scores') or []) if x is not None]\n"
        "if not scores:\n"
        "    raise ValueError('no score data')\n"
        "title = str(input_data.get('title') or 'Score Distribution')\n"
        "bins = min(15, max(6, int(np.sqrt(len(scores)))))\n"
        "plt.figure(figsize=(8, 4.8))\n"
        "plt.hist(scores, bins=bins, color='#3B82F6', edgecolor='white', alpha=0.92)\n"
        "mean_val = float(np.mean(scores))\n"
        "median_val = float(np.median(scores))\n"
        "plt.axvline(mean_val, color='#EF4444', linestyle='--', linewidth=1.8, label='mean=' + format(mean_val, '.1f'))\n"
        "plt.axvline(median_val, color='#10B981', linestyle='-.', linewidth=1.6, label='median=' + format(median_val, '.1f'))\n"
        "plt.title(title)\n"
        "plt.xlabel('Total Score')\n"
        "plt.ylabel('Students')\n"
        "plt.grid(axis='y', alpha=0.25)\n"
        "plt.legend(frameon=False)\n"
        "save_chart('score_distribution.png')\n"
    )


def chart_code_knowledge_radar() -> str:
    return (
        "import matplotlib.pyplot as plt\n"
        "import numpy as np\n"
        "items = input_data.get('items') or []\n"
        "labels = []\n"
        "values = []\n"
        "for row in items:\n"
        "    row = row or {}\n"
        "    label = str(row.get('label') or row.get('kp_id') or '').strip()\n"
        "    if not label:\n"
        "        continue\n"
        "    try:\n"
        "        val = float(row.get('mastery'))\n"
        "    except Exception:\n"
        "        continue\n"
        "    labels.append(label)\n"
        "    values.append(max(0.0, min(1.0, val)))\n"
        "if not labels:\n"
        "    raise ValueError('no knowledge data')\n"
        "title = str(input_data.get('title') or 'Knowledge Mastery Radar')\n"
        "plt.figure(figsize=(6.6, 6.2))\n"
        "if len(labels) >= 3:\n"
        "    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()\n"
        "    values_loop = values + values[:1]\n"
        "    angles_loop = angles + angles[:1]\n"
        "    ax = plt.subplot(111, polar=True)\n"
        "    ax.plot(angles_loop, values_loop, color='#2563EB', linewidth=2)\n"
        "    ax.fill(angles_loop, values_loop, color='#60A5FA', alpha=0.35)\n"
        "    ax.set_xticks(angles)\n"
        "    ax.set_xticklabels(labels)\n"
        "    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])\n"
        "    ax.set_ylim(0, 1.0)\n"
        "    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'])\n"
        "    ax.set_title(title, pad=18)\n"
        "else:\n"
        "    plt.bar(labels, values, color='#2563EB', alpha=0.9)\n"
        "    plt.ylim(0, 1.0)\n"
        "    plt.title(title)\n"
        "    plt.ylabel('Mastery (0-1)')\n"
        "    plt.grid(axis='y', alpha=0.25)\n"
        "save_chart('knowledge_radar.png')\n"
    )


def chart_code_class_compare() -> str:
    return (
        "import matplotlib.pyplot as plt\n"
        "items = input_data.get('items') or []\n"
        "labels = []\n"
        "avg_scores = []\n"
        "counts = []\n"
        "for row in items:\n"
        "    row = row or {}\n"
        "    label = str(row.get('label') or '').strip()\n"
        "    if not label:\n"
        "        continue\n"
        "    try:\n"
        "        avg = float(row.get('avg_total'))\n"
        "    except Exception:\n"
        "        continue\n"
        "    labels.append(label)\n"
        "    avg_scores.append(avg)\n"
        "    counts.append(int(row.get('student_count') or 0))\n"
        "if not labels:\n"
        "    raise ValueError('no class compare data')\n"
        "title = str(input_data.get('title') or 'Class Compare')\n"
        "x_label = str(input_data.get('x_label') or 'Group')\n"
        "plt.figure(figsize=(8, 4.8))\n"
        "bars = plt.bar(labels, avg_scores, color='#0EA5E9', alpha=0.9)\n"
        "for bar, cnt in zip(bars, counts):\n"
        "    h = bar.get_height()\n"
        "    plt.text(bar.get_x() + bar.get_width() / 2, h, 'n=' + str(cnt), ha='center', va='bottom', fontsize=9)\n"
        "plt.title(title)\n"
        "plt.xlabel(x_label)\n"
        "plt.ylabel('Average Total Score')\n"
        "plt.grid(axis='y', alpha=0.25)\n"
        "save_chart('class_compare.png')\n"
    )


def chart_code_question_discrimination() -> str:
    return (
        "import matplotlib.pyplot as plt\n"
        "import numpy as np\n"
        "items = input_data.get('items') or []\n"
        "labels = []\n"
        "values = []\n"
        "for row in items:\n"
        "    row = row or {}\n"
        "    label = str(row.get('label') or row.get('question_id') or '').strip()\n"
        "    if not label:\n"
        "        continue\n"
        "    try:\n"
        "        v = float(row.get('discrimination'))\n"
        "    except Exception:\n"
        "        continue\n"
        "    labels.append(label)\n"
        "    values.append(v)\n"
        "if not labels:\n"
        "    raise ValueError('no discrimination data')\n"
        "title = str(input_data.get('title') or 'Question Discrimination')\n"
        "height = max(4.8, 0.35 * len(labels) + 1.5)\n"
        "plt.figure(figsize=(9, height))\n"
        "y = np.arange(len(labels))\n"
        "colors = ['#10B981' if v >= 0.3 else ('#F59E0B' if v >= 0.2 else '#EF4444') for v in values]\n"
        "plt.barh(y, values, color=colors, alpha=0.92)\n"
        "plt.yticks(y, labels)\n"
        "plt.axvline(0.2, color='#F59E0B', linestyle='--', linewidth=1.2)\n"
        "plt.axvline(0.4, color='#10B981', linestyle='--', linewidth=1.2)\n"
        "x_min = min(-0.1, min(values) - 0.05)\n"
        "x_max = max(0.6, max(values) + 0.08)\n"
        "plt.xlim(x_min, x_max)\n"
        "for idx, v in enumerate(values):\n"
        "    offset = 0.01 if v >= 0 else -0.08\n"
        "    plt.text(v + offset, idx, format(v, '.2f'), va='center', fontsize=8)\n"
        "plt.gca().invert_yaxis()\n"
        "plt.title(title)\n"
        "plt.xlabel('Discrimination (Top27% - Bottom27%)')\n"
        "plt.grid(axis='x', alpha=0.25)\n"
        "save_chart('question_discrimination.png')\n"
    )


def exam_analysis_charts_generate(args: Dict[str, Any], deps: ExamAnalysisChartsDeps) -> Dict[str, Any]:
    exam_id = str(args.get("exam_id") or "").strip()
    if not exam_id:
        return {"error": "exam_id_required"}

    top_n = deps.safe_int_arg(args.get("top_n"), 12, 3, 30)
    timeout_sec = deps.safe_int_arg(args.get("timeout_sec"), 120, 30, 3600)
    chart_types = normalize_exam_chart_types(args.get("chart_types"))

    bundle = build_exam_chart_bundle_input(exam_id, top_n=top_n, deps=deps)
    if bundle.get("error"):
        return bundle

    warnings = list(bundle.get("warnings") or [])
    charts: List[Dict[str, Any]] = []

    def run_chart(
        chart_type: str,
        title: str,
        python_code: str,
        input_data: Dict[str, Any],
        save_as: str,
    ) -> None:
        result = deps.execute_chart_exec(
            {
                "python_code": python_code,
                "input_data": input_data,
                "chart_hint": f"{chart_type}:{exam_id}",
                "timeout_sec": timeout_sec,
                "save_as": save_as,
                "execution_profile": "template",
            },
            app_root=deps.app_root,
            uploads_dir=deps.uploads_dir,
        )
        entry = {
            "chart_type": chart_type,
            "title": title,
            "ok": bool(result.get("ok")),
            "run_id": result.get("run_id"),
            "image_url": result.get("image_url"),
            "meta_url": result.get("meta_url"),
            "artifacts": result.get("artifacts") or [],
        }
        if not entry["ok"]:
            stderr = str(result.get("stderr") or "").strip()
            if stderr:
                entry["stderr"] = stderr[:400]
            warnings.append(f"{title} 生成失败。")
        charts.append(entry)

    for chart_type in chart_types:
        if chart_type == "score_distribution":
            scores = bundle.get("scores") or []
            if not scores:
                warnings.append("成绩分布图数据不足。")
                continue
            run_chart(
                chart_type=chart_type,
                title="成绩分布图",
                python_code=chart_code_score_distribution(),
                input_data={"title": f"Score Distribution · {exam_id}", "scores": scores},
                save_as="score_distribution.png",
            )
            continue

        if chart_type == "knowledge_radar":
            kp_items = bundle.get("knowledge_points") or []
            if not kp_items:
                warnings.append("知识点雷达图数据不足。")
                continue
            run_chart(
                chart_type=chart_type,
                title="知识点掌握雷达图",
                python_code=chart_code_knowledge_radar(),
                input_data={"title": f"Knowledge Mastery · {exam_id}", "items": kp_items},
                save_as="knowledge_radar.png",
            )
            continue

        if chart_type == "class_compare":
            compare_items = bundle.get("class_compare") or []
            if not compare_items:
                warnings.append("班级/分层对比图数据不足。")
                continue
            compare_mode = str(bundle.get("class_compare_mode") or "class")
            x_label = "Class" if compare_mode == "class" else "Tier"
            run_chart(
                chart_type=chart_type,
                title="班级（或分层）均分对比图",
                python_code=chart_code_class_compare(),
                input_data={
                    "title": f"Average Score Compare · {exam_id}",
                    "x_label": x_label,
                    "items": compare_items,
                },
                save_as="class_compare.png",
            )
            continue

        if chart_type == "question_discrimination":
            items = bundle.get("question_discrimination") or []
            if not items:
                warnings.append("题目区分度图数据不足。")
                continue
            run_chart(
                chart_type=chart_type,
                title="题目区分度图（低到高）",
                python_code=chart_code_question_discrimination(),
                input_data={"title": f"Question Discrimination · {exam_id}", "items": items},
                save_as="question_discrimination.png",
            )
            continue

    successful = [c for c in charts if c.get("ok") and c.get("image_url")]
    markdown_lines = [f"### 考试分析图表 · {exam_id}"]
    for item in successful:
        title = str(item.get("title") or item.get("chart_type") or "chart")
        markdown_lines.append(f"#### {title}")
        markdown_lines.append(f"![{title}]({item.get('image_url')})")
    markdown = "\n\n".join(markdown_lines) if successful else ""

    return {
        "ok": bool(successful),
        "exam_id": exam_id,
        "chart_types_requested": chart_types,
        "generated_count": len(successful),
        "student_count": bundle.get("student_count"),
        "charts": charts,
        "warnings": warnings,
        "markdown": markdown,
    }

from __future__ import annotations

import re
from typing import List, Optional, Tuple

_CE_ID_RE = re.compile(r"\bCE\d+\b", flags=re.I)
_SINGLE_STUDENT_RE = re.compile(r"(某个学生|单个学生|该学生|同学.*(画像|诊断|表现))")
_ROUTING_RE = re.compile(r"(llm\s*routing|模型路由|路由(配置|仿真|回滚|策略|规则))", flags=re.I)


def _score_teacher_skill(
    skill_id: str,
    text: str,
    *,
    assignment_intent: bool,
    assignment_generation: bool,
) -> Tuple[int, List[str]]:
    score = 0
    hits: List[str] = []

    if skill_id == "physics-homework-generator":
        if assignment_intent and assignment_generation:
            score += 8
            hits.append("assignment_generation")
        elif assignment_intent:
            score += 2
            hits.append("assignment_intent")
        for key, weight in (
            ("生成作业", 4),
            ("布置作业", 4),
            ("作业id", 4),
            ("作业 id", 4),
            ("课后作业", 3),
            ("每个知识点", 2),
            ("题量", 2),
            ("渲染作业", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        if "作业" in text:
            score += 1
            hits.append("作业")
        return score, hits

    if skill_id == "physics-llm-routing":
        if _ROUTING_RE.search(text):
            score += 7
            hits.append("routing_regex")
        for key, weight in (
            ("teacher.llm_routing", 6),
            ("channel", 2),
            ("fallback", 2),
            ("provider", 2),
            ("model", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    if skill_id == "physics-lesson-capture":
        has_lesson = ("课堂" in text) or ("lesson" in text)
        has_capture = any(
            key in text
            for key in ("采集", "ocr", "识别", "抽取", "板书", "课件", "课堂材料")
        )
        if has_lesson and has_capture:
            score += 7
            hits.append("lesson_capture_combo")
        for key, weight in (
            ("课堂采集", 4),
            ("采集课堂", 4),
            ("lesson.capture", 4),
            ("ocr", 2),
            ("课堂材料", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    if skill_id == "physics-core-examples":
        if _CE_ID_RE.search(text):
            score += 5
            hits.append("ce_id")
        for key, weight in (
            ("核心例题", 5),
            ("变式题", 4),
            ("例题库", 3),
            ("登记例题", 3),
            ("标准解法", 2),
            ("core_example", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    if skill_id == "physics-student-focus":
        has_student = ("学生" in text) or ("同学" in text)
        has_focus = any(
            key in text
            for key in ("画像", "诊断", "最近作业", "薄弱", "个体", "个人", "针对")
        )
        if has_student and has_focus:
            score += 7
            hits.append("student_focus_combo")
        if _SINGLE_STUDENT_RE.search(text):
            score += 4
            hits.append("single_student_regex")
        return score, hits

    if skill_id == "physics-student-coach":
        for key, weight in (
            ("开始今天作业", 4),
            ("开始作业", 3),
            ("开始练习", 3),
            ("讲解错题", 3),
            ("错题讲解", 3),
            ("学习建议", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    if skill_id == "physics-teacher-ops":
        for key, weight in (
            ("考试分析", 5),
            ("分析考试", 5),
            ("试卷", 3),
            ("讲评", 3),
            ("备课", 3),
            ("课前检测", 3),
            ("课堂讨论", 2),
            ("exam", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    return score, hits


def score_role_skill(
    role_hint: Optional[str],
    skill_id: str,
    text: str,
    *,
    assignment_intent: bool,
    assignment_generation: bool,
) -> Tuple[int, List[str]]:
    role = str(role_hint or "").strip()
    if role == "teacher":
        return _score_teacher_skill(
            skill_id,
            text,
            assignment_intent=assignment_intent,
            assignment_generation=assignment_generation,
        )
    if role == "student":
        if skill_id == "physics-student-coach":
            score = 0
            hits: List[str] = []
            for key, weight in (
                ("开始今天作业", 4),
                ("开始作业", 3),
                ("开始练习", 3),
                ("诊断", 2),
                ("讲解", 2),
                ("错题", 2),
            ):
                if key in text:
                    score += weight
                    hits.append(key)
            return score, hits
        return 0, []
    return 0, []


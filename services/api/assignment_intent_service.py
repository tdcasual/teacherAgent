from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .assignment_requirements_service import normalize_class_level, parse_duration, parse_list_value


def normalize_numbered_block(text: str) -> str:
    return re.sub(r"(?<!\n)\s*([1-8][).）])", r"\n\1", text)


def extract_numbered_item(text: str, idx: int) -> Optional[str]:
    pattern = rf"(?:^|\n)\s*{idx}[).）]\s*(.*?)(?=\n\s*{idx+1}[).）]|$)"
    match = re.search(pattern, text, re.S)
    if not match:
        return None
    return match.group(1).strip()


def parse_subject_topic(text: str) -> Tuple[str, str]:
    subject = ""
    topic = ""
    if not text:
        return subject, topic
    subjects = ["物理", "数学", "化学", "生物", "语文", "英语", "历史", "地理", "政治"]
    for sub in subjects:
        if sub in text:
            subject = sub
            break
    if subject:
        topic = text.replace(subject, "").replace(":", "").replace("：", "").strip()
    else:
        parts = re.split(r"[+/｜|,，;；\s]+", text, maxsplit=1)
        if parts:
            subject = parts[0].strip() if parts[0].strip() else ""
            topic = parts[1].strip() if len(parts) > 1 else ""
    return subject, topic


def parse_grade_and_level(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    level = ""
    for key in ["偏弱", "中等", "较强", "混合", "弱", "强", "一般"]:
        if key in text:
            level = normalize_class_level(key) or ""
            text = text.replace(key, "").strip()
            break
    grade = text.replace("&", " ").replace("：", " ").strip()
    return grade, level


def extract_requirements_from_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    normalized = normalize_numbered_block(text)
    items = {}
    for idx in range(1, 9):
        items[idx] = extract_numbered_item(normalized, idx)
    if not any(items.values()):
        return {}
    req: Dict[str, Any] = {}
    subject, topic = parse_subject_topic(items.get(1) or "")
    if subject:
        req["subject"] = subject
    if topic:
        req["topic"] = topic
    grade_level, class_level = parse_grade_and_level(items.get(2) or "")
    if grade_level:
        req["grade_level"] = grade_level
    if class_level:
        req["class_level"] = class_level
    if items.get(3):
        req["core_concepts"] = parse_list_value(items.get(3))
    if items.get(4):
        req["typical_problem"] = items.get(4)
    if items.get(5):
        req["misconceptions"] = parse_list_value(items.get(5))
    if items.get(6):
        req["duration_minutes"] = parse_duration(items.get(6))
    if items.get(7):
        req["preferences"] = parse_list_value(items.get(7))
    if items.get(8):
        req["extra_constraints"] = items.get(8)
    return req


def detect_assignment_intent(text: str) -> bool:
    if not text:
        return False
    keywords = [
        "生成作业",
        "布置作业",
        "作业生成",
        "@physics-homework-generator",
        "作业ID",
        "作业 ID",
    ]
    if any(key in text for key in keywords):
        return True
    if re.search(r"(创建|新建|新增|安排|布置|生成|发)\S{0,6}作业", text):
        return True
    if "作业" in text and ("新" in text or "创建" in text or "安排" in text or "布置" in text or "生成" in text):
        return True
    if "作业" in text and re.search(r"\d{4}-\d{2}-\d{2}", text):
        return True
    return False


def extract_assignment_id(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(
        r"(?:作业ID|作业Id|作业id|ID|Id|id)\s*[:：]?\s*([\w\u4e00-\u9fff-]+_\d{4}-\d{2}-\d{2})",
        text,
    )
    if match:
        return match.group(1)
    match = re.search(r"[\w\u4e00-\u9fff-]+_\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    return None


def extract_date(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    return None


def extract_kp_list(text: str) -> List[str]:
    if not text:
        return []
    match = re.search(r"知识点[:：\s]*([^\n。；;]+)", text)
    if not match:
        return []
    return parse_list_value(match.group(1))


def extract_question_ids(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"\bQ\d+\b", text)))


def extract_per_kp(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"(?:每个|每)\s*(\d+)\s*题", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None

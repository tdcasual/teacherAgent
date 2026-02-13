#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root and skill script path available
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SKILL_OCR = Path('skills/physics-lesson-capture/scripts/ocr_utils.py')
if SKILL_OCR.exists():
    sys.path.insert(0, str(SKILL_OCR.parent))

try:
    from ocr_utils import load_env_from_dotenv, ocr_with_sdk
except Exception:
    def load_env_from_dotenv(*args, **kwargs):
        pass
    def ocr_with_sdk(*args, **kwargs):
        raise RuntimeError("ocr_utils not available")

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

try:
    from llm_gateway import LLMGateway, UnifiedLLMRequest
except Exception:
    LLMGateway = None
    UnifiedLLMRequest = None


SAFE_ID_RE = re.compile(r"^[\w-]+$")


def require_safe_id(value: str, field: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise SystemExit(f"{field} is required")
    if not SAFE_ID_RE.fullmatch(token):
        raise SystemExit(f"Invalid {field}: only letters, digits, '_' and '-' are allowed")
    return token


def resolve_under(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve()
    target = root_resolved.joinpath(*parts).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise SystemExit(f"Invalid path outside allowed root: {target}")
    return target


def read_assignment_questions(path: Path):
    # assignment file format: csv with columns question_id, kp_id, stem_ref, answer_ref, answer_text(optional)
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def normalize_symbols(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "×": "x",
        "＊": "x",
        "*": "x",
        "＝": "=",
        "－": "-",
        "—": "-",
        "–": "-",
        "＋": "+",
        "·": ".",
        "．": ".",
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
    }
    out = text
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def normalize_match_text(text: str) -> str:
    return normalize_symbols(text).lower().replace(" ", "")


def ocr_files(files: List[Path], out_dir: Path, language: str, mode: str):
    ensure_dir(out_dir)
    all_texts = []
    for idx, file in enumerate(files, start=1):
        try:
            text = ocr_with_sdk(file, language=language, mode=mode)
        except Exception as exc:
            raise SystemExit(f"OCR failed for {file}: {exc}")
        cleaned = normalize_symbols(clean_text(text))
        (out_dir / f"page_{idx}.json").write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / f"page_{idx}.txt").write_text(cleaned, encoding="utf-8")
        all_texts.append(cleaned)
    return "\n".join(all_texts)


def simple_match(answer_text: str, ocr_text: str) -> bool:
    if not answer_text:
        return False
    return normalize_match_text(answer_text) in normalize_match_text(ocr_text)


def normalize_choice(value: str) -> str:
    if not value:
        return ""
    letters = re.findall(r"[A-D]", value.upper())
    if not letters:
        return ""
    # keep order for single, sort for multi
    if len(letters) == 1:
        return letters[0]
    return "".join(sorted(set(letters)))


def extract_choice(text: str) -> str:
    if not text:
        return ""
    text = normalize_symbols(text).upper()
    m = re.search(r"(?:答案|答|选)(?:案)?[:：]?\s*([A-D]{1,4})", text)
    if m:
        return normalize_choice(m.group(1))
    candidates = re.findall(r"\b[A-D]{1,4}\b", text)
    if candidates:
        # choose the longest candidate
        candidates.sort(key=len, reverse=True)
        return normalize_choice(candidates[0])
    return ""


def parse_numeric_candidates(text: str) -> List[float]:
    if not text:
        return []
    normalized = normalize_symbols(text)
    matches = re.findall(r"-?\d+(?:\.\d+)?", normalized)
    values = []
    for m in matches:
        try:
            values.append(float(m))
        except Exception:
            continue
    return values


def detect_answer_type(expected: str) -> str:
    if not expected:
        return "unknown"
    normalized = normalize_symbols(expected).strip()
    choice = normalize_choice(normalized)
    if choice:
        return "mcq_multi" if len(choice) > 1 else "mcq_single"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
        return "numeric"
    return "text"


def score_objective_answer(expected: str, block_text: str) -> tuple[bool, str, str]:
    if not expected:
        return False, "", "missing_expected"
    expected_norm = normalize_symbols(expected).strip()
    ans_type = detect_answer_type(expected_norm)

    if ans_type in {"mcq_single", "mcq_multi"}:
        expected_choice = normalize_choice(expected_norm)
        student_choice = extract_choice(block_text)
        if not student_choice:
            return False, "", "choice_not_found"
        if ans_type == "mcq_single":
            return student_choice == expected_choice, student_choice, "mcq_single"
        # multi-choice
        exp_set = set(expected_choice)
        stu_set = set(student_choice)
        if stu_set == exp_set:
            return True, student_choice, "mcq_multi_full"
        if stu_set.issubset(exp_set):
            return False, student_choice, "mcq_multi_partial"
        return False, student_choice, "mcq_multi_wrong"

    if ans_type == "numeric":
        try:
            expected_val = float(expected_norm)
        except Exception:
            return simple_match(expected_norm, block_text), "", "numeric_fallback"
        candidates = parse_numeric_candidates(block_text)
        if not candidates:
            return False, "", "numeric_not_found"
        for val in candidates:
            rel_err = abs(val - expected_val) / max(abs(expected_val), 1e-6)
            abs_err = abs(val - expected_val)
            if rel_err <= 0.01 or abs_err <= 0.01:
                return True, str(val), "numeric_match"
        return False, str(candidates[0]), "numeric_mismatch"

    # text fallback
    matched = simple_match(expected_norm, block_text)
    return matched, "", "text_match" if matched else "text_mismatch"


def split_by_numbered_questions(text: str) -> List[tuple[int, str]]:
    if not text:
        return []
    lines = text.splitlines()
    blocks: List[tuple[int, List[str]]] = []
    current_num: Optional[int] = None
    current_lines: List[str] = []
    for line in lines:
        m = re.match(r"^\\s*(\\d{1,3})[\\.、\\)）]\\s*", line)
        if m:
            if current_lines and current_num is not None:
                blocks.append((current_num, current_lines))
            current_num = int(m.group(1))
            current_lines = [line]
        else:
            if current_num is not None:
                current_lines.append(line)
    if current_lines and current_num is not None:
        blocks.append((current_num, current_lines))
    return [(num, "\\n".join(lines).strip()) for num, lines in blocks]


def split_ocr_by_questions(ocr_text: str, questions: List[dict]) -> Dict[str, str]:
    blocks = split_by_numbered_questions(ocr_text)
    if not blocks:
        return {}
    by_num = {num: text for num, text in blocks}
    mapping: Dict[str, str] = {}
    # prefer numeric alignment (1-based index)
    aligned = 0
    for idx, _ in enumerate(questions, start=1):
        if idx in by_num:
            aligned += 1
    if aligned >= max(1, len(questions) // 2):
        for idx, q in enumerate(questions, start=1):
            if idx in by_num:
                mapping[q.get("question_id") or f"Q{idx}"] = by_num[idx]
    else:
        # fallback by order
        for q, (_, text) in zip(questions, blocks):
            mapping[q.get("question_id") or ""] = text
    return mapping


def extract_answer_from_ref(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "答案" in line or line.lower().startswith("answer"):
            if "：" in line:
                return line.split("：", 1)[1].strip()
            if ":" in line:
                return line.split(":", 1)[1].strip()
            return line
    return text.splitlines()[0].strip() if text.strip() else ""


def get_expected_answer(row: dict) -> str:
    expected = (row.get("answer_text") or "").strip()
    if expected:
        return expected
    ref = row.get("answer_ref") or ""
    if ref:
        return extract_answer_from_ref(Path(ref))
    return ""


def load_rubric(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path or not path.exists():
        return None
    ext = path.suffix.lower()
    try:
        if ext in {".json"}:
            return json.loads(path.read_text(encoding="utf-8"))
        if ext in {".yml", ".yaml"} and yaml is not None:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def score_rubric(text: str, rubric: Dict[str, Any]) -> Dict[str, Any]:
    steps = rubric.get("steps") or []
    matched_steps: List[str] = []
    missing_steps: List[str] = []
    total_score = 0.0
    gained = 0.0
    text_norm = normalize_match_text(text)
    for idx, step in enumerate(steps, start=1):
        score = float(step.get("score") or 1.0)
        total_score += score
        step_id = step.get("id") or f"step_{idx}"
        matched = False
        keywords = step.get("keywords") or []
        regexes = step.get("regex") or []
        for kw in keywords:
            if normalize_match_text(str(kw)) in text_norm:
                matched = True
                break
        if not matched:
            for pattern in regexes:
                try:
                    if re.search(pattern, text, re.I):
                        matched = True
                        break
                except Exception:
                    continue
        if matched:
            matched_steps.append(step_id)
            gained += score
        else:
            missing_steps.append(step_id)
    confidence = gained / total_score if total_score > 0 else 0.0
    return {
        "score": gained,
        "total_score": total_score,
        "matched_steps": matched_steps,
        "missing_steps": missing_steps,
        "confidence": round(confidence, 3),
    }


def subjective_pass(score: float, total_score: float, confidence: float) -> bool:
    if total_score <= 0:
        return False
    if confidence >= 0.6:
        return True
    return (score / total_score) >= 0.6


def parse_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n|```$", "", content, flags=re.S).strip()
    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else None
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except Exception:
                return None
    return None


def llm_grade_subjective(question_id: str, expected: str, rubric: Dict[str, Any], text: str) -> Optional[Dict[str, Any]]:
    if LLMGateway is None or UnifiedLLMRequest is None:
        return None
    gateway = LLMGateway()
    prompt = {
        "question_id": question_id,
        "expected": expected,
        "rubric": rubric,
        "ocr_text": text,
    }
    system = "你是评分助手，只输出JSON。"
    user = (
        "请根据rubric对学生作答评分，只输出JSON对象，字段："
        "score(number), total_score(number), matched_steps(array), missing_steps(array), "
        "confidence(0-1), reason(string), evidence(string)."
        f"输入：{json.dumps(prompt, ensure_ascii=False)}"
    )
    req = UnifiedLLMRequest(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    try:
        resp = gateway.generate(req, allow_fallback=True)
    except Exception:
        return None
    return parse_json_from_text(resp.text)


def load_profile(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_profile(path: Path, profile: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_assignment_id(text: str) -> Optional[str]:
    patterns = [
        r"Assignment\\s*ID\\s*[:：]\\s*([A-Za-z0-9_-]+)",
        r"Assignment\\s*[:：]\\s*([A-Za-z0-9_-]+)",
        r"作业\\s*[:：]\\s*([A-Za-z0-9_-]+)",
        r"练习\\s*[:：]\\s*([A-Za-z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None


def find_assignment_id_by_scan(text: str) -> Optional[str]:
    assignments_dir = (ROOT / "data" / "assignments").resolve()
    if not assignments_dir.exists():
        return None
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        md = folder / "assignment.md"
        if not md.exists():
            continue
        content = md.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"Assignment\\s*ID\\s*[:：]\\s*([A-Za-z0-9_-]+)", content)
        if m:
            assignment_id = m.group(1).strip()
            if assignment_id and assignment_id in text:
                return assignment_id
    return None


def main():
    parser = argparse.ArgumentParser(description="Grade student submission from photos using OCR")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--assignment-id", help="assignment id (optional if auto-detect)")
    parser.add_argument("--auto-assignment", action="store_true", help="auto-detect assignment id from OCR text")
    parser.add_argument("--files", nargs="+", required=True, help="image files")
    parser.add_argument("--assignment-questions", help="csv of assigned questions (optional if assignment id is detected)")
    parser.add_argument("--out-dir", default="data/student_submissions")
    parser.add_argument("--ocr-mode", default="FREE_OCR")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--llm-grade", action="store_true", help="use LLM to assist subjective grading")
    parser.add_argument("--llm-confidence-threshold", type=float, default=0.6, help="LLM trigger threshold")
    parser.add_argument("--review-threshold", type=float, default=0.6, help="low confidence review threshold")
    args = parser.parse_args()

    load_env_from_dotenv(Path('.env'))

    safe_student_id = require_safe_id(args.student_id, "student_id")
    out_root = Path(args.out_dir).resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = resolve_under(out_root, safe_student_id, f"submission_{timestamp}")
    ensure_dir(base_dir)

    files = [Path(f) for f in args.files]
    for f in files:
        if not f.exists():
            raise SystemExit(f"File not found: {f}")

    ocr_dir = base_dir / "ocr"
    ocr_text = ocr_files(files, ocr_dir, args.language, args.ocr_mode)

    # detect assignment id from OCR if requested
    assignment_id = args.assignment_id
    if args.auto_assignment or not assignment_id:
        assignment_id = detect_assignment_id(ocr_text)
        if not assignment_id:
            assignment_id = find_assignment_id_by_scan(ocr_text)
    if not assignment_id:
        raise SystemExit("Could not detect assignment_id. Provide --assignment-id.")
    assignment_id = require_safe_id(assignment_id, "assignment_id")

    # resolve assignment questions path
    if args.assignment_questions:
        questions_path = Path(args.assignment_questions).resolve()
    else:
        assignments_root = (ROOT / "data" / "assignments").resolve()
        questions_path = resolve_under(assignments_root, assignment_id, "questions.csv")
    if not questions_path.exists():
        raise SystemExit(f"Assignment questions not found: {questions_path}")
    questions = read_assignment_questions(questions_path)

    # move submission into assignment bucket as well
    assignment_bucket = resolve_under(out_root, assignment_id, safe_student_id, f"submission_{timestamp}")
    assignment_bucket.mkdir(parents=True, exist_ok=True)

    # copy OCR artifacts to assignment bucket
    assignment_ocr = assignment_bucket / "ocr"
    assignment_ocr.mkdir(parents=True, exist_ok=True)
    for f in ocr_dir.glob("*"):
        if f.is_file():
            assignment_ocr.joinpath(f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    # question-level splitting
    question_blocks = split_ocr_by_questions(ocr_text, questions)
    question_block_path = base_dir / "ocr" / "question_blocks.json"
    if question_blocks:
        question_block_path.write_text(
            json.dumps(
                [{"question_id": qid, "text": txt[:4000]} for qid, txt in question_blocks.items()],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # objective/subjective evaluation with per-question OCR
    results = []
    grading_items: List[Dict[str, Any]] = []
    review_items: List[Dict[str, Any]] = []
    correct_count = 0
    ungraded_count = 0
    kp_stats = {}
    for q in questions:
        qid = q.get("question_id")
        kp_id = q.get("kp_id") or "uncategorized"
        expected = get_expected_answer(q)
        rubric_ref = q.get("rubric_ref") or q.get("rubric") or ""
        rubric_path = Path(rubric_ref) if rubric_ref else None
        rubric = load_rubric(rubric_path) if rubric_path else None
        block_text = question_blocks.get(qid) if qid else None
        if not block_text:
            block_text = ocr_text

        matched = False
        student_answer = ""
        reason = "missing_expected"
        status = "ungraded"
        confidence = 0.0
        earned_score = 0.0
        matched_steps: List[str] = []
        missing_steps: List[str] = []

        if expected:
            matched, student_answer, reason = score_objective_answer(expected, block_text)
            status = "matched" if matched else "missed"
            confidence = 1.0 if matched or reason.startswith("numeric_") or reason.startswith("mcq_") else 0.5
            earned_score = 1.0 if matched else 0.0
        elif rubric:
            rubric_result = score_rubric(block_text, rubric)
            earned_score = float(rubric_result.get("score", 0.0))
            total_score = float(rubric_result.get("total_score", 0.0))
            confidence = float(rubric_result.get("confidence", 0.0))
            matched_steps = list(rubric_result.get("matched_steps", []))
            missing_steps = list(rubric_result.get("missing_steps", []))
            matched = subjective_pass(earned_score, total_score, confidence)
            status = "matched" if matched else "missed"
            reason = "rubric"
            llm_enabled = args.llm_grade or os.getenv("LLM_GRADE", "").lower() in {"1", "true", "yes"}
            if llm_enabled and confidence < args.llm_confidence_threshold:
                llm_result = llm_grade_subjective(qid or "", expected, rubric, block_text)
                if llm_result:
                    earned_score = float(llm_result.get("score") or earned_score)
                    total_score = float(llm_result.get("total_score") or total_score)
                    confidence = float(llm_result.get("confidence") or confidence)
                    matched_steps = list(llm_result.get("matched_steps", matched_steps))
                    missing_steps = list(llm_result.get("missing_steps", missing_steps))
                    matched = subjective_pass(earned_score, total_score, confidence)
                    status = "matched" if matched else "missed"
                    reason = "llm_rubric"
        else:
            pass

        results.append({
            "question_id": qid,
            "kp_id": kp_id,
            "expected": expected,
            "student_answer": student_answer if expected else "",
            "matched": matched,
            "status": status,
            "reason": reason,
            "score": earned_score,
            "confidence": round(confidence, 3),
            "matched_steps": matched_steps,
            "missing_steps": missing_steps,
        })
        grading_items.append({
            "question_id": qid,
            "kp_id": kp_id,
            "status": status,
            "reason": reason,
            "score": earned_score,
            "confidence": round(confidence, 3),
            "matched_steps": matched_steps,
            "missing_steps": missing_steps,
        })
        if confidence < args.review_threshold or status == "ungraded":
            review_items.append({
                "question_id": qid,
                "kp_id": kp_id,
                "status": status,
                "confidence": round(confidence, 3),
                "reason": reason,
                "matched_steps": matched_steps,
                "missing_steps": missing_steps,
            })

        count_for_stats = status != "ungraded" and confidence >= args.review_threshold
        if not count_for_stats:
            ungraded_count += 1
        if matched and count_for_stats:
            correct_count += 1

        stat = kp_stats.setdefault(kp_id, {"correct": 0, "total": 0, "ungraded": 0})
        if not count_for_stats:
            stat["ungraded"] += 1
        else:
            stat["total"] += 1
            if matched:
                stat["correct"] += 1

    feedback_lines = []
    feedback_lines.append(f"Student: {safe_student_id}")
    feedback_lines.append(f"Assignment: {assignment_id}")
    graded_total = len(questions) - ungraded_count
    feedback_lines.append(f"Total matched: {correct_count}/{len(questions)} (graded: {graded_total})")
    feedback_lines.append("")
    feedback_lines.append("Item Feedback:")
    for r in results:
        if r["status"] == "ungraded":
            status = "△"
        else:
            status = "✔" if r["matched"] else "✘"
        reason = r.get("reason")
        confidence = r.get("confidence")
        score_val = r.get("score")
        parts = []
        if reason and reason not in {"text_match"}:
            parts.append(str(reason))
        if score_val not in (None, 0, 0.0):
            parts.append(f"score={score_val}")
        if confidence is not None:
            parts.append(f"conf={confidence}")
        suffix = f" ({', '.join(parts)})" if parts else ""
        feedback_lines.append(f"- {r['question_id']} ({r['kp_id']}): {status}{suffix}")

    feedback_path = base_dir / "feedback.md"
    feedback_path.write_text("\n".join(feedback_lines), encoding="utf-8")

    # also copy feedback into assignment bucket
    assignment_feedback = assignment_bucket / "feedback.md"
    assignment_feedback.write_text("\n".join(feedback_lines), encoding="utf-8")

    # grading report + review queue
    report = {
        "student_id": safe_student_id,
        "assignment_id": assignment_id,
        "graded_total": graded_total,
        "ungraded": ungraded_count,
        "correct": correct_count,
        "items": grading_items,
    }
    (base_dir / "grading_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (assignment_bucket / "grading_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if review_items:
        review_payload = {
            "student_id": safe_student_id,
            "assignment_id": assignment_id,
            "items": review_items,
        }
        (base_dir / "review_queue.json").write_text(
            json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (assignment_bucket / "review_queue.json").write_text(
            json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # profile update suggestion
    weak_kp = []
    strong_kp = []
    medium_kp = []
    for kp, stat in kp_stats.items():
        if stat["total"] < 2:
            continue
        acc = stat["correct"] / stat["total"] if stat["total"] else 0
        if acc < 0.5:
            weak_kp.append(kp)
        elif acc >= 0.8:
            strong_kp.append(kp)
        else:
            medium_kp.append(kp)

    profile_lines = []
    profile_lines.append(f"Student: {safe_student_id}")
    profile_lines.append(f"Assignment: {assignment_id}")
    profile_lines.append(f"Graded: {graded_total} | Ungraded: {ungraded_count}")
    profile_lines.append("")
    profile_lines.append("Profile Update Suggestion (derived):")
    profile_lines.append(f"- recent_weak_kp: {', '.join(weak_kp) if weak_kp else '(none)'}")
    profile_lines.append(f"- strengths: {', '.join(strong_kp) if strong_kp else '(none)'}")
    profile_lines.append(f"- medium_kp: {', '.join(medium_kp) if medium_kp else '(none)'}")
    next_focus = weak_kp[0] if weak_kp else (medium_kp[0] if medium_kp else '(none)')
    profile_lines.append(f"- next_focus: {next_focus}")
    profile_lines.append(f"- practice_history: {assignment_id} completed, matched {correct_count}/{graded_total}")
    if graded_total < 3:
        profile_lines.append("- note: Low confidence (few graded items).")
    if ungraded_count > 0:
        profile_lines.append("- note: Some items excluded (missing answers or low confidence).")
    if review_items:
        profile_lines.append("- note: Review required for low-confidence items.")

    profile_path = base_dir / "profile_update_suggestion.md"
    profile_path.write_text("\n".join(profile_lines), encoding="utf-8")
    assignment_profile = assignment_bucket / "profile_update_suggestion.md"
    assignment_profile.write_text("\n".join(profile_lines), encoding="utf-8")

    review_gate = os.getenv("PROFILE_UPDATE_REQUIRE_REVIEW", "").lower() in {"1", "true", "yes"}
    if review_gate and review_items:
        print("[WARN] Low confidence items require review; skipping auto profile update.")
        print(f"[OK] Saved OCR to {ocr_dir}")
        print(f"[OK] Saved feedback to {feedback_path}")
        print(f"[OK] Saved profile suggestion to {profile_path}")
        return

    # auto write student profile (derived fields only)
    profiles_root = (ROOT / "data" / "student_profiles").resolve()
    profile_store = resolve_under(profiles_root, f"{safe_student_id}.json")
    profile = load_profile(profile_store)
    profile["student_id"] = safe_student_id
    profile["last_updated"] = datetime.now().isoformat(timespec="seconds")
    profile["recent_weak_kp"] = weak_kp
    profile["recent_strong_kp"] = strong_kp
    profile["recent_medium_kp"] = medium_kp
    profile["next_focus"] = next_focus

    mastery_by_kp = profile.get("mastery_by_kp", {})
    for kp, stat in kp_stats.items():
        if stat["total"] <= 0:
            continue
        acc = stat["correct"] / stat["total"] if stat["total"] else 0
        mastery_by_kp[kp] = {
            "accuracy": round(acc, 3),
            "evidence": assignment_id,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    profile["mastery_by_kp"] = mastery_by_kp

    practice_history = profile.get("practice_history", [])
    practice_history.append({
        "assignment_id": assignment_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "matched": correct_count,
        "graded": graded_total,
        "ungraded": ungraded_count,
    })
    # keep last 20
    profile["practice_history"] = practice_history[-20:]
    profile["summary"] = f"{assignment_id}: matched {correct_count}/{graded_total}, next focus {next_focus}"

    save_profile(profile_store, profile)

    print(f"[OK] Saved OCR to {ocr_dir}")
    print(f"[OK] Saved feedback to {feedback_path}")
    print(f"[OK] Saved profile suggestion to {profile_path}")


if __name__ == "__main__":
    main()

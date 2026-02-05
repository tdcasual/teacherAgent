#!/usr/bin/env python3
import argparse
import csv
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure mem0_config path for env
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mem0_config import load_dotenv
from llm_gateway import LLMGateway, UnifiedLLMRequest

load_dotenv()
LLM_GATEWAY = LLMGateway()


def read_question_bank(path: Path) -> List[dict]:
    if not path.exists():
        raise SystemExit(f"Question bank not found: {path}")
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_explicit_questions(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_assignment(path: Path, rows: List[dict]):
    if not rows:
        raise SystemExit("No questions selected.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def parse_kp_list(kp_str: str) -> List[str]:
    parts = [p.strip() for p in kp_str.replace("，", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]


def compute_mix(total: int) -> Tuple[int, int, int]:
    # 60% basic, 30% medium, 10% advanced
    basic = math.ceil(total * 0.6)
    medium = math.ceil(total * 0.3)
    advanced = max(total - basic - medium, 0)
    return basic, medium, advanced


def select_by_difficulty(rows: List[dict], difficulty: str, count: int, excluded_ids: set) -> List[dict]:
    items = [r for r in rows if (r.get("difficulty") or "").lower() == difficulty and r.get("question_id") not in excluded_ids]
    items.sort(key=lambda x: x.get("question_id", ""))
    return items[:count]


def fill_any(rows: List[dict], count: int, excluded_ids: set) -> List[dict]:
    items = [r for r in rows if r.get("question_id") not in excluded_ids]
    items.sort(key=lambda x: x.get("question_id", ""))
    return items[:count]


def make_generated(lesson_dir: Path, kp_id: str, difficulty: str, idx: int) -> dict:
    gen_id = f"GEN-{kp_id}-{difficulty}-{idx:02d}"
    stem_dir = lesson_dir / "generated_stems"
    sol_dir = lesson_dir / "generated_solutions"
    stem_dir.mkdir(parents=True, exist_ok=True)
    sol_dir.mkdir(parents=True, exist_ok=True)
    stem_ref = stem_dir / f"{gen_id}.md"
    answer_ref = sol_dir / f"{gen_id}.md"
    stem_ref.write_text(f"【待生成】{kp_id}（{difficulty}）习题\n请在此补充题干。", encoding="utf-8")
    answer_ref.write_text("【待生成】参考答案", encoding="utf-8")
    return {
        "question_id": gen_id,
        "kp_id": kp_id,
        "difficulty": difficulty,
        "type": "generated",
        "stem_ref": str(stem_ref),
        "answer_ref": str(answer_ref),
        "source": "generated",
        "tags": "",
    }


def make_explicit_placeholder(out_dir: Path, question_id: str) -> dict:
    stem_dir = out_dir / "explicit_stems"
    sol_dir = out_dir / "explicit_solutions"
    stem_dir.mkdir(parents=True, exist_ok=True)
    sol_dir.mkdir(parents=True, exist_ok=True)
    stem_ref = stem_dir / f"{question_id}.md"
    answer_ref = sol_dir / f"{question_id}.md"
    if not stem_ref.exists():
        stem_ref.write_text(f"【待录入】题目 {question_id}\n请补充题干。", encoding="utf-8")
    if not answer_ref.exists():
        answer_ref.write_text("【待录入】参考答案", encoding="utf-8")
    return {
        "question_id": question_id,
        "kp_id": "uncategorized",
        "difficulty": "basic",
        "type": "explicit_placeholder",
        "stem_ref": str(stem_ref),
        "answer_ref": str(answer_ref),
        "source": "explicit",
        "tags": "explicit:missing",
    }


def select_explicit_questions(rows: List[dict], question_ids: List[str], out_dir: Path) -> List[dict]:
    by_id = {r.get("question_id"): r for r in rows}
    selected = []
    seen = set()
    for qid in question_ids:
        if not qid or qid in seen:
            continue
        seen.add(qid)
        row = by_id.get(qid)
        if row:
            selected.append(row)
        else:
            selected.append(make_explicit_placeholder(out_dir, qid))
    return selected


def safe_date(date_str: str) -> str:
    if not date_str:
        return datetime.now().date().isoformat()
    try:
        return datetime.fromisoformat(date_str).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


def normalize_mode(mode: str, has_kp: bool, has_explicit: bool) -> str:
    if mode in {"kp", "explicit", "hybrid", "auto"}:
        return mode
    if has_kp and has_explicit:
        return "hybrid"
    if has_explicit:
        return "explicit"
    return "kp"


def parse_ids(value: str) -> List[str]:
    return parse_kp_list(value)


def load_recent_assignments(assignments_dir: Path, days: int) -> set:
    if not assignments_dir.exists():
        return set()
    cutoff = datetime.now() - timedelta(days=days)
    used = set()
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        # infer date from folder name suffix if exists
        csv_path = folder / "questions.csv"
        if not csv_path.exists():
            continue
        # file mtime as fallback
        mtime = datetime.fromtimestamp(csv_path.stat().st_mtime)
        if mtime < cutoff:
            continue
        with csv_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                qid = row.get("question_id")
                if qid:
                    used.add(qid)
    return used


def generate_with_llm(kp_id: str, difficulty: str, count: int) -> List[dict]:
    import json

    prompt = (
        f"请生成{count}道高中物理题，知识点{kp_id}，难度{difficulty}。\n"
        "每道题输出：题干、选项(若是选择题)、答案、解析。使用简洁中文。"
        "用JSON数组输出，每个元素包含 stem, options(可选), answer, solution, type。"
    )
    req = UnifiedLLMRequest(
        messages=[
            {"role": "system", "content": "你是高中物理出题助手"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    result = LLM_GATEWAY.generate(req, allow_fallback=True)
    content = result.text
    # try to extract json
    try:
        data = json.loads(content)
    except Exception:
        # attempt to extract JSON block
        import re
        match = re.search(r"\[.*\]", content, re.S)
        if match:
            data = json.loads(match.group(0))
        else:
            raise ValueError("LLM output not JSON")
    return data


def main():
    parser = argparse.ArgumentParser(description="Select practice questions from bank, fallback to generated")
    parser.add_argument("--assignment-id", required=True)
    parser.add_argument("--kp", default="", help="comma/semicolon-separated kp list")
    parser.add_argument("--question-ids", default="", help="comma/semicolon-separated question ids")
    parser.add_argument("--per-kp", type=int, default=5)
    parser.add_argument("--question-bank", default="data/question_bank/questions.csv")
    parser.add_argument("--explicit-file", default="", help="csv of explicit questions (optional)")
    parser.add_argument("--out", help="output assignment csv")
    parser.add_argument("--avoid-days", type=int, default=14, help="avoid repeating questions used in last N days")
    parser.add_argument("--generate", action="store_true", help="use LLM to generate missing items")
    parser.add_argument("--core-examples", help="comma/semicolon-separated core example IDs for templates")
    parser.add_argument("--mode", default="", help="kp | explicit | hybrid | auto")
    parser.add_argument("--date", default="", help="assignment date (YYYY-MM-DD)")
    parser.add_argument("--class-name", default="", help="target class name")
    parser.add_argument("--student-ids", default="", help="comma/semicolon-separated student ids")
    parser.add_argument("--source", default="teacher", help="teacher | auto")
    args = parser.parse_args()

    kp_list = parse_kp_list(args.kp)
    explicit_ids = parse_ids(args.question_ids)
    bank = read_question_bank(Path(args.question_bank))

    out_dir = Path("data/assignments") / args.assignment_id
    out_dir.mkdir(parents=True, exist_ok=True)

    explicit_file = Path(args.explicit_file) if args.explicit_file else out_dir / "explicit_questions.csv"
    explicit_rows = read_explicit_questions(explicit_file) if explicit_file.exists() else []

    has_kp = bool(kp_list)
    has_explicit = bool(explicit_ids) or bool(explicit_rows)
    mode = normalize_mode(args.mode, has_kp, has_explicit)
    if not has_kp and not has_explicit:
        raise SystemExit("Provide --kp or --question-ids or explicit questions file.")
    if mode == "kp" and not has_kp:
        raise SystemExit("Mode kp requires --kp.")

    recent_used = load_recent_assignments(Path("data/assignments"), args.avoid_days)

    selected = []

    if explicit_rows and mode in {"explicit", "hybrid", "auto"}:
        selected.extend(explicit_rows)
    if explicit_ids and mode in {"explicit", "hybrid", "auto"}:
        selected.extend(select_explicit_questions(bank, explicit_ids, out_dir))

    # core example variants (optional)
    if args.core_examples:
        core_ids = parse_kp_list(args.core_examples)
        from subprocess import run
        for ce_id in core_ids:
            # generate variants and include as practice items
            gen_script = Path("skills/physics-core-examples/scripts/generate_variants.py")
            run([sys.executable, str(gen_script), "--example-id", ce_id, "--count", str(args.per_kp)], check=True)
            idx_path = Path("data/assignments/generated_from_core") / ce_id / "index.json"
            if idx_path.exists():
                import json
                data = json.loads(idx_path.read_text(encoding="utf-8"))
                for item in data:
                    selected.append({
                        "question_id": item.get("id"),
                        "kp_id": ce_id,
                        "difficulty": "basic",
                        "type": "core_variant",
                        "stem_ref": item.get("stem_ref"),
                        "answer_ref": "",
                        "source": "core_example",
                        "tags": f"core:{ce_id}",
                    })
    existing_ids = {row.get("question_id") for row in selected if row.get("question_id")}

    if mode in {"kp", "hybrid", "auto"}:
        for kp in kp_list:
            kp_rows = [r for r in bank if r.get("kp_id") == kp and r.get("question_id") not in recent_used]
            total = args.per_kp
            basic_n, med_n, adv_n = compute_mix(total)

            chosen = []
            chosen.extend(select_by_difficulty(kp_rows, "basic", basic_n, recent_used | existing_ids))
            chosen.extend(select_by_difficulty(kp_rows, "medium", med_n, recent_used | existing_ids))
            chosen.extend(select_by_difficulty(kp_rows, "advanced", adv_n, recent_used | existing_ids))

            already_ids = {c.get("question_id") for c in chosen}
            if len(chosen) < total:
                remaining = total - len(chosen)
                chosen.extend(fill_any(kp_rows, remaining, already_ids | recent_used | existing_ids))

            # still not enough -> generate placeholders or LLM
            if len(chosen) < total:
                remaining = total - len(chosen)
                if args.generate:
                    # generate via LLM and write stem/solution
                    generated = generate_with_llm(kp, "basic", remaining)
                    for idx, item in enumerate(generated, start=1):
                        gen_id = f"GEN-{kp}-LLM-{idx:02d}"
                        stem_dir = out_dir / "generated_stems"
                        sol_dir = out_dir / "generated_solutions"
                        stem_dir.mkdir(parents=True, exist_ok=True)
                        sol_dir.mkdir(parents=True, exist_ok=True)
                        stem_ref = stem_dir / f"{gen_id}.md"
                        answer_ref = sol_dir / f"{gen_id}.md"
                        options = item.get("options")
                        stem_text = item.get("stem", "")
                        if options:
                            if isinstance(options, list):
                                opt_text = "\n".join(options)
                            else:
                                opt_text = str(options)
                            stem_text = stem_text + "\n" + opt_text
                        stem_ref.write_text(stem_text, encoding="utf-8")
                        answer_ref.write_text(
                            f"答案: {item.get('answer','')}\n解析: {item.get('solution','')}", encoding="utf-8"
                        )
                        chosen.append({
                            "question_id": gen_id,
                            "kp_id": kp,
                            "difficulty": item.get("difficulty", "basic"),
                            "type": item.get("type", "generated"),
                            "stem_ref": str(stem_ref),
                            "answer_ref": str(answer_ref),
                            "source": "generated",
                            "tags": "LLM",
                        })
                else:
                    for idx in range(1, remaining + 1):
                        chosen.append(make_generated(out_dir, kp, "basic", idx))

            selected.extend(chosen)
            existing_ids.update({row.get("question_id") for row in chosen if row.get("question_id")})

    out_path = Path(args.out) if args.out else out_dir / "questions.csv"
    write_assignment(out_path, selected)

    # also generate assignment markdown
    assignment_md = out_dir / "assignment.md"
    date_str = safe_date(args.date)
    student_ids = parse_ids(args.student_ids)
    lines = [
        f"Assignment ID: {args.assignment_id}",
        f"Date: {date_str}",
        f"Targets: {', '.join(kp_list)}",
        "Student: ____________________",
        "",
        "Items:",
    ]
    for row in selected:
        stem_ref = row.get("stem_ref")
        lines.append(f"- {row.get('question_id')} ({row.get('kp_id')}|{row.get('difficulty')}) -> {stem_ref}")
    assignment_md.write_text("\n".join(lines), encoding="utf-8")

    # write meta
    meta = {
        "assignment_id": args.assignment_id,
        "date": date_str,
        "mode": mode,
        "target_kp": kp_list,
        "question_ids": [row.get("question_id") for row in selected if row.get("question_id")],
        "class_name": args.class_name,
        "student_ids": student_ids,
        "source": args.source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (out_dir / "meta.json").write_text(
        __import__("json").dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[OK] Wrote assignment: {out_path}")
    print(f"[OK] Wrote assignment markdown: {assignment_md}")
    print(f"[OK] Wrote assignment meta: {out_dir / 'meta.json'}")


if __name__ == "__main__":
    main()

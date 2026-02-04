#!/usr/bin/env python3
import argparse
import csv
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure mem0_config path for env
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mem0_config import load_dotenv

load_dotenv()


def read_question_bank(path: Path) -> List[dict]:
    if not path.exists():
        raise SystemExit(f"Question bank not found: {path}")
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
    # Uses OpenAI-compatible API (SiliconFlow) for generation
    import json
    import requests

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("SILICONFLOW_LLM_MODEL", "deepseek-ai/DeepSeek-V3.2")

    url = base_url.rstrip("/") + "/chat/completions"
    prompt = (
        f"请生成{count}道高中物理题，知识点{kp_id}，难度{difficulty}。\n"
        "每道题输出：题干、选项(若是选择题)、答案、解析。使用简洁中文。"
        "用JSON数组输出，每个元素包含 stem, options(可选), answer, solution, type。"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是高中物理出题助手"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
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
    parser.add_argument("--kp", required=True, help="comma/semicolon-separated kp list")
    parser.add_argument("--per-kp", type=int, default=5)
    parser.add_argument("--question-bank", default="data/question_bank/questions.csv")
    parser.add_argument("--out", help="output assignment csv")
    parser.add_argument("--avoid-days", type=int, default=14, help="avoid repeating questions used in last N days")
    parser.add_argument("--generate", action="store_true", help="use LLM to generate missing items")
    parser.add_argument("--core-examples", help="comma/semicolon-separated core example IDs for templates")
    args = parser.parse_args()

    kp_list = parse_kp_list(args.kp)
    bank = read_question_bank(Path(args.question_bank))

    out_dir = Path("data/assignments") / args.assignment_id
    out_dir.mkdir(parents=True, exist_ok=True)

    recent_used = load_recent_assignments(Path("data/assignments"), args.avoid_days)

    selected = []
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
    for kp in kp_list:
        kp_rows = [r for r in bank if r.get("kp_id") == kp and r.get("question_id") not in recent_used]
        total = args.per_kp
        basic_n, med_n, adv_n = compute_mix(total)

        chosen = []
        chosen.extend(select_by_difficulty(kp_rows, "basic", basic_n, recent_used))
        chosen.extend(select_by_difficulty(kp_rows, "medium", med_n, recent_used))
        chosen.extend(select_by_difficulty(kp_rows, "advanced", adv_n, recent_used))

        already_ids = {c.get("question_id") for c in chosen}
        if len(chosen) < total:
            remaining = total - len(chosen)
            chosen.extend(fill_any(kp_rows, remaining, already_ids | recent_used))

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

    out_path = Path(args.out) if args.out else out_dir / "questions.csv"
    write_assignment(out_path, selected)

    # also generate assignment markdown
    assignment_md = out_dir / "assignment.md"
    lines = [
        f"Assignment ID: {args.assignment_id}",
        f"Targets: {', '.join(kp_list)}",
        "Student: ____________________",
        "",
        "Items:",
    ]
    for row in selected:
        stem_ref = row.get("stem_ref")
        lines.append(f"- {row.get('question_id')} ({row.get('kp_id')}|{row.get('difficulty')}) -> {stem_ref}")
    assignment_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Wrote assignment: {out_path}")
    print(f"[OK] Wrote assignment markdown: {assignment_md}")


if __name__ == "__main__":
    main()

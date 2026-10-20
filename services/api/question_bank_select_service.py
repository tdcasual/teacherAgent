from __future__ import annotations

import csv
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Set, Tuple

QUESTION_BANK_CSV_FIELDS = [
    "question_id",
    "kp_id",
    "difficulty",
    "type",
    "stem_ref",
    "answer_ref",
    "source",
    "tags",
]

FORBIDDEN_FIGURE_PATTERNS = [
    r"如图",
    r"见图",
    r"下图",
    r"如下图",
    r"图中",
    r"图示",
    r"如右图",
    r"如左图",
    r"上图",
    r"图\d+",
]


def contains_figure_reference(text: str) -> bool:
    if not text:
        return False
    payload = str(text)
    for pat in FORBIDDEN_FIGURE_PATTERNS:
        if re.search(pat, payload):
            return True
    return False


def read_question_bank(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_kp_list(kp_str: str) -> List[str]:
    parts = [p.strip() for p in str(kp_str or "").replace("，", ",").replace(";", ",").split(",")]
    return [p for p in parts if p]


def compute_mix(total: int) -> Tuple[int, int, int]:
    basic = math.ceil(total * 0.6)
    medium = math.ceil(total * 0.3)
    advanced = max(total - basic - medium, 0)
    return basic, medium, advanced


def select_by_difficulty(
    rows: List[dict], difficulty: str, count: int, excluded_ids: set
) -> List[dict]:
    items = [
        row
        for row in rows
        if (row.get("difficulty") or "").lower() == difficulty
        and row.get("question_id") not in excluded_ids
    ]
    items.sort(key=lambda item: item.get("question_id", ""))
    return items[:count]


def fill_any(rows: List[dict], count: int, excluded_ids: set) -> List[dict]:
    items = [row for row in rows if row.get("question_id") not in excluded_ids]
    items.sort(key=lambda item: item.get("question_id", ""))
    return items[:count]


def load_recent_assignments(assignments_dir: Path, days: int) -> set:
    if not assignments_dir.exists():
        return set()
    cutoff = datetime.now() - timedelta(days=days)
    used: set = set()
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        csv_path = folder / "questions.csv"
        if not csv_path.exists():
            continue
        mtime = datetime.fromtimestamp(csv_path.stat().st_mtime)
        if mtime < cutoff:
            continue
        with csv_path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                qid = row.get("question_id")
                if qid:
                    used.add(qid)
    return used


def question_bank_csv_path(data_dir: Path) -> Path:
    return (Path(data_dir) / "question_bank" / "questions.csv").resolve()


def ensure_questions_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUESTION_BANK_CSV_FIELDS)
        writer.writeheader()


def count_question_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(
            1
            for row in csv.DictReader(handle)
            if any(str(value or "").strip() for value in row.values())
        )


def write_questions_csv(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(QUESTION_BANK_CSV_FIELDS)
    if rows:
        extra = [key for key in rows[0].keys() if key not in fieldnames]
        fieldnames.extend(extra)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def resolve_bank_ref(ref: str, *, data_dir: Path, app_root: Path) -> Optional[Path]:
    raw = str(ref or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (Path(app_root) / path).resolve()
    else:
        path = path.resolve()
    jail = (Path(data_dir) / "question_bank").resolve()
    if path != jail and jail not in path.parents:
        return None
    return path


def resolve_assignment_folder_ref(
    ref: str, *, out_dir: Path, app_root: Path
) -> Optional[Path]:
    raw = str(ref or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (Path(app_root) / path).resolve()
    else:
        path = path.resolve()
    jail = Path(out_dir).resolve()
    if path != jail and jail not in path.parents:
        return None
    if not path.is_file():
        return None
    return path


def resolve_readable_stem_ref(
    ref: str,
    *,
    folder: Path,
    app_root: Path,
    data_dir: Path,
) -> Optional[Path]:
    raw = str(ref or "").strip()
    if not raw:
        return None
    folder_hit = resolve_assignment_folder_ref(raw, out_dir=folder, app_root=app_root)
    if folder_hit is not None:
        return folder_hit
    rel = Path(raw)
    if not rel.is_absolute():
        candidate = (Path(folder) / raw).resolve()
        jail = Path(folder).resolve()
        if (candidate == jail or jail in candidate.parents) and candidate.is_file():
            return candidate
    bank_hit = resolve_bank_ref(raw, data_dir=data_dir, app_root=app_root)
    if bank_hit is not None and bank_hit.is_file():
        return bank_hit
    return None


def stem_text_for_row(
    row: dict,
    *,
    data_dir: Path,
    app_root: Path,
    missing: str = "",
) -> str:
    ref_path = resolve_bank_ref(
        str(row.get("stem_ref") or ""), data_dir=data_dir, app_root=app_root
    )
    if ref_path is None or not ref_path.exists():
        return str(row.get("stem") or row.get("stem_text") or missing)
    try:
        return ref_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return missing


def _eligible_bank_rows(
    rows: Iterable[dict],
    *,
    data_dir: Path,
    app_root: Path,
    kp_list: Sequence[str],
    excluded_ids: Set[str],
) -> List[dict]:
    wanted = {str(item).strip() for item in kp_list if str(item).strip()}
    eligible: List[dict] = []
    for row in rows:
        qid = str(row.get("question_id") or "").strip()
        if not qid or qid in excluded_ids:
            continue
        kp_id = str(row.get("kp_id") or "").strip()
        if wanted and kp_id not in wanted:
            continue
        stem_ref = str(row.get("stem_ref") or "").strip()
        answer_ref = str(row.get("answer_ref") or "").strip()
        if stem_ref and resolve_bank_ref(stem_ref, data_dir=data_dir, app_root=app_root) is None:
            continue
        if answer_ref and resolve_bank_ref(answer_ref, data_dir=data_dir, app_root=app_root) is None:
            continue
        stem = stem_text_for_row(row, data_dir=data_dir, app_root=app_root)
        if contains_figure_reference(stem):
            continue
        eligible.append(row)
    return eligible


def pick_practice_items(
    *,
    data_dir: Path,
    app_root: Path,
    kp_list: list[str],
    excluded_ids: set[str],
    count: int = 3,
) -> dict[str, Any]:
    """Deterministic: KP match, unused ids, difficulty mix, no figure stems.
    Never calls LLM. Returns {ok, items, reason?}."""
    target = max(1, int(count or 1))
    bank_path = question_bank_csv_path(data_dir)
    if not bank_path.exists():
        return {"ok": False, "items": [], "reason": "question_bank_insufficient"}
    rows = read_question_bank(bank_path)
    eligible = _eligible_bank_rows(
        rows,
        data_dir=data_dir,
        app_root=app_root,
        kp_list=kp_list,
        excluded_ids=set(excluded_ids or set()),
    )
    if not eligible:
        return {"ok": False, "items": [], "reason": "question_bank_insufficient"}
    basic_n, med_n, adv_n = compute_mix(target)
    chosen: List[dict] = []
    used: set = set()
    chosen.extend(select_by_difficulty(eligible, "basic", basic_n, used))
    used.update(row.get("question_id") for row in chosen)
    chosen.extend(select_by_difficulty(eligible, "medium", med_n, used))
    used.update(row.get("question_id") for row in chosen)
    chosen.extend(select_by_difficulty(eligible, "advanced", adv_n, used))
    used.update(row.get("question_id") for row in chosen)
    if len(chosen) < target:
        chosen.extend(fill_any(eligible, target - len(chosen), used))
    if not chosen:
        return {"ok": False, "items": [], "reason": "question_bank_insufficient"}
    return {"ok": True, "items": chosen[:target]}

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _row_text(row: Dict[str, Any]) -> str:
    value = row.get("text")
    if value is None:
        value = row.get("last_user_text")
    return str(value or "").strip()


def _bucket_metrics(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(rows)
    total = len(items)
    if total <= 0:
        return {"total": 0, "top1_rate": 0.0, "default_rate": 0.0, "ambiguous_rate": 0.0}
    top1_hits = sum(1 for item in items if item.get("top1_hit"))
    default_count = sum(1 for item in items if "default" in str(item.get("reason") or ""))
    ambiguous_count = sum(1 for item in items if "ambiguous" in str(item.get("reason") or ""))
    return {
        "total": total,
        "top1_rate": float(top1_hits) / float(total),
        "default_rate": float(default_count) / float(total),
        "ambiguous_rate": float(ambiguous_count) / float(total),
    }


def _evaluate_row(
    row: Dict[str, Any],
    *,
    app_root: Path,
    resolve_effective_skill: Any,
    detect_assignment_intent: Any,
) -> Dict[str, Any]:
    role = str(row.get("role") or "teacher").strip() or "teacher"
    requested = str(row.get("requested_skill_id") or "").strip()
    text = _row_text(row)
    expected = str(row.get("expected_skill_id") or "").strip()
    bucket = str(row.get("bucket") or "unknown").strip() or "unknown"

    if not expected or not text:
        return {
            "ok": False,
            "skip": True,
            "error": "missing expected_skill_id or text",
            "bucket": bucket,
        }

    payload = resolve_effective_skill(
        app_root=app_root,
        role_hint=role,
        requested_skill_id=requested,
        last_user_text=text,
        detect_assignment_intent=detect_assignment_intent,
    )
    effective = str(payload.get("effective_skill_id") or "").strip()
    reason = str(payload.get("reason") or "").strip()

    return {
        "ok": True,
        "skip": False,
        "bucket": bucket,
        "expected_skill_id": expected,
        "effective_skill_id": effective,
        "reason": reason,
        "top1_hit": effective == expected,
    }


def _gate_failures(
    report: Dict[str, Any],
    *,
    gate_top1: Optional[float],
    gate_default: Optional[float],
    gate_ambiguous: Optional[float],
    per_skill_min_recall: Optional[float],
) -> List[str]:
    failed: List[str] = []
    top1_rate = float(report.get("top1_rate") or 0.0)
    default_rate = float(report.get("default_rate") or 0.0)
    ambiguous_rate = float(report.get("ambiguous_rate") or 0.0)
    if gate_top1 is not None and top1_rate < gate_top1:
        failed.append(f"top1_rate={top1_rate:.4f} < gate_top1={gate_top1:.4f}")
    if gate_default is not None and default_rate > gate_default:
        failed.append(f"default_rate={default_rate:.4f} > gate_default={gate_default:.4f}")
    if gate_ambiguous is not None and ambiguous_rate > gate_ambiguous:
        failed.append(f"ambiguous_rate={ambiguous_rate:.4f} > gate_ambiguous={gate_ambiguous:.4f}")

    if per_skill_min_recall is not None:
        per_skill = report.get("per_skill") if isinstance(report.get("per_skill"), dict) else {}
        for skill_id, stat in per_skill.items():
            total = int((stat or {}).get("total") or 0)
            if total <= 0:
                continue
            recall = float((stat or {}).get("recall") or 0.0)
            if recall < per_skill_min_recall:
                failed.append(
                    f"recall[{skill_id}]={recall:.4f} < per_skill_min_recall={per_skill_min_recall:.4f}"
                )
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress evaluate skill auto routing quality on a JSONL dataset.")
    parser.add_argument("--app-root", required=True, help="repo root containing skills/")
    parser.add_argument("--dataset", required=True, help="jsonl dataset path")
    parser.add_argument("--report", required=True, help="output report path (json)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--gate-top1", type=float, default=None)
    parser.add_argument("--gate-default", type=float, default=None)
    parser.add_argument("--gate-ambiguous", type=float, default=None)
    parser.add_argument("--per-skill-min-recall", type=float, default=None)
    parser.add_argument("--dump-confusion-matrix", action="store_true")
    args = parser.parse_args()

    app_root = Path(args.app_root).resolve()
    repo_root = app_root
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from services.api.assignment_intent_service import detect_assignment_intent  # type: ignore
    from services.api.skill_auto_router import resolve_effective_skill  # type: ignore

    rows = _load_jsonl(Path(args.dataset))
    workers = max(1, int(args.workers))

    results: List[Dict[str, Any]] = []
    skipped = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(
                _evaluate_row,
                row,
                app_root=app_root,
                resolve_effective_skill=resolve_effective_skill,
                detect_assignment_intent=detect_assignment_intent,
            )
            for row in rows
        ]
        for fut in as_completed(futs):
            try:
                item = fut.result()
            except Exception as exc:
                errors += 1
                results.append(
                    {
                        "ok": False,
                        "skip": False,
                        "error": f"exception:{type(exc).__name__}",
                        "bucket": "unknown",
                    }
                )
                continue
            if item.get("skip"):
                skipped += 1
            if not item.get("ok"):
                errors += 1
            results.append(item)

    valid = [x for x in results if x.get("ok") and not x.get("skip")]
    total = len(valid)
    top1_hits = sum(1 for x in valid if x.get("top1_hit"))
    reasons = Counter(str(x.get("reason") or "") for x in valid)
    default_count = sum(1 for x in valid if "default" in str(x.get("reason") or ""))
    ambiguous_count = sum(1 for x in valid if "ambiguous" in str(x.get("reason") or ""))
    auto_rule_count = sum(1 for x in valid if "auto_rule" in str(x.get("reason") or ""))

    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_skill_total: Counter[str] = Counter()
    per_skill_hits: Counter[str] = Counter()
    by_bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in valid:
        expected = str(item.get("expected_skill_id") or "")
        effective = str(item.get("effective_skill_id") or "")
        per_skill_total[expected] += 1
        if item.get("top1_hit"):
            per_skill_hits[expected] += 1
        confusion[expected][effective] += 1
        by_bucket[str(item.get("bucket") or "unknown")].append(item)

    denom = float(total or 1)
    report: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_path": str(Path(args.dataset).resolve()),
        "total_rows": len(rows),
        "total": total,
        "skipped_rows": skipped,
        "error_rows": errors,
        "top1_hits": top1_hits,
        "top1_rate": float(top1_hits) / denom,
        "default_rate": float(default_count) / denom,
        "ambiguous_rate": float(ambiguous_count) / denom,
        "auto_rule_rate": float(auto_rule_count) / denom,
        "by_reason": dict(reasons),
        "per_skill": {
            skill_id: {
                "total": int(per_skill_total.get(skill_id) or 0),
                "hits": int(per_skill_hits.get(skill_id) or 0),
                "recall": float(per_skill_hits.get(skill_id) or 0) / float(per_skill_total.get(skill_id) or 1),
            }
            for skill_id in sorted(per_skill_total.keys())
        },
        "confusion_matrix": {
            expected: dict(preds)
            for expected, preds in sorted(confusion.items(), key=lambda x: x[0])
        },
        "by_bucket": {
            bucket: _bucket_metrics(items)
            for bucket, items in sorted(by_bucket.items(), key=lambda x: x[0])
        },
    }

    failed = _gate_failures(
        report,
        gate_top1=args.gate_top1,
        gate_default=args.gate_default,
        gate_ambiguous=args.gate_ambiguous,
        per_skill_min_recall=args.per_skill_min_recall,
    )
    report["gates"] = {
        "gate_top1": args.gate_top1,
        "gate_default": args.gate_default,
        "gate_ambiguous": args.gate_ambiguous,
        "per_skill_min_recall": args.per_skill_min_recall,
        "passed": not failed,
        "failed": failed,
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "PASS" if not failed else "FAIL"
    print(
        f"[{status}] total={report['total']} top1={report['top1_rate']:.3f} "
        f"default={report['default_rate']:.3f} ambiguous={report['ambiguous_rate']:.3f}"
    )
    if failed:
        for msg in failed:
            print(f"- gate failed: {msg}")
        return 1

    if args.dump_confusion_matrix:
        print(json.dumps(report.get("confusion_matrix") or {}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

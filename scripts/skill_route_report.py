#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def _read_events(path: Path) -> List[Dict[str, Any]]:
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


def build_report(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    skill_rows = [x for x in events if str(x.get("event") or "") == "skill.resolve"]
    total = len(skill_rows)

    by_reason: Counter[str] = Counter()
    by_effective: Counter[str] = Counter()
    by_role: Counter[str] = Counter()
    transitions: Counter[str] = Counter()
    explicit = 0
    auto = 0
    defaulted = 0
    ambiguous = 0

    for item in skill_rows:
        role = str(item.get("role") or "unknown").strip() or "unknown"
        reason = str(item.get("reason") or "").strip() or "unknown"
        requested_raw = str(item.get("requested_skill_id") or "").strip()
        effective = str(item.get("effective_skill_id") or "").strip()
        requested = requested_raw or "(empty)"

        by_role[role] += 1
        by_reason[reason] += 1
        if effective:
            by_effective[effective] += 1
        transitions[f"{requested} -> {effective or '(empty)'}"] += 1

        if reason == "explicit":
            explicit += 1
        if "auto_rule" in reason:
            auto += 1
        if "default" in reason:
            defaulted += 1
        if "ambiguous" in reason:
            ambiguous += 1

    denom = float(total or 1)
    return {
        "total": total,
        "explicit": explicit,
        "auto_rule": auto,
        "default": defaulted,
        "ambiguous": ambiguous,
        "auto_hit_rate": float(auto) / denom,
        "default_rate": float(defaulted) / denom,
        "ambiguous_rate": float(ambiguous) / denom,
        "reasons": dict(by_reason),
        "roles": dict(by_role),
        "effective_skills": dict(by_effective),
        "transitions": dict(transitions),
    }


def _render_text(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"Total skill.resolve events: {int(report.get('total') or 0)}")
    lines.append(
        f"Breakdown: explicit={int(report.get('explicit') or 0)} "
        f"auto_rule={int(report.get('auto_rule') or 0)} "
        f"default={int(report.get('default') or 0)} "
        f"ambiguous={int(report.get('ambiguous') or 0)}"
    )
    lines.append(
        f"Rates: auto_hit_rate={float(report.get('auto_hit_rate') or 0.0):.3f} "
        f"default_rate={float(report.get('default_rate') or 0.0):.3f} "
        f"ambiguous_rate={float(report.get('ambiguous_rate') or 0.0):.3f}"
    )

    reasons = report.get("reasons") or {}
    lines.append("Reasons:")
    for key in sorted(reasons.keys(), key=lambda x: (-int(reasons.get(x) or 0), x)):
        lines.append(f"- {key}: {int(reasons.get(key) or 0)}")

    roles = report.get("roles") or {}
    lines.append("Roles:")
    for key in sorted(roles.keys(), key=lambda x: (-int(roles.get(x) or 0), x)):
        lines.append(f"- {key}: {int(roles.get(key) or 0)}")

    skills = report.get("effective_skills") or {}
    lines.append("Effective Skills:")
    for key in sorted(skills.keys(), key=lambda x: (-int(skills.get(x) or 0), x)):
        lines.append(f"- {key}: {int(skills.get(key) or 0)}")

    transitions = report.get("transitions") or {}
    if transitions:
        lines.append("Requested -> Effective:")
        for key in sorted(transitions.keys(), key=lambda x: (-int(transitions.get(x) or 0), x)):
            lines.append(f"- {key}: {int(transitions.get(key) or 0)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize skill.resolve routing events from diagnostics logs.")
    parser.add_argument("--log", default="tmp/diagnostics.log", help="diagnostics log path")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    rows = _read_events(Path(args.log))
    report = build_report(rows)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from services.api.assignment_intent_service import detect_assignment_intent
from services.api.skill_auto_router import resolve_effective_skill

FIXTURE_PATH = APP_ROOT / "tests" / "fixtures" / "teacher_workflow_routing_cases.json"


def main() -> int:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    mismatches: list[str] = []
    fallback_total = 0
    low_confidence_total = 0

    for case in cases:
        result = resolve_effective_skill(
            app_root=APP_ROOT,
            role_hint=case.get("role_hint") or "teacher",
            requested_skill_id=case.get("requested_skill_id") or "",
            last_user_text=case.get("last_user_text") or "",
            detect_assignment_intent=detect_assignment_intent,
        )
        expected_skill = case.get("expected_skill_id")
        expected_reason = case.get("expected_reason")
        actual_skill = result.get("effective_skill_id")
        actual_reason = result.get("reason")
        confidence = float(result.get("confidence") or 0.0)
        if actual_reason == "role_default" or str(actual_reason).endswith("_default"):
            fallback_total += 1
        if confidence < 0.5:
            low_confidence_total += 1
        if actual_skill != expected_skill or actual_reason != expected_reason:
            first_candidate = ((result.get('candidates') or [{}])[0]).get('skill_id')
            mismatches.append(
                f"- {case.get('name')}: expected {expected_skill}/{expected_reason}, got {actual_skill}/{actual_reason}, first_candidate={first_candidate}"
            )

    print(f"cases={len(cases)} mismatches={len(mismatches)} fallbacks={fallback_total} low_confidence={low_confidence_total}")
    if mismatches:
        print("mismatch details:")
        for item in mismatches:
            print(item)
        return 1
    print("routing fixture evaluation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

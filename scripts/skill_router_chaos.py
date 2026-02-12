#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_DEFAULT_TEXTS: Dict[str, str] = {
    "teacher": "请帮我生成作业，作业ID A2403_2026-02-04，每个知识点 5 题",
    "student": "开始今天作业",
}


def _copy_app_root(app_root: Path, target_root: Path) -> None:
    (target_root / "skills").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app_root / "skills", target_root / "skills")


def _pick_skill_yaml(skills_root: Path, rng: random.Random) -> Path:
    candidates = sorted(skills_root.glob("*/skill.yaml"))
    if not candidates:
        raise RuntimeError("no skill.yaml found")
    return rng.choice(candidates)


def _role_allowed(spec: Any, role: str) -> bool:
    roles = list(getattr(spec, "allowed_roles", []) or [])
    if not roles:
        return True
    return role in set(roles)


def _is_effective_valid(effective: str, loaded: Any, role: str) -> bool:
    skills = dict(getattr(loaded, "skills", {}) or {})
    available = [sid for sid, spec in skills.items() if _role_allowed(spec, role)]
    if not available:
        return effective == ""
    return effective in set(available)


def _scenario_corrupt_yaml(skills_root: Path, rng: random.Random) -> Dict[str, Any]:
    path = _pick_skill_yaml(skills_root, rng)
    path.write_text("id: broken\nrouting: [\n", encoding="utf-8")
    return {"scenario": "corrupt_yaml", "expect_load_error": True}


def _scenario_non_mapping_yaml(skills_root: Path, rng: random.Random) -> Dict[str, Any]:
    path = _pick_skill_yaml(skills_root, rng)
    path.write_text("[]\n", encoding="utf-8")
    return {"scenario": "non_mapping_yaml", "expect_load_error": True}


def _scenario_missing_yaml(skills_root: Path, rng: random.Random) -> Dict[str, Any]:
    path = _pick_skill_yaml(skills_root, rng)
    has_skill_md_fallback = (path.parent / "SKILL.md").exists()
    path.unlink(missing_ok=True)
    return {"scenario": "missing_yaml", "expect_load_error": not has_skill_md_fallback}


def _run_single_case(
    *,
    app_root: Path,
    suite: str,
    seed: int,
    resolve_effective_skill: Any,
    detect_assignment_intent: Any,
    load_skills: Any,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    role = "teacher"
    text = _DEFAULT_TEXTS[role]

    with tempfile.TemporaryDirectory(prefix="skill-chaos-") as td:
        local_root = Path(td) / "app"
        _copy_app_root(app_root, local_root)
        skills_root = local_root / "skills"

        stale_event = False
        expect_load_error = False
        scenario_name = "none"

        if suite == "p0":
            op = rng.choice(
                [_scenario_corrupt_yaml, _scenario_non_mapping_yaml, _scenario_missing_yaml]
            )
            meta = op(skills_root, rng)
            scenario_name = str(meta.get("scenario") or "p0")
            expect_load_error = bool(meta.get("expect_load_error"))
        elif suite == "combined_disaster":
            _scenario_corrupt_yaml(skills_root, rng)
            _scenario_missing_yaml(skills_root, rng)
            scenario_name = "combined_disaster"
            expect_load_error = True
        elif suite == "hot_reload":
            target = _pick_skill_yaml(skills_root, rng)
            original = target.read_text(encoding="utf-8")
            target.write_text("id: broken\nrouting: [\n", encoding="utf-8")
            first = resolve_effective_skill(
                app_root=local_root,
                role_hint=role,
                requested_skill_id="",
                last_user_text=text,
                detect_assignment_intent=detect_assignment_intent,
            )
            first_errors = int(first.get("load_errors") or 0)
            target.write_text(original, encoding="utf-8")
            target.touch()
            second = resolve_effective_skill(
                app_root=local_root,
                role_hint=role,
                requested_skill_id="",
                last_user_text=text,
                detect_assignment_intent=detect_assignment_intent,
            )
            second_errors = int(second.get("load_errors") or 0)
            stale_event = first_errors > 0 and second_errors > 0
            loaded_second = load_skills(local_root / "skills")
            effective_second = str(second.get("effective_skill_id") or "")
            return {
                "scenario": "hot_reload_cycle",
                "crashed": False,
                "load_errors": second_errors,
                "expect_load_error": False,
                "effective_skill_id": effective_second,
                "reason": str(second.get("reason") or ""),
                "fallback_valid": _is_effective_valid(effective_second, loaded_second, role),
                "stale_event": stale_event,
            }
        elif suite == "nightly":
            op = rng.choice(
                [_scenario_corrupt_yaml, _scenario_non_mapping_yaml, _scenario_missing_yaml]
            )
            meta = op(skills_root, rng)
            scenario_name = str(meta.get("scenario") or "nightly")
            expect_load_error = bool(meta.get("expect_load_error"))
        else:
            raise RuntimeError(f"unsupported suite: {suite}")

        payload = resolve_effective_skill(
            app_root=local_root,
            role_hint=role,
            requested_skill_id="",
            last_user_text=text,
            detect_assignment_intent=detect_assignment_intent,
        )
        loaded = load_skills(local_root / "skills")
        effective = str(payload.get("effective_skill_id") or "")
        return {
            "scenario": scenario_name,
            "crashed": False,
            "load_errors": int(payload.get("load_errors") or 0),
            "expect_load_error": expect_load_error,
            "effective_skill_id": effective,
            "reason": str(payload.get("reason") or ""),
            "fallback_valid": _is_effective_valid(effective, loaded, role),
            "stale_event": stale_event,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chaos test runner for skill router configuration resilience."
    )
    parser.add_argument("--app-root", required=True, help="repo root containing skills/")
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--suite",
        choices=["p0", "hot_reload", "combined_disaster", "nightly"],
        default="p0",
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--assert-no-crash", action="store_true")
    parser.add_argument("--assert-fallback-valid", action="store_true")
    parser.add_argument("--assert-load-errors-visible", action="store_true")
    parser.add_argument("--max-stale-ratio", type=float, default=None)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--seed", type=int, default=20260208)
    args = parser.parse_args()

    app_root = Path(args.app_root).resolve()
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    from services.api.assignment_intent_service import detect_assignment_intent  # type: ignore
    from services.api.skill_auto_router import resolve_effective_skill  # type: ignore
    from services.api.skills.loader import load_skills  # type: ignore

    rounds = max(1, int(args.rounds))
    workers = max(1, int(args.workers))
    base_seed = int(args.seed)

    results: List[Dict[str, Any]] = []
    crashes = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(
                _run_single_case,
                app_root=app_root,
                suite=args.suite,
                seed=base_seed + i,
                resolve_effective_skill=resolve_effective_skill,
                detect_assignment_intent=detect_assignment_intent,
                load_skills=load_skills,
            )
            for i in range(rounds)
        ]
        for fut in as_completed(futs):
            try:
                item = fut.result()
            except Exception as exc:
                crashes += 1
                item = {
                    "scenario": "exception",
                    "crashed": True,
                    "load_errors": 0,
                    "expect_load_error": False,
                    "effective_skill_id": "",
                    "reason": f"exception:{type(exc).__name__}",
                    "fallback_valid": False,
                    "stale_event": False,
                }
            results.append(item)
            if args.fail_fast and item.get("crashed"):
                break

    by_scenario = Counter(str(item.get("scenario") or "unknown") for item in results)
    fallback_invalid = sum(1 for item in results if not bool(item.get("fallback_valid")))
    load_error_missing = sum(
        1
        for item in results
        if bool(item.get("expect_load_error")) and int(item.get("load_errors") or 0) <= 0
    )
    stale_events = sum(1 for item in results if bool(item.get("stale_event")))
    total_cases = len(results)
    stale_ratio = float(stale_events) / float(total_cases or 1)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "suite": args.suite,
        "total_cases": total_cases,
        "crashes": crashes,
        "fallback_invalid": fallback_invalid,
        "load_error_missing": load_error_missing,
        "stale_events": stale_events,
        "stale_ratio": stale_ratio,
        "by_scenario": dict(by_scenario),
    }

    failures: List[str] = []
    if args.assert_no_crash and crashes > 0:
        failures.append(f"crashes={crashes} > 0")
    if args.assert_fallback_valid and fallback_invalid > 0:
        failures.append(f"fallback_invalid={fallback_invalid} > 0")
    if args.assert_load_errors_visible and load_error_missing > 0:
        failures.append(f"load_error_missing={load_error_missing} > 0")
    if args.max_stale_ratio is not None and stale_ratio > float(args.max_stale_ratio):
        failures.append(
            f"stale_ratio={stale_ratio:.4f} > max_stale_ratio={float(args.max_stale_ratio):.4f}"
        )

    report["assertions"] = {
        "assert_no_crash": bool(args.assert_no_crash),
        "assert_fallback_valid": bool(args.assert_fallback_valid),
        "assert_load_errors_visible": bool(args.assert_load_errors_visible),
        "max_stale_ratio": args.max_stale_ratio,
        "passed": not failures,
        "failed": failures,
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    status = "PASS" if not failures else "FAIL"
    print(
        f"[{status}] suite={args.suite} total={total_cases} crashes={crashes} "
        f"fallback_invalid={fallback_invalid} load_error_missing={load_error_missing} stale_ratio={stale_ratio:.4f}"
    )
    if failures:
        for msg in failures:
            print(f"- assertion failed: {msg}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

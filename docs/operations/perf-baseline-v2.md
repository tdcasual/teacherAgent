# V2 Performance Baseline And P95 Gate

Date: 2026-03-02

## Goal

Provide a repeatable process to validate the hard-cut rewrite performance gate:

- target: `P95 improvement >= 30%`
- gate command: `scripts/perf/compare_p95.sh`

## Load Script

Use:

- `scripts/perf/k6-v2-core.js`

Endpoints covered:

1. `GET /healthz`
2. `POST /api/v2/auth/student/login`
3. `POST /api/v2/chat/send`

## Baseline Capture

Save legacy-system P95 (milliseconds):

```bash
echo "1200" > output/rewrite_baseline_p95_ms.txt
```

## Current Capture

Run k6 against Go v2 service:

```bash
k6 run scripts/perf/k6-v2-core.js
```

Write current P95 (milliseconds):

```bash
echo "780" > output/rewrite_current_p95_ms.txt
```

## Gate Check

```bash
bash scripts/perf/compare_p95.sh
```

Pass condition:

- improvement `>= 30%`

The script prints baseline, current, computed improvement, threshold, and `PASS/FAIL`.

## Notes

- You can override threshold with `P95_IMPROVEMENT_THRESHOLD`, for example:

```bash
P95_IMPROVEMENT_THRESHOLD=35 bash scripts/perf/compare_p95.sh
```

- Files may be replaced with CI-generated artifacts if needed:

```bash
bash scripts/perf/compare_p95.sh /path/to/baseline.txt /path/to/current.txt
```

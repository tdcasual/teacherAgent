# V2 Smoke Case List

Current automated count: 20 cases (script: `scripts/release/smoke_go_api_v2.sh`)

## Health (2)

1. `S01` `GET /healthz`
2. `S02` `GET /health`

## Auth (2)

1. `S03` student login success
2. `S04` student login invalid credential

## Files (2)

1. `S05` file upload accepted
2. `S06` file upload oversize rejected

## Assignment / Exam (4)

1. `S07` assignment confirm queued
2. `S08` assignment invalid state
3. `S09` exam parse queued
4. `S10` exam parse missing resource rejected

## Chat / Jobs (4)

1. `S11` chat send queued
2. `S12` chat send validation rejected
3. `S13` chat events stream available
4. `S14` job status returns terminal state

## Admin (3)

1. `S15` reset teacher token success
2. `S16` reset teacher token validation rejected
3. `S17` reset teacher token server failure path

## Charts (3)

1. `S18` chart file missing returns `CHART_NOT_FOUND`
2. `S19` chart meta missing returns `CHART_RUN_NOT_FOUND`
3. `S20` chart SVG file missing returns `CHART_NOT_FOUND`

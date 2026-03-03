# Model Policy (Go-Only, No Routing)

Date: 2026-03-02

## Current Active Models

The runtime keeps exactly two active model slots:

1. `embedding` model
   - Purpose: vector indexing / retrieval features.
   - Env: `EMBEDDING_MODEL_ID`
   - Default: `text-embedding-3-large`

2. `drawing` model
   - Purpose: shared drawing generation for both teacher and student flows.
   - Env: `DRAWING_MODEL_ID`
   - Default: `gpt-image-1`

## Routing Policy

- Model routing is intentionally removed.
- Per-user, per-role, or per-channel model switching is not supported.
- Provider registry and probe-model style workflows are outside the retained scope.

## Extension Slots (Reserved, Disabled by Default)

The following env keys are reserved for future capability expansion:

- `IMAGE_GENERATION_MODEL_ID`
- `VIDEO_GENERATION_MODEL_ID`

If unset, the corresponding capability is treated as disabled.

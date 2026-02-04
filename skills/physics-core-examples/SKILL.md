---
name: physics-core-examples
description: Teacher-facing workflow to add, discuss, and maintain core example problems. Capture standard solution methods, core ideas/models, and variant templates; link to lesson materials and question bank. Use when teachers add or discuss core examples.
---

# Physics Core Examples

## Overview
Use this skill to curate **core example problems** and their **standard solution method** and **core model**. Core examples serve as teaching anchors and can drive homework generation (by parameter variation). Inputs can be PDFs, screenshots, or teacher notes.

## Required Inputs
- example_id (or request to create new)
- source material (PDF/image/lesson example) OR teacher-provided stem
- standard solution method (or discussion notes)
- core model (template / invariant steps)
- knowledge point mapping (KP)

## Workflow
1. **Ingest source**
   - If input is PDF/image: use `physics-lesson-capture` to OCR and extract example text.
   - If example already exists in `data/lessons/<lesson_id>/examples.csv`, promote it to core.

2. **Create core example record**
   - Store stem, solution, core model, and discussion notes under `data/core_examples/`.
   - Append a row in `data/core_examples/examples.csv`.

3. **Teacher discussion capture**
   - Record "standard method", "core idea", "typical pitfalls".
   - See `references/discussion_template.md`.

4. **Variant template (optional)**
   - If this example is a template for variations, record parameterized variant rules.
   - See `references/variant_template.md`.

5. **Integrations**
   - **Question bank**: add a reference entry with source `core_example`.
   - **Homework**: allow specifying core example IDs as the basis for assignment generation.
   - **Student coach**: use core examples for guided discussion + Feynman reflection.
   - Variant generation: use `scripts/generate_variants.py`.

## CLI Quick Start
```bash
python3 skills/physics-core-examples/scripts/register_core_example.py \
  --example-id CE001 \
  --kp-id KP-M01 \
  --core-model "匀强电场中类抛体运动模型" \
  --stem-file /path/to/stem.md \
  --solution-file /path/to/solution.md \
  --model-file /path/to/model.md \
  --figure-file /path/to/figure.png \
  --source-ref "lesson:L2403_2026-02-04#E003"
```

Promote from lesson example:
```bash
python3 skills/physics-core-examples/scripts/register_core_example.py \
  --example-id CE002 \
  --kp-id KP-E04 \
  --from-lesson L2403_2026-02-04 \
  --lesson-example-id E003 \
  --lesson-figure fig1.png \
  --core-model "电势差与场强关系" \
  --source-ref "lesson:L2403_2026-02-04#E003"
```

Generate variants:
```bash
python3 skills/physics-core-examples/scripts/generate_variants.py \\
  --example-id CE001 \\
  --count 3
```

Render core example PDF:
```bash
python3 skills/physics-core-examples/scripts/render_core_example_pdf.py \\
  --example-id CE001
```

## References
- references/core_example_schema.md
- references/discussion_template.md
- references/variant_template.md
- references/integration.md

# Core Example Schema

## Storage
```
data/core_examples/
  examples.csv
  stems/<example_id>.md
  solutions/<example_id>.md
  models/<example_id>.md
  discussions/<example_id>.md
  variants/<example_id>.md
  assets/<example_id>.<ext>
```

## examples.csv fields
- example_id
- kp_id
- core_model
- difficulty (basic|medium|advanced)
- source_ref
- stem_ref
- solution_ref
- model_ref
- discussion_ref
- variant_ref (optional)
- tags

## Notes
- Keep stems/solutions separate for reuse.
- Use `source_ref` to trace back to lesson/exam/handout.
- Use `[FIGURE: path]` tag inside stem to reference images.

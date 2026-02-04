# Example Extraction Rules

Use these heuristics to split OCR text into example questions.

## Common Patterns
- Numbered stems: `1.` `2.` `3.` or `（1）` `（2）`
- Option blocks: lines starting with `A.` `B.` `C.` `D.`
- "如图" lines often indicate a new example block

## Steps
1. Normalize whitespace and remove page headers/footers if possible.
2. Split by numbered lines.
3. Attach contiguous option lines to the nearest stem.
4. If options are missing, keep as short-answer example.

## Output
For each example, capture:
- stem_text
- options (if any)
- source_ref (file + page)

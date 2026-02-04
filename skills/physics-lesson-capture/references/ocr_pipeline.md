# OCR Pipeline (DeepSeek-OCR via SiliconFlow)

## When to OCR
- Scanned PDFs (image-only)
- Images/photographs of the board or handouts
- DOCX images that contain text

## Model
- Use SiliconFlow DeepSeek-OCR: `deepseek-ai/DeepSeek-OCR`
- Use the SiliconFlow base URL (cn domain) and API key in `.env`.
  - `OPENAI_API_KEY` or `SILICONFLOW_API_KEY`
  - `SILICONFLOW_BASE_URL` (if it ends with `/v1`, the script appends `/chat/completions`)
  - Optional override: `DS_OCR_BASE_URL` and `SILICONFLOW_OCR_MODEL`

## Expected Output
Store both:
- Raw OCR JSON (for traceability)
- Cleaned text (plain text for later parsing)

## Notes
- Keep page/image references so examples can be traced back to the source.
- If OCR output is low quality, flag it and request a better scan/photo.

#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import subprocess
from pathlib import Path
from typing import List


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_examples(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def list_text_previews(text_dir: Path, max_lines: int) -> List[tuple]:
    previews = []
    if not text_dir.exists():
        return previews
    for file in sorted(text_dir.glob("*.txt")):
        content = file.read_text(encoding="utf-8", errors="ignore")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        snippet = "\n".join(lines[:max_lines])
        previews.append((file.name, snippet))
    return previews


def list_images(source_dir: Path) -> List[Path]:
    images = []
    if not source_dir.exists():
        return images
    for file in source_dir.rglob("*"):
        if file.is_file() and file.suffix.lower() in IMAGE_EXTS:
            images.append(file)
    return sorted(images)


def safe_cell(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ")
    return text


def render_pdf_preview(pdf_path: Path, preview_dir: Path, max_pages: int = 2) -> List[Path]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = preview_dir / pdf_path.stem
    cmd = ["pdftoppm", "-png", "-f", "1", "-l", str(max_pages), str(pdf_path), str(output_prefix)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        return []
    images = sorted(preview_dir.glob(f"{pdf_path.stem}-*.png"))
    return images


def detect_suspicious_example(stem: str, options: str) -> List[str]:
    issues = []
    if not stem or len(stem.strip()) < 10:
        issues.append("stem too short")
    if options:
        # count A-D options
        letters = re.findall(r"\b[A-D][\.、]", options)
        if len(letters) < 3:
            issues.append("options incomplete")
    else:
        issues.append("options missing")
    if "（）" in stem or "( )" in stem:
        issues.append("blank detected")
    return issues


def propose_kp_candidates(stem: str) -> List[str]:
    # heuristic keyword mapping
    keywords = {
        "电势差": "KP-E04",
        "场强": "KP-E04",
        "电势能": "KP-E02",
        "等效电流": "KP-E01",
        "电流表": "KP-E03",
        "分流": "KP-E03",
        "带电粒子": "KP-M01",
        "匀强电场": "KP-M01",
        "抛": "KP-M02",
    }
    found = []
    for kw, kp in keywords.items():
        if kw in stem:
            found.append(kp)
    # deduplicate
    out = []
    for kp in found:
        if kp not in out:
            out.append(kp)
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate a visual review report for lesson OCR + examples")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--base-dir", default="data/lessons")
    parser.add_argument("--out", help="output markdown path")
    parser.add_argument("--max-examples", type=int, default=20)
    parser.add_argument("--max-preview-lines", type=int, default=8)
    parser.add_argument("--render-pdf", action="store_true", help="render PDF previews using pdftoppm if available")
    parser.add_argument("--pdf-pages", type=int, default=2)
    args = parser.parse_args()

    lesson_dir = Path(args.base_dir) / args.lesson_id
    manifest = load_manifest(lesson_dir / "manifest.json")
    examples = read_examples(lesson_dir / "examples.csv")

    source_dir = lesson_dir / "sources"
    text_dir = lesson_dir / "text"
    previews = list_text_previews(text_dir, args.max_preview_lines)

    images = list_images(source_dir)
    rendered_pdf_images = []
    if args.render_pdf and source_dir.exists():
        preview_dir = lesson_dir / "previews"
        for pdf in source_dir.glob("*.pdf"):
            rendered_pdf_images.extend(render_pdf_preview(pdf, preview_dir, args.pdf_pages))

    out_path = Path(args.out) if args.out else lesson_dir / "lesson_review.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"Lesson Review: {manifest.get('lesson_id', args.lesson_id)}")
    lines.append(f"Topic: {manifest.get('topic', '')}")
    if manifest.get("class_name"):
        lines.append(f"Class: {manifest.get('class_name')}")
    lines.append("")

    lines.append("Sources:")
    if manifest.get("sources"):
        for src in manifest["sources"]:
            lines.append(f"- {src.get('file')} ({src.get('type')})")
    else:
        lines.append("- (no manifest sources)")

    lines.append("")
    lines.append("OCR Text Preview:")
    if previews:
        for name, snippet in previews:
            lines.append(f"- {name}")
            lines.append("```text")
            lines.append(snippet)
            lines.append("```")
    else:
        lines.append("- (no text files found)")

    lines.append("")
    lines.append("Extracted Examples (preview):")
    if examples:
        lines.append("| id | stem | options | source | flags | kp_candidates |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for ex in examples[: args.max_examples]:
            stem = ex.get("stem_text", "")
            options = ex.get("options", "")
            flags = ", ".join(detect_suspicious_example(stem, options))
            kp_candidates = ", ".join(propose_kp_candidates(stem))
            lines.append(
                f"| {safe_cell(ex.get('example_id',''))} | {safe_cell(stem)} | {safe_cell(options)} | {safe_cell(ex.get('source_ref',''))} | {safe_cell(flags)} | {safe_cell(kp_candidates)} |"
            )
        if len(examples) > args.max_examples:
            lines.append("")
            lines.append(f"(Showing first {args.max_examples} of {len(examples)} examples)")
    else:
        lines.append("- (no examples extracted)")

    lines.append("")
    lines.append("Suspected Issues:")
    if examples:
        for ex in examples:
            stem = ex.get("stem_text", "")
            options = ex.get("options", "")
            flags = detect_suspicious_example(stem, options)
            if flags:
                lines.append(f"- {ex.get('example_id','')}: {', '.join(flags)}")
    else:
        lines.append("- (no examples extracted)")

    lines.append("")
    lines.append("Knowledge Point Candidates:")
    if examples:
        kp_rows = []
        for ex in examples:
            stem = ex.get("stem_text", "")
            kp_candidates = propose_kp_candidates(stem)
            if kp_candidates:
                kp_rows.append((ex.get("example_id", ""), kp_candidates))
        if kp_rows:
            lines.append("| example_id | kp_candidates | confirm |")
            lines.append("| --- | --- | --- |")
            for ex_id, kps in kp_rows:
                lines.append(f"| {safe_cell(ex_id)} | {safe_cell(', '.join(kps))} | ☐ |")
        else:
            lines.append("- (no candidates)")
    else:
        lines.append("- (no examples extracted)")

    lines.append("")
    lines.append("Image Previews:")
    if images:
        for img in images:
            lines.append(f"- {img.name}")
            lines.append(f"![{img.name}]({img.resolve()})")
    else:
        lines.append("- (no image sources found)")

    if rendered_pdf_images:
        lines.append("")
        lines.append("PDF Page Previews:")
        for img in rendered_pdf_images:
            lines.append(f"- {img.name}")
            lines.append(f"![{img.name}]({img.resolve()})")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Wrote {out_path}")


if __name__ == "__main__":
    main()

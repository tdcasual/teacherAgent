#!/usr/bin/env python3
import argparse
import csv
import textwrap
from pathlib import Path


def find_example(example_id: str) -> dict:
    csv_path = Path("data/core_examples/examples.csv")
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("example_id") == example_id:
                    return row
    return {}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_stem_with_figures(text: str):
    lines = text.splitlines()
    blocks = []
    for line in lines:
        line = line.strip()
        if not line:
            blocks.append({"type": "spacer"})
            continue
        if line.startswith("[FIGURE:"):
            fig = line.replace("[FIGURE:", "").replace("]", "").strip()
            blocks.append({"type": "figure", "path": fig})
        else:
            blocks.append({"type": "text", "text": line})
    return blocks


def render_pdf(example_id: str, stem_text: str, out_pdf: Path):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
    except Exception as exc:
        raise SystemExit("Missing reportlab. Install: python3 -m pip install reportlab") from exc

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    width, height = A4
    margin = 2 * cm
    line_height = 14

    c = canvas.Canvas(str(out_pdf), pagesize=A4)
    c.setTitle(f"Core Example {example_id}")

    x = margin
    y = height - margin

    def new_page():
        nonlocal y
        c.showPage()
        y = height - margin

    def draw_line(text: str, bold=False):
        nonlocal y
        if y < margin + line_height:
            new_page()
        if bold:
            c.setFont("Helvetica-Bold", 12)
        else:
            c.setFont("Helvetica", 11)
        c.drawString(x, y, text)
        y -= line_height

    # header
    draw_line(f"Core Example: {example_id}", bold=True)
    draw_line("", bold=False)

    blocks = parse_stem_with_figures(stem_text)
    for b in blocks:
        if b["type"] == "spacer":
            y -= line_height
            continue
        if b["type"] == "text":
            for line in textwrap.wrap(b["text"], width=80):
                draw_line(line)
            continue
        if b["type"] == "figure":
            fig_path = Path(b["path"])
            if not fig_path.exists():
                draw_line(f"[图像缺失] {fig_path}")
                continue
            # scale image to fit width
            try:
                img = ImageReader(str(fig_path))
                iw, ih = img.getSize()
                max_w = width - 2 * margin
                scale = max_w / iw
                scaled_h = ih * scale
            except Exception:
                img = None
                scaled_h = 200
                max_w = width - 2 * margin
            if y - scaled_h < margin:
                new_page()
            if img:
                c.drawImage(img, x, y - scaled_h, width=max_w, height=scaled_h, preserveAspectRatio=True, mask='auto')
            else:
                draw_line(f"[图像无法渲染] {fig_path}")
            y -= scaled_h + line_height

    c.save()


def main():
    parser = argparse.ArgumentParser(description="Render core example to PDF")
    parser.add_argument("--example-id", required=True)
    parser.add_argument("--out", help="output pdf path")
    args = parser.parse_args()

    example = find_example(args.example_id)
    stem_path = Path(example.get("stem_ref", "")) if example else Path("data/core_examples/stems") / f"{args.example_id}.md"
    stem_text = read_text(stem_path)
    if not stem_text:
        raise SystemExit(f"Stem not found: {stem_path}")

    out_pdf = Path(args.out) if args.out else Path("output/pdf") / f"core_example_{args.example_id}.pdf"
    render_pdf(args.example_id, stem_text, out_pdf)
    print(f"[OK] Wrote PDF: {out_pdf}")


if __name__ == "__main__":
    main()

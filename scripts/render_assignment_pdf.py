#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.question_bank_select_service import resolve_readable_stem_ref  # noqa: E402

_MISSING_STEM_TEXT = "[题干缺失] 请补充题干。"


def read_assignment_questions(path: Path):
    import csv
    if not path.exists():
        raise SystemExit(f"Assignment questions not found: {path}")
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def stem_text_for_pdf(
    stem_ref: str,
    *,
    folder: Path,
    app_root: Path,
    data_dir: Path,
) -> str:
    ref = str(stem_ref or "").strip()
    if not ref:
        return _MISSING_STEM_TEXT
    path = resolve_readable_stem_ref(ref, folder=folder, app_root=app_root, data_dir=data_dir)
    if path is None:
        return _MISSING_STEM_TEXT
    text = read_text(path)
    return text if str(text or "").strip() else _MISSING_STEM_TEXT


def render_pdf(
    assignment_id: str,
    questions: list,
    out_pdf: Path,
    *,
    folder: Path,
    app_root: Path,
    data_dir: Path,
):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise SystemExit("Missing reportlab. Install: python3 -m pip install reportlab") from exc

    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    width, height = A4
    margin = 2 * cm
    line_height = 14

    c = canvas.Canvas(str(out_pdf), pagesize=A4)
    c.setTitle(f"Assignment {assignment_id}")

    x = margin
    y = height - margin

    def draw_line(text: str, bold=False):
        nonlocal y
        if y < margin + line_height:
            c.showPage()
            y = height - margin
        if bold:
            c.setFont("Helvetica-Bold", 12)
        else:
            c.setFont("Helvetica", 11)
        payload = str(text or "")
        try:
            payload.encode("latin-1")
        except UnicodeEncodeError:
            payload = payload.encode("ascii", "replace").decode("ascii")
        try:
            c.drawString(x, y, payload)
        except UnicodeEncodeError:
            payload = payload.encode("ascii", "replace").decode("ascii")
            c.drawString(x, y, payload)
        y -= line_height

    # Header
    draw_line(f"Assignment ID: {assignment_id}", bold=True)
    draw_line("Student: ____________________", bold=False)
    draw_line("", bold=False)

    # Questions
    for idx, q in enumerate(questions, start=1):
        stem_ref = q.get("stem_ref")
        stem_text = stem_text_for_pdf(
            str(stem_ref or ""), folder=folder, app_root=app_root, data_dir=data_dir
        )
        draw_line(f"{idx}. {q.get('question_id')} ({q.get('kp_id')}|{q.get('difficulty')})", bold=True)
        for line in stem_text.splitlines() or [stem_text]:
            draw_line(line)
        draw_line("", bold=False)

    c.save()


def main():
    parser = argparse.ArgumentParser(description="Render assignment PDF with full stems")
    parser.add_argument("--assignment-id", required=True)
    parser.add_argument("--assignment-questions", help="path to assignment questions csv")
    parser.add_argument("--out", help="output pdf path")
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--app-root", default="")
    args = parser.parse_args()

    app_root = Path(args.app_root).resolve() if str(args.app_root or "").strip() else ROOT
    data_dir = (
        Path(args.data_dir).resolve()
        if str(args.data_dir or "").strip()
        else Path(os.environ.get("DATA_DIR") or (app_root / "data")).resolve()
    )
    assignments_root = (data_dir / "assignments").resolve()
    if args.assignment_questions:
        questions_path = Path(args.assignment_questions).resolve()
    else:
        questions_path = assignments_root / args.assignment_id / "questions.csv"
    questions = read_assignment_questions(questions_path)

    out_pdf = Path(args.out) if args.out else Path("output/pdf") / f"assignment_{args.assignment_id}.pdf"
    render_pdf(
        args.assignment_id,
        questions,
        out_pdf,
        folder=questions_path.parent,
        app_root=app_root,
        data_dir=data_dir,
    )
    print(f"[OK] Wrote PDF: {out_pdf}")


if __name__ == "__main__":
    main()

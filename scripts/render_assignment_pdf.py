#!/usr/bin/env python3
import argparse
from pathlib import Path


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


def render_pdf(assignment_id: str, questions: list, out_pdf: Path):
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
        c.drawString(x, y, text)
        y -= line_height

    # Header
    draw_line(f"Assignment ID: {assignment_id}", bold=True)
    draw_line("Student: ____________________", bold=False)
    draw_line("", bold=False)

    # Questions
    for idx, q in enumerate(questions, start=1):
        stem_ref = q.get("stem_ref")
        stem_text = read_text(Path(stem_ref)) if stem_ref else ""
        draw_line(f"{idx}. {q.get('question_id')} ({q.get('kp_id')}|{q.get('difficulty')})", bold=True)
        if stem_text:
            for line in stem_text.splitlines():
                draw_line(line)
        else:
            draw_line("[题干缺失] 请补充题干。")
        draw_line("", bold=False)

    c.save()


def main():
    parser = argparse.ArgumentParser(description="Render assignment PDF with full stems")
    parser.add_argument("--assignment-id", required=True)
    parser.add_argument("--assignment-questions", help="path to assignment questions csv")
    parser.add_argument("--out", help="output pdf path")
    args = parser.parse_args()

    questions_path = Path(args.assignment_questions) if args.assignment_questions else Path("data/assignments") / args.assignment_id / "questions.csv"
    questions = read_assignment_questions(questions_path)

    out_pdf = Path(args.out) if args.out else Path("output/pdf") / f"assignment_{args.assignment_id}.pdf"
    render_pdf(args.assignment_id, questions, out_pdf)
    print(f"[OK] Wrote PDF: {out_pdf}")


if __name__ == "__main__":
    main()

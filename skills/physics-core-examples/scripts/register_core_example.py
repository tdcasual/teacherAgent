#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def read_lesson_example(lesson_id: str, example_id: str) -> dict:
    lesson_csv = Path("data/lessons") / lesson_id / "examples.csv"
    if not lesson_csv.exists():
        raise SystemExit(f"lesson examples not found: {lesson_csv}")
    with lesson_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("example_id") == example_id:
                return row
    raise SystemExit(f"example_id {example_id} not found in {lesson_csv}")


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_examples_row(examples_csv: Path, row: dict):
    if not examples_csv.exists():
        examples_csv.parent.mkdir(parents=True, exist_ok=True)
        with examples_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)
        return
    with examples_csv.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Register a core example")
    parser.add_argument("--example-id", required=True)
    parser.add_argument("--kp-id", required=True)
    parser.add_argument("--core-model", required=True)
    parser.add_argument("--difficulty", default="medium")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--stem-file", help="markdown file for stem")
    parser.add_argument("--solution-file", help="markdown file for solution")
    parser.add_argument("--model-file", help="markdown file for core model")
    parser.add_argument("--figure-file", help="figure image file to attach")
    parser.add_argument("--discussion-file", help="markdown file for discussion")
    parser.add_argument("--variant-file", help="markdown file for variant template")
    parser.add_argument("--from-lesson", help="lesson_id")
    parser.add_argument("--lesson-example-id", help="example id in lesson examples.csv")
    parser.add_argument("--lesson-figure", help="figure filename in lesson sources (optional)")
    args = parser.parse_args()

    base = Path("data/core_examples")
    stems = base / "stems"
    solutions = base / "solutions"
    models = base / "models"
    discussions = base / "discussions"
    variants = base / "variants"
    for d in [stems, solutions, models, discussions, variants]:
        ensure_dir(d)

    stem_ref = stems / f"{args.example_id}.md"
    solution_ref = solutions / f"{args.example_id}.md"
    model_ref = models / f"{args.example_id}.md"
    discussion_ref = discussions / f"{args.example_id}.md"
    variant_ref = variants / f"{args.example_id}.md"

    if args.from_lesson and args.lesson_example_id:
        ex = read_lesson_example(args.from_lesson, args.lesson_example_id)
        stem_text = ex.get("stem_text", "")
        options = ex.get("options", "")
        if options:
            stem_text = stem_text + "\n" + options
        write_text(stem_ref, stem_text)
    elif args.stem_file:
        write_text(stem_ref, Path(args.stem_file).read_text(encoding="utf-8"))
    else:
        write_text(stem_ref, "[待补充题干]")

    if args.solution_file:
        write_text(solution_ref, Path(args.solution_file).read_text(encoding="utf-8"))
    else:
        write_text(solution_ref, "[待补充解答]")

    if args.model_file:
        write_text(model_ref, Path(args.model_file).read_text(encoding="utf-8"))
    else:
        write_text(model_ref, args.core_model)

    if args.discussion_file:
        write_text(discussion_ref, Path(args.discussion_file).read_text(encoding="utf-8"))
    else:
        write_text(discussion_ref, f"Standard Method:\n- \nCore Idea:\n- \nCore Model:\n- {args.core_model}\nTypical Pitfalls:\n- ")

    if args.variant_file:
        write_text(variant_ref, Path(args.variant_file).read_text(encoding="utf-8"))

    # attach figure if provided or auto from lesson sources
    fig_src = Path(args.figure_file) if args.figure_file else None
    if not fig_src and args.from_lesson:
        lesson_dir = Path("data/lessons") / args.from_lesson / "sources"
        if lesson_dir.exists():
            if args.lesson_figure:
                candidate = lesson_dir / args.lesson_figure
                if candidate.exists():
                    fig_src = candidate
            else:
                # pick first image file
                for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"):
                    imgs = list(lesson_dir.glob(f"*{ext}"))
                    if imgs:
                        fig_src = imgs[0]
                        break
                # fallback to previews
                if not fig_src:
                    preview_dir = Path("data/lessons") / args.from_lesson / "previews"
                    if preview_dir.exists():
                        previews = list(preview_dir.glob("*.png"))
                        if previews:
                            fig_src = previews[0]

    if fig_src:
        if not fig_src.exists():
            raise SystemExit(f"Figure not found: {fig_src}")
        assets_dir = base / "assets"
        ensure_dir(assets_dir)
        fig_dest = assets_dir / f"{args.example_id}{fig_src.suffix.lower()}"
        fig_dest.write_bytes(fig_src.read_bytes())
        stem_content = stem_ref.read_text(encoding="utf-8")
        if "[FIGURE:" not in stem_content:
            stem_content += f"\n\n[FIGURE: {fig_dest}]\n"
            stem_ref.write_text(stem_content, encoding="utf-8")

    examples_csv = base / "examples.csv"
    row = {
        "example_id": args.example_id,
        "kp_id": args.kp_id,
        "core_model": args.core_model,
        "difficulty": args.difficulty,
        "source_ref": args.source_ref,
        "stem_ref": str(stem_ref),
        "solution_ref": str(solution_ref),
        "model_ref": str(model_ref),
        "discussion_ref": str(discussion_ref),
        "variant_ref": str(variant_ref) if args.variant_file else "",
        "tags": args.tags,
    }
    append_examples_row(examples_csv, row)

    print(f"[OK] Registered core example {args.example_id}")


if __name__ == "__main__":
    main()

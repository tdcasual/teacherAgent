#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_variables(text: str) -> dict:
    # simple parse: lines like "m = 2", "E = 3.0"
    vars = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key and val:
                vars[key] = val
    return vars


def apply_variation(stem: str, var_map: dict) -> str:
    out = stem
    for k, v in var_map.items():
        out = out.replace(f"{{{k}}}", str(v))
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate variants from core example template")
    parser.add_argument("--example-id", required=True)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--out-dir", default="data/assignments/generated_from_core")
    args = parser.parse_args()

    base = Path("data/core_examples")
    stem_path = base / "stems" / f"{args.example_id}.md"
    variant_path = base / "variants" / f"{args.example_id}.md"
    if not stem_path.exists():
        raise SystemExit(f"Stem not found: {stem_path}")

    stem = read_text(stem_path)
    variant_text = read_text(variant_path)
    vars = parse_variables(variant_text)

    if not vars:
        raise SystemExit("No variables found in variant template. Use {var} placeholders in stem.")

    out_dir = Path(args.out_dir) / args.example_id
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = []
    for i in range(1, args.count + 1):
        # naive variation: append index to numeric vars
        var_map = {}
        for k, v in vars.items():
            if re.fullmatch(r"-?\d+(\.\d+)?", v):
                num = float(v)
                var_map[k] = str(num + i)
            else:
                var_map[k] = v
        vstem = apply_variation(stem, var_map)
        out_file = out_dir / f"{args.example_id}_V{i:02d}.md"
        out_file.write_text(vstem, encoding="utf-8")
        variants.append({"id": f"{args.example_id}_V{i:02d}", "stem_ref": str(out_file)})

    index_path = out_dir / "index.json"
    index_path.write_text(json.dumps(variants, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Generated {len(variants)} variants in {out_dir}")


if __name__ == "__main__":
    main()

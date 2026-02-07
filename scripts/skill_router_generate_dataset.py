#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List


_BASE_CASES: Dict[str, List[Dict[str, str]]] = {
    "golden": [
        {
            "role": "teacher",
            "text": "请帮我生成作业，作业ID A2403_2026-02-04，每个知识点 5 题",
            "expected_skill_id": "physics-homework-generator",
        },
        {
            "role": "teacher",
            "text": "先读取当前模型路由配置，再回滚到版本 3",
            "expected_skill_id": "physics-llm-routing",
        },
        {
            "role": "teacher",
            "text": "采集课堂材料并做 OCR 抽取",
            "expected_skill_id": "physics-lesson-capture",
        },
        {
            "role": "teacher",
            "text": "登记核心例题 CE001 并生成 3 道变式题",
            "expected_skill_id": "physics-core-examples",
        },
        {
            "role": "teacher",
            "text": "请分析某个学生最近作业表现并更新画像",
            "expected_skill_id": "physics-student-focus",
        },
        {
            "role": "teacher",
            "text": "请做一次考试分析并给试卷讲评建议",
            "expected_skill_id": "physics-teacher-ops",
        },
        {
            "role": "student",
            "text": "开始今天作业",
            "expected_skill_id": "physics-student-coach",
        },
    ],
    "drift": [
        {
            "role": "teacher",
            "text": "帮我生成一套课后巩固包，按知识点分层出题",
            "expected_skill_id": "physics-homework-generator",
        },
        {
            "role": "teacher",
            "text": "把教师端模型分流策略回退到上一个稳定版本",
            "expected_skill_id": "physics-llm-routing",
        },
        {
            "role": "teacher",
            "text": "把这节课材料做板书识别并抽取例题结构",
            "expected_skill_id": "physics-lesson-capture",
        },
        {
            "role": "teacher",
            "text": "新增一个 CE 题模板并扩展同构变式",
            "expected_skill_id": "physics-core-examples",
        },
        {
            "role": "teacher",
            "text": "给这个学生做个体学习诊断并更新画像卡",
            "expected_skill_id": "physics-student-focus",
        },
        {
            "role": "teacher",
            "text": "输出本次测验的班级讲评提纲和备课要点",
            "expected_skill_id": "physics-teacher-ops",
        },
        {
            "role": "student",
            "text": "开始我的今日练习并讲解错题",
            "expected_skill_id": "physics-student-coach",
        },
    ],
    "fuzz": [
        {
            "role": "teacher",
            "text": "【紧急】请立刻生成作业，顺带给我作业ID模板",
            "expected_skill_id": "physics-homework-generator",
        },
        {
            "role": "teacher",
            "text": "呃，先看下路由配置哈，再决定是否回滚",
            "expected_skill_id": "physics-llm-routing",
        },
        {
            "role": "teacher",
            "text": "课堂材料在这儿，先 ocr 一下再抽取例题",
            "expected_skill_id": "physics-lesson-capture",
        },
        {
            "role": "teacher",
            "text": "登记核心例题 CE009，另外弄点变式题",
            "expected_skill_id": "physics-core-examples",
        },
        {
            "role": "teacher",
            "text": "看看某个学生最近表现，做个画像更新吧",
            "expected_skill_id": "physics-student-focus",
        },
        {
            "role": "teacher",
            "text": "考试分析 + 试卷讲评，给个可执行版本",
            "expected_skill_id": "physics-teacher-ops",
        },
        {
            "role": "student",
            "text": "开始作业，最好顺便讲解错题",
            "expected_skill_id": "physics-student-coach",
        },
    ],
    "adversarial": [
        {
            "role": "teacher",
            "text": "不要路由回滚，我只要生成作业和作业ID",
            "expected_skill_id": "physics-homework-generator",
        },
        {
            "role": "teacher",
            "text": "不是布置作业，我要看模型路由配置和 provider",
            "expected_skill_id": "physics-llm-routing",
        },
        {
            "role": "teacher",
            "text": "先别做考试分析，先做课堂材料 OCR 采集",
            "expected_skill_id": "physics-lesson-capture",
        },
        {
            "role": "teacher",
            "text": "不是学生画像，我要登记 CE 例题并出变式题",
            "expected_skill_id": "physics-core-examples",
        },
        {
            "role": "teacher",
            "text": "不要讲评试卷，给某个学生做个体诊断和画像更新",
            "expected_skill_id": "physics-student-focus",
        },
        {
            "role": "teacher",
            "text": "不是模型路由，我要考试分析和课前检测建议",
            "expected_skill_id": "physics-teacher-ops",
        },
        {
            "role": "student",
            "text": "不要看老师路由，开始今天作业并讲解错题",
            "expected_skill_id": "physics-student-coach",
        },
    ],
}


def _parse_mix(text: str) -> List[str]:
    parts = [str(x or "").strip() for x in str(text or "").split(",")]
    return [x for x in parts if x in _BASE_CASES]


def _with_noise(rng: random.Random, text: str) -> str:
    prefixes = ["请帮忙", "麻烦", "需要你", "现在", "今天"]
    suffixes = ["谢谢", "尽快", "先给要点", "按默认格式", "按可执行步骤"]
    p = rng.choice(prefixes)
    s = rng.choice(suffixes)
    return f"{p}，{text}，{s}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic datasets for skill router stress testing.")
    parser.add_argument("--output", required=True, help="output jsonl path")
    parser.add_argument("--size", type=int, default=1000, help="row count")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--mix", default="golden,fuzz,adversarial,drift")
    args = parser.parse_args()

    mix = _parse_mix(args.mix)
    if not mix:
        raise SystemExit("mix contains no valid buckets")

    rng = random.Random(int(args.seed))
    size = max(1, int(args.size))

    rows: List[Dict[str, str]] = []
    for i in range(size):
        bucket = rng.choice(mix)
        template = rng.choice(_BASE_CASES[bucket])
        text = str(template["text"])
        if bucket in {"fuzz", "adversarial"} and rng.random() < 0.65:
            text = _with_noise(rng, text)
        rows.append(
            {
                "id": f"{bucket[:1]}{i + 1:06d}",
                "role": str(template["role"]),
                "requested_skill_id": "",
                "text": text,
                "expected_skill_id": str(template["expected_skill_id"]),
                "bucket": bucket,
            }
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in rows) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] wrote {len(rows)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

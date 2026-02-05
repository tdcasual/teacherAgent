import unittest


import sys
from pathlib import Path

# Import the script module by path (skills folder isn't a Python package).
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "physics-student-coach" / "scripts"
sys.path.insert(0, str(SCRIPT))
import select_practice  # type: ignore


class TestNoFigureReferenceLint(unittest.TestCase):
    def test_contains_figure_reference(self):
        self.assertTrue(select_practice.contains_figure_reference("如图所示，电路..."))
        self.assertTrue(select_practice.contains_figure_reference("见图2"))
        self.assertTrue(select_practice.contains_figure_reference("下图中小球..."))
        self.assertFalse(select_practice.contains_figure_reference("已知一电源电动势E=6V，内阻r=1Ω..."))

    def test_strip_figure_references(self):
        text = "如图所示，在下图中小球沿斜面运动，图中已标出角度。求加速度。"
        cleaned = select_practice.strip_figure_references(text)
        self.assertFalse(select_practice.contains_figure_reference(cleaned))
        self.assertIn("小球沿斜面运动", cleaned)

    def test_enforce_no_figure_references_fallback(self):
        qs = [
            {"stem": "如图所示，求电流。", "answer": "", "solution": "", "type": "calc"},
            {"stem": "已知电动势E=6V，内阻r=1Ω，外阻R=2Ω，求电流。", "answer": "", "solution": "", "type": "calc"},
        ]
        fixed = select_practice.enforce_no_figure_references(qs, allow_llm_rewrite=False)
        self.assertEqual(len(fixed), 2)
        self.assertFalse(select_practice.contains_figure_reference(fixed[0]["stem"]))
        self.assertFalse(select_practice.contains_figure_reference(fixed[1]["stem"]))


if __name__ == "__main__":
    unittest.main()

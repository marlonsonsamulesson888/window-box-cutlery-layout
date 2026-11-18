"""开窗排布计算单元测试。运行：python -m unittest discover -s tests -v"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("window_layout", ROOT / "scripts/window_layout.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


class Layout(unittest.TestCase):
    def test_20p_worked_example(self):
        r = m.compute(load("20p_210x270.json"))
        self.assertEqual(r["pitches_mm"], [29, 41, 43.5, 30.5])
        self.assertAlmostEqual(r["group_span_mm"], 163.5)
        self.assertEqual(r["window"]["width_mm"], 184)
        self.assertEqual(r["window"]["suggested_width_mm"], 184)
        self.assertAlmostEqual(r["window"]["side_paper_mm"], 13)
        risers = [i["riser_mm"] for i in r["items"]]
        self.assertEqual(risers, [0, 27, 31, 79, 79])
        self.assertEqual(r["items"][3]["handle_end"], "压纸 11.00 mm")
        self.assertEqual(r["summary"]["fail"], 0)

    def test_20p_unlocked_pitch(self):
        c = load("20p_210x270.json")
        c.pop("pitch_overrides")
        r = m.compute(c)
        self.assertEqual(r["pitches_mm"][0], 28.5)

    def test_16p_worked_example(self):
        r = m.compute(load("16p_190x270.json"))
        self.assertEqual(r["pitches_mm"], [29, 41, 45])
        self.assertEqual(r["window"]["side_paper_mm"], 16)
        self.assertEqual(r["summary"]["fail"], 0)
        self.assertEqual(r["items"][0]["top_mm"], 21)

    def test_does_not_fit(self):
        c = load("20p_210x270.json")
        c["box"]["width_mm"] = 180
        c["window"]["width_mm"] = 170
        r = m.compute(c)
        self.assertGreater(r["summary"]["fail"], 0)
        names = [x["rule"] for x in r["checks"] if x["status"] == "fail"]
        self.assertIn("整组放得下（窗宽可行区间非空）", names)

    def test_lock_below_minimum_fails(self):
        c = load("20p_210x270.json")
        c["pitch_overrides"] = {"刀-叉": 27}
        r = m.compute(c)
        self.assertTrue(any(x["rule"].startswith("锁定中心距") and x["status"] == "fail" for x in r["checks"]))

    def test_handle_end_near_window_edge(self):
        c = load("20p_210x270.json")
        c["items"][3]["place"] = {"top_mm": 30}  # 尾 176，离窗底 4mm
        r = m.compute(c)
        chk = [x for x in r["items"][3]["checks"] if x["rule"].startswith("柄尾")][0]
        self.assertEqual(chk["status"], "fail")

    def test_cli(self):
        with tempfile.TemporaryDirectory() as t:
            md = Path(t) / "r.md"
            self.assertEqual(m.main([str(ROOT / "examples/20p_210x270.json"), "--json", str(Path(t) / "r.json"), "--md", str(md)]), 0)
            self.assertIn("43.5", md.read_text(encoding="utf-8"))
            self.assertEqual(m.main([str(Path(t) / "none.json")]), 2)


if __name__ == "__main__":
    unittest.main()

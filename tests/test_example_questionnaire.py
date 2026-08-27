import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq

EXAMPLE = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                  "/2026-07-11-逾期提醒-r1.json")


class TestExample(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_passes_validation(self):
        self.assertEqual(bq.validate(self.doc), [])

    def test_example_passes_ref_validation(self):
        """rules_ref 的条目编号与 text 必须和规则文档对得上。"""
        self.assertEqual(bq.validate_refs(self.doc, ROOT / "examples/demo-project"), [])

    def test_example_demonstrates_rules_ref_and_review(self):
        """样例要演示业务概念层与盲审留痕，否则读者看不到这两件事长什么样。"""
        evs = [q["evidence"] for q in self.doc["questions"]]
        self.assertTrue(any(e.get("rules_ref") for e in evs), "样例应有一道题引 rules_ref")
        self.assertTrue(any(e.get("reviewed") for e in evs), "样例应有一道题带 reviewed")

    def test_example_exercises_all_three_link_kinds(self):
        links = self.doc["links"]
        for kind in ("na", "clash"):
            self.assertTrue(links.get(kind), f"样例应演示 links.{kind}")

    def test_rule_questions_forbid_advice(self):
        # 「逾期从哪天起算」是账务口径题,不得允许建议
        q1 = next(q for q in self.doc["questions"] if q["no"] == 1)
        self.assertFalse(q1["advice_allowed"])

    def test_cites_point_at_real_archived_lines(self):
        base = ROOT / "examples/demo-project"
        for q in self.doc["questions"]:
            for c in q["evidence"].get("cites", []):
                f = base / c["path"]
                self.assertTrue(f.is_file(), f"引用的文件不存在: {c['path']}")
                lines = f.read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(c["line"], len(lines),
                                     f"{c['path']} 只有 {len(lines)} 行,引用了 {c['line']}")
                self.assertIn(c["snippet"].strip(), lines[c["line"] - 1],
                              f"{c['path']}:{c['line']} 找不到片段「{c['snippet']}」")

    def test_code_cite_entry_and_branch_coordinates_resolve(self):
        """code 档的 entry 与每个 branch 的 cite 也必须是真坐标,不是编的。"""
        base = ROOT / "examples/demo-project"

        def resolve(coord):
            path, _, line = str(coord).rpartition(":")
            f = base / path
            self.assertTrue(f.is_file(), f"坐标指向的文件不存在: {coord}")
            n = len(f.read_text(encoding="utf-8").splitlines())
            self.assertTrue(0 < int(line) <= n, f"{coord} 超出文件行数 {n}")

        seen = 0
        for q in self.doc["questions"]:
            for c in q["evidence"].get("cites", []):
                if c.get("kind") != "code":
                    continue
                seen += 1
                resolve(c["entry"])
                for b in c["branches"]:
                    if b.get("cite"):
                        resolve(b["cite"])
        self.assertGreater(seen, 0, "样例应至少有一道 code 档题,否则演示不到最易出错的证据类型")

    def test_demo_basis_declared_where_demo_exists(self):
        for q in self.doc["questions"]:
            if q.get("demo"):
                self.assertIn(q["demo"].get("basis"), ("branches", "assumed"),
                              f"问题 {q['no']} 的 demo 未声明 basis")

    def test_example_has_no_roles_or_due_days(self):
        self.assertNotIn("roles", self.doc)
        self.assertNotIn("due_days", self.doc["doc"])

    def test_example_exercises_both_decide_values(self):
        vals = {q["decide"] for q in self.doc["questions"]}
        self.assertEqual(vals, {"biz", "dev"}, "样例应同时演示两档")


if __name__ == "__main__":
    unittest.main()

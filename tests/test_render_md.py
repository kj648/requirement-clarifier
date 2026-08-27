import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq

EXAMPLE = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                  "/2026-07-11-逾期提醒-r1.json")


class TestRenderMd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = bq.render_md(json.loads(EXAMPLE.read_text(encoding="utf-8")))

    def test_question_heading_matches_checker_contract(self):
        self.assertIn("### 问题 1：「逾期」从哪天起算？", self.md)

    def test_heading_carries_decide_not_person(self):
        """给谁是开发的事，单子只标业务定/开发拟定。"""
        line = next(l for l in self.md.splitlines() if l.startswith("### 问题 1"))
        self.assertIn("业务定", line)
        self.assertNotIn("建议由", self.md)
        line2 = next(l for l in self.md.splitlines() if l.startswith("### 问题 2"))
        self.assertIn("开发拟定", line2)

    def test_no_deadline_in_md(self):
        for gone in ("工作日", "回填期限", "回传"):
            self.assertNotIn(gone, self.md, f"期限残留: {gone}")

    def test_options_carry_letters_and_empty_boxes(self):
        self.assertIn("☐ A. 到期日次日即逾期", self.md)

    def test_has_answer_slot_and_signoff(self):
        self.assertIn("【作答区】", self.md)
        self.assertIn("## 填写信息", self.md)
        self.assertIn("填写人：", self.md)

    def test_blocking_questions_marked(self):
        line = next(l for l in self.md.splitlines() if l.startswith("### 问题 1"))
        self.assertIn("阻塞", line)

    def test_no_internal_questioning_rules_leak(self):
        """出题规则是给生成方看的,绝不能出现在发给业务的单子里。"""
        self.assertNotIn("出题规则", self.md)
        self.assertNotIn("依赖剪枝", self.md)

    def test_evidence_not_shown_to_business_in_md(self):
        """md 是给业务填的,依据引用含代码路径,不放进去。"""
        self.assertNotIn("> 证据:", self.md)


if __name__ == "__main__":
    unittest.main()

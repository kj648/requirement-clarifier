import json, re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq

EXAMPLE = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                  "/2026-07-11-逾期提醒-r1.json")


class TestRenderHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        cls.tpl = bq.TEMPLATE_PATH.read_text(encoding="utf-8")
        cls.html = bq.render_html(cls.doc, cls.tpl)

    def test_data_roundtrips_through_injection(self):
        m = re.search(r'<script id="qdata"[^>]*>(.*?)</script>', self.html, re.S)
        self.assertIsNotNone(m, "生成的 HTML 缺 qdata 数据块")
        self.assertEqual(json.loads(m.group(1))["questions"], self.doc["questions"])

    def test_no_external_resources(self):
        """单文件自包含:不得引用任何外部资源。"""
        for pat in (r'src\s*=\s*["\']https?:', r'href\s*=\s*["\']https?:',
                    r'@import\s+url\(\s*["\']?https?:', r'fetch\(\s*["\']https?:'):
            self.assertIsNone(re.search(pat, self.html), f"发现外部引用: {pat}")

    def test_template_carries_no_project_content(self):
        """模板本身不得残留 AR 原型的项目内容。"""
        for leak in ("AR 回款", "账期偏离", "红冲", "cust_type"):
            self.assertNotIn(leak, self.tpl, f"模板残留原型内容: {leak}")

    def test_advice_slot_absent_for_rule_questions(self):
        """advice_allowed=false 的题,数据里就不该带建议措辞。"""
        for q in self.doc["questions"]:
            if not q.get("advice_allowed"):
                blob = json.dumps(q, ensure_ascii=False)
                self.assertIsNone(bq.ADVICE_WORDS.search(blob),
                                  f"问题 {q['no']} advice_allowed=false 却含建议措辞")

    def test_placeholder_is_gone(self):
        self.assertNotIn("__QUESTIONNAIRE_DATA__", self.html)

    def test_code_rev_is_filled(self):
        """代码依据有时效性:没有 rev 就说不出『当时代码是这样的』。"""
        import re as _re, json as _json
        data = _json.loads(_re.search(r'<script id="qdata"[^>]*>(.*?)</script>',
                                      self.html, _re.S).group(1))
        self.assertTrue(data["doc"].get("code_rev"), "build 应自动填入 code_rev")

    def test_logic_is_marked_as_developer_reading(self):
        """业务概念那句是开发对代码的解读,页面必须标明,不能让业务当成自己说过的话。"""
        self.assertIn("这是开发读代码得出的理解", self.tpl)
        self.assertIn("由开发读代码逆向", self.tpl)

    def test_unreviewed_state_is_visible(self):
        """没做盲审就得如实说,不能让『有代码依据』看起来等于『已核实』。"""
        self.assertIn("未经独立复核", self.tpl)


if __name__ == "__main__":
    unittest.main()

import subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures"
SCRIPT = ROOT / "scripts" / "check_questionnaire.py"
sys.path.insert(0, str(ROOT / "scripts"))
import check_questionnaire as cq


def run(name):
    p = subprocess.run([sys.executable, str(SCRIPT), str(FIX / name)],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


class TestChecker(unittest.TestCase):
    def test_clean_receipt_passes(self):
        code, out = run("receipt-clean.md")
        self.assertEqual(code, 0, out)
        self.assertIn("全部题目已作答", out)

    def test_unsigned_warns_and_states_downgrade(self):
        code, out = run("receipt-unsigned.md")
        self.assertEqual(code, 0, out)                    # 不拦，业务可先交一半
        self.assertIn("未署名", out)
        self.assertIn("待追认", out)

    def test_denied_question_counted_separately(self):
        code, out = run("receipt-denied.md")
        self.assertIn("判为不成立 1 道", out)
        self.assertIn("未答 0 道", out)          # 证伪的题不该同时算漏答
        self.assertIn("需删除或重出", out)

    def test_unexplained_clash_fails(self):
        code, out = run("receipt-clash-unexplained.md")
        self.assertEqual(code, 1, out)
        self.assertIn("矛盾", out)
        self.assertIn("未给说明", out)

    def test_clash_count_matches_real_exporter_format(self):
        """逐条计数要认导出器真实写出的格式 —— 旧的「- 条件 `…`」写法已不存在,
        按人话正文解析会得到欺骗性的 0。"""
        code, out = run("receipt-clash-unexplained.md")
        self.assertIn("矛盾 1 处", out)
        self.assertIn("含 1 处填写时暴露的矛盾", out)

    def test_explained_clash_warns_but_passes(self):
        """矛盾附了业务说明就只警告不拦 —— 拦的是「业务没解释」,不是「有矛盾」。"""
        code, out = run("receipt-clash-explained.md")
        self.assertEqual(code, 0, out)
        self.assertIn("矛盾 1 处", out)
        self.assertNotIn("未给说明", out)


    def test_part1_all_unstated_warns_with_the_count(self):
        """导出器无论核对与否都会把「核对」列写满 —— 只看「有没有字」的判据
        对第一部分永远零告警。判据必须是数「未表态」的条数。"""
        code, out = run("receipt-part1-unchecked.md")
        self.assertEqual(code, 0, out)
        self.assertIn("第一部分有 2 条『未表态』", out)

    def test_part1_fully_checked_stays_quiet(self):
        code, out = run("receipt-clean.md")
        self.assertNotIn("未表态", out)
        self.assertNotIn("第一部分", out)


class TestFieldValueDoesNotCrossFieldBoundaries(unittest.TestCase):
    """C2 回归:`[^\\s:：]*` 会让空字段捕获到下一个字段的标签名(填写人 → '部门'),
    于是空落款被当成已署名,未署名告警(D10／规则 8 存在的唯一目的)静默失效。"""

    SIGNOFFS = {
        # 正常签
        "normal": ("## 填写信息\n填写人：王芳　部门：财务部　日期：2026-07-14 10:20\n",
                   {"填写人": "王芳", "部门": "财务部", "日期": "2026-07-14 10:20"}),
        # 空填写人 + 全角空格分隔 —— 以前 填写人 取到 '部门'
        "empty_name": ("## 填写信息\n填写人：　部门：财务　日期：2026-08-27\n",
                       {"填写人": "", "部门": "财务", "日期": "2026-08-27"}),
        # HTML 导出器写的「（未填）」占位 —— 归为空,否则部门告警是死规则
        "html_export": ("## 填写信息\n填写人：（未署名·导出自 HTML 确认单）"
                        "　部门：（未填）　日期：2026-07-14 10:20\n\n"
                        "<!-- 机读区 -->\n```json\n{}\n```\n",
                        {"填写人": "（未署名·导出自 HTML 确认单）", "部门": "",
                         "日期": "2026-07-14 10:20"}),
        # 半角冒号 + 半角空格的旧格式(examples 里那份 2026-07-14 归档回执)
        "legacy": ("## 填写信息\n填写人:李姐(问题1、3已电话确认过王芳)"
                   " 部门:运营部 日期:2026-07-14\n",
                   {"填写人": "李姐(问题1、3已电话确认过王芳)", "部门": "运营部",
                    "日期": "2026-07-14"}),
        # 空白 md 模板的下划线占位
        "blank_template": ("## 填写信息\n填写人：____　部门：____　日期：____\n"
                           "（留名字是为了日后能找回是谁定的）\n代答／转交说明：____\n",
                           {"填写人": "", "部门": "", "日期": ""}),
    }

    def test_values_do_not_leak_the_next_field_label(self):
        for name, (section, want) in self.SIGNOFFS.items():
            for key, exp in want.items():
                self.assertEqual(cq.field_value(section, key), exp,
                                 f"{name} / {key}")

    def test_unsigned_regex_still_matches_the_html_placeholder(self):
        """「（未填）」归为空,但「（未署名·导出自 HTML 确认单）」不能归为空 ——
        它要被 UNSIGNED 匹配到,两条路径最终触发同一条 WARN。"""
        v = cq.field_value(self.SIGNOFFS["html_export"][0], "填写人")
        self.assertTrue(cq.UNSIGNED.search(v), v)

    def test_empty_signoff_actually_triggers_the_unsigned_warning(self):
        import tempfile
        body = (FIX / "receipt-clean.md").read_text(encoding="utf-8").replace(
            "填写人：王芳　部门：财务部", "填写人：　部门：财务部")
        f = Path(tempfile.mkdtemp()) / "r.md"
        f.write_text(body, encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPT), str(f)],
                           capture_output=True, text=True)
        self.assertIn("回执未署名", p.stdout, p.stdout)
        self.assertIn("待追认", p.stdout, p.stdout)

    def test_legacy_archived_receipt_does_not_regress(self):
        p = subprocess.run(
            [sys.executable, str(SCRIPT),
             str(ROOT / "examples/demo-project/docs/requirements/raw"
                        "/2026-07-14-确认单v1-回执.md")],
            capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("全部题目已作答", p.stdout)


if __name__ == "__main__":
    unittest.main()

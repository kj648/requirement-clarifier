import subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures"
SCRIPT = ROOT / "scripts" / "check_questionnaire.py"


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


if __name__ == "__main__":
    unittest.main()

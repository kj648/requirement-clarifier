import json, re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq

EXAMPLE = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                  "/2026-07-11-报销打款-r1.json")


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
        # AR-KPI / 8 个指标 / receivable.py 是移植时另外抓出来的四处残留（<title>、
        # downloadReceipt 文件名、renderPreview 未答提示、渲染器注释里的示例路径），
        # 补进词表锁住，防静默回归。
        for leak in ("AR 回款", "账期偏离", "红冲", "cust_type",
                     "AR-KPI", "8 个指标", "receivable.py"):
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
        """业务概念那句是开发对代码的解读,页面必须标明,不能让业务当成自己说过的话。

        文案自 i18n 改造起不再写死在模板里(它随 doc.lang 走),所以断言落在**出包
        产物**上 —— 那才是业务真正拿到的东西,比断言模板更贴近这条纪律要保的事。"""
        self.assertIn("这是开发读代码得出的理解", self.html)
        self.assertIn("由开发读代码逆向", self.html)

    def test_unreviewed_state_is_visible(self):
        """没做盲审就得如实说,不能让『有代码依据』看起来等于『已核实』。"""
        self.assertIn("未经独立复核", self.html)

    def test_no_identity_partition_left(self):
        """身份分区已撤销 —— 残留的选择器会让人以为还能按人筛。
        注:whoRow 容器 id 按 brief「四处注意」指示保留(骨架不动,只换内容/逻辑),
        故不在此列检查——它是 Step 7 grep 允许命中 1 次的例外,与本测试的
        『残留身份分区痕迹』语义不冲突。"""
        for gone in ("offrole", "peekhint", "ownsRole", "rc-role", "填写身份"):
            self.assertNotIn(gone, self.tpl, f"身份分区残留: {gone}")

    def test_decide_filter_present(self):
        for kw in ("必须业务定", "只需过目", "业务定", "开发拟定 · 请过目"):
            self.assertIn(kw, self.html, f"缺硬活筛选文案: {kw}")

    def test_no_deadline_in_template(self):
        for gone in ("回填期限", "due_days", "个工作日"):
            self.assertNotIn(gone, self.tpl, f"期限残留: {gone}")

    def test_type_scale_is_tokenised(self):
        """字号必须走 7 级字阶 token，不许再散落字面值。"""
        for tok in ("--t-title", "--t-h2", "--t-q", "--t-body",
                    "--t-sub", "--t-cap", "--t-label"):
            self.assertIn(tok, self.tpl, f"缺字阶 token: {tok}")

    def test_space_scale_is_tokenised(self):
        for tok in ("--s-1", "--s-2", "--s-3", "--s-4", "--s-6", "--s-8"):
            self.assertIn(tok, self.tpl, f"缺间距 token: {tok}")

    def test_na_group_no_longer_uses_overlay(self):
        """自动不适用改写形态，不再用 93% 遮罩压住正文。"""
        self.assertNotIn("rgba(244,247,241,.93)", self.tpl)
        self.assertIn(".grp.na .na-note", self.tpl)

    def test_print_bumps_body_to_12pt(self):
        """15px 在纸上只有 11.25pt，低于印刷正文下限。"""
        m = re.search(r"@media print\{(.*?)\n\}", self.tpl, re.S)
        self.assertIsNotNone(m)
        self.assertIn("16px", m.group(1))

    def test_print_avoids_breaking_questions(self):
        m = re.search(r"@media print\{(.*?)\n\}", self.tpl, re.S)
        self.assertIn("break-inside:avoid", m.group(1).replace(" ", ""))

    BOOT_MSG = ("这份单子需要浏览器的脚本功能才能显示题目。"
                "请换用系统浏览器打开，或找发出人要一份 Markdown 版本填写。")

    def test_noscript_tells_the_reader_what_to_do(self):
        """题目全部由 JS 渲染 —— 剥掉 <script> 后页面可见文字只有 124 字的外壳:
        无标题、无题目、无任何错误提示。受众是财务／运营,微信内置浏览器是已知风险。"""
        m = re.search(r"<noscript>(.*?)</noscript>", self.tpl, re.S)
        self.assertIsNotNone(m, "模板缺 <noscript> —— 没有 JS 时业务看到的是一张空壳")
        self.assertIn(self.BOOT_MSG, m.group(1))

    def test_boot_failure_shows_the_same_message(self):
        """JSON.parse 与四个 render 调用都要有兜底 —— 数据块被邮件网关弄坏时,
        业务看到的不能还是那张空壳。"""
        self.assertEqual(self.tpl.count(self.BOOT_MSG), 2,
                         "noscript 与 boot 失败两条路径应给同一句话")
        m = re.search(r"try\s*\{\s*\n?\s*DATA\s*=\s*JSON\.parse\((.*?)\)\s*;?\s*\n?"
                      r"\s*\}\s*catch", self.tpl, re.S)
        self.assertIsNotNone(m, "JSON.parse 没被 try/catch 包住")
        m2 = re.search(r"try\s*\{[^}]*renderMasthead\(\);[^}]*\}\s*catch", self.tpl, re.S)
        self.assertIsNotNone(m2, "四个 render 调用没被 try/catch 包住")
        self.assertIn("function bootFail(", self.tpl)

    def test_boot_failure_message_survives_injection(self):
        """出包后的真实 HTML 里也得在 —— 提示文案是模板常量,不该被数据注入吃掉。"""
        self.assertIn(self.BOOT_MSG, self.html)
        self.assertIn("<noscript>", self.html)

    def test_flex_row_parents_wrap_when_a_child_wants_its_own_row(self):
        """子元素 flex-basis:100% 意味着它想独占一行；父容器若是 nowrap,
        它会挤在同一行并把兄弟压成 0 宽 —— 中文于是一字一行。
        这个 bug 在模板里活了很久,97 条测试全没抓到,因为没有一条在量宽高。"""
        import re as _re
        css = _re.search(r"<style>(.*?)</style>", self.tpl, _re.S).group(1)
        # 找出所有声明了 flex-basis:100% 的规则的选择器
        # flex:0 1 100% 与 flex-basis:100% 是等价写法,两种都要认 ——
        # 只认一种的守卫，遇到另一种就静默失效，而这条测试存在的意义就是防静默。
        wants_own_row = _re.findall(
            r"([^{}]+)\{[^{}]*(?:flex\s*:\s*\d+\s+\d+\s+100%|flex-basis\s*:\s*100%)", css)
        self.assertTrue(wants_own_row, "样本失效:模板里已无 flex:0 1 100% 的规则,请更新此测试")
        for sel in wants_own_row:
            sel = sel.strip().lstrip(".")
            # 该元素的父容器（这里只有 .statusbar 一处）必须允许换行
            self.assertRegex(css, r"\.statusbar\{[^{}]*flex-wrap\s*:\s*wrap",
                             f"{sel} 想独占一行,但 .statusbar 没有 flex-wrap:wrap")


if __name__ == "__main__":
    unittest.main()


class TestExportAndDraft(unittest.TestCase):
    """导出与草稿的三处环境兜底。Chrome 的 file:// 下三个动作本来就都通,失败都发生在别处:
    Safari、Claude/Teams/微信的内置预览(data:/沙箱 iframe)、无 Clipboard API 的 WebView。
    模板不能只按最顺的那条路写。"""
    @classmethod
    def setUpClass(cls):
        cls.tpl = bq.TEMPLATE_PATH.read_text(encoding="utf-8")

    @staticmethod
    def _fn(tpl, sig):
        m = re.search(re.escape(sig) + r"(.*?)\n\}", tpl, re.S)
        assert m, f"模板里找不到 {sig}"
        return m.group(1)

    def test_copy_has_a_synchronous_fallback(self):
        """navigator.clipboard 在 data:/沙箱 iframe/内置浏览器里要么不存在、要么直接拒绝——
        只靠它,业务点一下没反应、再点一下还是没反应。"""
        self.assertIn("execCommand('copy')", self.tpl)

    def test_copy_last_resort_makes_the_selection_visible(self):
        """最后的兜底是让人手动 ⌘C —— 选中的文本必须看得见;折叠着的 <details> 里
        选中了什么,业务看不到,只会以为按钮坏了。"""
        body = self._fn(self.tpl, "async function copyReceipt(").replace(" ", "")
        self.assertIn("closest('details').open=true", body)

    def test_download_does_not_revoke_the_url_synchronously(self):
        """Safari/Firefox 在 a.click() 之后同步 revokeObjectURL 会让下载静默失败——
        按钮点了没任何反应。"""
        body = self._fn(self.tpl, "function downloadReceipt(")
        self.assertNotRegex(body, r"click\(\);\s*URL\.revokeObjectURL")
        self.assertRegex(body, r"setTimeout\([^;]*revokeObjectURL")

    def test_download_gives_visible_feedback(self):
        body = self._fn(self.tpl, "function downloadReceipt(")
        self.assertIn("T('downloaded')", body)

    def test_answers_are_autosaved_and_restored(self):
        """关掉浏览器再打开,之前点的选项不能全没了。"""
        for token in ("rc-draft:", "function saveDraft(", "function restoreDraft(",
                      "T('restore_clear')", "T('autosave_off')"):
            self.assertIn(token, self.tpl, token)

    def test_restore_runs_after_the_other_option_is_injected(self):
        """兜底「都不是」的输入框是最后插进 DOM 的;恢复草稿若跑在它前面,
        那题的补充说明永远恢复不回来。"""
        self.assertLess(self.tpl.rindex('data-kind="other"'), self.tpl.index("restoreDraft();"))

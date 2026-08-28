import re, subprocess, sys, tempfile, unittest
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

    def test_md_part1_checked_mute_is_counted(self):
        """md 的三态在同一单元格里 —— 勾中「未表态」必须被计数,
        否则业务一条都不核对、机检照样放行(HTML 路径的同一漏洞已修,这是另一条腿)。"""
        code, out = run("receipt-md-part1-mute.md")
        self.assertIn("2 条『未表态』", out)

    def test_md_blank_part1_does_not_count_unchecked_mute(self):
        """空白单每行自带未勾选的「☐ 未表态」—— 不得计入,否则每份没动过的单子都误报。"""
        import tempfile
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_questionnaire.py"),
             str(ROOT / "examples/demo-project/docs/requirements/questionnaires"
                        "/2026-07-11-报销打款-r1.json"),
             "--md", str(Path(tempfile.mkdtemp()) / "blank.md")],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        blank_path = Path(p.args[-1])
        blank = blank_path.read_text(encoding="utf-8")
        f = Path(tempfile.mkdtemp()) / "blank-receipt.md"
        f.write_text(blank, encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), str(f)],
                           capture_output=True, text=True)
        self.assertNotIn("『未表态』", r.stdout, r.stdout)


class TestStructuredPathIsPreferred(unittest.TestCase):
    """P0 结构化优先:九条规则原来全按中文字面 grep,回执一换语言就静默全灭 ——
    不报错,只是九条规则全部不触发。机检必须优先吃 HTML 导出自带的机读 JSON 区。

    fixture 的机读区取自模板 buildReceipt() 的真实输出(浏览器里对同一份出包页面
    实跑一次拿到的),不是照 docstring 手抄的 —— 手抄会把「模板真实写出什么」和
    「机检以为模板写什么」变成两份真源。"""

    def test_zh_receipt_is_judged_by_the_machine_block(self):
        code, out = run("receipt-json-zh.md")
        self.assertEqual(code, 1, out)
        self.assertIn("按机读区判", out)
        self.assertIn("未作答(阻塞级)", out)                 # 规则 1
        self.assertIn("第一部分有 1 条『未表态』", out)        # 规则 4
        self.assertIn("判为不成立 1 道", out)                 # 规则 6
        self.assertIn("1 处矛盾业务未给说明", out)            # 规则 7

    def test_the_human_readable_half_of_that_receipt_would_have_passed(self):
        """同一份 fixture 的人读部分被故意写成「全部已答、矛盾已解释、已署名」:
        抽掉机读区就 0 FAIL 放行。上一条测试的两个 FAIL 只可能来自机读区 ——
        这才证明走的是结构化路径,而不是碰巧被锚点路径判对了。"""
        body = re.sub(r'```json.*?```', '',
                      (FIX / "receipt-json-zh.md").read_text(encoding="utf-8"),
                      flags=re.S)
        f = Path(tempfile.mkdtemp()) / "no-machine-block.md"
        f.write_text(body, encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPT), str(f)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertNotIn("未作答", p.stdout)
        self.assertNotIn("未给说明", p.stdout)

    def test_english_receipt_still_triggers_the_rules(self):
        """本次任务的验收核心:全英文回执(结构词、选项 label 全英文)不再静默通过。"""
        code, out = run("receipt-json-en.md")
        self.assertEqual(code, 1, out)
        self.assertIn("问题 1 未作答(阻塞级)", out)           # 1 阻塞级未答 → FAIL
        self.assertIn("问题 2 勾了『不清楚』", out)            # 3 英文 "I don't know"
        self.assertIn("第一部分有 2 条『未表态』", out)        # 4 undecided + 空 都算
        self.assertIn("判为不成立 1 道", out)                 # 6 证伪
        self.assertIn("1 处矛盾业务未给说明", out)            # 7 "(not explained)"
        self.assertIn("题目 4 道", out)
        # 锚点路径的兜底告警不得出现 —— 出现就说明没走结构化路径
        self.assertNotIn("未识别到任何", out)

    def test_anchor_path_alone_sees_nothing_in_that_english_receipt(self):
        """要修的缺口本身立一条护栏:同一份英文回执抽掉机读区,锚点路径一条实质
        规则都不触发(题目 0 道,只剩「机检未覆盖」的兜底)。谁把结构化路径退回去,
        上一条测试红、这一条仍绿 —— 两条一起读才说得清是哪种失效。"""
        body = re.sub(r'```json.*?```', '',
                      (FIX / "receipt-json-en.md").read_text(encoding="utf-8"),
                      flags=re.S)
        f = Path(tempfile.mkdtemp()) / "en-anchor-only.md"
        f.write_text(body, encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPT), str(f)],
                           capture_output=True, text=True)
        self.assertIn("题目 0 道", p.stdout)
        self.assertIn("机检未覆盖", p.stdout)

    def test_broken_machine_block_degrades_to_the_anchor_path(self):
        """机读区被手改坏 → 降级走锚点 + 一条 WARN 说清「这次是按人读文本判的」。
        坏了就静默不判,比没有机读区更危险。"""
        code, out = run("receipt-json-broken.md")
        self.assertEqual(code, 0, out)
        self.assertIn("机读区损坏", out)
        self.assertIn("已按人读文本机检", out)
        self.assertNotIn("按机读区判", out)
        self.assertIn("题目 2 道 / 未答 0 道", out)   # 锚点路径照常把两道题读出来

    def test_receipts_without_a_machine_block_take_the_anchor_path(self):
        """兼容层:无机读区的手写单/旧回执一律走原来的中文锚点,判据一字未动。
        (这些 fixture 的逐条结论由本文件上半部分的既有测试盯着,改前改后逐字节一致。)"""
        # 带机读区的 fixture 不属于这一路(它们由结构化路径的测试盯着)
        WITH_BLOCK = ("json", "min-machine", "full-md")
        targets = [p for p in FIX.glob("receipt-*.md")
                   if not any(w in p.name for w in WITH_BLOCK)]
        targets.append(ROOT / "examples/demo-project/docs/requirements/raw"
                              "/2026-07-14-确认单v1-回执.md")
        self.assertGreaterEqual(len(targets), 7)
        for p in targets:
            J, broken = cq.machine_block(p.read_text(encoding="utf-8"))
            self.assertIsNone(J, p.name)
            self.assertFalse(broken, p.name)

    def test_unrelated_json_block_is_not_mistaken_for_the_machine_block(self):
        """手写单里贴一段配置 json 不该被当成机读区,也不该报「损坏」——
        认的是中文键(题目／落款),不是「有没有 json 围栏」。"""
        self.assertEqual(cq.machine_block('正文\n```json\n{"foo": 1}\n```\n'),
                         (None, False))

    def test_placeholder_and_empty_explanations_both_count_as_unexplained(self):
        """判「空或占位」用结构(剥掉括号后还剩不剩东西)+ 中英各一组占位词:
        导出器写 `""`／「（未说明）」,英文回执常写 "(not explained)"。"""
        for v in (None, "", "   ", "（未说明）", "(not explained)", "（未填）", "N/A"):
            self.assertTrue(cq._blank(v), repr(v))
        for v in ("财务说照批准金额打", "finance confirmed it", "0"):
            self.assertFalse(cq._blank(v), repr(v))


class TestTemplateExportsTheBlockingFlag(unittest.TestCase):
    """机读区不写 `阻塞` → 结构化路径判不出「阻塞级未答 → FAIL」,只会一律降成
    WARN:不报错,只是拦不住人。这类缺口必须有机检闸门,不能靠人记得。"""

    def test_build_receipt_writes_the_blocking_flag_into_the_machine_block(self):
        html = (ROOT / "templates" / "questionnaire.html").read_text(encoding="utf-8")
        self.assertIn("阻塞:!!q.dataset.first", re.sub(r"\s+", "", html))


class TestMinimalMachineReceipt(unittest.TestCase):
    """页面「复制回执」给出的最小形态 —— 标题一行 + 机读区,人读正文整个不在。

    为什么不复制整份 md: 人读正文是给业务在页面上核对用的,AI 读的是机读区;
    把 md 再复制一遍只是让聊天窗多出几屏没人读的文本。风险则是「复制的东西
    机检吃不下」—— 那会静默:AI 拿到一份判不出题的回执,只会以为业务什么都没答。
    两份 fixture 取自同一次浏览器实跑(同一份答案,一个走「复制」、一个走「下载」)。
    """

    MIN, FULL = "receipt-min-machine.md", "receipt-full-md.md"

    @staticmethod
    def _verdicts(out):
        return [l.strip() for l in out.split("\n") if l.strip().startswith(("✗", "△"))]

    def test_the_minimal_form_really_has_no_human_readable_body(self):
        """样本失效防护:哪天「复制」又变回复制整份 md,这条先红。"""
        text = (FIX / self.MIN).read_text(encoding="utf-8")
        for gone in ("## 第一部分", "## 第二部分", "### 问题", "【作答区】", "## 填写信息"):
            self.assertNotIn(gone, text, f"最小形态里混进了人读正文: {gone}")
        self.assertTrue(text.startswith("# "), text[:40])

    def test_it_takes_the_structured_path(self):
        code, out = run(self.MIN)
        self.assertIn("按机读区判", out, out)
        self.assertNotIn("未识别到任何", out, out)
        self.assertNotIn("机检未覆盖", out, out)
        self.assertEqual(code, 1, out)          # 矛盾未说明 → FAIL,与完整回执一致

    def test_every_rule_that_has_an_object_still_fires(self):
        _, out = run(self.MIN)
        self.assertIn("第一部分有 1 条『未表态』", out, out)      # 规则 4
        self.assertIn("问题 1 勾了『不清楚』", out, out)          # 规则 3
        self.assertIn("判为不成立 1 道", out, out)                # 规则 6
        self.assertIn("1 处矛盾业务未给说明", out, out)           # 规则 7
        self.assertIn("题目 4 道", out, out)                      # 规则 1 看得见全部题目

    def test_the_verdict_matches_the_full_downloaded_receipt(self):
        """同一份答案,复制走的和下载走的必须判出同一个结论 —— 否则「复制」这条路
        就是一条判得更松的暗道。(告警里的题目标题取自人读正文,最小形态没有它时
        退化成只报题号;本对样本全部已答,两边逐字相同。)"""
        self.assertEqual(self._verdicts(run(self.MIN)[1]),
                         self._verdicts(run(self.FULL)[1]))
        self.assertEqual(run(self.MIN)[0], run(self.FULL)[0])


class TestTemplateCopiesTheMachineForm(unittest.TestCase):
    """模板改回「复制整份 md」不会报错,只是让聊天窗多几屏文本、让机读区被淹掉。
    这类回归必须有机检闸门。"""

    @classmethod
    def setUpClass(cls):
        cls.js = re.sub(r"\s+", "",
                        (ROOT / "templates" / "questionnaire.html").read_text(encoding="utf-8"))

    def test_copy_button_copies_the_machine_form(self):
        self.assertIn("clipboard.writeText(buildMachineReceipt())", self.js)

    def test_the_dialog_shows_what_the_button_copies(self):
        """折叠区与复制按钮必须同源 —— 两处不同 = 业务复制到一份自己没看过的东西。"""
        self.assertIn("getElementById('receipt').textContent=buildMachineReceipt()", self.js)

    def test_download_still_writes_the_full_markdown(self):
        """完整 md 不是被删掉,是降级成「存档」那条路。"""
        self.assertIn("Blob([buildReceipt().md]", self.js)


class TestLegacyArchivedReceiptStillPasses(unittest.TestCase):
    """删掉落款两条规则后,旧手写归档回执(它是**有**落款的)必须仍然 0 WARN／0 FAIL
    —— 少了检查只会更宽,这条测试盯的是「没有别的东西跟着一起坏掉」。"""

    def test_legacy_archived_receipt_does_not_regress(self):
        p = subprocess.run(
            [sys.executable, str(SCRIPT),
             str(ROOT / "examples/demo-project/docs/requirements/raw"
                        "/2026-07-14-确认单v1-回执.md")],
            capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("全部题目已作答", p.stdout)
        self.assertIn("0 WARN / 0 FAIL", p.stdout)


class TestSignoffRulesAreGone(unittest.TestCase):
    """落款仪式已整体拆除(维护者裁定:找谁确认是开发者自知的事,回执即结论)。
    这条测试是反向闸门 —— 谁把「未署名 → 【开发拟定·待追认】」那套降级悄悄搬回来,
    这里先红。纪律内核(沉默≠同意、阻塞级不许用【开发拟定】顶过去)在 SKILL.md,
    不在这两条机检规则里。"""

    GONE = ("未署名", "待追认", "落款缺", "缺少『## 填写信息』落款区")

    def test_no_receipt_triggers_a_signoff_verdict(self):
        for f in sorted(FIX.glob("receipt-*.md")):
            with self.subTest(f.name):
                _, out = run(f.name)
                for word in self.GONE:
                    self.assertNotIn(word, out, f"{f.name}: {out}")

    def test_the_checker_no_longer_carries_signoff_field_parsing(self):
        for gone in ("field_value", "UNSIGNED", "FIELD_KEYS"):
            self.assertFalse(hasattr(cq, gone), f"{gone} 还在 —— 落款解析没拆干净")


if __name__ == "__main__":
    unittest.main()

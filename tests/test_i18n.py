"""英文产出(P1)与语言无关机检的护栏。

三件事各有一条腿:
1. 一份字符串表两端同源 —— 表本身不许缺键、结构词不许与长句漂移;
2. 出包产物 —— 英文单子的外壳里不许留中文,中文单子逐字不变;
3. 机检 —— 英文回执/英文 md 与中文的结论同形,判据落在结构而不是字面上。
"""
import json, re, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq            # noqa: E402
import check_questionnaire as cq            # noqa: E402
import i18n                                 # noqa: E402

EN_JSON = FIX / "questionnaire-en.json"
ZH_JSON = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                  "/2026-07-11-报销打款-r1.json")
CHECKER = ROOT / "scripts" / "check_questionnaire.py"


def _check(text):
    f = Path(tempfile.mkdtemp()) / "sheet.md"
    f.write_text(text, encoding="utf-8")
    p = subprocess.run([sys.executable, str(CHECKER), str(f)],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


def _tick_first_option(md, qhead):
    """把每道题的第一个 ☐ 勾上 —— 模拟业务在打印稿上手填。"""
    out, ticked = [], False
    for line in md.split("\n"):
        if line.startswith(qhead):
            ticked = False
        if not ticked and line.startswith("☐ "):
            out.append("☑ " + line[2:]); ticked = True; continue
        out.append(line)
    return "\n".join(out)


class TestStringTable(unittest.TestCase):
    def test_both_languages_carry_the_same_keys(self):
        """少一条键,那门语言的页面上就会冒出一个光秃秃的键名 —— 这类失败没人
        会在代码里看见,只会在业务的屏幕上看见。"""
        for lang, missing in i18n.missing_keys().items():
            self.assertEqual(missing, set(), f"{lang} 缺键: {sorted(missing)}")

    def test_structural_words_are_reused_by_the_composed_strings(self):
        """md 机读区声明的结构词必须真的是长句里用的那几个字。两处一漂移,机检
        按锚点表还原时就对不上 —— 不报错,只是又回到「英文单子九条规则全灭」。"""
        for lang in i18n.LANGS:
            S, A = i18n.strings(lang), i18n.anchors(lang)
            self.assertIn(A["问题"], S["rc_qhead"], lang)
            self.assertIn(A["阻塞"], S["rc_blocking"], lang)
            self.assertIn(A["第一部分"], S["md_p1_head"], lang)
            self.assertIn(A["第二部分"], S["md_p2_head"], lang)
            self.assertIn(A["填写信息"], S["md_sign_head"], lang)
            self.assertIn(A["未表态"], S["p1_cell"].format(
                ok=S["p1_ok"], no=S["p1_no"], mute=S["p1_mute"]), lang)

    def test_the_signoff_strings_are_gone(self):
        """落款仪式整体拆除后,两门表里都不该再留下这些键 —— 留着就会有人再把
        署名栏接回去,而机检那一侧已经没有对应规则了。"""
        for lang in i18n.LANGS:
            for gone in ("w_name", "w_dept", "sign_name", "sign_dept", "sign_why",
                         "rc_unsigned", "rc_unsigned_ph", "rc_file_unsigned",
                         "pv_sign", "pv_unsigned", "md_sign_why"):
                self.assertNotIn(gone, i18n.strings(lang), f"{lang}/{gone}")


class TestDocLang(unittest.TestCase):
    def _doc(self, **over):
        d = json.loads(EN_JSON.read_text(encoding="utf-8"))
        d["doc"].update(over)
        return d

    def test_supported_langs_pass(self):
        for lang in i18n.LANGS:
            self.assertEqual(bq.validate(self._doc(lang=lang)), [], lang)

    def test_lang_is_optional(self):
        d = self._doc()
        d["doc"].pop("lang")
        self.assertEqual(bq.validate(d), [])

    def test_unsupported_lang_is_rejected(self):
        """写 "en-US"／"英文" 以前是静默退回中文外壳:出题者以为出了英文单,
        业务收到的是中文页面。"""
        for bad in ("en-US", "英文", "EN", "ja"):
            errs = bq.validate(self._doc(lang=bad))
            self.assertTrue(any("lang" in e for e in errs), f"{bad}: {errs}")

    def test_handwritten_i18n_is_rejected(self):
        """_i18n 是 build 注入的;手写的那份会被静默覆盖 —— 改半天不生效。"""
        errs = bq.validate(self._doc(_i18n={"export": "Send"}))
        self.assertTrue(any("_i18n" in e for e in errs), errs)


class TestEnglishArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(EN_JSON.read_text(encoding="utf-8"))
        cls.html = bq.render_html(cls.doc, bq.TEMPLATE_PATH.read_text(encoding="utf-8"))
        cls.md = bq.render_md(cls.doc)

    def test_the_en_table_is_injected(self):
        data = json.loads(re.search(r'<script id="qdata"[^>]*>(.*?)</script>',
                                    self.html, re.S).group(1))
        self.assertEqual(data["doc"]["_i18n"], i18n.strings("en"))

    def test_static_skeleton_chinese_is_confined_to_ids_the_boot_overwrites(self):
        """静态骨架里的中文只是 no-JS 兜底,启动时会被 fillChrome() 覆盖。
        新加一句没有 id 的骨架文案 = 英文单子上一块永远换不掉的中文,而且没人
        会发现 —— 这条测试就是拦它的。"""
        tpl = bq.TEMPLATE_PATH.read_text(encoding="utf-8")
        body = tpl.split("<body>", 1)[1].split("<script>\n/* ── 渲染器", 1)[0]
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        # noscript / bootfail 是刻意留中文的:没有 JS 时业务本来也填不了这张单,
        # 那句话只负责告诉他改用系统浏览器或要一份 md。
        body = re.sub(r"<noscript>.*?</noscript>", "", body, flags=re.S)
        body = re.sub(r'<div class="bootfail".*?</div>\s*</div>', "", body, flags=re.S)
        filled = set(re.findall(r"setText\('(\w+)'", tpl))
        for line in body.split("\n"):
            if not re.search(r"[一-鿿]", line):
                continue
            self.assertTrue(any(f'id="{i}"' in line for i in filled)
                            or "aria-label" in line,
                            f"骨架里这句中文没有 fillChrome() 会覆盖的 id:\n{line}")

    def test_en_md_has_no_chinese_outside_the_machine_block(self):
        """机读区的键名恒为中文(协议不翻译),正文一个中文字都不该有。"""
        body = re.sub(r"```json.*?```", "", self.md, flags=re.S)
        hits = [l for l in body.split("\n") if re.search(r"[一-鿿]", l)]
        self.assertEqual(hits, [], hits)

    def test_en_md_has_no_full_width_punctuation_outside_the_machine_block(self):
        """全角「；」「（）」比汉字更容易漏掉,但一样刺眼。"""
        body = re.sub(r"```json.*?```", "", self.md, flags=re.S)
        hits = [l for l in body.split("\n") if re.search(r"[，。；：（）「」／　]", l)]
        self.assertEqual(hits, [], hits)


class TestMdMachineBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zh = bq.render_md(json.loads(ZH_JSON.read_text(encoding="utf-8")))
        cls.en = bq.render_md(json.loads(EN_JSON.read_text(encoding="utf-8")))

    def test_md_form_is_not_mistaken_for_a_receipt(self):
        """表单里没有答案(答案在人读文本里)。按回执判会报「全部未答」,
        把手填的答案整份吃掉 —— 比没有机读区更糟。"""
        for md in (self.zh, self.en):
            self.assertEqual(cq.machine_block(md), (None, False))
            self.assertIsNotNone(cq.md_form(md))

    def test_chinese_sheet_is_left_untouched_by_canonicalisation(self):
        """中文锚点表是恒等映射 —— 归一必须一个字符都不动,否则「兼容层判据
        一字不动」这条承诺就名存实亡。"""
        form = cq.md_form(self.zh)
        self.assertEqual(cq.canonicalize(self.zh, form["锚点"]), self.zh)

    def test_english_sheet_is_restored_to_the_canonical_words(self):
        form = cq.md_form(self.en)
        got = cq.canonicalize(self.en, form["锚点"])
        self.assertIn("### 问题 1: ", got)
        self.assertIn("（阻塞）".replace("（", "(").replace("）", ")"), got)  # " (阻塞)"
        self.assertIn("## 第一部分", got)
        self.assertIn("## 第二部分", got)
        self.assertIn("## 填写信息", got)
        self.assertIn("【作答区】", got)

    def test_question_titles_keep_their_own_words(self):
        """归一只动结构词。题目正文里再出现一次 "Question" 不该被改掉 ——
        业务写的话不许被机检改写。"""
        en = self.en.replace("### Question 4: What counts as \"paid\"?",
                             "### Question 4: Which Question wins?")
        got = cq.canonicalize(en, cq.md_form(en)["锚点"])
        self.assertIn("### 问题 4: Which Question wins?", got)


class TestEnglishMdGoesThroughTheChecker(unittest.TestCase):
    """本任务的验收核心之一:英文 md 与中文 md 的机检结论同形。"""

    @classmethod
    def setUpClass(cls):
        d = json.loads(EN_JSON.read_text(encoding="utf-8"))
        cls.n_q = len(d["questions"])
        cls.blocking = sorted(q["no"] for q in d["questions"] if q.get("blocking"))
        cls.md = bq.render_md(d)
        cls.code, cls.out = _check(cls.md)

    def test_every_question_is_seen(self):
        self.assertIn(f"题目 {self.n_q} 道", self.out, self.out)
        self.assertIn(f"未答 {self.n_q} 道", self.out, self.out)

    def test_blocking_questions_fail_not_warn(self):
        for no in self.blocking:
            self.assertTrue(
                any(f"问题 {no}" in l and "阻塞级" in l and l.strip().startswith("✗")
                    for l in self.out.splitlines()), f"问题 {no} 未报 FAIL:\n{self.out}")
        self.assertEqual(self.code, 1, self.out)

    def test_the_anchor_fallback_warning_does_not_appear(self):
        """出现这条就说明结构词没还原成功,机检其实什么都没看见。"""
        self.assertNotIn("未识别到任何", self.out, self.out)

    def test_a_filled_english_sheet_passes(self):
        """手填的英文单子必须能通过 —— md 这一路的存在意义就是手填后交回来。
        落款拆除后连日期都不必补:机检已无落款规则,单子填完题就该过。"""
        text = _tick_first_option(self.md, "### Question ").replace(
            "Date: ____", "Date: 2026-08-28")
        code, out = _check(text)
        self.assertNotIn("勾选了", out, out)
        self.assertEqual(code, 0, out)

    def test_ticked_undecided_row_is_counted(self):
        """三态在同一格里,勾中 Undecided 必须被数出来 —— 否则业务一条都不核对、
        机检照样放行(中文侧的同一漏洞已有测试盯着,这是英文那条腿)。"""
        text = self.md.replace("☐ Undecided", "☑ Undecided")
        code, out = _check(text)
        self.assertIn("2 条『未表态』", out, out)

    def test_blank_sheet_does_not_report_unticked_undecided(self):
        self.assertNotIn("『未表态』", self.out, self.out)

    def test_declared_question_count_is_cross_checked(self):
        """结构词被人改写过 → 人读文本认不出题目。机读区的题号表是唯一能说出
        「本来有几题」的东西,对不上必须出声,不能悄悄少看几道。"""
        broken = self.md.replace("### Question ", "### Q. ")
        code, out = _check(broken)
        self.assertIn("机读区声明本单共 4 题", out, out)


class TestBrokenAnchorTableDegradesInsteadOfCrashing(unittest.TestCase):
    """md 这一路的定位就是「手填、可能被改坏」。机读区 JSON 整个坏掉都只降级加一条
    WARN,没有道理唯独 `锚点` 的**类型**错误让 CLI 整个 traceback 崩掉 ——
    `(anchors or {}).get(...)` 对字符串/列表抛 AttributeError,而 check_file() 不捕获。

    既有测试只盖了「取值错位」(锚点写得不对,归一结果不对),没盖「类型损坏」。
    """

    @classmethod
    def setUpClass(cls):
        cls.md = bq.render_md(json.loads(EN_JSON.read_text(encoding="utf-8")))

    def _with_anchor(self, value):
        """把 md 末尾机读区的 `锚点` 换成 value;value 为 KeyError 时整个删掉该键。"""
        m = re.search(r'^```[ \t]*json[ \t]*\r?\n(.*?)^```', self.md, re.M | re.S)
        obj = json.loads(m.group(1))
        if value is KeyError:
            obj.pop("锚点")
        else:
            obj["锚点"] = value
        return self.md[:m.start(1)] + json.dumps(obj, ensure_ascii=False) + "\n" \
            + self.md[m.end(1):]

    @staticmethod
    def _body(out):
        """去掉带临时路径的抬头行,只留结论。"""
        return "\n".join(l for l in out.split("\n") if not l.startswith("== 机检 "))

    MALFORMED = {"字符串": "被手改坏了", "列表": ["问题", "作答区"], "数字": 42,
                 "空字符串": "", "键整个没了": KeyError}

    def test_no_traceback(self):
        for name, v in self.MALFORMED.items():
            with self.subTest(name):
                code, out = _check(self._with_anchor(v))
                self.assertNotIn("Traceback", out, out)
                self.assertNotIn("AttributeError", out, out)
                # 崩溃时 stdout 是空的、退出码是 1;这里要的是「跑完了」
                self.assertIn("== 摘要 ==", out, out)

    def test_the_damage_is_reported(self):
        """静默降级比崩溃更危险 —— 得说清「这次是按中文规范词判的」。"""
        for name, v in self.MALFORMED.items():
            with self.subTest(name):
                _, out = _check(self._with_anchor(v))
                self.assertIn("锚点表损坏", out, out)

    def test_every_malformed_shape_lands_on_the_same_verdict(self):
        """类型坏掉 ≡ 锚点表整个没有 ≡ 空表:都退化成恒等映射(按中文规范词判)。
        三种畸形给出三种不同结论的话,业务/开发看到的诊断就取决于坏的方式。"""
        base = self._body(_check(self._with_anchor(KeyError))[1])
        for name, v in self.MALFORMED.items():
            with self.subTest(name):
                self.assertEqual(self._body(_check(self._with_anchor(v))[1]), base)

    def test_a_chinese_sheet_survives_the_same_damage_with_its_verdict_intact(self):
        """中文单子的锚点表本来就是恒等映射 —— 表坏掉不该改变任何结论,
        只多那一条「锚点表损坏」的提示。"""
        zh = bq.render_md(json.loads(ZH_JSON.read_text(encoding="utf-8")))
        m = re.search(r'^```[ \t]*json[ \t]*\r?\n(.*?)^```', zh, re.M | re.S)
        obj = json.loads(m.group(1)); obj["锚点"] = "被手改坏了"
        broken = zh[:m.start(1)] + json.dumps(obj, ensure_ascii=False) + "\n" + zh[m.end(1):]
        good_code, good = _check(zh)
        bad_code, bad = _check(broken)
        verdicts = lambda out: [l for l in out.split("\n")
                                if l.strip().startswith(("✗", "△"))]
        self.assertEqual(bad_code, good_code)
        self.assertEqual([l for l in verdicts(bad) if "锚点表损坏" not in l],
                         verdicts(good))
        # 摘要里的 WARN 数只该多出那一条,不多不少
        n = lambda out: int(re.search(r"/ (\d+) WARN", out).group(1))
        self.assertEqual(n(bad), n(good) + 1)

    def test_canonicalize_itself_returns_the_text_untouched(self):
        for v in ("坏了", ["a"], 42, None, 0):
            with self.subTest(repr(v)):
                self.assertEqual(cq.canonicalize(self.md, v), self.md)


class TestRealEnglishReceipt(unittest.TestCase):
    """fixture 取自浏览器里对 tests/fixtures/questionnaire-en.json 的真实出包页面
    实跑一次 buildReceipt() 的输出,不是照 docstring 手抄的 —— 手抄会把「模板真实
    写出什么」和「机检以为模板写什么」变成两份真源。"""

    FIX_FILE = FIX / "receipt-json-en-kind.md"

    @classmethod
    def setUpClass(cls):
        cls.text = cls.FIX_FILE.read_text(encoding="utf-8")
        cls.code, cls.out = _check(cls.text)

    def test_the_receipt_body_is_english(self):
        body = re.sub(r"```json.*?```", "", self.text, flags=re.S)
        self.assertEqual([l for l in body.split("\n") if re.search(r"[一-鿿]", l)], [])

    def test_all_the_rules_fire_with_the_same_wording_as_chinese(self):
        self.assertEqual(self.code, 1, self.out)
        self.assertIn("按机读区判", self.out)
        self.assertIn("第一部分有 1 条『未表态』", self.out)          # 4 靠 mute 枚举
        self.assertIn("问题 1 勾了『不清楚』", self.out)               # 3 靠 主选kind
        self.assertIn("判为不成立 1 道", self.out)                    # 6
        self.assertIn("1 处矛盾业务未给说明", self.out)               # 7
        self.assertIn("题目 4 道", self.out)
        self.assertNotIn("未识别到任何", self.out)

    def test_part1_column_carries_the_machine_enum(self):
        """人读表格写 Yes/Undecided,机读区写 ok/mute —— 判据落在后者。"""
        J, _ = cq.machine_block(self.text)
        self.assertEqual([r["核对"] for r in J["第一部分"]], ["ok", "mute"])
        self.assertIn("| 2 | Undecided |", self.text)

    def test_dontknow_survives_a_label_the_keywords_would_miss(self):
        """把 label 换成关键词表认不出的说法 —— 结构判据必须照样触发。
        这一条才证明规则 3 真的不再靠猜字面。"""
        text = self.text.replace("I don't know", "Ask whoever runs the ledger")
        code, out = _check(text)
        self.assertIn("问题 1 勾了『不清楚』", out, out)


class TestStructuredRulesAreLanguageNeutral(unittest.TestCase):
    """规则 3／4 从「猜 label 的字面」改成「读结构」。"""

    def _run(self, J):
        warns, fails = [], []
        cq.check_json(J, "", warns, fails)
        return warns, fails

    def test_part1_machine_enum_is_counted(self):
        J = {"第一部分": [{"条": 1, "核对": "ok"}, {"条": 2, "核对": "no"},
                          {"条": 3, "核对": "mute"}],
             "题目": [], "落款": {"导出时间": "2026-08-28", "补充说明": ""}}
        warns, _ = self._run(J)
        self.assertTrue(any("1 条『未表态』" in w for w in warns), warns)

    def test_legacy_chinese_values_still_counted(self):
        """旧回执写的是「对/不对/未表态」—— 换枚举不得让老单子静默失效。"""
        J = {"第一部分": [{"条": 1, "核对": "对"}, {"条": 2, "核对": "未表态"}],
             "题目": [], "落款": {"导出时间": "x", "补充说明": ""}}
        warns, _ = self._run(J)
        self.assertTrue(any("1 条『未表态』" in w for w in warns), warns)

    def test_dontknow_is_judged_by_kind_not_by_wording(self):
        """label 是自由文本。kind 说了算 —— 写成 "Ask the finance team" 也照样命中。"""
        J = {"题目": [{"题号": 1, "阻塞": False, "主选": "C. Ask the finance team",
                       "主选kind": "dontknow", "子项": {}, "跳过": [], "补充": ""}],
             "落款": {"导出时间": "x", "补充说明": ""}}
        warns, _ = self._run(J)
        self.assertTrue(any("勾了『不清楚』" in w for w in warns), warns)

    def test_kind_overrides_a_misleading_label(self):
        """反过来也要成立:label 里带「不清楚」但这个选项没有语义档(导出器写
        `主选kind: null`)就不该报 —— 关键词兜底会误报,结构判不会。"""
        J = {"题目": [{"题号": 1, "阻塞": False, "主选": "A. 谁都不清楚的那条老规则",
                       "主选kind": None, "子项": {}, "跳过": [], "补充": ""}],
             "落款": {"导出时间": "x", "补充说明": ""}}
        warns, _ = self._run(J)
        self.assertFalse([w for w in warns if "勾了『不清楚』" in w], warns)

    def test_keyword_fallback_survives_for_receipts_without_kind(self):
        J = {"题目": [{"题号": 1, "阻塞": False, "主选": "C. I don't know",
                       "子项": {}, "跳过": [], "补充": ""}],
             "落款": {"导出时间": "x", "补充说明": ""}}
        warns, _ = self._run(J)
        self.assertTrue(any("勾了『不清楚』" in w for w in warns), warns)


class TestTemplateExportsTheOptionKind(unittest.TestCase):
    """模板不写 主选kind → 规则 3 悄悄退回关键词兜底:不报错,只是判得更差。
    这类缺口必须有机检闸门,不能靠人记得。"""

    @classmethod
    def setUpClass(cls):
        cls.js = re.sub(r"\s+", "",
                        bq.TEMPLATE_PATH.read_text(encoding="utf-8"))

    def test_selected_option_kind_reaches_the_machine_block(self):
        self.assertIn("rec.主选kind=i.dataset.kind||null", self.js)

    def test_option_kind_is_written_onto_the_input(self):
        self.assertIn('data-kind="${esc(o.kind)}"', self.js)

    def test_no_chinese_punctuation_is_hardcoded_as_a_joiner(self):
        """全角标点比汉字更容易漏 —— 浏览器验收时英文页面上写着「question 1、3」,
        142 条测试一条都没照出来(它在 JS 里,md 那侧的标点守卫看不到)。
        标点也得走表:拼接符一律 T('sep_*')。"""
        for bad in ("join('、')", "join('；')", "join('／')", "join('：')"):
            self.assertNotIn(bad, self.js.replace(" ", ""),
                             f"模板里写死了中文拼接符 {bad} —— 英文单子上会露出来")

    def test_the_fallback_exit_is_marked_other(self):
        """「都不是」是模板自动追加的,不在 json 里 —— 它的 kind 只能由模板写死。
        它是阶段三「选项集猜错了、要再来一轮」的结构信号。"""
        self.assertIn('data-kind="other"', self.js)


if __name__ == "__main__":
    unittest.main()

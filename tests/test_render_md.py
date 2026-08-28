import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq

EXAMPLE = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                  "/2026-07-11-报销打款-r1.json")


class TestRenderMd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = bq.render_md(json.loads(EXAMPLE.read_text(encoding="utf-8")))

    def test_question_heading_matches_checker_contract(self):
        self.assertIn("### 问题 1：「可打款」从哪个节点算起？", self.md)

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
        self.assertIn("☐ A. 审批通过即可打", self.md)

    def test_has_answer_slot_and_signoff(self):
        self.assertIn("【作答区】", self.md)
        self.assertIn("## 填写信息", self.md)
        self.assertIn("日期：____", self.md)

    def test_no_signoff_ceremony_is_asked_for(self):
        """填写人/部门已整体拆除 —— 单子不再向业务索要身份信息。"""
        for gone in ("填写人", "部门：", "署名", "待追认"):
            self.assertNotIn(gone, self.md, f"落款仪式残留: {gone}")

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

    def test_only_main_group_gets_checkboxes(self):
        """一题只允许一个勾选标记 —— 子问发独立勾选框会让机检判为多选。"""
        for blk in self.md.split("### 问题 ")[1:]:
            body = blk.split("【作答区】")[0]
            self.assertNotIn("子问", body, f"子问不该出现在勾选区：{blk[:40]}")
        self.assertIn("　· 重试 3 次仍失败怎么办（", self.md)

    def test_filled_md_passes_checker_without_multiselect_warning(self):
        """把生成的 md 填一份丢给真实机检,不该出现『勾选了 N 项』。"""
        import re as _re, subprocess, sys as _sys, tempfile
        from pathlib import Path as _P
        out, ticked = [], False
        for line in self.md.splitlines():
            if line.startswith("### 问题 "):
                ticked = False
            if not ticked and line.startswith("☐ "):
                out.append("☑ " + line[2:]); ticked = True
                continue
            out.append(line)
        text = "\n".join(out).replace("日期：____", "日期：2026-07-14")
        f = _P(tempfile.mkdtemp()) / "r.md"
        f.write_text(text, encoding="utf-8")
        p = subprocess.run(
            [_sys.executable, str(ROOT / "scripts" / "check_questionnaire.py"), str(f)],
            capture_output=True, text=True)
        self.assertNotIn("勾选了", p.stdout, p.stdout)
        self.assertEqual(p.returncode, 0, p.stdout)


    def test_part1_is_three_state_without_global_no_objection(self):
        """第一部分逐条三态,与 HTML 侧同一契约(D6)。全局「无异议」和逐条核对
        自相矛盾:一句话盖住所有条目等于没核对。"""
        rows = [l for l in self.md.splitlines() if l.startswith("| 1 |")]
        self.assertTrue(rows, self.md[:400])
        for s in ("☐ 对", "☐ 不对", "☐ 未表态"):
            self.assertIn(s, rows[0], rows[0])
        part1 = self.md.split("## 第一部分")[1].split("## 第二部分")[0]
        self.assertNotIn("无异议", part1, part1)

    def test_cost_is_rendered_even_when_advice_is_forbidden(self):
        """cost 是「该选项的代价/影响」,advice_allowed 管的是建议措辞 ——
        按 advice_allowed 过滤 cost 会让规则/账务口径题(最需要看代价的一档)
        拿到一张剥掉了全部代价的决策单。"""
        d = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        q = next(q for q in d["questions"] if not q.get("advice_allowed"))
        q["groups"][0]["options"][0]["cost"] = "会多算一天利息"
        self.assertIn("（会多算一天利息）", bq.render_md(d))

    def test_demo_table_reaches_the_print_path_too(self):
        """阻塞级题的 demo 是硬要求;md 不渲染它就等于给打印/内网那一路的业务
        一张剥掉了对照表的决策单。"""
        blk = next(b for b in self.md.split("### 问题 ")[1:] if b.startswith("1："))
        self.assertIn("演示对照", blk)
        self.assertIn("非任何选项的背书", blk)
        self.assertIn("3-01 当天进批次", blk)
        self.assertIn("3-03 复核完才进批次", blk)
        self.assertIn("未从代码验证", blk)      # basis=assumed 必须如实标注

    def test_no_advice_wording_smuggled_in_cost(self):
        """cost 只写代价,不兼职装建议。"""
        for word in ("开发建议", "建议选", "推荐选"):
            self.assertNotIn(word, self.md, f"cost 里混了建议措辞: {word}")


class TestBlankMdIsFullyReportedAsUnanswered(unittest.TestCase):
    """C1 回归:子问提示行若写在【作答区】之后,substantive() 会把模板自带的提示
    文字当成实质作答 —— 凡带子问组的题在 md 路径上永远判为已作答,阻塞级漏的
    是 FAIL 而不是 WARN。一字未填的空白单必须报出全部题目未答。"""

    @classmethod
    def setUpClass(cls):
        import subprocess, sys as _sys, tempfile
        from pathlib import Path as _P
        d = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        cls.n_q = len(d["questions"])
        cls.blocking = sorted(q["no"] for q in d["questions"] if q.get("blocking"))
        f = _P(tempfile.mkdtemp()) / "blank.md"
        f.write_text(bq.render_md(d), encoding="utf-8")
        p = subprocess.run(
            [_sys.executable, str(ROOT / "scripts" / "check_questionnaire.py"), str(f)],
            capture_output=True, text=True)
        cls.out, cls.code = p.stdout, p.returncode

    def test_every_question_is_reported_unanswered(self):
        self.assertIn(f"未答 {self.n_q} 道", self.out, self.out)

    def test_part1_is_reported_uncheck(self):
        """第一部分的提示语同样不能写在【作答区】之后 —— 否则模板自带的
        「哪条不对、哪里不对」被当成业务的异议说明,兜底判据永不触发。"""
        self.assertIn("第一部分", self.out, self.out)

    def test_question_with_subgroups_is_not_silently_counted_as_answered(self):
        """问题 2 有子问组 —— 正是以前永远漏报的那一道。"""
        self.assertIn("问题 2", self.out, self.out)

    def test_blocking_questions_fail_not_warn(self):
        for no in self.blocking:
            self.assertTrue(
                any(f"问题 {no}" in l and "阻塞级" in l and l.strip().startswith("✗")
                    for l in self.out.splitlines()),
                f"问题 {no} 未报 FAIL:\n{self.out}")
        self.assertEqual(self.code, 1, self.out)

    def test_subquestion_prompt_stays_above_the_answer_slot(self):
        """提示行必须在【作答区】之前,且自身不得含「【作答区】」四字。"""
        md = bq.render_md(json.loads(EXAMPLE.read_text(encoding="utf-8")))
        blk = next(b for b in md.split("### 问题 ")[1:] if b.startswith("2："))
        head, _, tail = blk.partition("【作答区】")
        self.assertIn("　· 重试 3 次仍失败怎么办（", head)
        self.assertNotIn("　·", tail)


if __name__ == "__main__":
    unittest.main()

import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_questionnaire as bq


def doc(**over):
    """最小合法文档；用 over 或就地删字段造反例。"""
    base = {
        "doc": {"id": "T", "title": "测试单", "round": 1,
                "sent_by": "开发", "sent_on": "2026-08-27", "due_days": 3,
                "usage": "答案会写进开发规格"},
        "roles": [{"id": "fin", "name": "财务"}],
        "part1": [],
        "layers": [{"n": 1}, {"n": 2}],
        "questions": [
            {"no": 1, "layer": 1, "blocking": True, "title": "口径 A 还是 B？",
             "who": ["fin"], "background": "背景", "advice_allowed": False,
             "evidence": {"tier": "code", "cites": [
                 {"kind": "code", "path": "a.py", "line": 1, "snippet": "x = 1",
                  "logic": "取值为 1，没有其它赋值点",
                  "entry": "api.py:9",
                  "branches": [{"cond": "总是", "then": "x = 1", "cite": "a.py:1"}],
                  "branches_exhaustive": True}]},
             "groups": [{"id": "main", "options": [
                 {"key": "A", "label": "按 A"},
                 {"key": "B", "label": "按 B", "terminal": True}]}],
             "reveal": [{"when": "A", "ask": "A 的细则"}]},
            {"no": 2, "layer": 2, "title": "后续题", "who": ["fin"],
             "background": "背景", "advice_allowed": True,
             "evidence": {"tier": "guess", "cites": [],
                          "weak": "整题无据：口径在代码里没有现成算法"},
             "groups": [{"id": "main", "options": [{"key": "X", "label": "选 X"}]}]},
        ],
        "links": {"na": [], "carry": [], "clash": []},
    }
    base.update(over)
    return base


class TestValidate(unittest.TestCase):
    def test_minimal_document_passes(self):
        self.assertEqual(bq.validate(doc()), [])

    def test_who_must_reference_declared_role(self):
        d = doc()
        d["questions"][0]["who"] = ["财务"]              # 自由文本，不是 role id
        errs = bq.validate(d)
        self.assertTrue(any("who" in e and "roles" in e for e in errs), errs)

    def test_dangling_when_reference_is_rejected(self):
        d = doc()
        d["links"]["na"] = [{"when": "9=A", "target": "2.main", "note": "n"}]
        errs = bq.validate(d)
        self.assertTrue(any("问题 9" in e for e in errs), errs)

    def test_backward_layer_dependency_is_rejected(self):
        d = doc()
        # 问题 1 在 layer 1，却依赖 layer 2 的问题 2 —— 反向依赖
        d["links"]["na"] = [{"when": "2=X", "target": "1.main", "note": "n"}]
        errs = bq.validate(d)
        self.assertTrue(any("layer" in e for e in errs), errs)

    def test_same_question_group_dependency_is_allowed(self):
        """同题内主问决定子问，天然同层，不是反向依赖。"""
        d = doc()
        d["questions"][0]["groups"].append(
            {"id": "sub", "ask": "细则", "options": [{"key": "s1", "label": "细则一"}]})
        d["links"]["na"] = [{"when": "1=B", "target": "1.sub", "note": "n"}]
        self.assertEqual(bq.validate(d), [])

    def test_asymmetric_branch_without_terminal_is_rejected(self):
        d = doc()
        del d["questions"][0]["groups"][0]["options"][1]["terminal"]
        errs = bq.validate(d)
        self.assertTrue(any("terminal" in e and "B" in e for e in errs), errs)

    def test_symmetric_terminal_group_needs_no_annotation(self):
        """整组都没有后续时不必逐个标注——只有不对称才是漏了。"""
        d = doc()
        d["questions"][0].pop("reveal")
        del d["questions"][0]["groups"][0]["options"][1]["terminal"]
        self.assertEqual(bq.validate(d), [])

    def test_advice_wording_forbidden_when_advice_not_allowed(self):
        d = doc()
        d["questions"][0]["groups"][0]["options"][0]["cost"] = "开发建议：选 A，顺现有结构"
        errs = bq.validate(d)
        self.assertTrue(any("advice_allowed" in e for e in errs), errs)

    def test_advice_wording_allowed_when_flag_set(self):
        d = doc()
        d["questions"][1]["groups"][0]["options"][0]["cost"] = "开发建议：选 X"
        self.assertEqual(bq.validate(d), [])

    def test_src_or_code_tier_requires_cites(self):
        d = doc()
        d["questions"][0]["evidence"]["cites"] = []
        errs = bq.validate(d)
        self.assertTrue(any("cites" in e for e in errs), errs)

    def test_guess_tier_requires_weak_explanation(self):
        """无据也要说清哪儿没据、为什么还问，否则标红是空标。"""
        d = doc()
        d["questions"][1]["evidence"] = {"tier": "guess", "cites": []}
        errs = bq.validate(d)
        self.assertTrue(any("weak" in e for e in errs), errs)

    def test_code_cite_requires_logic_entry_branches(self):
        """单点行引用只证明那行存在,不证明当前页面的行为。"""
        for field in ("logic", "entry", "branches"):
            d = doc()
            del d["questions"][0]["evidence"]["cites"][0][field]
            errs = bq.validate(d)
            self.assertTrue(any(field in e for e in errs), f"{field}: {errs}")

    def test_non_exhaustive_branches_forces_guess_tier(self):
        """声明没读完分支 → 该题必须降为 guess,不得继续冒充 code 档。"""
        d = doc()
        d["questions"][0]["evidence"]["cites"][0]["branches_exhaustive"] = False
        errs = bq.validate(d)
        self.assertTrue(any("guess" in e for e in errs), errs)

    def test_non_exhaustive_branches_ok_when_tier_is_guess(self):
        d = doc()
        ev = d["questions"][0]["evidence"]
        ev["cites"][0]["branches_exhaustive"] = False
        ev["tier"] = "guess"
        ev["weak"] = "只读了主流程，别处可能还有覆盖，请当作未取证看"
        self.assertEqual(bq.validate(d), [])

    def test_demo_basis_is_required(self):
        d = doc()
        d["questions"][0]["demo"] = {"given": "输入", "rows": [{"when": ["A"], "v": "1"}]}
        errs = bq.validate(d)
        self.assertTrue(any("basis" in e for e in errs), errs)

    def test_demo_basis_branches_needs_actual_branches(self):
        d = doc()
        d["questions"][1]["demo"] = {"given": "输入", "basis": "branches",
                                     "rows": [{"when": ["X"], "v": "1"}]}
        errs = bq.validate(d)   # 问题 2 是 guess 档,没有 code 引用
        self.assertTrue(any("branches" in e for e in errs), errs)

    def test_demo_basis_assumed_is_allowed_without_code(self):
        d = doc()
        d["questions"][1]["demo"] = {"given": "输入", "basis": "assumed",
                                     "rows": [{"when": ["X"], "v": "1"}]}
        self.assertEqual(bq.validate(d), [])

    def test_over_threshold_requires_rules_ref(self):
        """分支 >2 就该沉淀进 rules/，不该 inline 在题目里。"""
        d = doc()
        d["questions"][0]["evidence"]["cites"][0]["branches"] = [
            {"cond": "c1", "then": "t1"}, {"cond": "c2", "then": "t2"},
            {"cond": "c3", "then": "t3"}]
        errs = bq.validate(d)
        self.assertTrue(any("rules_ref" in e for e in errs), errs)

    def test_over_threshold_satisfied_by_rules_ref(self):
        d = doc()
        ev = d["questions"][0]["evidence"]
        ev["cites"][0]["branches"] = [
            {"cond": "c1", "then": "t1"}, {"cond": "c2", "then": "t2"},
            {"cond": "c3", "then": "t3"}]
        ev["rules_ref"] = [{"id": "R1", "doc": "docs/requirements/rules/x.md",
                            "text": "规则一句话"}]
        self.assertEqual(bq.validate(d), [])

    def test_multi_file_code_cites_require_rules_ref(self):
        d = doc()
        d["questions"][0]["evidence"]["cites"].append(
            {"kind": "code", "path": "b.py", "line": 2, "snippet": "y = 2",
             "logic": "另一处", "entry": "api.py:9",
             "branches": [{"cond": "总是", "then": "y = 2"}]})
        errs = bq.validate(d)
        self.assertTrue(any("跨" in e and "rules_ref" in e for e in errs), errs)

    def test_reused_logic_text_requires_rules_ref(self):
        """同一句 logic 出现在两道题里 —— 该沉淀，不该抄两遍。"""
        d = doc()
        d["questions"][1]["evidence"] = {
            "tier": "code",
            "cites": [{"kind": "code", "path": "a.py", "line": 1, "snippet": "x = 1",
                       "logic": "取值为 1，没有其它赋值点",
                       "entry": "api.py:9",
                       "branches": [{"cond": "总是", "then": "x = 1"}]}]}
        errs = bq.validate(d)
        self.assertTrue(any("复用" in e for e in errs), errs)

    def test_logic_optional_when_rules_ref_given(self):
        """业务概念由规则文档承载时，题目里不必再抄一份 logic。"""
        d = doc()
        ev = d["questions"][0]["evidence"]
        del ev["cites"][0]["logic"]
        ev["rules_ref"] = [{"id": "R1", "doc": "docs/requirements/rules/x.md",
                            "text": "规则一句话"}]
        self.assertEqual(bq.validate(d), [])

    def test_reviewed_fields_complete_when_present(self):
        d = doc()
        d["questions"][0]["evidence"]["reviewed"] = {"by": "独立盲审"}
        errs = bq.validate(d)
        self.assertTrue(any("reviewed" in e for e in errs), errs)

    def test_reviewed_with_diffs_requires_note(self):
        d = doc()
        d["questions"][0]["evidence"]["reviewed"] = {
            "by": "独立盲审", "on": "2026-08-27", "diffs": 2}
        errs = bq.validate(d)
        self.assertTrue(any("note" in e for e in errs), errs)

    def test_reviewed_is_optional(self):
        """没审也能出包 —— 页面如实标『未经独立复核』，不拦在 build。"""
        d = doc()
        d["questions"][0]["evidence"].pop("reviewed", None)
        errs = bq.validate(d)
        self.assertFalse([e for e in errs if "reviewed" in e], errs)

    def test_reveal_when_must_be_own_option_key(self):
        d = doc()
        d["questions"][0]["reveal"] = [{"when": "Z", "ask": "不存在的选项"}]
        errs = bq.validate(d)
        self.assertTrue(any("reveal.when" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()

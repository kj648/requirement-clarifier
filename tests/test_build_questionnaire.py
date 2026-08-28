import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq


def doc(**over):
    """最小合法文档；用 over 或就地删字段造反例。"""
    base = {
        "doc": {"id": "T", "title": "测试单", "round": 1,
                "sent_by": "开发", "sent_on": "2026-08-27",
                "usage": "答案会写进开发规格"},
        "part1": [],
        "layers": [{"n": 1}, {"n": 2}],
        "questions": [
            {"no": 1, "layer": 1, "blocking": True, "title": "口径 A 还是 B？",
             "decide": "biz", "background": "背景", "advice_allowed": False,
             "evidence": {"tier": "code", "cites": [
                 {"kind": "code", "path": "a.py", "line": 1, "snippet": "x = 1",
                  "logic": "取值为 1，没有其它赋值点",
                  "entry": "api.py:9",
                  "branches": [{"cond": "总是", "then": "x = 1", "cite": "a.py:1"}],
                  "branches_exhaustive": True}]},
             "groups": [{"id": "main", "options": [
                 {"key": "A", "label": "按 A"},
                 {"key": "B", "label": "按 B", "terminal": True}]}],
             # 阻塞级必须配 demo（跨分支对照），否则是「只画岔口不算数」
             "demo": {"given": "一笔 1000 元的单子", "basis": "branches",
                      "rows": [{"when": ["A"], "k": "结果", "v": "按 A 算得 1000"},
                               {"when": ["B"], "k": "结果", "v": "按 B 算得 950"}]},
             "reveal": [{"when": "A", "ask": "A 的细则"}]},
            {"no": 2, "layer": 2, "title": "后续题", "decide": "dev",
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

    def test_decide_must_be_biz_or_dev(self):
        """角色只有开发与业务两档 —— 给谁是开发的事，不写进单子。"""
        for bad in ("fin", "财务", "BIZ", "", None):
            d = doc()
            d["questions"][0]["decide"] = bad
            errs = bq.validate(d)
            self.assertTrue(any("decide" in e for e in errs), f"{bad!r}: {errs}")

    def test_decide_both_values_pass(self):
        # 用非阻塞的问题 2 —— 问题 1 是 blocking:True,标 dev 会撞
        # test_blocking_question_must_be_decided_by_business 那条规则,
        # 这里只想单独验证 biz/dev 两个枚举值本身都合法。
        for good in ("biz", "dev"):
            d = doc()
            d["questions"][1]["decide"] = good
            self.assertEqual(bq.validate(d), [])

    def test_roles_key_is_rejected_as_leftover(self):
        """顶层 roles 已废弃 —— 留着会让人以为还能按人分区。"""
        d = doc()
        d["roles"] = [{"id": "fin", "name": "财务"}]
        errs = bq.validate(d)
        self.assertTrue(any("roles" in e and "废弃" in e for e in errs), errs)

    def test_stale_who_field_is_rejected(self):
        """who 已废弃 —— 静默忽略会让标的回答人无声消失,写的人不会知道。"""
        d = doc()
        d["questions"][0]["who"] = ["fin"]
        errs = bq.validate(d)
        self.assertTrue(any("who" in e for e in errs), errs)

    def test_stale_who_error_names_the_questions(self):
        d = doc()
        d["questions"][0]["who"] = ["fin"]
        d["questions"][1]["who"] = ["ops"]
        errs = [e for e in bq.validate(d) if "who" in e]
        self.assertTrue(errs)
        self.assertIn("1", errs[0]); self.assertIn("2", errs[0])

    def test_due_days_is_rejected_as_leftover(self):
        d = doc()
        d["doc"]["due_days"] = 3
        errs = bq.validate(d)
        self.assertTrue(any("due_days" in e for e in errs), errs)

    def test_blocking_question_must_be_decided_by_business(self):
        """阻塞级不许用【开发拟定】顶过去 —— 只能推迟或升级。"""
        d = doc()
        d["questions"][0]["blocking"] = True
        d["questions"][0]["decide"] = "dev"
        errs = bq.validate(d)
        self.assertTrue(any("阻塞" in e for e in errs), errs)

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

    def test_advice_wording_in_label_also_caught(self):
        """建议措辞藏在 label 里同样要拦 —— 否则换个字段就绕过了。"""
        d = doc()
        d["questions"][0]["groups"][0]["options"][0]["label"] = "开发建议：选 A，最省事"
        errs = bq.validate(d)
        self.assertTrue(any("advice_allowed" in e for e in errs), errs)

    def test_malformed_roles_returns_error_not_exception(self):
        d = doc()
        d["roles"] = ["fin"]                 # 字符串列表,不是对象列表
        errs = bq.validate(d)                # 必须返回而不是抛
        self.assertTrue(any("roles" in e for e in errs), errs)

    def test_malformed_links_returns_error_not_exception(self):
        d = doc()
        d["links"] = ["oops"]
        errs = bq.validate(d)
        self.assertTrue(any("links" in e for e in errs), errs)

    def test_malformed_option_returns_error_not_exception(self):
        d = doc()
        d["questions"][0]["groups"][0]["options"] = ["oops-a-string"]
        errs = bq.validate(d)                # 必须返回而不是抛
        self.assertTrue(any("options" in e for e in errs), errs)

    def test_unsupported_when_operator_is_rejected(self):
        """meets() 只实现了 & 和 = —— 没实现的算子必须在出包时红字,
        不能让它在业务面前静默瘫痪整页。"""
        for expr in ("2!=X", "1=A | 2=X", "2 in [A,B]"):
            d = doc()
            d["links"]["na"] = [{"when": expr, "target": "2.main", "note": "n"}]
            errs = bq.validate(d)
            self.assertTrue(any("when" in e for e in errs), f"{expr}: {errs}")

    def test_supported_when_operator_passes(self):
        d = doc()
        d["links"]["na"] = [{"when": "1=A", "target": "2.main", "note": "n"}]
        self.assertEqual(bq.validate(d), [])

    def test_option_key_with_operator_char_is_rejected(self):
        """key 原样拼进 data-when 与 radio value,带算子字符条件显隐就永不命中。"""
        d = doc()
        d["questions"][1]["groups"][0]["options"] = [{"key": "A|B", "label": "选 A 或 B"}]
        errs = bq.validate(d)
        self.assertTrue(any("key" in e for e in errs), errs)

    def test_carry_must_land_on_a_reveal_field(self):
        """carry 落不到输入框上就是死链路:页面不报错、业务看不出、事实也没传过去。"""
        d = doc()
        d["links"]["carry"] = [{"from": "1.A", "to": "2.nope", "kind": "fact"}]
        errs = bq.validate(d)
        self.assertTrue(any("carry" in e for e in errs), errs)

    def test_carry_resolving_to_reveal_fields_passes(self):
        d = doc()
        d["questions"][1]["reveal"] = [{"when": "X", "ask": "X 的细则"}]
        d["links"]["carry"] = [{"from": "1.A", "to": "2.X", "kind": "fact"}]
        self.assertEqual(bq.validate(d), [])


class TestMalformedInputReturnsInsteadOfRaising(unittest.TestCase):
    """validate() 的 docstring 承诺「格式错的 json 也要给出诊断而不是让工具崩掉」。
    这四种畸形输入以前是直接 traceback —— 出题者拿到的是栈,不是诊断。"""

    def _errs(self, mutate):
        d = doc()
        mutate(d)
        try:
            return bq.validate(d)
        except Exception as e:                      # noqa: BLE001 —— 抛了就是失败
            self.fail(f"validate() 抛了 {type(e).__name__}: {e}")

    def test_reviewed_diffs_in_words(self):
        def m(d):
            d["questions"][0]["evidence"]["reviewed"] = {
                "by": "独立盲审", "on": "2026-08-27", "diffs": "两处"}
        errs = self._errs(m)
        self.assertTrue(any("diffs" in e and "整数" in e for e in errs), errs)

    def test_reviewed_not_a_dict(self):
        errs = self._errs(lambda d: d["questions"][0]["evidence"].__setitem__(
            "reviewed", "审过了"))
        self.assertTrue(any("reviewed" in e and "对象" in e for e in errs), errs)

    def test_cites_is_a_string_array(self):
        errs = self._errs(lambda d: d["questions"][0]["evidence"].__setitem__(
            "cites", ["a.py:1"]))
        self.assertTrue(any("cites" in e and "对象数组" in e for e in errs), errs)

    def test_demo_not_a_dict(self):
        errs = self._errs(lambda d: d["questions"][0].__setitem__("demo", "选 A 得 1000"))
        self.assertTrue(any("demo" in e and "对象" in e for e in errs), errs)

    def test_evidence_not_a_dict(self):
        errs = self._errs(lambda d: d["questions"][0].__setitem__("evidence", "src"))
        self.assertTrue(any("evidence" in e and "对象" in e for e in errs), errs)


class TestRequiredFieldsMatchSchema(unittest.TestCase):
    """schema 的 required 全仓 0 处被代码引用 —— 缺字段时以前是 validate PASS →
    render_md KeyError。校验说没事,出包却崩。"""

    def test_schema_required_matches_validator(self):
        """schema 是给出题者读的契约,validate() 是真执行者 —— 两处 required 一旦
        分叉,就会出现『schema 说必填、validate 放行、render 崩』的静默链。历史上
        分叉过一次,靠人工同步没拦住;这条测试把它锁死。

        注:`lang` 是可选的(缺省 zh),不进 required —— 加进去会让所有既有单子失效。"""
        import json
        schema = json.loads((ROOT / "templates" / "questionnaire.schema.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]["doc"]["required"]),
                         set(bq.DOC_FIELDS),
                         "schema 的 doc.required 与 build_questionnaire.DOC_FIELDS 分叉了")
        self.assertEqual(
            set(schema["properties"]["questions"]["items"]["required"]),
            set(bq.Q_FIELDS),
            "schema 的 questions[].required 与 build_questionnaire.Q_FIELDS 分叉了")

    def test_missing_question_fields_are_caught_before_render(self):
        for field in ("layer", "title", "no", "decide", "advice_allowed",
                      "evidence", "groups"):
            d = doc()
            del d["questions"][0][field]
            errs = bq.validate(d)
            self.assertTrue(any(field in e for e in errs), f"{field}: {errs}")

    def test_missing_doc_fields_are_caught_before_render(self):
        for field in ("round", "usage", "sent_by", "id", "title", "sent_on"):
            d = doc()
            del d["doc"][field]
            errs = bq.validate(d)
            self.assertTrue(any(field in e for e in errs), f"{field}: {errs}")

    def test_render_md_would_have_crashed_on_those(self):
        """反证:这些字段确实是 render_md 直接下标取的,少一个就 KeyError。"""
        for field in ("round", "usage", "sent_by", "title", "sent_on"):
            d = doc()
            del d["doc"][field]
            with self.assertRaises(KeyError, msg=f"doc.{field} 似乎不再是必填"):
                bq.render_md(d)

    def test_question_no_must_be_int(self):
        """页面用 === 严格比较题号,字符串 "1" 会让 clash 静默不挂载。"""
        d = doc()
        d["questions"][0]["no"] = "1"
        errs = bq.validate(d)
        self.assertTrue(any("no" in e and "整数" in e for e in errs), errs)

    def test_question_layer_must_be_int(self):
        d = doc()
        d["questions"][0]["layer"] = "1"
        errs = bq.validate(d)
        self.assertTrue(any("layer" in e and "整数" in e for e in errs), errs)

    def test_bool_is_not_an_acceptable_no(self):
        d = doc()
        d["questions"][0]["no"] = True
        errs = bq.validate(d)
        self.assertTrue(any("整数" in e for e in errs), errs)


class TestBlockingNeedsDemo(unittest.TestCase):
    def test_blocking_question_without_demo_is_rejected(self):
        """只画岔口不算数 = 让人凭抽象拍板。硬要求以前没有闸门。"""
        d = doc()
        d["questions"][0].pop("demo")
        errs = bq.validate(d)
        self.assertTrue(any("demo" in e and "阻塞" in e for e in errs), errs)

    def test_non_blocking_question_needs_no_demo(self):
        d = doc()
        self.assertFalse(d["questions"][1].get("blocking"))
        self.assertFalse([e for e in bq.validate(d) if "demo" in e])


class TestOptionKeyUniqueness(unittest.TestCase):
    def test_duplicate_key_across_groups_in_one_question_is_rejected(self):
        """whenInWords() 按 key 反查标签,重名时取先出现的组 —— 业务会看到用错组
        的措辞描述自己的选择。不改 JS,把错文案变成出包时拒收。"""
        d = doc()
        d["questions"][0]["groups"].append(
            {"id": "sub", "ask": "细则", "options": [{"key": "A", "label": "细则 A"}]})
        errs = bq.validate(d)
        self.assertTrue(any("跨组唯一" in e for e in errs), errs)

    def test_same_key_in_different_questions_is_fine(self):
        """跨题重名无害 —— data-when 带题号前缀。"""
        keys = [{o["key"] for g in q["groups"] for o in g["options"]}
                for q in doc()["questions"]]
        d = doc()
        d["questions"][1]["groups"][0]["options"] = [{"key": "A", "label": "选 A"}]
        self.assertEqual(bq.validate(d), [], keys)


class TestCodeRev(unittest.TestCase):
    def test_non_repo_returns_empty_string_not_exception(self):
        """code_rev 取的是 root 的 HEAD;root 不是仓库时返回空串,不抛、也不退回 cwd 的 sha
        —— 拿 cwd 的 sha 会让抬头声称一个和被引用代码毫无关系的出处。"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(bq.code_rev(d), "")

    def test_root_repo_head_is_used(self):
        self.assertRegex(bq.code_rev(Path(__file__).resolve().parents[1]), r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()

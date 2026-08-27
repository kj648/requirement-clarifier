# HTML 可交互确认单 实施计划（P0）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把阶段二产出的确认单从"业务不会填的 Markdown"换成"单文件 HTML 点选即填、导出可机检回执"，且题目依赖与出题纪律变成可机检的声明式字段。

**Architecture:** `questionnaire.json`（题目数据）→ `build_questionnaire.py`（校验 + 注入）→ `templates/questionnaire.html`（固定模板，运行时从注入的 JSON 渲染 DOM 并承载全部交互）→ 业务导出回执 `.md`（人读正文 + 末尾压缩 JSON 机读区）→ `check_questionnaire.py` 机检。校验逻辑全在 Python 侧（可 CI），渲染与交互全在模板 JS 侧（浏览器侧人工验收）。

**Tech Stack:** Python 3 标准库（无第三方依赖）、`unittest`、原生 HTML/CSS/JS 单文件、GitHub Actions。

设计依据：[2026-08-27-html-questionnaire-design.md](../specs/2026-08-27-html-questionnaire-design.md)。已提交的原型 [2026-08-27-html-questionnaire-prototype.html](../specs/2026-08-27-html-questionnaire-prototype.html) 是模板的移植来源——它的样式、交互、导出逻辑均已在浏览器里验证过，Task 3 是把它从"硬编码 11 道 AR 题"改造成"从 JSON 渲染"。

## Global Constraints

- **仅标准库**：`scripts/` 下不得引入第三方依赖（现状：`re/sys/json/argparse/pathlib` 而已）。JSON Schema 文件只作契约文档，校验由手写 Python 实现——语义校验（悬空引用、反向 layer、分支空洞、建议措辞）本就无法用 JSON Schema 表达。
- **单文件自包含**：生成的 HTML 不得引用任何外部资源（无 CDN、无外链字体、无外部图片），双击可开、可离线、可内网、可打印。
- **不破现有回执契约**：`check_questionnaire.py` 现有识别格式必须继续有效——`### 问题 N：`、`☐ A. `／`☑ `／`☒ `、`【作答区】`、`## 填写信息` 的 `填写人/部门/日期`。一题只允许一个勾选标记（子问答案写进【作答区】）。
- **三档标签原样全角**：`【业务确认】`／`【开发拟定】`／`【假设】`／`【假设·未取证】`，不得简写或换半角括号（机检按字面 grep）。
- **`advice_allowed: false` 是结构约束**：规则／账务口径题不得渲染任何"开发建议"位；违规在 build 阶段拒绝出包，不靠自律。
- **中文文案面向业务方**：页面与回执里给业务看的每一句话都用后果说话，不用内部术语（"开发只能按待追认入账，日后有人问这是谁定的就查不到了"，而非"缺少 provenance"）。

---

### Task 1: questionnaire.json 契约与校验器

校验器是整个 P0 的地基：它把"分支穷举义务""依赖闭环""禁止建议措辞"从纪律变成机检。纯函数、无 IO，先 TDD 写它。

**Files:**
- Create: `templates/questionnaire.schema.json`
- Create: `scripts/build_questionnaire.py`
- Test: `tests/test_build_questionnaire.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `validate(doc: dict) -> list[str]` — 纯函数（结构与语义），返回错误消息列表，空列表表示通过。**不抛异常、不摸文件系统**。
  - `validate_refs(doc: dict, root: str | Path) -> list[str]` — 摸文件系统的部分：`rules_ref[].doc` 存在、条目编号找得到、`text` 没和规则文档漂移。`cites` 的路径行号真伪归 `verify_evidence.py`，不重复实现。
  - 模块级常量 `ADVICE_WORDS: re.Pattern`、`RULE_ENTRY: re.Pattern`。

- [ ] **Step 1: 写失败测试**

Create `tests/test_build_questionnaire.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest discover -s tests -p 'test_build*.py' -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_questionnaire'`

- [ ] **Step 3: 写校验器**

Create `scripts/build_questionnaire.py`：

```python
#!/usr/bin/env python3
"""build_questionnaire.py — questionnaire.json → 单文件 HTML 确认单

用法:
  python3 scripts/build_questionnaire.py <questionnaire.json> [-o 输出.html] [--md 输出.md]
  python3 scripts/build_questionnaire.py <questionnaire.json> --check   # 只校验不出包

校验四件事(全部 FAIL,不出包):
1. 角色引用: questions[].who 必须是 roles[].id,不得是自由文本
   ——否则「财务」与「财务 AR 负责人」会被算成两个人,一份单子分裂出幽灵收件人。
2. 依赖闭环: links/reveal 的 when 引用的题必须存在,且其 layer 严格小于被约束题的 layer。
3. 分支对称: 同一 main 组内若部分选项有后续、部分没有,没有后续的必须显式标 terminal
   ——一次性发单、异步回填,中间没有 AI 追问,漏掉的分支要等一整轮才能补。
4. 建议措辞: advice_allowed=false 的题,任何选项不得出现建议措辞(防锚定替答)。
5. 业务概念层: code 引用超过 inline 阈值(分支>2 / 跨多文件 / logic 被别题复用)
   必须沉淀进 rules/<模块名>.md 并给 rules_ref —— 否则同一段逻辑抄三遍、写不一致、
   拼不出整体、读代码的理解无处沉淀。
另: evidence.tier 为 src/code 必须有 cites;为 guess 必须写 weak(无据也要说清哪儿没据);
reviewed(独立盲审记录)选填,但填了字段要完整,diffs>0 必须写 note。

纯逻辑校验(validate)与摸文件系统的校验(validate_refs)分开:前者任何环境可跑,
后者要项目根。cites 的路径行号真伪归 verify_evidence.py,不在此重复实现。
"""
import argparse
import json
import re
import sys
from pathlib import Path

TIERS = ("src", "code", "guess")
ADVICE_WORDS = re.compile(r"开发建议|建议选|推荐选|我的默认建议")
RULE_ENTRY = re.compile(r"^##\s*(?P<id>R\d+)\.\s*(?P<text>.*)$", re.M)
# when 表达式里的题号引用:  "1=B"、"4=B & 1=B"、"7.crm!=x"
WHEN_REF = re.compile(r"(?<![\w.])(\d+)\s*(?:\.\w+)?\s*(?:!=|=)")


def _when_refs(expr):
    """从 when 表达式里取出被引用的题号。"""
    return {int(m) for m in WHEN_REF.findall(str(expr))}


def validate(doc):
    errs = []
    for key in ("doc", "roles", "questions"):
        if key not in doc:
            errs.append(f"缺顶层字段 `{key}`")
    if errs:
        return errs

    role_ids = {r.get("id") for r in doc["roles"]}
    layer_of = {q.get("no"): q.get("layer", 1) for q in doc["questions"]}
    # 同一句 logic 出现在多道题里 → 该沉淀进 rules/,不该抄两遍
    logic_counts = {}
    for q in doc["questions"]:
        for c in (q.get("evidence") or {}).get("cites", []) or []:
            if c.get("kind") == "code" and c.get("logic"):
                k = _norm(c["logic"])
                logic_counts[k] = logic_counts.get(k, 0) + 1

    for q in doc["questions"]:
        no = q.get("no")
        tag = f"问题 {no}"

        for w in q.get("who", []):
            if w not in role_ids:
                errs.append(f"{tag}: who「{w}」不在 roles 声明里 —— 回答人必须是 role id,不得是自由文本")

        groups = {g.get("id"): g for g in q.get("groups", [])}
        if "main" not in groups:
            errs.append(f"{tag}: 缺 main 组")

        ev = q.get("evidence") or {}
        tier = ev.get("tier")
        if tier not in TIERS:
            errs.append(f"{tag}: evidence.tier 必须是 {'/'.join(TIERS)},实际「{tier}」")
        elif tier in ("src", "code") and not ev.get("cites"):
            errs.append(f"{tag}: tier={tier} 却没有 cites —— 声称有据就得给出引用")
        elif tier == "guess" and not (ev.get("weak") or "").strip():
            errs.append(f"{tag}: tier=guess 必须写 weak,说明哪儿没据、为什么还问")

        errs.extend(_check_code_cites(ev, tier, tag))
        errs.extend(_check_rules_threshold(ev, tag, logic_counts))
        errs.extend(_check_reviewed(ev, tag))
        errs.extend(_check_demo(q, ev, tag))

        if not q.get("advice_allowed", False):
            for g in q.get("groups", []):
                for o in g.get("options", []):
                    hit = ADVICE_WORDS.search(str(o.get("cost", "")))
                    if hit:
                        errs.append(
                            f"{tag} 选项 {o.get('key')}: advice_allowed=false 却带建议措辞"
                            f"「{hit.group()}」—— 规则/账务口径题标建议等于替业务拍板")

        errs.extend(_check_branches(q, tag))
        for r in q.get("reveal", []):
            own_keys = {o.get("key") for g in q.get("groups", []) for o in g.get("options", [])}
            if str(r.get("when")) not in own_keys:
                errs.append(f"{tag}: reveal.when「{r.get('when')}」不是本题任何选项的 key")

    for kind, items in (doc.get("links") or {}).items():
        for it in items or []:
            errs.extend(_check_link(kind, it, layer_of))

    return errs


def _norm(s):
    return re.sub(r"\s+", "", str(s))


def _check_rules_threshold(ev, tag, logic_counts):
    """超过阈值的逻辑必须沉淀进 rules/,不许 inline 在题目里(D19)。"""
    code_cites = [c for c in ev.get("cites", []) if c.get("kind") == "code"]
    if not code_cites or ev.get("rules_ref"):
        return []
    files = {c.get("path") for c in code_cites}
    max_br = max((len(c.get("branches") or []) for c in code_cites), default=0)
    why = []
    if max_br > 2:
        why.append(f"分支 {max_br} 条(>2)")
    if len(files) > 1:
        why.append(f"跨 {len(files)} 个文件")
    if any(logic_counts.get(_norm(c.get("logic", "")), 0) > 1 for c in code_cites):
        why.append("logic 文本被别的题复用")
    if not why:
        return []
    return [f"{tag}: {'、'.join(why)} —— 超过 inline 阈值,必须沉淀进 "
            f"rules/<模块名>.md 并给 rules_ref;同一段逻辑抄多遍会写不一致、也拼不出整体"]


def _check_reviewed(ev, tag):
    """reviewed 选填 —— 没审也能出包,页面如实标『未经独立复核』。填了就要完整。"""
    rv = ev.get("reviewed")
    if rv is None:
        return []
    errs = [f"{tag}: reviewed 缺 `{f}`" for f in ("by", "on", "diffs")
            if rv.get(f) in (None, "")]
    if not errs and int(rv.get("diffs") or 0) > 0 and not str(rv.get("note") or "").strip():
        errs.append(f"{tag}: reviewed.diffs>0 必须写 `note` —— 盲审发现的差异怎么处理的要留痕")
    return errs


def validate_refs(doc, root):
    """摸文件系统的校验:规则文档存在、条目编号找得到、text 没和文档漂移。"""
    errs, root = [], Path(root)
    for q in doc.get("questions", []):
        for r in (q.get("evidence") or {}).get("rules_ref") or []:
            tag = f"问题 {q.get('no')}"
            f = root / str(r.get("doc", ""))
            if not f.is_file():
                errs.append(f"{tag}: rules_ref 指向的规则文档不存在: {r.get('doc')}")
                continue
            body = f.read_text(encoding="utf-8", errors="replace")
            m = next((m for m in RULE_ENTRY.finditer(body) if m.group("id") == r.get("id")), None)
            if not m:
                errs.append(f"{tag}: {r.get('doc')} 里找不到条目 {r.get('id')}")
                continue
            if _norm(r.get("text", "")) not in _norm(body[m.start():m.start() + 800]):
                errs.append(f"{tag}: rules_ref {r.get('id')} 的 text 与 {r.get('doc')} 里的"
                            f"条目不一致 —— 规则文档改过了,题目里的副本没跟上")
    return errs


def _check_code_cites(ev, tier, tag):
    """code 档的失败模式不是『原话被改写』,而是『单点引用冒充整体逻辑』。
    一行赋值不证明它是唯一赋值点、没有别处覆盖、没有 flag 短路。"""
    errs, code_cites = [], [c for c in ev.get("cites", []) if c.get("kind") == "code"]
    has_rules = bool(ev.get("rules_ref"))
    for c in code_cites:
        where = f"{c.get('path')}:{c.get('line')}"
        if not has_rules and not str(c.get("logic") or "").strip():
            errs.append(f"{tag}: code 引用 {where} 缺 `logic` —— 要有一句白话说清"
                        f"这段代码实际做什么,给业务否掉的机会（或改为引 rules_ref）")
        if not str(c.get("entry") or "").strip():
            errs.append(f"{tag}: code 引用 {where} 缺 `entry` —— 业务问的是『页面上』,"
                        f"得指出这段逻辑从哪个页面/接口进来")
        if not c.get("branches"):
            errs.append(f"{tag}: code 引用 {where} 缺 `branches` —— 分支穷举义务同样适用于证据;"
                        f"确实没读完请写 branches_exhaustive:false")
    if any(c.get("branches_exhaustive") is False for c in code_cites) and tier != "guess":
        errs.append(f"{tag}: 有 code 引用声明 branches_exhaustive:false,"
                    f"该题 evidence.tier 必须降为 guess 并写 weak —— 没读完的逻辑不得冒充有据")
    return errs


def _check_demo(q, ev, tag):
    """演示数字是照逻辑算出来的。逻辑从哪来必须说清,否则业务照凭空的数字选口径。"""
    demo = q.get("demo")
    if not demo:
        return []
    basis = demo.get("basis")
    if basis not in ("branches", "assumed"):
        return [f"{tag}: demo.basis 必须是 branches 或 assumed,实际「{basis}」"
                f" —— 演示数字得说清算法从哪来"]
    if basis == "branches":
        has = any(c.get("branches") for c in ev.get("cites", []) if c.get("kind") == "code")
        if not has:
            return [f"{tag}: demo.basis=branches 但没有任何 code 引用的 branches 可依据;"
                    f"若数字是开发自己假设的算法,请改 basis=assumed(页面会标注未从代码验证)"]
    return []


def _check_branches(q, tag):
    """分支对称:部分选项有后续、部分没有 → 没后续的必须显式 terminal。"""
    main = next((g for g in q.get("groups", []) if g.get("id") == "main"), None)
    if not main:
        return []
    downstream = {str(r.get("when")) for r in q.get("reveal", [])}
    opts = main.get("options", [])
    has = [o for o in opts if str(o.get("key")) in downstream]
    if not has:                     # 整组到此为止,不必逐个标注
        return []
    return [f"{tag} 选项 {o.get('key')}: 同组里 {has[0].get('key')} 有后续而它没有,"
            f"若确实到此为止请显式标 terminal:true —— 不对称的分支通常是漏了"
            for o in opts
            if str(o.get("key")) not in downstream and not o.get("terminal")]


def _check_link(kind, it, layer_of):
    errs, tgt = [], str(it.get("target") or it.get("to") or "")
    tgt_no = int(tgt.split(".")[0]) if tgt.split(".")[0].isdigit() else None
    refs = _when_refs(it.get("when", "")) | (
        {int(str(it.get("from", "")).split(".")[0])}
        if str(it.get("from", "")).split(".")[0].isdigit() else set())
    for r in sorted(refs):
        if r not in layer_of:
            errs.append(f"links.{kind}: 引用了不存在的问题 {r}")
        elif r == tgt_no:
            continue          # 同题内主问决定子问,天然同层,不是反向依赖
        elif tgt_no in layer_of and layer_of[r] >= layer_of[tgt_no]:
            errs.append(
                f"links.{kind}: 问题 {tgt_no}(layer {layer_of[tgt_no]}) 依赖问题 "
                f"{r}(layer {layer_of[r]}) —— 反向或同层依赖,前置必须在更早的 layer")
    return errs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_path")
    ap.add_argument("-o", "--out")
    ap.add_argument("--md")
    ap.add_argument("--check", action="store_true", help="只校验不出包")
    ap.add_argument("--root", default=".", help="项目根,用于解析 rules_ref 的路径")
    args = ap.parse_args()

    doc = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    errs = validate(doc) + validate_refs(doc, args.root)
    for e in errs:
        print(f"  ✗ {e}")
    if errs:
        print(f"\n✗ 校验未通过: {len(errs)} 项。修正后重跑;不出包。")
        sys.exit(1)
    print(f"✓ 校验通过: {len(doc['questions'])} 道题 / {len(doc['roles'])} 个角色")
    if args.check:
        return


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m unittest discover -s tests -p 'test_build*.py' -v`
Expected: PASS，26 个测试

- [ ] **Step 5: 写 schema 契约文档**

Create `templates/questionnaire.schema.json`。它是**给出题者读的契约**，不参与运行时校验（校验在 `build_questionnaire.py`）：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "requirement-clarifier 确认单题目数据",
  "description": "语义校验(依赖闭环/分支对称/建议措辞)由 scripts/build_questionnaire.py 执行,JSON Schema 无法表达。",
  "type": "object",
  "required": ["doc", "roles", "questions"],
  "properties": {
    "doc": {
      "type": "object",
      "required": ["id", "title", "round", "sent_by", "sent_on", "usage"],
      "properties": {
        "round": {"type": "integer", "description": "第 N 轮确认单。与 questions[].layer(依赖层级)是两个概念。"},
        "code_rev": {"type": "string", "description": "build 时自动填 git rev-parse HEAD;仓库外运行留空。单子发出到收回代码可能变过,没有 rev 就说不出『当时代码是这样的』。"},
        "due_days": {"type": "integer", "default": 3},
        "usage": {"type": "string", "description": "给业务看的『你的答案会被用到哪里』"}
      }
    },
    "roles": {
      "type": "array", "minItems": 1,
      "items": {"type": "object", "required": ["id", "name"]},
      "description": "回答人必须在此声明;questions[].who 只能引用 id。"
    },
    "part1": {
      "type": "array",
      "items": {"type": "object", "required": ["n", "we_understand"],
                "properties": {"note": {"type": "string"}}},
      "description": "第一部分逐条核对项。页面渲染为三态(对/不对/未表态),不设全局『无异议』。"
    },
    "layers": {"type": "array", "items": {"type": "object", "required": ["n"]}},
    "questions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["no", "layer", "title", "who", "advice_allowed", "evidence", "groups"],
        "properties": {
          "blocking": {"type": "boolean", "default": false},
          "advice_allowed": {
            "type": "boolean",
            "description": "false = 规则/账务口径题,模板不渲染任何建议位,选项里出现建议措辞则拒绝出包。"
          },
          "evidence": {
            "type": "object", "required": ["tier"],
            "properties": {
              "tier": {"enum": ["src", "code", "guess"]},
              "cites": {"type": "array", "items": {
                "type": "object", "required": ["kind", "path", "line", "snippet"],
                "properties": {
                  "kind": {"enum": ["src", "code"]},
                  "logic": {"type": "string", "description": "kind=code 必填:一句白话说清这段代码实际做什么。这是开发对代码的解读,不是代码原文,页面上会标明。"},
                  "entry": {"type": "string", "description": "kind=code 必填:这段逻辑从哪个页面/接口进来(path:line)。业务问的是『页面上』。"},
                  "branches": {"type": "array", "description": "kind=code 必填:分支列表。",
                    "items": {"type": "object", "required": ["cond", "then"],
                              "properties": {"cite": {"type": "string"}}}},
                  "branches_exhaustive": {"type": "boolean", "default": true,
                    "description": "false = 没读完;此时该题 evidence.tier 必须降为 guess。"}
                }}},
              "weak": {"type": "string", "description": "tier=guess 必填:哪儿没据、为什么还问。"}
            }
          },
          "groups": {
            "type": "array",
            "items": {
              "type": "object", "required": ["id", "options"],
              "properties": {
                "id": {"type": "string", "description": "'main' 为主问,其余为子问。"},
                "ask": {"type": "string", "description": "子问的问法,会成为回执里『小问：答案』的左半。"},
                "tier": {"enum": ["src", "code", "guess"], "description": "子问可单独标无据,不必整题降档。"},
                "inline": {"type": "boolean"},
                "options": {"type": "array", "items": {
                  "type": "object", "required": ["key", "label"],
                  "properties": {
                    "cost": {"type": "string", "description": "该选项的代价/影响。"},
                    "terminal": {"type": "boolean", "description": "显式声明此分支到此为止。"},
                    "kind": {"enum": ["nonexistent", "dontknow"],
                             "description": "nonexistent=这种情况不存在;dontknow=我不清楚。『都不是』兜底出口由模板自动追加,不在此声明。"}
                  }}}
              }
            }
          },
          "demo": {
            "type": "object",
            "properties": {
              "given": {"type": "string", "description": "演示数字的输入前提。"},
              "basis": {"enum": ["branches", "assumed"],
                        "description": "必填。branches=照 code 引用的分支算的;assumed=开发假设的算法,页面标注『未从代码验证』。"},
              "rows": {"type": "array", "items": {
                "type": "object", "required": ["when", "v"],
                "properties": {"when": {"type": "array", "items": {"type": "string"}}}}}
            }
          },
          "reveal": {"type": "array", "items": {
            "type": "object", "required": ["when", "ask"]}}
        }
      }
    },
    "links": {
      "type": "object",
      "properties": {
        "na": {"type": "array", "items": {"type": "object", "required": ["when", "target", "note"]}},
        "carry": {"type": "array", "items": {"type": "object", "required": ["from", "to"]}},
        "clash": {"type": "array", "items": {
          "type": "object", "required": ["when", "why"],
          "properties": {"require_explain": {"type": "boolean", "default": true}}}}
      }
    }
  }
}
```

- [ ] **Step 6: 提交**

```bash
git add scripts/build_questionnaire.py templates/questionnaire.schema.json tests/test_build_questionnaire.py
git commit -m "feat: questionnaire.json 契约与校验器

把出题纪律变成机检：角色必须 id 引用（防幽灵收件人）、依赖闭环、分支对称
（不对称通常是漏了分支，而一次性发单没有 AI 追问的机会）、advice_allowed=false
禁建议措辞（防锚定替答）、guess 档必须写清哪儿没据。"
```

---

### Task 2: 逾期提醒样例 questionnaire.json

先有真实数据，Task 3 的渲染器才有东西可渲染。沿用 `examples/demo-project` 已有的逾期提醒案例，引用真实的归档原话行号。

**Files:**
- Create: `templates/rules-template.md`（规则文档骨架，原来只有口头描述没有模板）
- Create: `examples/demo-project/app/reminder_rules.py`（桩件，让样例能演示 `code` 档证据）
- Create: `examples/demo-project/docs/requirements/rules/reminder.md`（从源码逆向出的业务概念层）
- Create: `examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json`
- Modify: `examples/README.md`
- Test: `tests/test_example_questionnaire.py`

**Interfaces:**
- Consumes: `build_questionnaire.validate()`（Task 1）
- Produces: 样例 json 路径，Task 3/6 均引用它

- [ ] **Step 1: 写失败测试**

Create `tests/test_example_questionnaire.py`：

```python
import json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_questionnaire as bq

EXAMPLE = (ROOT / "examples/demo-project/docs/requirements/questionnaires"
                  "/2026-07-11-逾期提醒-r1.json")


class TestExample(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_passes_validation(self):
        self.assertEqual(bq.validate(self.doc), [])

    def test_example_passes_ref_validation(self):
        """rules_ref 的条目编号与 text 必须和规则文档对得上。"""
        self.assertEqual(bq.validate_refs(self.doc, ROOT / "examples/demo-project"), [])

    def test_example_demonstrates_rules_ref_and_review(self):
        """样例要演示业务概念层与盲审留痕，否则读者看不到这两件事长什么样。"""
        evs = [q["evidence"] for q in self.doc["questions"]]
        self.assertTrue(any(e.get("rules_ref") for e in evs), "样例应有一道题引 rules_ref")
        self.assertTrue(any(e.get("reviewed") for e in evs), "样例应有一道题带 reviewed")

    def test_example_exercises_all_three_link_kinds(self):
        links = self.doc["links"]
        for kind in ("na", "clash"):
            self.assertTrue(links.get(kind), f"样例应演示 links.{kind}")

    def test_rule_questions_forbid_advice(self):
        # 「逾期从哪天起算」是账务口径题,不得允许建议
        q1 = next(q for q in self.doc["questions"] if q["no"] == 1)
        self.assertFalse(q1["advice_allowed"])

    def test_cites_point_at_real_archived_lines(self):
        base = ROOT / "examples/demo-project"
        for q in self.doc["questions"]:
            for c in q["evidence"].get("cites", []):
                f = base / c["path"]
                self.assertTrue(f.is_file(), f"引用的文件不存在: {c['path']}")
                lines = f.read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(c["line"], len(lines),
                                     f"{c['path']} 只有 {len(lines)} 行,引用了 {c['line']}")
                self.assertIn(c["snippet"].strip(), lines[c["line"] - 1],
                              f"{c['path']}:{c['line']} 找不到片段「{c['snippet']}」")

    def test_code_cite_entry_and_branch_coordinates_resolve(self):
        """code 档的 entry 与每个 branch 的 cite 也必须是真坐标,不是编的。"""
        base = ROOT / "examples/demo-project"

        def resolve(coord):
            path, _, line = str(coord).rpartition(":")
            f = base / path
            self.assertTrue(f.is_file(), f"坐标指向的文件不存在: {coord}")
            n = len(f.read_text(encoding="utf-8").splitlines())
            self.assertTrue(0 < int(line) <= n, f"{coord} 超出文件行数 {n}")

        seen = 0
        for q in self.doc["questions"]:
            for c in q["evidence"].get("cites", []):
                if c.get("kind") != "code":
                    continue
                seen += 1
                resolve(c["entry"])
                for b in c["branches"]:
                    if b.get("cite"):
                        resolve(b["cite"])
        self.assertGreater(seen, 0, "样例应至少有一道 code 档题,否则演示不到最易出错的证据类型")

    def test_demo_basis_declared_where_demo_exists(self):
        for q in self.doc["questions"]:
            if q.get("demo"):
                self.assertIn(q["demo"].get("basis"), ("branches", "assumed"),
                              f"问题 {q['no']} 的 demo 未声明 basis")


if __name__ == "__main__":
    unittest.main()
```

最后一个测试是**防幻觉的关键**：它保证样例里的每条 `> 证据:` 引用真的指向归档原文的那一行，而不是编出来的坐标。

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_example_questionnaire -v`
Expected: FAIL — `FileNotFoundError`（样例 json 还不存在）

- [ ] **Step 3: 写代码桩件**

样例项目原本只有 `docs/`，无法演示 `code` 档证据——而 `code` 档恰恰是最容易"单点引用
冒充整体逻辑"的一类。加一个最小桩件，行号必须与下面完全一致（Task 2 的测试会逐条核验坐标）。

Create `examples/demo-project/app/reminder_rules.py`：

```python
"""逾期提醒的现有判定逻辑。

demo 桩件：让样例确认单能演示 code 档证据（logic / entry / branches）。
真实项目里这里是你自己的代码。
"""
GRACE_DAYS = 0


def is_overdue(bill, today):
    if bill.due_date is None:          # 没填账期的单子没有到期日
        return False
    return today > bill.due_date + GRACE_DAYS


def should_remind(bill, today, sent_times):
    if not is_overdue(bill, today):
        return False
    if bill.balance <= 0:              # 余额清零即视为已还清,不看状态字段
        return False
    return sent_times < 3              # 最多发 3 次
```

在 `examples/README.md` 末尾加一段说明，免得读者以为 skill 要求这个目录结构：

```markdown
## 关于 `app/reminder_rules.py`

这是**桩件**，不是 skill 的目录约定。它存在的唯一目的是让样例确认单能演示
`code` 档证据——`logic`（白话逻辑）／`entry`（页面入口）／`branches`（分支），
以及测试如何逐条核验这些坐标是真的。真实项目里对应的是你自己的代码。
```

- [ ] **Step 4: 写规则模板与样例规则文档**

先建模板。`SKILL.md` 原来只描述了"做成勾选格式——每条留有效/已废弃/需修改位"，没有模板文件。

Create `templates/rules-template.md`：

```markdown
# 规则文档：<来源名>
> 来源：<Excel 导出件 / 源码模块> · 逆向日期 · 逆向人 · **规则 owner：<谁能裁决这些规则>**
> 代码依据取自 <code_rev>（源码逆向时填；这之后代码若变动，条目需重新确认）

每条请 owner 勾一个：☐ 有效　☐ 已废弃　☐ 需修改（写明怎么改）

**这里有两条不同的轴，别压成一条：**

| 轴 | 问的是 | 谁判 | 机器能查吗 |
|---|---|---|---|
| 下面每条的 `> 证据:` 坐标 | 代码/表格**确实是这么写的** | 坐标说话 | 能（grep） |
| owner 勾选 | 这条规则**该不该继续有效** | 业务裁决 | 不能 |

一条规则可以「代码确实这么写」**同时**被 owner 判「已废弃」——这正是逆向老系统最常见的
情形。所以：**未勾选时，不得把这条规则当作「业务已认可的规则」写进 spec**（按【假设】入账）；
但它作为「现状是什么」的陈述仍然成立、仍然可核验，确认单里照样可以引它来问业务。

## R1. <一句业务语言的规则——业务能看懂，不出现表结构/字段名/接口>

☐ 有效　☐ 已废弃　☐ 需修改：______

> 证据: <path>:<line> | "<原文片段>"

- 入口：`<path:line>`（源码逆向时填，指出这条规则从哪个页面/接口进来）
- 分支：
  - <条件> → <结果>（`<path:line>`）
  - <条件> → <结果>（`<path:line>`）
- 分支是否穷举：☐ 是　☐ 否（说明：______）
- 独立复核：☐ 未复核　☐ 已盲审（日期 ____ / 差异 __ 处 / 处置：______）
```

再写样例规则文档。**注意分支有三条**——最初我只列了两条（余额 ≤ 0 和已逾期），漏了"未逾期"那条，这本身就是"单点引用冒充整体逻辑"的活例子，正好用来演示盲审抓到了什么。

Create `examples/demo-project/docs/requirements/rules/reminder.md`：

```markdown
# 规则文档：逾期提醒（源码逆向）
> 来源：源码模块 `app/reminder_rules.py` · 逆向 2026-07-11 · 逆向人：开发 · **规则 owner：财务 王芳**
> 代码依据取自 HEAD（这之后代码若变动，条目需重新确认）

每条请 owner 勾一个：☐ 有效　☐ 已废弃　☐ 需修改（写明怎么改）
**未勾选的按【假设】处理，不得作为开发依据。**

## R1. 没填账期的单子不算逾期，一直不会触发提醒

☐ 有效　☐ 已废弃　☐ 需修改：______

> 证据: app/reminder_rules.py:10 | "if bill.due_date is None:"

- 入口：`app/reminder_rules.py:9`
- 分支：
  - 没有到期日 → 不算逾期（`app/reminder_rules.py:11`）
  - 有到期日 → 过了到期日才算逾期（`app/reminder_rules.py:12`）
- 分支是否穷举：☐ 是　☐ 否（说明：______）
- 独立复核：☐ 未复核　☐ 已盲审（日期 ____ / 差异 __ 处 / 处置：______）

## R3. 已还清的判定：余额清零即视为已还清，不看单子的状态字段

☑ 有效　☐ 已废弃　☐ 需修改：______（王芳 2026-07-11 电话确认）

> 证据: app/reminder_rules.py:18 | "if bill.balance <= 0:"

- 入口：`app/reminder_rules.py:15`
- 分支：
  - 还没到逾期 → 不提醒（`app/reminder_rules.py:17`）
  - 余额 ≤ 0 → 不提醒（`app/reminder_rules.py:19`）
  - 已逾期且余额 > 0 → 提醒，累计发满 3 次为止（`app/reminder_rules.py:20`）
- 分支是否穷举：☑ 是　☐ 否（说明：______）
- 独立复核：☐ 未复核　☑ 已盲审（日期 2026-07-11 / 差异 1 处 / 处置：复核方独立读代码时列出了"还没到逾期"这条分支，原稿只写了余额和逾期两条，已补入）
```

两处刻意的细节：

- **条目编号跳过 R2**——真实逆向里条目会增删，编号不该被要求连续，`validate_refs` 只按 id 查找。
- **R1 的 owner 勾选留空、R3 勾了「有效」**——演示两条轴的区别。R1 的 `> 证据:` 坐标一样
  可核验（代码确实这么写），但 owner 还没裁决它该不该继续有效，所以它不得作为「业务已认可
  的规则」写进 spec；R3 王芳验真过，问题 4 才引它。**`evidence.tier` 与 owner 勾选是两条
  独立的轴**，前者说来源可不可核验，后者说规则该不该有效。

- [ ] **Step 5: 写样例 json**

Create `examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json`。引用的两行原话来自 `raw/2026-07-10-李姐微信语音转述.md` 第 6 行「别发太勤,客户烦。」与第 7 行「对了,提醒完了要是还没还,过几天再提醒一次。」：

```json
{
  "doc": {
    "id": "逾期提醒", "title": "逾期提醒", "round": 1,
    "sent_by": "开发", "sent_on": "2026-07-11", "due_days": 3,
    "usage": "您的答案会写进开发规格并落库存档，日后提醒发错时按这份回执追溯——照实答，不确定的地方标出来比猜一个更有用。"
  },
  "roles": [
    {"id": "fin_wang", "name": "财务 王芳"},
    {"id": "ops_li", "name": "运营 李姐"}
  ],
  "part1": [
    {"n": 1, "we_understand": "客户逾期后系统自动提醒，不再靠财务翻表人工发。",
     "note": "如有异议请说明"},
    {"n": 2, "we_understand": "营销类短信要审批、业务通知类不用——本功能按业务通知类走，不走审批。",
     "note": "2026-06-20 已确认过的口径"}
  ],
  "layers": [
    {"n": 1, "why": "起算日与是否继续提醒决定其余规则"},
    {"n": 2}
  ],
  "questions": [
    {
      "no": 1, "layer": 1, "blocking": true,
      "title": "「逾期」从哪天起算？",
      "who": ["fin_wang"],
      "background": "合同到期没还就算逾期，还是给几天宽限期？这决定提醒的触发时点。",
      "advice_allowed": false,
      "evidence": {
        "tier": "src",
        "cites": [{"kind": "src",
                   "path": "docs/requirements/raw/2026-07-10-李姐微信语音转述.md",
                   "line": 4,
                   "snippet": "客户逾期了系统就提醒一下呗"}],
        "weak": null
      },
      "groups": [{"id": "main", "options": [
        {"key": "A", "label": "到期日次日即逾期", "terminal": true},
        {"key": "B", "label": "有宽限期，宽限期后才算"},
        {"key": "dk", "kind": "dontknow", "label": "我不清楚", "terminal": true}
      ]}],
      "reveal": [{"when": "B", "ask": "宽限期几天"}]
    },
    {
      "no": 2, "layer": 2,
      "title": "重复提醒的频率和上限？",
      "who": ["ops_li"],
      "background": "您说「别发太勤」「过几天再提醒」，需要落成具体数字才能开发。",
      "advice_allowed": true,
      "evidence": {
        "tier": "src",
        "cites": [
          {"kind": "src", "path": "docs/requirements/raw/2026-07-10-李姐微信语音转述.md",
           "line": 6, "snippet": "别发太勤"},
          {"kind": "src", "path": "docs/requirements/raw/2026-07-10-李姐微信语音转述.md",
           "line": 7, "snippet": "过几天再提醒一次"}
        ]
      },
      "groups": [
        {"id": "main", "options": [
          {"key": "A", "label": "每 3 天一次，最多 3 次",
           "cost": "开发建议：选 A，上限明确、好排查"},
          {"key": "B", "label": "每 7 天一次，直到还清", "terminal": true}
        ]},
        {"id": "after_cap", "ask": "达到上限后还没还，怎么办",
         "inline": true, "tier": "guess",
         "options": [
           {"key": "manual", "label": "转人工跟进"},
           {"key": "stop", "label": "就此停止，不再提醒"}
         ]}
      ],
      "reveal": [{"when": "A", "ask": "达到上限后怎么办"}]
    },
    {
      "no": 4, "layer": 1,
      "title": "「已还清」按余额判还是按状态字段判？",
      "who": ["fin_wang"],
      "background": "代码现在按余额是否清零判定已还清。如果单子的状态字段和余额可能不一致（比如做过差额处理但余额没归零），就会继续发提醒。",
      "advice_allowed": false,
      "evidence": {
        "tier": "code",
        "rules_ref": [{
          "id": "R3",
          "doc": "docs/requirements/rules/reminder.md",
          "text": "已还清的判定：余额清零即视为已还清，不看单子的状态字段"
        }],
        "reviewed": {
          "by": "独立盲审", "on": "2026-07-11", "diffs": 1,
          "note": "复核方独立读代码时列出了「还没到逾期」这条分支，原稿只写了余额和逾期两条，已补入 R3"
        },
        "cites": [{
          "kind": "code",
          "path": "app/reminder_rules.py", "line": 18,
          "snippet": "if bill.balance <= 0:",
          "entry": "app/reminder_rules.py:15",
          "branches": [
            {"cond": "还没到逾期", "then": "不提醒", "cite": "app/reminder_rules.py:17"},
            {"cond": "余额 ≤ 0", "then": "不再提醒", "cite": "app/reminder_rules.py:19"},
            {"cond": "余额 > 0 且已逾期", "then": "提醒，累计发满 3 次为止", "cite": "app/reminder_rules.py:20"}
          ],
          "branches_exhaustive": true
        }]
      },
      "groups": [{"id": "main", "options": [
        {"key": "A", "label": "就按余额判（与现在代码一致，不用改）", "terminal": true},
        {"key": "B", "label": "按状态字段判（差额处理过的单子即视为已还清）", "terminal": true}
      ]}],
      "demo": {
        "given": "一张单子应收 1000 元，收到 950 元，剩 50 元做了差额处理但余额字段仍为 50",
        "basis": "branches",
        "rows": [
          {"when": ["A"], "k": "系统行为", "v": "继续提醒"},
          {"when": ["B"], "k": "系统行为", "v": "停止提醒"}
        ]
      }
    },
    {
      "no": 3, "layer": 1, "blocking": true,
      "title": "客户还了一部分，还提醒吗？",
      "who": ["fin_wang"],
      "background": "部分还款后单子仍有余额，是继续提醒还是停。",
      "advice_allowed": false,
      "evidence": {
        "tier": "guess", "cites": [],
        "weak": "整题无据：部分还款这个场景李姐没提过，是开发从盲区清单（金额与账务口径）推出来的。如果业务上不存在部分还款，请直接判本题不成立。"
      },
      "groups": [{"id": "main", "options": [
        {"key": "A", "label": "只要有余额就继续提醒", "terminal": true},
        {"key": "B", "label": "部分还款后暂停，由人工决定", "terminal": true}
      ]}]
    }
  ],
  "links": {
    "na": [{"when": "2=B", "target": "2.after_cap",
            "note": "因问题 2 选了 B：一直提醒到还清，没有上限"}],
    "carry": [],
    "clash": [{"when": "3=B & 2=B",
               "why": "问题 2 选 B 是「一直自动提醒到还清」，问题 3 选 B 是「部分还款后交人工决定」——两者对「什么时候停」给了不同答案，客户还了一部分之后到底还发不发？",
               "require_explain": true}]
  }
}
```

`links.na` 的 `when: "2=B"` 与 `target: "2.after_cap"` 是**同一题内的组间依赖**——主问
决定子问，天然同层，Task 1 的 `_check_link` 已对自引用豁免层级检查。

- [ ] **Step 6: 运行测试，确认通过**

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
Expected: PASS，全部测试通过（含 `test_cites_point_at_real_archived_lines` —— 它保证
样例里每条引用真的指向归档原文那一行）

- [ ] **Step 7: 提交**

```bash
git add templates/rules-template.md examples/demo-project/app/ examples/README.md \
        examples/demo-project/docs/requirements/rules/ \
        examples/demo-project/docs/requirements/questionnaires/ \
        tests/test_example_questionnaire.py
git commit -m "feat: 逾期提醒样例 questionnaire.json

演示 reveal / links.na / links.clash 三种依赖，含一道 tier=guess 的无据题
（部分还款场景是从盲区清单推的，不是业务说过的）。测试逐条核验 cites 真的
指向归档原文那一行、code 档的 entry 与每个 branch 的 cite 也是真坐标，防编造。

加了 app/reminder_rules.py 桩件：样例原本只有 docs/，演示不到 code 档——而 code 档
恰恰是最容易『单点引用冒充整体逻辑』的一类。

问题 4 走业务概念层：三条分支超过 inline 阈值，逻辑沉淀进 rules/reminder.md 的 R3，
题目只引条目编号 + 业务语言那一句。R3 的 reviewed 记录了盲审真实抓到的东西——原稿
漏了『还没到逾期』这条分支，这正是单点引用会漏掉的那类东西。

同时补 templates/rules-template.md：SKILL.md 原来只描述了勾选格式，没有模板文件。"
```

---

### Task 3: HTML 模板从 JSON 渲染

把原型从"硬编码 11 道 AR 题"改造成"运行时从注入的 JSON 渲染"。原型的样式与交互逻辑（条件显隐、跨题联动、演示数字结算条、逐条核对、证伪出口、身份分区、人读预览、回执导出）已在浏览器里验证过，本任务只换数据来源。

**Files:**
- Create: `templates/questionnaire.html`（从 `docs/superpowers/specs/2026-08-27-html-questionnaire-prototype.html` 移植）
- Modify: `scripts/build_questionnaire.py`（加 `render_html`）
- Test: `tests/test_render_html.py`

**Interfaces:**
- Consumes: `validate()`（Task 1）、样例 json（Task 2）
- Produces:
  - `render_html(doc: dict, template: str) -> str` — 把 `doc` 注入模板的 `<script id="qdata">` 占位块
  - `TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "questionnaire.html"`
  - 模板侧 JS 全局：`buildReceipt() -> str`、`renderPreview() -> str`（回执与预览，供 Task 5 的样例回执生成）

- [ ] **Step 1: 写失败测试**

Create `tests/test_render_html.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_render_html -v`
Expected: FAIL — `AttributeError: module 'build_questionnaire' has no attribute 'TEMPLATE_PATH'`

- [ ] **Step 3: 移植模板**

从原型建模板：

```bash
cp docs/superpowers/specs/2026-08-27-html-questionnaire-prototype.html \
   templates/questionnaire.html
```

然后做四处改造（其余 CSS 与交互函数原样保留）：

**3a. 抬头与题目区改为空壳 + 数据块。** 删掉 `<header class="masthead">` 到 `</section>`（第二部分结尾）之间**所有写死的项目内容**，替换为容器与数据占位：

```html
<script id="qdata" type="application/json">__QUESTIONNAIRE_DATA__</script>

<header class="masthead" id="masthead"></header>
<div class="howto" id="howto"></div>
<div class="statusbar">
  <div class="meter"><i id="meter"></i></div>
  <div class="status-text" id="statusText">尚未开始</div>
  <button class="btn ghost" type="button" onclick="jumpNext()">跳到下一道未答</button>
  <div class="whorow" id="whoRow"></div>
</div>
<div class="body">
  <nav class="rail" aria-label="题号索引">
    <div class="rail-hd">题号索引</div>
    <ol id="rail"></ol>
  </nav>
  <main>
    <section class="part" id="part1"></section>
    <section class="part" id="part2"></section>
  </main>
</div>
<section class="signoff" id="signoff"></section>
```

**3b. 加渲染器。** 在 `<script>` 顶部（`const QS = ...` 之前）插入，把 JSON 渲染成原型那套 DOM：

```javascript
const DATA = JSON.parse(document.getElementById('qdata').textContent);
const ROLE_NAME = Object.fromEntries(DATA.roles.map(r => [r.id, r.name]));
const esc = s => String(s ?? '').replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const TIER_LABEL = {src:['原话','src'], code:['代码','code'], guess:['无据 · 请证伪','guess']};

function renderMasthead(){
  const d = DATA.doc, blocking = DATA.questions.filter(q => q.blocking).map(q => q.no);
  document.getElementById('masthead').innerHTML = `
    <div class="masthead-main">
      <div class="doc-kicker">需求确认单 · 第 ${d.round} 轮</div>
      <h1>${esc(d.title)}</h1>
      <div class="doc-meta">
        发出人：<b>${esc(d.sent_by)}</b>　·　发出日期：<b>${esc(d.sent_on)}</b><br>
        本轮共 <b>${DATA.questions.length} 道</b>待确认问题${
          blocking.length ? `，其中 <b>问题 ${blocking.join('、')}</b> 请先答` : ''}。<br>
        <span class="usage">${esc(d.usage)}</span>
        ${d.code_rev ? `<span class="rev">代码依据取自 ${esc(d.code_rev.slice(0,8))}
          —— 这之后代码若有变动，结论需重新确认</span>` : ''}
      </div>
    </div>
    <div class="seal"><span class="no">${esc(d.id)}</span>
      <span class="v">v${d.round} / R${d.round}</span>
      <span class="due">回填期限<br>${d.due_days ?? 3} 个工作日</span></div>`;
  document.getElementById('howto').innerHTML =
    '第一部分请<b>逐条核对</b>；第二部分请<b>点选</b>选项、必要处补充说明。'
  + '标注「建议由 XX 回答」的题目不归您管，<b>请转交对应的人</b>——转交比替答重要。'
  + '答不了的题可以留空先发，剩下的转交别人接着填。填完点底部<b>导出回执</b>发回即可。';
  document.title = `需求确认单 · ${d.title}`;
}

function renderPart1(){
  if(!DATA.part1?.length){ document.getElementById('part1').remove(); return; }
  const rows = DATA.part1.map(r => `
    <tr><td class="n">${r.n}</td><td>${esc(r.we_understand)}</td>
      <td class="rm">${esc(r.note || '')}</td>
      <td class="chk">
        <label class="mini"><input type="radio" name="p1-${r.n}" value="ok"><span class="mk"></span>对</label>
        <label class="mini"><input type="radio" name="p1-${r.n}" value="no"><span class="mk"></span>不对</label>
        <textarea class="p1why" id="p1-${r.n}-why" rows="2" placeholder="哪里不对"></textarea>
      </td></tr>`).join('');
  document.getElementById('part1').innerHTML = `
    <div class="part-hd"><h2>第一部分 · 我们理解的</h2>
      <span class="hint">请逐条核对，不对的地方写在旁边</span></div>
    <table class="ledger">
      <thead><tr><th class="n">#</th><th>我们理解的</th><th class="rm">备注</th>
        <th class="chk">对不对</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="ans"><label for="a-part1">上面之外，还想让我们知道的（选填）</label>
      <textarea id="a-part1" rows="2"></textarea></div>`;
}

/* 依据区分两层：外层给业务看白话，坐标折叠在内层给开发与复核。
   业务看不懂 app/models/receivable.py:41，直接怼给他是噪音。 */
function citeHtml(c){
  const kindLabel = c.kind === 'src' ? '原话' : '代码';
  const coords = `<code>&gt; 证据: ${esc(c.path)}:${c.line} | "${esc(c.snippet)}"</code>`;
  if(c.kind !== 'code')
    return `<div class="cite"><span class="cite-k src">${kindLabel}</span>${coords}</div>`;
  const brs = (c.branches || []).map(b =>
    `<li>${esc(b.cond)} → ${esc(b.then)}${b.cite ? ` <code>${esc(b.cite)}</code>` : ''}</li>`).join('');
  return `<div class="cite code-cite">
      <div class="logic"><b>我们查代码看到系统现在是这么做的：</b>${esc(c.logic)}
        <span class="logic-note">（这是开发读代码得出的理解，不是您说过的话——不对请直接指出）</span></div>
      <details class="coords"><summary>代码位置与分支（开发看）</summary>
        <div>${coords}</div>
        <div class="entry">入口：<code>${esc(c.entry)}</code></div>
        ${brs ? `<ul class="brs">${brs}</ul>` : ''}
        ${c.branches_exhaustive === false
          ? '<div class="ev-weak">⚠ 分支未读完，本题依据已降为「无据」处理</div>' : ''}
      </details>
    </div>`;
}

/* 业务概念层：有 rules_ref 就显示规则条目那句业务语言，代码坐标留给内层。 */
function rulesHtml(ev){
  return (ev.rules_ref || []).map(r =>
    `<div class="cite rule-cite">
       <div class="logic"><b>系统现在的规则是：</b>${esc(r.text)}
         <span class="logic-note">（引自规则文档 ${esc(r.id)}，由开发读代码逆向、交规则
           owner 验真——不对请直接指出）</span></div>
       <details class="coords"><summary>规则文档位置（开发看）</summary>
         <div><code>${esc(r.doc)} · ${esc(r.id)}</code></div></details>
     </div>`).join('');
}

function reviewHtml(ev){
  const rv = ev.reviewed;
  if(!rv) return '<div class="unreviewed">未经独立复核——上面这段理解只有一个人读过代码</div>';
  return `<div class="reviewed">已独立盲审（${esc(rv.on)}，发现 ${rv.diffs} 处差异`
       + `${rv.diffs > 0 ? '，已处置' : ''}）</div>`;
}

/* 已有规则条目承载业务语言时，代码引用只出坐标，不再重复一句解读。 */
function codeCoordsOnly(c){
  if(c.kind !== 'code') return citeHtml(c);
  const brs = (c.branches || []).map(b =>
    `<li>${esc(b.cond)} → ${esc(b.then)}${b.cite ? ` <code>${esc(b.cite)}</code>` : ''}</li>`).join('');
  return `<details class="coords"><summary>代码位置与分支（开发看）</summary>
      <div><code>&gt; 证据: ${esc(c.path)}:${c.line} | "${esc(c.snippet)}"</code></div>
      <div class="entry">入口：<code>${esc(c.entry)}</code></div>
      ${brs ? `<ul class="brs">${brs}</ul>` : ''}
      ${c.branches_exhaustive === false
        ? '<div class="ev-weak">⚠ 分支未读完，本题依据已降为「无据」处理</div>' : ''}
    </details>`;
}

function evHtml(q){
  const ev = q.evidence || {}, [label, cls] = TIER_LABEL[ev.tier] || TIER_LABEL.guess;
  const open = (ev.tier === 'guess' || ev.weak) ? ' open' : '';
  const hasCode = (ev.cites || []).some(c => c.kind === 'code');
  const cites = (rulesHtml(ev)
    + (ev.rules_ref?.length ? (ev.cites || []).map(codeCoordsOnly).join('')
                            : (ev.cites || []).map(citeHtml).join(''))
    + (hasCode ? reviewHtml(ev) : ''))
    || '<div class="cite none">这道题没有任何来源引用——纯粹是开发从盲区清单推的。</div>';
  return `<details class="ev tier-${cls}"${open}>
      <summary><span class="ev-badge ${cls}">${label}</span>
        <span class="ev-more">这道题的依据</span></summary>
      <div class="ev-b">${cites}${ev.weak ? `<div class="ev-weak">⚠ ${esc(ev.weak)}</div>` : ''}</div>
    </details>
    <div class="deny">
      <label class="deny-t"><input type="checkbox" class="deny-x" data-q="${q.no}">
        <span class="mk"></span>这题不成立：场景不存在，或问错了</label>
      <textarea class="deny-w" id="deny-${q.no}" rows="2"
        placeholder="为什么不成立——写清楚我们就删题，不用勉强在错的选项里挑一个"></textarea>
    </div>`;
}

function optHtml(name, o, allowAdvice){
  const isChoice = /^[A-Z]\d*$/.test(o.key);
  const extra = o.kind === 'nonexistent' || o.kind === 'dontknow' ? ' none' : '';
  const mark = o.kind === 'nonexistent' ? '⊘ ' : '';
  const cost = allowAdvice && o.cost ? `<span class="cost">${esc(o.cost)}</span>` : '';
  return `<label class="opt${extra}"><input type="radio" name="${name}" value="${esc(o.key)}"`
       + ` data-label="${esc(o.label)}"><span class="mk"></span>`
       + `<span>${isChoice ? `<span class="k">${esc(o.key)}.</span>` : ''}`
       + `${mark}${esc(o.label)}${cost}</span></label>`;
}

function groupHtml(q, g){
  const name = g.id === 'main' ? `q${q.no}` : `q${q.no}_${g.id}`;
  const opts = g.options.map(o => optHtml(name, o, q.advice_allowed)).join('');
  const ask = g.ask ? `<div class="grp-q"${g.askShort ? ` data-ask="${esc(g.askShort)}"` : ''}>`
                    + `${esc(g.ask)}</div>` : '';
  const na = DATA.links?.na?.find(l => l.target === `${q.no}.${g.id}`);
  const naAttr = na ? ` data-na-when="${esc(whenToDom(na.when))}"`
                    + ` data-na-note="${esc(na.note)}"` : '';
  return `<div class="grp" data-grp="${g.id === 'main' ? 'main' : 'sub'}"${naAttr}>`
       + `${ask}<div class="opts${g.inline ? ' inline' : ''}">${opts}</div></div>`;
}

function demoHtml(q){
  if(!q.demo) return '';
  const rows = q.demo.rows.map(r =>
    `<tr data-hit="${r.when.join('|')}"><td class="k">${esc(r.k || '结果')}</td>`
  + `<td class="v">${esc(r.v)}</td></tr>`).join('');
  const assumed = q.demo.basis === 'assumed'
    ? '<div class="demo-assumed">演示数字基于开发假设的算法，未从代码验证——'
      + '如果实际不是这么算的，请在补充说明里写明</div>' : '';
  return `<div class="demo"><div class="demo-hd"><span class="lb">演示数字</span>
      <span class="given">${esc(q.demo.given)}</span></div>
    <table><tbody>${rows}</tbody></table>${assumed}</div>`;
}

/** schema 用题号（"2=B"），DOM 用输入框 name（"q2=B"）。 */
function whenToDom(expr){ return String(expr).replace(/(^|[\s&|])(\d+)(?=\s*(?:!=|=))/g, '$1q$2'); }

function questionHtml(q){
  const who = q.who.map(id => ROLE_NAME[id] || id).join(' + ');
  const tags = [
    q.blocking ? '<span class="tag first">请先答</span>' : '',
    `<span class="tag who">建议由 ${esc(who)} 回答</span>`].join('');
  const reveals = (q.reveal || []).map(r =>
    `<div class="cond" data-when="q${q.no}=${esc(r.when)}">
       <div class="cond-hd" data-ask="${esc(r.ask)}">因您选了 ${esc(r.when)}，还要定一件事</div>
       <div class="fld"><label for="rv-${q.no}-${esc(r.when)}">${esc(r.ask)}</label>
         <input type="text" id="rv-${q.no}-${esc(r.when)}"></div>
     </div>`).join('');
  const clash = (DATA.links?.clash || [])
    .filter(c => _when_first_no(c.when) === q.no)
    .map(c => `<div class="clash" data-clash-when="${esc(whenToDom(c.when))}">
       <b>这两个选择打架了。</b>${esc(c.why)}
       ${c.require_explain === false ? ''
         : '<textarea id="clash-' + q.no + '" rows="2" placeholder="写明怎么处理，或回去改一个选择"></textarea>'}
     </div>`).join('');
  return `<article class="q" id="q${q.no}" data-no="${q.no}"
      data-title="${esc(q.title)}" data-who="${esc(who)}"${q.blocking ? ' data-first="1"' : ''}
      data-layer="${q.layer}">
    <div class="q-hd"><div class="q-no">${q.no}</div><div class="h">
      <h3 class="q-t">${esc(q.title)}</h3><div class="tags">${tags}</div></div></div>
    <div class="q-bd">${evHtml(q)}
      ${q.background ? `<p class="bg">${esc(q.background)}</p>` : ''}
      ${q.groups.map(g => groupHtml(q, g)).join('')}
      ${demoHtml(q)}${reveals}${clash}
      <div class="ans"><label for="a-q${q.no}">补充说明（选填）</label>
        <textarea id="a-q${q.no}" rows="2"></textarea></div>
    </div></article>`;
}

/** clash 挂在其条件里题号最大的那道题上——业务是选到那一步才会撞上冲突。 */
function _when_first_no(expr){
  const nos = [...String(expr).matchAll(/(\d+)\s*(?:!=|=)/g)].map(m => +m[1]);
  return nos.length ? Math.max(...nos) : null;
}

function renderPart2(){
  const layers = [...new Set(DATA.questions.map(q => q.layer))].sort((a, b) => a - b);
  document.getElementById('part2').innerHTML =
    `<div class="part-hd"><h2>第二部分 · 待确认问题</h2>
       <span class="hint">${DATA.questions.length} 题</span></div>`
  + layers.map(n => {
      const why = (DATA.layers || []).find(l => l.n === n)?.why;
      const qs = DATA.questions.filter(q => q.layer === n);
      const head = n === layers[0] ? ''
        : `<div class="layer-hd">下面这些要等前面定了才有意义${why ? `（${esc(why)}）` : ''}</div>`;
      return head + qs.map(questionHtml).join('');
    }).join('');
}

function renderSignoff(){
  document.getElementById('signoff').innerHTML = `
    <h2>填写信息</h2>
    <p class="why2">日期由页面在导出时自动记录，不用填。留名字是为了日后能找回是谁定的——
      不填也能导出，但回执会自动标注「未署名」，我们只能按【开发拟定·待追认】入账。</p>
    <div class="sign-grid">
      <div class="fld"><label for="s-name">填写人（选填，浏览器会记住）</label>
        <input type="text" id="s-name" placeholder="您的名字"></div>
      <div class="fld"><label for="s-dept">部门（选填）</label>
        <input type="text" id="s-dept" placeholder="部门"></div>
      <div class="fld"><label>导出时间（自动）</label>
        <input type="text" id="s-date" readonly></div>
    </div>
    <div class="ans" style="margin-top:14px">
      <label for="s-relay">代答／转交说明</label>
      <textarea id="s-relay" rows="2"
        placeholder="例：问题 1、3 已电话确认过王芳；问题 2 已转交李姐"></textarea>
    </div>`;
}

renderMasthead(); renderPart1(); renderPart2(); renderSignoff();
```

**3c. 回执头部改为读 DATA。** 把原型 `buildReceipt()` 里写死的三行改为：

```javascript
  L.push(`# 需求确认单回执：${DATA.doc.title}（第 ${DATA.doc.round} 轮）`);
  L.push(`> 导出于 ${stamp()}（页面自动记录）· 发出 ${DATA.doc.sent_on} · 发出人 ${DATA.doc.sent_by}`);
```

并把 `J` 的初始化改为 `{单据: DATA.doc.id, 轮次: DATA.doc.round, 代码依据: DATA.doc.code_rev, ...}`。

回执的机读区要带上业务概念层与复核状态——把原型里收集 `rec.依据` 的那一行

```javascript
    q.querySelectorAll('.ev .cite code').forEach(c=>rec.依据.push(c.textContent.replace(/^&gt; ?/,'')));
```

改为

```javascript
    q.querySelectorAll('.ev code').forEach(c=>rec.依据.push(c.textContent.replace(/^&gt; ?/,'')));
    const _ev = (DATA.questions.find(x=>String(x.no)===no)||{}).evidence || {};
    if(_ev.rules_ref) rec.规则引用 = _ev.rules_ref;
    rec.独立复核 = _ev.reviewed
      || ((_ev.cites||[]).some(c=>c.kind==='code') ? '未复核' : null);
```

——AI 在阶段三读回执时，必须能看出"这道题的现状说明有没有被第二个人独立读过代码"。同时删掉原型里 `no==='6'` 的阻塞原因表特例——那是 AR 项目专有的题型，P0 不支持表格题（见「已知限制」）。

**3d. 加 layer 分隔样式。** 在 CSS 里加：

```css
.rev{display:block;margin-top:4px;color:var(--ink-45);font-size:12px;font-family:var(--mono)}
.layer-hd{margin:26px 0 8px;padding:7px 12px;background:var(--sheet-2);
  border-left:2px solid var(--ink-45);font-size:13px;color:var(--ink-70)}

/* 依据两层：白话在外，坐标折叠在内 */
.code-cite{display:block;padding:8px 0}
.code-cite .logic{font-size:13.5px;line-height:1.75;color:var(--ink)}
.code-cite .logic b{color:var(--blue)}
.logic-note{color:var(--ink-45);font-size:12.5px}
.coords{margin-top:7px}
.coords summary{cursor:pointer;font-size:12px;color:var(--ink-45);font-family:var(--mono)}
.coords summary:hover{color:var(--ink)}
.coords>div,.coords .brs{margin-top:6px}
.coords .entry{font-size:12px;color:var(--ink-70)}
.coords .brs{margin:6px 0 0;padding-left:18px;font-size:12.5px;color:var(--ink-70)}
.demo-assumed{padding:7px 13px;border-top:1px dashed var(--red);
  background:var(--red-soft);font-size:12.5px;color:var(--ink)}
.rule-cite .logic b{color:var(--green)}
.unreviewed{margin-top:8px;padding:6px 10px;background:#FBF3D9;
  border-left:2px solid var(--amber);font-size:12.5px;color:var(--ink)}
.reviewed{margin-top:8px;padding:6px 10px;background:#EAF1EB;
  border-left:2px solid var(--green);font-size:12.5px;color:var(--ink-70)}
```

- [ ] **Step 4: 加 `render_html`**

在 `scripts/build_questionnaire.py` 顶部常量区加：

```python
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "questionnaire.html"
PLACEHOLDER = "__QUESTIONNAIRE_DATA__"
```

并加函数（放在 `validate` 之后）：

```python
def code_rev():
    """当前仓库的 HEAD。单子发出到收回代码可能变过,没有 rev 就说不出『当时代码是这样的』。
    仓库外运行(chat/agent 环境)返回空串。"""
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def render_html(doc, template):
    """把题目数据注入模板的 qdata 块。模板不含任何项目内容,数据只此一处。"""
    if PLACEHOLDER not in template:
        raise ValueError(f"模板缺占位符 {PLACEHOLDER}")
    doc = {**doc, "doc": {**doc["doc"], "code_rev": doc["doc"].get("code_rev") or code_rev()}}
    # </script> 会提前闭合数据块;JSON 里的 < 一律转义,不影响 json.loads
    payload = json.dumps(doc, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, payload)
```

在 `main()` 里 `--check` 之后接上出包：

```python
    if args.check:
        return
    out = Path(args.out or f"confirm-{doc['doc']['id']}-r{doc['doc']['round']}.html")
    out.write_text(render_html(doc, TEMPLATE_PATH.read_text(encoding="utf-8")),
                   encoding="utf-8")
    print(f"✓ 已出包 {out}（{out.stat().st_size // 1024} KB，单文件自包含）")
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
Expected: PASS

- [ ] **Step 6: 出包并在浏览器里人工验收**

Run:
```bash
python3 scripts/build_questionnaire.py \
  examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json \
  -o /tmp/confirm-逾期提醒-r1.html
```

在浏览器打开该文件，逐条核对（CI 无法覆盖 JS 渲染，这一步必须人工做）：

- [ ] 抬头显示「逾期提醒 · 第 1 轮」、骑缝编号、回填期限 3 个工作日，`usage` 那句在抬头里
- [ ] 第一部分两条，每条「对／不对」三态；选「不对」才展开说明框
- [ ] 三道题都渲染出来；问题 1、3 带「请先答」红标；问题 2 在 layer 2 分隔条之下
- [ ] 问题 1 依据区显示绿色 `原话` badge + `> 证据: docs/.../李姐微信语音转述.md:4 | "客户逾期了系统就提醒一下呗"`
- [ ] 问题 4 依据区**外层只显示业务语言**：「系统现在的规则是：已还清的判定：余额清零即视为已还清，不看单子的状态字段（引自规则文档 R3，由开发读代码逆向、交规则 owner 验真——不对请直接指出）」；`app/reminder_rules.py:18`、入口、**三条**分支折叠在「代码位置与分支（开发看）」里；底下绿底一行「已独立盲审（2026-07-11，发现 1 处差异，已处置）」
- [ ] 临时删掉问题 4 的 `reviewed` 重新出包 → 外层应出现黄底「未经独立复核——上面这段理解只有一个人读过代码」（验完记得改回来）
- [ ] 问题 4 的演示数字两行（继续提醒／停止提醒）随选项点亮，且**没有**「基于开发假设的算法」那条红底提示（因为 `basis` 是 `branches`）
- [ ] 抬头末行显示「代码依据取自 <8 位 sha> —— 这之后代码若有变动，结论需重新确认」
- [ ] 问题 3 依据区**默认展开**、红色 `无据 · 请证伪` badge，⚠ 那段 weak 文案在里面
- [ ] 问题 1 选 B → 展开「宽限期几天」；选回 A → 收起
- [ ] 问题 2 选 A → 展开「达到上限后怎么办」；选 B → `after_cap` 组灰掉并盖上「因问题 2 选了 B…」
- [ ] 问题 2 选 B **且** 问题 3 选 B → 红色 clash 框弹出，进度条报「1 处选择互相打架」
- [ ] 每题末尾都有 `⊕ 都不是——我要选的不在这几个里`，选中展开自由文本
- [ ] 每题都有 `⊘ 这题不成立`，勾选后整题灰掉
- [ ] 身份选择器有「全部／财务 王芳／运营 李姐」，选「运营 李姐」后只剩问题 2 亮着
- [ ] 落款：无签章位、日期只读且已自动填、填写人可留空
- [ ] 点「导出回执」→ 预览是人读摘要（成色卡片 + 逐题清单），原始 markdown 折叠在最底部
- [ ] 打印预览（⌘P）：进度条／索引／身份选择器隐藏，条件块展开

- [ ] **Step 7: 提交**

```bash
git add templates/questionnaire.html scripts/build_questionnaire.py tests/test_render_html.py
git commit -m "feat: HTML 模板从 JSON 渲染

模板不再含任何项目内容，题目数据注入 qdata 块后由运行时渲染 DOM。测试锁住
三件事：数据注入后可原样 round-trip、生成的 HTML 零外部引用（单文件自包含）、
模板里不残留原型的 AR 项目内容。

layer 只做分层排布与提示，前沿推进由页面的条件引擎执行——一次性发单、异步
回填，中间没有 AI 重算前沿。"
```

---

### Task 4: 同一份 json 出 md

内网、打印、docx 场合仍需要 Markdown。md 必须由同一份 json 生成，否则 `questionnaire-template.md` 和 json 会成为两个真源。同时把混在模板里的「出题规则」搬出去——现有 `check_questionnaire.py` 有一条规则专门抓这段内部注释泄漏，布局改对后那条规则就是多余的。

**Files:**
- Modify: `scripts/build_questionnaire.py`（加 `render_md`）
- Create: `references/questioning-rules.md`
- Modify: `templates/questionnaire-template.md`（改为生成产物示例）
- Test: `tests/test_render_md.py`

**Interfaces:**
- Consumes: `validate()`、样例 json（Task 8 之后：无 `roles`、无 `due_days`，每题带 `decide: "biz"|"dev"`）
- Produces: `render_md(doc: dict) -> str`

- [ ] **Step 1: 写失败测试**

Create `tests/test_render_md.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_render_md -v`
Expected: FAIL — `AttributeError: module 'build_questionnaire' has no attribute 'render_md'`

- [ ] **Step 3: 写 `render_md`**

加到 `scripts/build_questionnaire.py`（`render_html` 之后）：

```python
def render_md(doc):
    """同一份 json 出 Markdown,供打印/docx/内网场合。
    格式必须与 check_questionnaire.py 认的契约一致:
    `### 问题 N：`、`☐ A. `、`【作答区】`、`## 填写信息`。"""
    d = doc["doc"]
    L = [f"# 需求确认单：{d['title']}（第 {d['round']} 轮）",
         f"> 第 {d['round']} 轮 · {d['sent_on']} · 发出人：{d['sent_by']}"
         f" · 共 {len(doc['questions'])} 题", ""]
    L += [d["usage"], "",
          "填写说明：第一部分请逐条核对；第二部分请在 ☐ 打勾、【作答区】作答。"
          "标「业务定」的题必须您自己拍板；标「开发拟定」的是我们已经拟好的默认规则，"
          "请过目，无异议即生效。填完发回即可。", ""]

    if doc.get("part1"):
        L += ["## 第一部分 · 我们理解的（请逐条核对）", "",
              "| # | 我们理解的 | 备注 | 对不对 |", "|---|---|---|---|"]
        L += [f"| {r['n']} | {r['we_understand']} | {r.get('note', '')} | ☐ 对　☐ 不对 |"
              for r in doc["part1"]]
        L += ["", "【作答区】哪条不对、哪里不对（全对就写「无异议」）：", ""]

    L += ["## 第二部分 · 待确认问题（请作答）", ""]
    for q in sorted(doc["questions"], key=lambda x: (x["layer"], x["no"])):
        decide = "业务定" if q["decide"] == "biz" else "开发拟定·请过目"
        L.append(f"### 问题 {q['no']}：{q['title']}（{decide}）"
                 + ("（阻塞）" if q.get("blocking") else ""))
        if q.get("background"):
            L.append(f"背景：{q['background']}")
        for g in q["groups"]:
            if g["id"] != "main":
                L.append(f"子问 · {g.get('ask', '')}：")
            for o in g["options"]:
                key = f"{o['key']}. " if re.fullmatch(r"[A-Z]\d*", str(o["key"])) else ""
                mark = "⊘ " if o.get("kind") == "nonexistent" else ""
                cost = f"（{o['cost']}）" if q.get("advice_allowed") and o.get("cost") else ""
                L.append(f"☐ {key}{mark}{o['label']}{cost}")
        L.append("☐ 都不是——我要选的不在这几个里（请在作答区写明实际口径）")
        for r in q.get("reveal", []):
            L.append(f"（若选 {r['when']}，请在作答区一并回答：{r['ask']}）")
        L += ["【作答区】", ""]

    L += ["## 填写信息",
          "填写人：____　部门：____　日期：____",
          "（留名字是为了日后能找回是谁定的；不填也能交，但只能按【开发拟定·待追认】入账）",
          "代答／转交说明：____", ""]
    return "\n".join(L)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m unittest tests.test_render_md -v`
Expected: PASS，6 个测试

- [ ] **Step 5: 把出题规则搬出模板**

Create `references/questioning-rules.md`，内容是从 `templates/questionnaire-template.md` 里那段 `出题规则(给生成方,不进正式单)` 搬过来并扩写：

```markdown
# 出题规则（给生成方，不进正式单）

阶段二生成 `questionnaire.json` 时逐条遵守。多数规则已由
`scripts/build_questionnaire.py` 机检——违反者拒绝出包。

## 一、问之前先自己查（机检不了，纪律）

能从代码、数据库、`raw/` 归档里查到的事实，**一律不问业务**。查得到就别出题；
查不到才出题，并标 `evidence.tier: "guess"` + 写清 `weak`（哪儿没据、为什么还问）。
把业务的时间花在只有他能回答的事上。

## 二、每题必挂三档依据（机检：tier/cites/weak）

- `src` — 引自 `raw/` 归档的原始材料，必须有 `cites`
- `code` — 引自代码或 schema，必须有 `cites`（带行号与原文片段）
- `guess` — 无据，必须写 `weak`；页面会标红并默认展开依据区

无据的题**照样出**——盲区清单的价值就在问出没人想过的场景；靠公开标记加一键
证伪控幻觉，而非禁止提问。但无据题排在同层最后。

## 二之二、代码依据比原话依据要求更高（机检：logic/entry/branches）

`src`（原话）和 `code`（代码）的失败模式不同，别用同一个标准。

- **`src` 的风险是被改写**：`path:line + snippet` 就够——`verify_evidence.py` 能 grep 出来。
- **`code` 的风险是单点引用冒充整体逻辑**：一行赋值不证明它是唯一赋值点、没有别处覆盖、
  没有 flag 短路。三条全 PASS 的引用照样能让业务确认一个错误的现状——**而且是有落款的
  错误**，比没有证据更糟。尤其危险是演示数字照这个逻辑算的：逻辑读了一半，业务就照错
  数字选口径。

所以 `code` 档每条引用额外必填三样：

```json
{"kind": "code",
 "path": "app/reminder_rules.py", "line": 18,
 "snippet": "if bill.balance <= 0:",
 "logic": "代码现在按余额是否 ≤ 0 判定已还清，完全不看单子的状态字段",
 "entry": "app/reminder_rules.py:15",
 "branches": [
   {"cond": "余额 ≤ 0", "then": "不再提醒", "cite": "app/reminder_rules.py:19"},
   {"cond": "余额 > 0 且已逾期", "then": "提醒，累计发满 3 次为止", "cite": "app/reminder_rules.py:20"}],
 "branches_exhaustive": true}
```

- **`logic`** — 一句白话说清这段代码实际做什么。**它是你对代码的解读，不是代码原文**，
  harness 判不了它对不对。页面会写成「我们查代码看到系统现在是这么做的：…（这是开发读
  代码得出的理解，不是您说过的话——不对请直接指出）」，把否掉的机会留给业务。
- **`entry`** — 这段逻辑从哪个页面／接口进来。业务问的是"页面上"，没有 `entry` 他没法
  判断"你说的是不是我天天看的那个页面"，"代码 vs 口述冲突题"也就问不准。
- **`branches`** — 分支列表。**确实没读完就写 `branches_exhaustive: false`**，此时该题
  `tier` 必须降为 `guess`，页面按无据题处理（标红、默认展开、给证伪出口）。不把"没读完"
  逼成谎话，但也不让它冒充有据。

演示数字必须声明来源：`demo.basis` 为 `"branches"`（照分支算的）或 `"assumed"`（你自己
假设的算法，页面会标注"未从代码验证"）。

`doc.code_rev` 由 build 自动填 HEAD——单子发出到收回可能隔几天，代码变了结论就得重新确认。

## 二之三、超过阈值就沉淀进 rules/，别 inline（机检：rules_ref）

`logic` 挂在每道题里会出四个问题：同一段逻辑抄多遍、抄得不一致、业务拼不出整体、
读代码的理解无处沉淀下次还得重读。

**逆向场景本来就有这条通道**：Excel／老系统是 `raw/` 导出件 → `rules/<来源名>.md` 条目化
→ 交规则 owner 验真 → 再出题。**源码只是换了个"来源"**，走同一条路：

```
源码 ──读懂──► rules/<模块名>.md（模板 templates/rules-template.md）
                  R3. 已还清的判定：余额清零即视为已还清，不看状态字段
                      > 证据: app/reminder_rules.py:18 | "if bill.balance <= 0:"
                      入口 / 分支 / 穷举声明 / 复核状态 / owner 勾选位
                  ▼
            题目引 R3，不直接引代码行；业务看到的就是这句业务语言
```

**阈值**（三条全满足才允许 inline `logic`，任一不满足必须给 `rules_ref`）：

- 该引用的 `branches` ≤ 2
- 该题的 code 引用只涉 1 个文件
- 同一句 `logic` 没在别的题里重复出现

别为小改动加中间产物；但多分支／跨文件／会被复用的逻辑必须沉淀。

`rules_ref` 每项 `{id, doc, text}`——`text` 是条目的业务语言副本，供页面渲染。**它不是
自由复制**：机检要求它能在 `doc` 里那条条目附近找到，防规则文档改了而题目副本没跟上。

## 二之四、独立盲审（可选强化，开发显式触发）

`path:line + snippet` 有脚本能验；**业务概念那句话没有**。它是你对代码的解读，机器判不了
对错。盲审能补一层，但要按规矩做，否则等于没做。

**① 必须盲审。** 先给复核方看现有描述再问"对不对"，它会顺着说对。正确顺序：

1. 复核方**不看**现有描述，自己读代码，独立写一份；
2. **diff 两份**；
3. **差异才是产出。**

两份描述都来自概率性过程，但"两份不一样"这个事实是硬的——diff 把概率判断转成了可视差异，
人扫一眼就知道该查哪儿。

**② 给具体失败模式清单，不说"仔细看看"**（照 `chain-audit-checklist.md` 七种缺陷模式的
思路）：

- 还有别的赋值点／覆盖点吗？
- 有上游 `if` 短路吗？
- 有 feature flag／配置开关吗？
- `entry` 是唯一入口吗？
- `branches` 漏了分支吗？
- 这行是死代码吗？

**`branches` 在这里作用被放大**：它把"这段代码是什么意思"这种开放问题，收成"还有别的分支
吗"这种**有界**问题——有界问题盲审起来又快又准。

**③ 结果必须落痕。** 记进 `evidence.reviewed = {by, on, diffs, note}`，`diffs > 0` 必须写
`note` 说明怎么处置的。没审就不填，页面如实标「未经独立复核」。

**④ 别说成"已验证"。** 盲审是**抽样检查**，不是证明——同一份描述审两次可能不同结论。过了
只能说"经一次独立复核未发现矛盾"。它换的是标签，不是保证类型。

**⑤ 它进不了 CI。** 不确定、要花钱、要模型。CI 只能查 `reviewed` 填没填，查不了审得对不对。

## 三、分支穷举是义务（机检：分支对称）

一次性发单、业务异步回填，中间**没有 AI 追问**。选 A 的下游、选 B 的下游都要
在本轮写全；漏掉的分支要等一整轮确认单才能补。

同一 main 组内若部分选项有后续、部分没有，没有后续的必须显式标
`terminal: true`——不对称的分支通常是漏了，逼出题者过一遍脑子。

## 四、依赖用 layer + links 声明，不写散文（机检：依赖闭环）

不要再写「若第 1 题选 A，第 3、4 题可跳过」这种注释——业务不会照着跳。用
`layer`（依赖层级）+ `reveal`／`links.na` 声明，页面运行时执行。

`links` 里 `when` 引用的题必须存在，且其 `layer` 严格小于被约束题的 `layer`
（同题内主问决定子问除外）。

**注意**：`layer` 是依赖层级，`doc.round` 是第 N 轮确认单，两个概念别混。

## 五、建议选项分级（机检：advice_allowed）

- **规则／账务口径类**（含税、起算日、尾差、锁定规则、金额算法）→
  `advice_allowed: false`。**永不标建议**——标了就是替业务拍板，日后一句
  「我没说过」，返工归开发。模板对这类题不渲染建议位，写了也渲染不出来。
- **纯偏好／成本敏感类**（格式、时点、入口位置）→ `advice_allowed: true`，
  可在 `cost` 里写「开发建议：选 X（理由：省 N 天／顺现有结构）」以加速回填。

这一条是本 skill 与通用 grill 类技能的分界：`grilling` 对每题都给推荐答案，
因为它面对的是**开发者自己**，答错自己担；确认单面对的是**第三方业务方**。

## 六、阻塞级岔口必须配跨分支演示数字（`demo`）

同一组输入，每个候选选项各算一遍摆对照表。只算一个选项 = 暗中替业务拍板；
只画岔口不算数 = 让人凭抽象拍板。`demo.given` 写明输入前提，`rows[].when`
标该行对应哪些选项组合——页面会在业务选中时点亮对应那行。

## 七、每题标建议回答人，且必须是声明过的角色（机检：who）

知情人常散在多拨人手里（提需求业务、财务、外围系统操作者）。`who` 只能引用
`roles[].id`——写自由文本会让「财务」和「财务 AR 负责人」变成两个人，一份单子
分裂出幽灵收件人。**警惕替答**：别让提需求的人替财务拍板。

## 八、给台阶

- `kind: "dontknow"` — 「我不清楚」，顺势索要真正知情人
- `kind: "nonexistent"` — 「这种情况不存在」，用于无据题
- 「都不是」兜底出口由模板自动追加，**不要写进 json**
```

然后把 `templates/questionnaire-template.md` 整份替换为"生成产物示例"：

```bash
python3 -c "
import json, sys
from pathlib import Path
sys.path.insert(0, 'scripts')
import build_questionnaire as bq
doc = json.loads(Path('examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json').read_text(encoding='utf-8'))
hdr = '''<!-- 本文件是 scripts/build_questionnaire.py 从 questionnaire.json 生成的 Markdown 示例。
     不要手改这里的内容——出题规则见 references/questioning-rules.md，
     字段契约见 templates/questionnaire.schema.json。
     重新生成：python3 scripts/build_questionnaire.py <json> --md templates/questionnaire-template.md -->

'''
Path('templates/questionnaire-template.md').write_text(hdr + bq.render_md(doc), encoding='utf-8')
print('已重新生成')
"
```

并在 `main()` 里接上 `--md`：

```python
    if args.md:
        Path(args.md).write_text(render_md(doc), encoding="utf-8")
        print(f"✓ 已出 Markdown {args.md}")
```

- [ ] **Step 6: 确认 `check_questionnaire.py` 的模板残留规则已无对象**

Run: `python3 -c "print('出题规则' in open('templates/questionnaire-template.md',encoding='utf-8').read())"`
Expected: `False`

该规则（`check_questionnaire.py` 里检测「出题规则(给生成方」的那条）**保留不删**——旧版模板可能还在别人手上，留着当兜底，但它从此不该再被触发。

- [ ] **Step 7: 提交**

```bash
git add scripts/build_questionnaire.py references/questioning-rules.md \
        templates/questionnaire-template.md tests/test_render_md.py
git commit -m "feat: 同一份 json 出 md，出题规则搬出模板

md 由 json 生成，不再手写维护——否则模板与 json 是两个真源。测试锁住 md 仍
符合 check_questionnaire.py 的格式契约（### 问题 N：/ ☐ A. / 【作答区】/
## 填写信息）。

出题规则从 questionnaire-template.md 搬到 references/questioning-rules.md：
给 AI 的指令本来不该塞在一份要发给业务的文档里——checker 里那条专抓内部注释
泄漏的规则，就是这个布局的补丁。"
```

---

### Task 5: check_questionnaire.py 三条新规则

**Files:**
- Modify: `scripts/check_questionnaire.py`
- Create: `tests/fixtures/receipt-clean.md`
- Create: `tests/fixtures/receipt-unsigned.md`
- Create: `tests/fixtures/receipt-denied.md`
- Create: `tests/fixtures/receipt-clash-unexplained.md`
- Test: `tests/test_check_questionnaire.py`

**Interfaces:**
- Consumes: 无（独立脚本）
- Produces: `check_file(fp) -> (n_q, n_unanswered, warns, fails)` — 现有签名保持不变，新规则往 `warns`／`fails` 里加消息

- [ ] **Step 1: 写四份 golden 回执 fixture**

Create `tests/fixtures/receipt-clean.md`：

```markdown
# 需求确认单回执：逾期提醒（第 1 轮）
> 导出于 2026-07-14 10:20（页面自动记录）· 发出 2026-07-11 · 发出人 开发
> 回执成色：已答 2/2 · 第一部分核对 1/1

## 第一部分 · 已确认事项（请核对）

| # | 核对 | 说明 |
|---|---|---|
| 1 | 对 | |

【作答区】1 条全部核对为「对」，无异议

## 第二部分 · 待确认问题（请作答）

### 问题 1：「逾期」从哪天起算？（业务定）（阻塞）
☑ A. 到期日次日即逾期
☐ B. 有宽限期，宽限期后才算
【作答区】到期日次日。

### 问题 2：重复提醒的频率和上限？（开发拟定·请过目）
☑ A. 每 3 天一次，最多 3 次
☐ B. 每 7 天一次，直到还清
【作答区】达到上限后还没还，怎么办：转人工跟进

## 填写信息
填写人：王芳　部门：财务部　日期：2026-07-14 10:20
```

Create `tests/fixtures/receipt-unsigned.md` —— 与 clean 相同，但落款行改为：

```markdown
## 填写信息
填写人：（未署名·导出自 HTML 确认单）　部门：（未填）　日期：2026-07-14 10:20
```

并在头部第 4 行加：

```markdown
> ⚠ 未署名：本回执不得记为【业务确认】，须按【开发拟定·待追认】入账，回头补落款才能转正。
```

Create `tests/fixtures/receipt-denied.md` —— 与 clean 相同，但问题 2 改为：

```markdown
### 问题 2：重复提醒的频率和上限？（开发拟定·请过目）
☒ 本题不成立（业务证伪）：频率运营已有固定 SOP，每 5 天一次，不用问。
☐ A. 每 3 天一次，最多 3 次
☐ B. 每 7 天一次，直到还清
【作答区】本题不成立：频率运营已有固定 SOP，每 5 天一次，不用问。
```

Create `tests/fixtures/receipt-clash-unexplained.md` —— 与 clean 相同，但在 `## 第一部分` 之前插入：

```markdown
## ⚠ 填写时暴露的矛盾（请开发优先处理）

- 条件 `q3=B & q2=B` 同时成立：问题 2 选 B 是「一直自动提醒到还清」，问题 3 选 B 是「部分还款后交人工决定」——两者对「什么时候停」给了不同答案…
  业务说明：（未说明）
```

- [ ] **Step 2: 写失败测试**

Create `tests/test_check_questionnaire.py`：

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_check_questionnaire -v`
Expected: 4 个测试里 3 个 FAIL —— `receipt-unsigned` 因缺填写人报 FAIL 退出 1、`判为不成立 1 道` 找不到、矛盾段不报错

- [ ] **Step 4: 加三条规则**

改 `scripts/check_questionnaire.py`。

**4a.** 顶部常量区加：

```python
DENIED = re.compile(r'^☒\s*本题不成立[^：:]*[：:]\s*(?P<why>.*)$', re.M)
UNSIGNED = re.compile(r'未署名')
CLASH_HEAD = re.compile(r'^##\s*⚠?\s*填写时暴露的矛盾.*?$(?P<body>.*?)(?=^##\s|\Z)', re.M | re.S)
CLASH_ITEM = re.compile(r'^-\s+条件\s+`(?P<when>[^`]+)`', re.M)
NO_EXPLAIN = re.compile(r'业务说明[：:]\s*（未说明）')
```

**4b.** 更新模块 docstring 的规则清单，把 6 件事改成 9 件事：

```
7. 业务证伪: `☒ 本题不成立` 单独计数并逐条列出 —— 该题需删除或重出,不得直接合并。
8. 未署名: 填写人为空或含「未署名」→ WARN + 声明须按【开发拟定·待追认】入账
   (落款可留空是刻意的:业务常需先交一半再转交;纪律靠标签降级而非拦截)。
9. 矛盾段: 存在「填写时暴露的矛盾」→ WARN;其中未附业务说明的 → FAIL(必须回问,不得自行选一边)。
```

**4c.** 在 `check_file` 的逐题循环里，`answered` 判定之后加证伪识别：

```python
            m_deny = DENIED.search(blk)
            if m_deny:
                denied.append((no, m_deny.group("why").strip()))
                warns.append(f"问题 {no} 被业务判为不成立：{m_deny.group('why').strip()[:40]}"
                             f" —— 该题需删除或重出,不得直接合并")
```

并在循环前初始化 `denied = []`；把 `unanswered` 那行改为不把已证伪的算进去（`☒` 已被 `CHECKED` 匹配，故 `answered` 已为真，无需额外处理——此处仅确认行为）。

**4d.** 落款检查改为：填写人不再 FAIL，改 WARN + 降级声明；日期仍 FAIL。

```python
    if signoff is not None:
        name = field_value(signoff, "填写人")
        if not name or UNSIGNED.search(name):
            warns.append("回执未署名 —— 不得记为【业务确认】,须按【开发拟定·待追认】入账,"
                         "补落款后才能转正")
        if not field_value(signoff, "日期"):
            fails.append("落款缺『日期』(导出时自动填入,缺失说明回执被手改过)")
        if not field_value(signoff, "部门"):
            warns.append("落款缺『部门』")
    else:
        fails.append("缺少『## 填写信息』落款区 —— 无落款的回答不得标【业务确认】")
```

**4e.** 加矛盾段检查（放在落款检查之后）：

```python
    m_clash = CLASH_HEAD.search(text)
    n_clash = n_mute = 0
    if m_clash:
        body = m_clash.group("body")
        n_clash = len(CLASH_ITEM.findall(body))
        n_mute = len(NO_EXPLAIN.findall(body))
        warns.append(f"回执含 {n_clash} 处填写时暴露的矛盾,须优先处理")
        if n_mute:
            fails.append(f"{n_mute} 处矛盾业务未给说明 —— 必须回问,不得自行选一边")
```

**4f.** 返回值与摘要带上新计数。`check_file` 的 return 改为：

```python
    return n_q, len(unanswered), len(denied), n_clash, warns, fails
```

`main()` 相应改为：

```python
def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    t_q = t_un = t_den = t_cl = t_warn = t_fail = 0
    for fp in sys.argv[1:]:
        n_q, n_un, n_den, n_cl, warns, fails = check_file(fp)
        t_q += n_q; t_un += n_un; t_den += n_den; t_cl += n_cl
        t_warn += len(warns); t_fail += len(fails)
    print("\n== 摘要 ==")
    print(f"题目 {t_q} 道 / 未答 {t_un} 道 / 判为不成立 {t_den} 道 / 矛盾 {t_cl} 处"
          f" / {t_warn} WARN / {t_fail} FAIL")
    if t_fail:
        print("✗ 机检未通过: 阻塞级未答、落款缺失或矛盾无说明。追答/补落款/回问后重跑;"
              "机检通过≠验收完成,AI 仍须做成色分级与冲突检测。")
        sys.exit(1)
    if t_den:
        print(f"△ 有 {t_den} 道被业务判为不成立 —— 先决定删题还是重出,别直接合并。")
    print("✓ 机检通过。接下来交给 AI: 成色分级、冲突检测、新需求剥离。")
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `python3 -m unittest tests.test_check_questionnaire -v`
Expected: PASS，4 个测试

- [ ] **Step 6: 回归旧回执样本**

现有 `examples/demo-project` 里那份手写回执必须仍然可检（证明新规则没破旧格式）：

Run: `python3 scripts/check_questionnaire.py "examples/demo-project/docs/requirements/raw/2026-07-14-确认单v1-回执.md"`
Expected: 退出码 0；输出里应有「问题 2」未作答之类的 WARN（该样本问题 2 只写了「你看着办」没打勾），且**不应**出现新增的 FAIL

若出现意料外的 FAIL，说明 4d 的日期规则太严——该样本落款是 `日期:2026-07-14`，应能取到值；确认 `field_value` 对全角空格分隔仍有效。

- [ ] **Step 7: 提交**

```bash
git add scripts/check_questionnaire.py tests/fixtures/ tests/test_check_questionnaire.py
git commit -m "feat: 机检加三条规则（证伪计数/未署名降级/矛盾段）

三条都是原型实测撞出来的缺口，不是推测：
- 未署名回执因落款字段非空静默绕过 FAIL，纪律会无声烂掉 → 改 WARN + 明确
  声明须按【开发拟定·待追认】入账（不拦截，业务常需先交一半再转交）
- 被业务判为不成立的题被算成普通已答，AI 会漏掉『这题该删』的信号 → 单独计数
- 带着未解决矛盾的回执照报『✓ 通过』→ 矛盾 WARN，未附业务说明升级 FAIL

四份 golden fixture 覆盖四种成色，旧手写回执样本回归通过。"
```

---

### Task 6: CI 与可执行测试接线

现状：`tests/` 下四份是给人读的场景描述，CI 只在 `release` 时跑、且只验 frontmatter——**仓库最有价值的两个机检脚本从来没被自动验证过**。本任务把它接上。

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `tests/README.md`

**Interfaces:**
- Consumes: 前五个任务的全部测试
- Produces: push/PR 上的 CI 门禁

- [ ] **Step 1: 本地先跑通全套**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/validate_skill.py .
python3 scripts/build_questionnaire.py \
  examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json --check
python3 scripts/verify_evidence.py \
  examples/demo-project/docs/requirements/specs/逾期提醒.md --root examples/demo-project
python3 scripts/check_questionnaire.py \
  "examples/demo-project/docs/requirements/raw/2026-07-14-确认单v1-回执.md"
```
Expected: 五条全部退出码 0（`verify_evidence` 已确认现状为 7 PASS / 0 FAIL）

- [ ] **Step 2: 写 CI**

Create `.github/workflows/ci.yml`：

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Validate skill frontmatter
        run: python3 scripts/validate_skill.py .

      - name: Unit tests
        run: python3 -m unittest discover -s tests -p 'test_*.py' -v

      - name: 样例确认单校验（依赖闭环/分支对称/建议措辞）
        run: |
          python3 scripts/build_questionnaire.py \
            "examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json" \
            --check --root examples/demo-project

      - name: 样例确认单出包（单文件自包含）
        run: |
          python3 scripts/build_questionnaire.py \
            "examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json" \
            -o /tmp/confirm.html
          test -s /tmp/confirm.html

      - name: 证据核验（样例 spec 的引用真伪）
        run: |
          python3 scripts/verify_evidence.py \
            "examples/demo-project/docs/requirements/specs/逾期提醒.md" \
            --root examples/demo-project

      - name: 回执机检（旧手写样本回归）
        run: |
          python3 scripts/check_questionnaire.py \
            "examples/demo-project/docs/requirements/raw/2026-07-14-确认单v1-回执.md"

      - name: 模板 JS 语法检查
        run: python3 scripts/check_template_js.py
```

**为什么加最后这步**：模板里那段 `<script>` 是整个页面的命脉——语法一错，业务打开就是一片空白且零提示，而 Python 侧的测试一条都照不出来。`node` 在 `ubuntu-latest` 上预装，抠出来跑 `node --check` 是最便宜的一道保险。

- [ ] **Step 3: 加模板 JS 的语法与契约检查**

Create `scripts/check_template_js.py`：

```python
#!/usr/bin/env python3
"""check_template_js.py — 抠出模板里的 <script> 交给 node 检查

用法:
  python3 scripts/check_template_js.py [模板路径]

为什么需要: 模板里那段 <script> 是整个页面的命脉 —— 语法一错,业务打开就是
一片空白且零提示,而 Python 侧的测试一条都照不出来。

机判两件事:
1. 语法: node --check。node 不可用则跳过并打印说明(不算失败,本地可能没装)。
2. whenToDom 契约: schema 用题号(`2=B`),DOM 用输入框 name(`q2=B`)。这个转换
   一旦静默失效,所有条件显隐/不适用/矛盾全部不匹配,页面不报错、只是什么都不发生。
   这里直接跑模板里的真实实现,不在 Python 侧镜像一份 —— 镜像就是两份真源。
"""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

TPL = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "templates" / "questionnaire.html")

# schema 题号 → DOM name 的对照;左边喂给 whenToDom,右边是期望输出
WHEN_CASES = [
    ("1=A", "q1=A"),
    ("2=B", "q2=B"),
    ("4=B & 1=B", "q4=B & q1=B"),
    ("10=C", "q10=C"),
    ("q1=A", "q1=A"),          # 已经是 DOM name,不该被二次加前缀
]


def extract_script(html: str) -> str:
    blocks = re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*type=)[^>]*>(.*?)</script>",
                        html, re.S)
    if not blocks:
        print("  ✗ 模板里找不到可检查的 <script> 块"); sys.exit(1)
    return max(blocks, key=len)


def main():
    html = TPL.read_text(encoding="utf-8")
    js = extract_script(html)
    node = shutil.which("node")
    if not node:
        print("  △ 未找到 node,跳过模板 JS 检查(CI 上 ubuntu-latest 预装 node)")
        return

    d = Path(tempfile.mkdtemp())
    f = d / "tpl.js"
    f.write_text(js, encoding="utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ✗ 模板 JS 语法错误:\n{r.stderr.strip()}"); sys.exit(1)
    print(f"  ✓ 模板 JS 语法通过({len(js)} 字节)")

    # whenToDom 契约:抠出函数体单独跑,不依赖 DOM
    m = re.search(r"function whenToDom\(.*?\n\}", js, re.S)
    if not m:
        print("  ✗ 模板里找不到 whenToDom() —— 条件表达式的题号→DOM name 转换没了"); sys.exit(1)
    probe = d / "probe.mjs"
    probe.write_text(m.group(0) + "\n"
                     + f"const cases = {json.dumps(WHEN_CASES, ensure_ascii=False)};\n"
                     + "const bad = cases.filter(([i, o]) => whenToDom(i) !== o)\n"
                     + "  .map(([i, o]) => `${i} -> ${whenToDom(i)} (期望 ${o})`);\n"
                     + "console.log(JSON.stringify(bad));\n", encoding="utf-8")
    r = subprocess.run([node, str(probe)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ✗ whenToDom 探针跑不起来:\n{r.stderr.strip()}"); sys.exit(1)
    bad = json.loads(r.stdout.strip() or "[]")
    for b in bad:
        print(f"  ✗ whenToDom 契约不符: {b}")
    if bad:
        print("\n✗ 题号→DOM name 的转换失效 —— 条件显隐/不适用/矛盾会全部静默不匹配")
        sys.exit(1)
    print(f"  ✓ whenToDom 契约通过({len(WHEN_CASES)} 组)")


if __name__ == "__main__":
    main()
```

Run: `python3 scripts/check_template_js.py`
Expected: 两条 ✓（若本机没装 node，第一条应打印「跳过」而**不是**失败）

- [ ] **Step 4: 说明两类测试的分工**

Modify `tests/README.md`，在开头插入：

```markdown
## 两类测试

- **`test_*.py`** — 可执行断言，CI 每次 push/PR 跑（`python3 -m unittest discover -s tests`）。
  覆盖：questionnaire.json 校验、样例数据、HTML/MD 渲染、回执机检。
- **`scenario-*.md`** — 给人读的场景剧本，用来人工回归 skill 的**判断质量**
  （成色分级、冲突检测、剥离阀门）——这些没法用断言表达，需要人读产出评估。

- **`scripts/check_template_js.py`** — 抠出模板里的 `<script>` 跑 `node --check`，并用
  node 跑模板里真实的 `whenToDom()` 核对「schema 题号 → DOM name」的转换。这两件事
  Python 测试照不出来：语法一错业务看到空白页且零提示；转换一失效条件显隐/不适用/矛盾
  全部静默不匹配。

**CI 覆盖不到的**：模板的**渲染结果与视觉**需要浏览器（语法与 whenToDom 已由上面那条覆盖）。
每次改 `templates/questionnaire.html` 后按实施计划 Task 3 Step 6 的清单人工过一遍。
```

- [ ] **Step 5: 提交并确认 CI 绿**

```bash
git add .github/workflows/ci.yml scripts/check_template_js.py tests/README.md
git commit -m "ci: 把机检脚本接进 push/PR 门禁

原来 CI 只在 release 时跑、且只验 frontmatter——仓库最有价值的两个机检脚本
（verify_evidence / check_questionnaire）从来没被自动验证过，tests/ 下的场景
也只是给人读的 markdown，不可执行。这半天就手工撞出三处格式契约不一致。

现在 push/PR 会跑：frontmatter 校验、单元测试、样例确认单校验与出包、样例
spec 证据核验、旧手写回执回归。并抠出模板 <script> 跑 node --check 与 whenToDom 契约探针。视觉与打印仍需人工过浏览器清单（tests/README 已注明）。"
git push
```

Expected: GitHub Actions 全绿。若失败，读日志修到绿再进 Task 7。

---

### Task 7: SKILL.md 出题纪律与陈旧地址

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `references/questioning-rules.md`（Task 4）、`scripts/build_questionnaire.py`（Task 1）
- Produces: 无（文档收尾）

- [ ] **Step 1: 阶段二第 3 步改为产出 json**

在 `SKILL.md` 里，把阶段二的第 3 步：

```
3. **产出问题清单**（结构见下），并生成**可填写确认单**（模板 `templates/questionnaire-template.md`，正式场合出 docx）。
```

替换为：

```
3. **产出问题清单**（结构见下），并生成 `questionnaire.json` → 出**单文件 HTML 确认单**：

   ```bash
   python3 scripts/build_questionnaire.py <项目>/questionnaire.json -o confirm-<项目>-r<N>.html
   ```

   出题规则**必读** `references/questioning-rules.md`（问之前先自查事实、三档依据、
   分支穷举、layer+links 声明依赖、建议选项分级、演示数字、角色 id、台阶）。字段契约见
   `templates/questionnaire.schema.json`。**校验不过不出包**——依赖悬空、分支不对称、
   规则题带建议措辞都会被拒。
   
   业务在浏览器里点选后导出回执 `.md`（人读正文 + 末尾机读 JSON），发回给你。
   需要打印／docx／内网时，同一份 json 加 `--md` 出 Markdown，不要另写一份。
```

- [ ] **Step 2: 阶段二确认单要求改为指向新机制**

把这一段：

```
确认单额外要求：①开头附"已确认事项核对表"，把口头共识变成有落款的凭证；②每题 ☐ 选项 + 作答区；③"建议由 XX 回答，不归您管请转交"；④给"我不清楚"台阶，顺势索要真正知情人。
```

替换为：

```
确认单额外要求（多数已由 build 脚本机检，详见 `references/questioning-rules.md`）：
①开头附"已确认事项核对表"，**逐条三态核对**（对／不对／未表态），不设全局"无异议"——
全局勾与"可补充异议"自相矛盾，"无异议"应是结论而非前置动作；②每题挂三档依据，无据题
标红并给证伪出口；③"建议由 XX 回答，不归您管请转交"，`who` 必须是声明过的角色 id；
④给"我不清楚"台阶顺势索要知情人，给"这种情况不存在"出口证伪伪场景；⑤**每题必有
「都不是」兜底**（模板自动追加）——一次性发单没有 AI 追问的机会，选项集猜错时业务
只能靠自由文本告诉你。
```

- [ ] **Step 3: 阶段三加证伪与矛盾的处置**

把阶段三开头这句：

```
用户带回答案后**不要直接合并**。回执先跑 `python3 scripts/check_questionnaire.py <回执文件>`——机器报完未答题、缺落款、模板残留（机检通过 ≠ 验收完成），再做两件判断题：
```

替换为：

```
用户带回答案后**不要直接合并**。回执先跑 `python3 scripts/check_questionnaire.py <回执文件>`
——机器报完未答题、缺落款、**业务证伪的题**、**未说明的矛盾**（机检通过 ≠ 验收完成）。

**先处理三种"需要下一轮"的信号**，它们不是答案，是出题出错了：
- `☒ 本题不成立` → 该题**删除或重出**，绝不直接合并；理由写进 changes.md
- 「都不是」的自由文本作答 → 选项集猜错了，按业务的实际口径重出该题
- 未附业务说明的矛盾 → 回问，不得自行选一边

再做两件判断题：
```

- [ ] **Step 4: 落款检查改为标签降级**

把「落款检查」那段里这句：

```
缺落款提醒补。
```

替换为：

```
**填写人可留空**（业务常需先交一半再转交），但回执会自动标「未署名」——此时答案
**只能按【开发拟定·待追认】入账，不得记为【业务确认】**，补落款后才转正。日期由页面
导出时自动记录，缺失说明回执被手改过。
```

- [ ] **Step 5: 参考文件清单补两项，并修陈旧仓库地址**

在 `## 参考文件` 的 references 段后加：

```
- `references/questioning-rules.md` — 阶段二出题规则（生成 questionnaire.json 前必读）
- `scripts/build_questionnaire.py` — questionnaire.json → 单文件 HTML 确认单，校验不过不出包
- `templates/questionnaire.schema.json` — 题目数据字段契约
```

然后修三处改名后失效的地址（账号 `JK-yan` → `kj648`）：

```bash
sed -i '' 's#github.com/JK-yan/requirement-clarifier#github.com/kj648/requirement-clarifier#g' \
  SKILL.md README.md
grep -rn "JK-yan" SKILL.md README.md || echo "已无陈旧地址"
```

- [ ] **Step 6: 版本与 CHANGELOG**

把 `SKILL.md` frontmatter 的 `version: 2.5.0` 改为 `version: 2.6.0`，标题 `# Requirement Clarifier（需求澄清器）v2.5` 改为 `v2.6`。

在 `CHANGELOG.md` 顶部加：

```markdown
## v2.6.0

**HTML 可交互确认单。** 阶段二的确认单从 Markdown 换成单文件 HTML——业务点选即填，
不用碰 markdown。题目数据是 `questionnaire.json`，交互写在固定模板里，一次写好全项目复用。

- 依赖从散文注释（"若第 1 题选 A，第 3、4 题可跳过"）变成声明式 `layer` + `links`，
  由页面运行时执行；悬空引用、反向依赖、分支不对称在出包前 FAIL
- 每题挂三档依据（原话／代码／无据），无据题标红且给业务一键证伪出口
- 跨题联动：自动不适用、事实传播、**矛盾当场暴露**——把冲突检测从阶段三提前到填写现场
- 每题必有「都不是」兜底出口：一次性发单没有 AI 追问的机会，选项集猜错时业务得有路可走
- 第一部分改逐条三态核对，取消自相矛盾的全局「无异议」
- 落款：日期自动，填写人可留空但自动降级为【开发拟定·待追认】
- 按建议回答人分区，一份单子多拨人各看自己那部分
- 机检加三条：业务证伪单独计数、未署名降级、矛盾段告警（未附说明则 FAIL）
- CI 从"只在 release 验 frontmatter"改为 push/PR 跑全套机检脚本与单元测试

设计与借鉴取舍见 `docs/superpowers/specs/2026-08-27-html-questionnaire-design.md`。
```

- [ ] **Step 7: 全量验证并提交**

Run:
```bash
python3 scripts/validate_skill.py .
python3 -m unittest discover -s tests -p 'test_*.py'
```
Expected: 均退出码 0

```bash
git add SKILL.md README.md CHANGELOG.md
git commit -m "docs: 阶段二出题纪律接入 HTML 确认单，v2.6.0

- 阶段二第 3 步改为产出 questionnaire.json → build 出单文件 HTML；出题规则
  拆到 references/questioning-rules.md（必读）
- 阶段三新增三种『需要下一轮』信号的处置：证伪题删除或重出、『都不是』作答
  说明选项集猜错、未说明的矛盾必须回问——它们不是答案，是出题出错了
- 落款纪律从『缺就提醒补』改为『可留空但自动降级【开发拟定·待追认】』
- 修三处账号改名后失效的仓库地址（JK-yan → kj648）"
```

---

### Task 8: 角色模型简化（先做——Task 4 依赖它）

真实用法是开发或产品拿着单子自己去找人确认，**给谁是开发的事，不是单子的机制**。按人分区解决了一个不存在的问题。本任务把它拆掉，换成「开发／业务」两档，并删掉单子上的期限。

**Files:**
- Modify: `scripts/build_questionnaire.py`（`validate` 的角色校验换成 `decide` enum；删 `roles` 相关；`_check_carry_refs` 等不动）
- Modify: `templates/questionnaire.schema.json`
- Modify: `templates/questionnaire.html`（拆身份分区，换硬活筛选；抬头去期限）
- Modify: `examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json`
- Modify: `SKILL.md`（删「业务沉默协议」整节，两句并进铁律 4 与落款检查）
- Test: `tests/test_build_questionnaire.py`、`tests/test_example_questionnaire.py`、`tests/test_render_html.py`

**Interfaces:**
- Consumes: Task 1/2/3 的全部产物
- Produces: `decide` 字段契约（`"biz"` | `"dev"`）；模板侧 `DECIDE_LABEL` 与 `refreshDecideFilter()`

- [ ] **Step 1: 写失败测试**

在 `tests/test_build_questionnaire.py` 的 `doc()` 里，把每道题的 `"who": ["fin"]` 换成 `"decide": "biz"`（问题 2 换 `"dev"`），删掉顶层 `"roles"`，并删掉 `doc` 里的 `due_days`。然后把 `test_who_must_reference_declared_role` 整个替换为：

```python
    def test_decide_must_be_biz_or_dev(self):
        """角色只有开发与业务两档 —— 给谁是开发的事，不写进单子。"""
        for bad in ("fin", "财务", "BIZ", "", None):
            d = doc()
            d["questions"][0]["decide"] = bad
            errs = bq.validate(d)
            self.assertTrue(any("decide" in e for e in errs), f"{bad!r}: {errs}")

    def test_decide_both_values_pass(self):
        for good in ("biz", "dev"):
            d = doc()
            d["questions"][0]["decide"] = good
            self.assertEqual(bq.validate(d), [])

    def test_roles_key_is_rejected_as_leftover(self):
        """顶层 roles 已废弃 —— 留着会让人以为还能按人分区。"""
        d = doc()
        d["roles"] = [{"id": "fin", "name": "财务"}]
        errs = bq.validate(d)
        self.assertTrue(any("roles" in e and "废弃" in e for e in errs), errs)

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
```

在 `tests/test_render_html.py` 加：

```python
    def test_no_identity_partition_left(self):
        """身份分区已撤销 —— 残留的选择器会让人以为还能按人筛。"""
        for gone in ("whoRow", "offrole", "peekhint", "ownsRole", "rc-role", "填写身份"):
            self.assertNotIn(gone, self.tpl, f"身份分区残留: {gone}")

    def test_decide_filter_present(self):
        for kw in ("必须业务定", "只需过目", "业务定", "开发拟定 · 请过目"):
            self.assertIn(kw, self.tpl, f"缺硬活筛选文案: {kw}")

    def test_no_deadline_in_template(self):
        for gone in ("回填期限", "due_days", "个工作日"):
            self.assertNotIn(gone, self.tpl, f"期限残留: {gone}")
```

在 `tests/test_example_questionnaire.py` 里把 `test_rule_questions_forbid_advice` 之外涉及 `roles`/`who` 的断言改为 `decide`，并加：

```python
    def test_example_has_no_roles_or_due_days(self):
        self.assertNotIn("roles", self.doc)
        self.assertNotIn("due_days", self.doc["doc"])

    def test_example_exercises_both_decide_values(self):
        vals = {q["decide"] for q in self.doc["questions"]}
        self.assertEqual(vals, {"biz", "dev"}, "样例应同时演示两档")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
Expected: FAIL —— `decide`／`roles`／`due_days`／身份分区相关的新测试全红

- [ ] **Step 3: 改校验器**

`scripts/build_questionnaire.py`：

- 顶部加 `DECIDE = ("biz", "dev")`
- `validate()` 里删掉 `role_ids` 与 who 校验，换成：

```python
    if "roles" in doc:
        errs.append("顶层 `roles` 已废弃 —— 角色只有开发与业务两档,由每题的 decide 声明;"
                    "留着 roles 会让人以为还能按人分区(给谁是开发的事,不写进单子)")
    if "due_days" in (doc.get("doc") or {}):
        errs.append("`doc.due_days` 已废弃 —— 单子上不写回填期限;"
                    "期限与催办是人找人的事,skill 观察不到也不该教")
```

- 逐题校验里，把 who 那段换成：

```python
        if q.get("decide") not in DECIDE:
            errs.append(f"{tag}: decide 必须是 {'/'.join(DECIDE)},实际「{q.get('decide')}」"
                        f" —— biz=业务定(记【业务确认】),dev=开发拟定请业务过目(记【开发拟定】)")
        elif q.get("blocking") and q.get("decide") == "dev":
            errs.append(f"{tag}: 阻塞级的题不许标 decide=dev —— 【开发拟定】不得顶过阻塞级岔口,"
                        f"只能推迟开发或向拍板人升级")
```

- `--check` 的通过提示里把「N 个角色」换成按 decide 分档的计数。

`templates/questionnaire.schema.json`：`doc` 的 `required` 去掉与期限相关项、`properties` 删 `due_days`；顶层删 `roles`；`questions[].required` 里 `who` 换 `decide`，并加 `"decide": {"enum": ["biz", "dev"]}` 与说明。

- [ ] **Step 4: 改模板**

`templates/questionnaire.html`：

**4a. 抬头去期限。** `renderMasthead()` 里骑缝框那行

```javascript
      <span class="due">回填期限<br>${d.due_days ?? 3} 个工作日</span></div>`;
```

换成（骑缝框保留单据 id 与轮次，补上题量）：

```javascript
      <span class="due">共 ${DATA.questions.length} 题</span></div>`;
```

**4b. 题头标签换语义。** 顶部加常量，`questionHtml()` 里 `who` 相关全部替换：

```javascript
const DECIDE_LABEL = {
  biz: ['业务定', 'biz'],
  dev: ['开发拟定 · 请过目', 'dev'],
};
```

题头 tags 由 `<span class="tag who">建议由 … 回答</span>` 改为
`<span class="tag d-${cls}">${label}</span>`，并去掉 `data-who` 属性、改为 `data-decide="${q.decide}"`。

**4c. 拆掉身份分区，换硬活筛选。** 删掉 `ROLES`／`myRole`／`ownsRole()`／`buildWhoRow()`／`refreshRoles()`／那个 `document.addEventListener('click', …)` 的 peek 展开、以及 `localStorage` 的 `rc-role`；`refreshAll()` 里去掉 `refreshRoles(); buildWhoRow();`。换成：

```javascript
/* 硬活筛选：业务想先看哪些必须自己定。只改显隐，不改归属——没有"我是谁"，也不折叠任何题。 */
let decideFilter = '';   // '' | 'biz' | 'dev'
function buildDecideRow(){
  const row = document.getElementById('whoRow');
  const count = v => QS.filter(q => !v || q.dataset.decide === v);
  const cell = (v, label) => {
    const mine = count(v), done = mine.filter(answered).length;
    return `<button type="button" class="whochip${decideFilter === v ? ' on' : ''}"`
         + ` data-decide="${v}">${label}<span class="c">${done}/${mine.length}</span></button>`;
  };
  row.innerHTML = '<span class="lb">先看</span>'
    + cell('', '全部') + cell('biz', '必须业务定') + cell('dev', '只需过目');
  row.querySelectorAll('.whochip').forEach(b => b.onclick = () => {
    decideFilter = b.dataset.decide; refreshAll();
  });
}
function refreshDecideFilter(){
  QS.forEach(q => q.hidden = !!decideFilter && q.dataset.decide !== decideFilter);
  rail.querySelectorAll('a').forEach(a => {
    const q = document.getElementById(a.dataset.q);
    a.classList.toggle('dim', !!q && q.hidden);
  });
}
```

`refreshAll()` 末尾改为 `refreshDecideFilter(); buildDecideRow();`。

**4d. CSS。** 删 `.q.offrole`／`.q.offrole:not(.peek) .q-bd`／`.q.offrole .q-hd`／`.peekhint`／`.q.peek`；`.tag.who` 换成两条：

```css
.tag.d-biz{border-color:#C8D2DE;color:#1F3A5F;background:#EEF3F8}
.tag.d-dev{border-color:#D3DBCE;color:#4A585F;background:#F4F7F1}
```

**4e. 回执按 decide 分段小计。** `buildReceipt()` 的成色行后面加一行：

```javascript
  const byDecide = v => QS.filter(q => q.dataset.decide === v);
  const bizQ = byDecide('biz'), devQ = byDecide('dev');
  L.push(`> 分档：业务定 ${bizQ.length} 题（已答 ${bizQ.filter(answered).length}）`
       + ` · 开发拟定 ${devQ.length} 题（已过目 ${devQ.filter(answered).length}）`);
```

并删掉 `J.落款` 里的 `填写身份` 与那句 `L.push('填写身份：…')`；题块标题里 `（建议由 ${DATA...} 回答）` 换成 `（${q.decide === 'biz' ? '业务定' : '开发拟定·请过目'}）`。

- [ ] **Step 5: 改样例**

`examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json`：删顶层 `roles`、删 `doc.due_days`；四道题的 `"who": [...]` 换成 `decide`——问题 1、3、4 是 `"biz"`（起算日、部分还款、已还清判定都是账务口径，业务必须定），问题 2 是 `"dev"`（提醒频率开发已给默认「每 3 天最多 3 次」，请业务过目）。问题 2 原本 `advice_allowed: true` 正好对应 `dev` 档，不用改。

- [ ] **Step 6: 改 SKILL.md**

删掉整段「**业务沉默协议：**…」（第 94 行），把两句承重内容并入：

在铁律 4 的 **【开发拟定】** 那条末尾追加：

```
**业务没回话不等于无异议**——开发拟的默认规则可以先按【开发拟定】往下做，但标签**只因落款转正，不因时间转正**；没落款就永远是【开发拟定】。
```

在「**落款检查：**」那段末尾追加：

```
**阻塞级的题不许用【开发拟定】顶过去**，只能推迟开发或向拍板人升级。
```

并把阶段二第 3 步与确认单要求里「每题标建议回答人」「建议由 XX 回答，不归您管请转交」「警惕替答」相关文字，改为按 `decide: biz|dev` 标档，并写明：**给谁是开发的责任**，出题前自己确认知情人是谁、再决定这份单子发给谁；单子里不体现具体收件人。

- [ ] **Step 7: 跑测试并出包核对**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/build_questionnaire.py \
  "examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json" \
  --root examples/demo-project -o /tmp/rv8.html
grep -c "回填期限\|whoRow\|offrole\|填写身份" /tmp/rv8.html
```
Expected: 测试全绿；最后一条 grep 计数为 0（`whoRow` 作为容器 id 仍在 HTML 骨架里，故只对产物里的**残留文案**计数——若 `whoRow` 命中 1 次属正常，其余三个必须为 0）

- [ ] **Step 8: 提交**

```bash
git add scripts/build_questionnaire.py templates/questionnaire.schema.json \
        templates/questionnaire.html SKILL.md \
        examples/demo-project/docs/requirements/questionnaires/ tests/
git commit -m "feat: 角色收成开发/业务两档，去掉单子上的期限

真实用法是开发或产品拿着单子自己去找人确认——给谁是开发的事，不是单子的
机制。按人分区解决了一个不存在的问题，还带来『角色是自由文本』那类麻烦
（此前评审纠结的『财务 与 财务 AR 负责人 算成两个人』由此连根拔除）。

- roles 顶层声明删除；每题改标 decide: biz|dev。biz=业务必须自己定（答案记
  【业务确认】），dev=开发已拟默认规则请业务过目（记【开发拟定】）
- 阻塞级不许标 dev —— 【开发拟定】不得顶过阻塞级岔口，出包时红字
- 身份分区（whoRow/offrole/peek/填写身份）整体拆除，换成硬活筛选
  『全部 / 必须业务定 / 只需过目』，只改显隐、不折叠任何题
- 单子上不写回填期限；SKILL.md 删除『业务沉默协议』整节与『超时临时生效』
  第四档标签，标签体系回到干净的三档。协议里真正承重的两句并入铁律 4
  （业务没回话不等于无异议，标签只因落款转正、不因时间转正）与落款检查
  （阻塞级不许用【开发拟定】顶过去）"
```

---

### Task 9: UI 方案落到模板（最后做）

方案见已发布的画板（`.superpowers/design/` 下的 `Main/Tokens/States/Receipt/Print.dc.html` 是其working 源）。本任务只改样式与打印，不动功能。

**Files:**
- Modify: `templates/questionnaire.html`（`:root` token 化 + 四处刻意改动 + 打印规格）
- Test: `tests/test_render_html.py`

**Interfaces:**
- Consumes: Task 8 之后的模板
- Produces: 命名 CSS custom properties，与方案一一对照

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python3 -m unittest tests.test_render_html -v`
Expected: FAIL —— 五条新测试全红

- [ ] **Step 3: token 化 `:root`**

在现有 `:root` 的颜色 token 之后追加字阶与间距，并把模板里散落的字号／内外边距逐处换成 `var(--t-*)` / `var(--s-*)`。对照表见方案画板 01：

```css
  /* 字阶：7 级，比率 1.18–1.30。原来是 12 个互不成比的字号 */
  --t-title:28px; --t-h2:21px; --t-q:17px; --t-body:15px;
  --t-sub:13.5px; --t-cap:12.5px; --t-label:11px;
  /* 间距：6 级。原来是 14 个散值 */
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px; --s-6:24px; --s-8:32px;
```

`h1` 的 `clamp(22px,3.4vw,32px)` 改为 `var(--t-title)`——单据标题不需要随视口伸缩。

- [ ] **Step 4: 四处刻意改动**

**4a. amber 升为正式角色。** `.unreviewed` 已用 amber；再把「演示数字基于开发假设」（`.demo-assumed`）从红改 amber、「核对未表态」的计数在 `statusText` 里用 amber。红只留给拦人（阻塞／无据／矛盾／未署名）。

**4b. 正文行宽。** 给 `.bg`、`.logic`、`.clash`、`.guess-w`、`.why2`、`.ev-weak` 加 `max-width:62ch`——中文一行 50 多字会跳行。

**4c. 自动不适用不再遮罩。** 删掉 `.grp.na::after` 整条与 `.grp.na{position:relative;opacity:.45}`，换成：

```css
.grp.na>.grp-q{color:var(--ink-45);text-decoration:line-through}
.grp.na>.opts,.grp.na>.demo{display:none}
.grp.na .na-note{padding:var(--s-2) var(--s-3);background:var(--sheet-2);
  border:1px dashed var(--ink-45);font-size:var(--t-cap);color:var(--ink-70);line-height:1.7}
```

并在 `refreshNA()` 里，为 `.na` 的组插入（或更新）一个真实的 `.na-note` 元素，内容为 `<b>本小问不适用</b>——${note}。回执里会写成这句推导，不算漏答。`——不再靠 `content:attr()`。

**4d. 落款搬回 `<main>` 内。** Step 3a 的骨架把 `<section class="signoff">` 放在 `.body` 之外，导致落款整页通栏、伸到左侧索引底下。移进 `<main>`，与题目同宽——单据的落款必须与正文对齐。

- [ ] **Step 5: 打印规格**

`@media print` 整段替换为：

```css
@media print{
  @page{margin:15mm}
  body{background:#fff;background-image:none;font-size:16px;color:#000}
  .statusbar,.dock,.rail,.howto,.deny,.ev summary::after{display:none!important}
  .body{grid-template-columns:1fr;gap:0}
  .q,.masthead,.signoff,.ledger tr,.demo{break-inside:avoid}
  .cond,.ev,.ev-b,.coords{display:block!important}
  .seal{border-color:#000;color:#000}
  .tag.first,.badge.guess{border:1.5px solid #000;color:#000;background:#fff;font-weight:700}
  .badge.guess{background:#000;color:#fff}
  .demo td.v,.ledger td.n{border-left-color:#000;border-right-color:#000}
  .clash,.guess-w,.ev-weak{border-color:#000;background:#fff}
  textarea,input[type=text]{border-color:#000;background:
    repeating-linear-gradient(#fff 0 27px,#ccc 27px 28px)}
}
```

要点：正文上调到 16px（=12pt，印刷正文下限；屏幕的 15px 在纸上只有 11.25pt）；条件块与依据区强制展开（纸上没法点开，藏起来等于没给）；颜色退化为线宽与反白（红在单色打印机上印成灰、浅底色吃墨）；作答区给手写横线而不是空白框。

- [ ] **Step 6: 跑测试并出包，人工过浏览器与打印预览**

Run:
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/build_questionnaire.py \
  "examples/demo-project/docs/requirements/questionnaires/2026-07-11-逾期提醒-r1.json" \
  --root examples/demo-project -o /tmp/rv9.html
```

人工验收（CI 覆盖不到，交控制方在浏览器里做）：
- [ ] 与方案画板「全页版式」对照：抬头、骑缝、吸顶条、两栏、题卡、落款在右栏内
- [ ] 无据题依据区红底默认展开；代码档外层只显示业务语言、坐标折叠在内
- [ ] 自动不适用：标题带删除线、选项整组消失、推导链是真实元素（不是遮罩）
- [ ] 矛盾红框、兜底出口、硬活筛选三钮
- [ ] 人读回执弹窗：成色卡片、署名条、逐题清单、原始 md 折叠在最底
- [ ] ⌘P 打印预览：正文明显变大、进度条／索引／底部条消失、条件块与依据区展开、题卡不跨页断开、作答区是横线

- [ ] **Step 7: 提交**

```bash
git add templates/questionnaire.html tests/test_render_html.py
git commit -m "style: 落实 UI 方案 —— 字阶/间距 token 化、amber 升为角色、去遮罩、打印规格

方案（已发布画板，working 源在 .superpowers/design/）基于现有 CSS 真实值，
四处是刻意改动：

- 字号从 12 个互不成比的散值收成 7 级字阶；间距从 14 个散值收成 6 级；
  h1 的 clamp 改定值 —— 单据标题不需要随视口伸缩
- amber 从『只在一处高亮』升为正式角色『成立但没验过』，把『有据』与
  『已核实』在视觉上分开；红只留给拦人
- 自动不适用不再用 93% 遮罩压住正文（文字叠糊、还挡住『原本问什么』），
  改为标题加删除线 + 选项整组移除 + 推导链作为真实元素
- 落款搬回 <main> 内与题目同宽 —— 单据落款必须与正文对齐
- 打印从『藏掉 chrome』改为真印刷规格：正文上调到 16px（15px 在纸上只有
  11.25pt，低于下限）、条件块与依据区强制展开、颜色退化为线宽与反白、
  题卡 break-inside:avoid、作答区给手写横线
- 正文加 62ch 行宽约束 —— 中文一行 50 多字会跳行"
```

---

## 已知限制（P0 不做，写进 spec §11 的缺口表）

- **表格题**：原型里 AR 的"阻塞原因×责任部门"可编辑表格是项目专有题型，P0 的 schema 只支持单选／多选／文本。需要时另加 `groups[].kind: "table"`。
- **JS 渲染无自动化测试**：CI 只覆盖 Python 侧。模板改动后必须人工过 Task 3 Step 6 的清单。
- **业务概念层不受 harness 保护**：`path:line + snippet` 能被 grep 核验，但规则条目／`logic` 是开发对代码的**解读**，机器判不了它对不对。缓解四条：页面明写它是解读、强制列 `branches`（把开放问题收成有界问题）、给业务证伪出口、可选盲审 diff。
- **盲审是抽样不是证明**：概率性检查，换的是标签（`reviewed`）不是保证类型，不得写成"已验证"；进不了 CI，CI 只查填没填。
- **`code_rev` 只记不校**：回执回来时若 `code_rev` 已不是 HEAD，说明期间代码变过，需人工判断结论是否仍成立；P0 只记录不自动比对。
- **`kind:"receipt"` 非文件引用**：`verify_evidence.py` 仍校验不了，处置照 spec §9——回执归档进 `raw/` 后改真路径引用。
- **P1 延后**：`verify_evidence.py` 吃 json 与禁用措辞探测、`spec-template.md` 的 Rejected 段自动产出、`blindspot-checklist.md` 逐维度判据。
- **架构复审里另两条延后**：覆盖阈值魔数 8 与实际 12 个维度脱钩（`verify_evidence.py:110`，应改为从 checklist 动态数）；SKILL.md 拆薄壳入口（先用 skill-creator 测出触发基线再决定）。

## 自查

**Spec 覆盖**：§4 产物清单 → Task 1/3/4/5/6；§5 schema → Task 1；§6 依赖分层与两条硬约束 → Task 1（分支对称机检）+ Task 3（layer 渲染）+ Task 4（规则文档）；§7 页面行为八条 → Task 3 Step 6 验收清单逐条对应；§8 借鉴取舍 → Task 4 的 questioning-rules.md 第五条写明与 grilling 的分界；§9 三处机检缺口 → Task 5；§10 测试 → Task 1/2/3/4/5 的测试 + Task 6 的 CI；§12 P0 范围 → 全部覆盖。

**新增覆盖**：§3 的 D18/D19/D20/D21 → Task 1（`_check_rules_threshold` / `_check_reviewed` / `validate_refs` 与 8 个测试）+ Task 2（`templates/rules-template.md`、样例规则文档、问题 4 改引 R3 并带 `reviewed`）+ Task 3（`rulesHtml` / `codeCoordsOnly` / `reviewHtml`、机读区带规则引用与复核状态、两条验收项）+ Task 4（questioning-rules 二之三、二之四节）。§3 的 D15/D16/D17 → Task 1（`_check_code_cites` / `_check_demo` 与 6 个测试）+ Task 2（样例桩件与真坐标核验）+ Task 3（`citeHtml` 两层渲染、`code_rev` 自动填、`demo.basis` 标注）+ Task 4（questioning-rules 第二之二节）。

**类型一致**：`validate(doc) -> list[str]`、`render_html(doc, template) -> str`、`render_md(doc) -> str`、`TEMPLATE_PATH`、`PLACEHOLDER`、`ADVICE_WORDS` 在 Task 1/3/4 间一致；`check_file` 返回值从 4 元组改 6 元组只在 Task 5 内部，`main()` 同任务同步。模板侧 `whenToDom()` 负责 schema 题号（`2=B`）到 DOM name（`q2=B`）的转换，Task 3 定义、Task 3 内自用。`_check_code_cites(ev, tier, tag)`、`_check_demo(q, ev, tag)`、`code_rev()`、`citeHtml(c)`、`rulesHtml(ev)`、`codeCoordsOnly(c)`、`reviewHtml(ev)` 均在 Task 1／Task 3 内定义并调用；`validate_refs(doc, root)` 在 Task 1 定义，Task 2 的测试与 Task 6 的 CI（`--root`）调用。无跨任务悬空引用。

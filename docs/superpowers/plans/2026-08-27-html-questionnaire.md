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
  - `validate(doc: dict) -> list[str]` — 返回错误消息列表，空列表表示通过。**不抛异常**。
  - 模块级常量 `ADVICE_WORDS: re.Pattern` — 建议措辞探测。

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
另: evidence.tier 为 src/code 必须有 cites;为 guess 必须写 weak(无据也要说清哪儿没据)。
"""
import argparse
import json
import re
import sys
from pathlib import Path

TIERS = ("src", "code", "guess")
ADVICE_WORDS = re.compile(r"开发建议|建议选|推荐选|我的默认建议")
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


def _check_code_cites(ev, tier, tag):
    """code 档的失败模式不是『原话被改写』,而是『单点引用冒充整体逻辑』。
    一行赋值不证明它是唯一赋值点、没有别处覆盖、没有 flag 短路。"""
    errs, code_cites = [], [c for c in ev.get("cites", []) if c.get("kind") == "code"]
    for c in code_cites:
        where = f"{c.get('path')}:{c.get('line')}"
        if not str(c.get("logic") or "").strip():
            errs.append(f"{tag}: code 引用 {where} 缺 `logic` —— 要有一句白话说清"
                        f"这段代码实际做什么,给业务否掉的机会")
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
    args = ap.parse_args()

    doc = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    errs = validate(doc)
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
Expected: PASS，18 个测试

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
- Create: `examples/demo-project/app/reminder_rules.py`（桩件，让样例能演示 `code` 档证据）
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

- [ ] **Step 4: 写样例 json**

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
        "cites": [{
          "kind": "code",
          "path": "app/reminder_rules.py", "line": 18,
          "snippet": "if bill.balance <= 0:",
          "logic": "代码现在按余额是否 ≤ 0 判定已还清，完全不看单子的状态字段；余额没归零就一直算未还清。",
          "entry": "app/reminder_rules.py:15",
          "branches": [
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

- [ ] **Step 5: 运行测试，确认通过**

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
Expected: PASS，全部测试通过（含 `test_cites_point_at_real_archived_lines` —— 它保证
样例里每条引用真的指向归档原文那一行）

- [ ] **Step 6: 提交**

```bash
git add examples/demo-project/app/ examples/README.md \
        examples/demo-project/docs/requirements/questionnaires/ \
        tests/test_example_questionnaire.py
git commit -m "feat: 逾期提醒样例 questionnaire.json

演示 reveal / links.na / links.clash 三种依赖，含一道 tier=guess 的无据题
（部分还款场景是从盲区清单推的，不是业务说过的）。测试逐条核验 cites 真的
指向归档原文那一行、code 档的 entry 与每个 branch 的 cite 也是真坐标，防编造。

加了 app/reminder_rules.py 桩件：样例原本只有 docs/，演示不到 code 档——而 code 档
恰恰是最容易『单点引用冒充整体逻辑』的一类。"
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
        """logic 是开发对代码的解读,页面必须标明,不能让业务当成自己说过的话。"""
        self.assertIn("这是开发读代码得出的理解", self.tpl)


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

function evHtml(q){
  const ev = q.evidence || {}, [label, cls] = TIER_LABEL[ev.tier] || TIER_LABEL.guess;
  const open = (ev.tier === 'guess' || ev.weak) ? ' open' : '';
  const cites = (ev.cites || []).map(citeHtml).join('')
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

并把 `J` 的初始化改为 `{单据: DATA.doc.id, 轮次: DATA.doc.round, ...}`。同时删掉原型里 `no==='6'` 的阻塞原因表特例——那是 AR 项目专有的题型，P0 不支持表格题（见「已知限制」）。

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
- [ ] 问题 4 依据区**外层只显示白话**：「我们查代码看到系统现在是这么做的：代码现在按余额是否 ≤ 0 判定已还清……（这是开发读代码得出的理解，不是您说过的话——不对请直接指出）」；`app/reminder_rules.py:18`、入口、两条分支都**折叠**在「代码位置与分支（开发看）」里
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
- Consumes: `validate()`、样例 json
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
    d, role = doc["doc"], {r["id"]: r["name"] for r in doc["roles"]}
    L = [f"# 需求确认单：{d['title']}（第 {d['round']} 轮）",
         f"> 第 {d['round']} 轮 · {d['sent_on']} · 发出人：{d['sent_by']}"
         f" · 请于 {d.get('due_days', 3)} 个工作日内填写后回传", ""]
    L += [d["usage"], "",
          "填写说明：第一部分请逐条核对；第二部分请在 ☐ 打勾、【作答区】作答。"
          "标注「建议由 XX 回答」的题目不归您管请转交。填完发回即可。", ""]

    if doc.get("part1"):
        L += ["## 第一部分 · 我们理解的（请逐条核对）", "",
              "| # | 我们理解的 | 备注 | 对不对 |", "|---|---|---|---|"]
        L += [f"| {r['n']} | {r['we_understand']} | {r.get('note', '')} | ☐ 对　☐ 不对 |"
              for r in doc["part1"]]
        L += ["", "【作答区】哪条不对、哪里不对（全对就写「无异议」）：", ""]

    L += ["## 第二部分 · 待确认问题（请作答）", ""]
    for q in sorted(doc["questions"], key=lambda x: (x["layer"], x["no"])):
        who = " + ".join(role.get(i, i) for i in q["who"])
        L.append(f"### 问题 {q['no']}：{q['title']}（建议由 {who} 回答）"
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

### 问题 1：「逾期」从哪天起算？（建议由 财务 王芳 回答）（阻塞）
☑ A. 到期日次日即逾期
☐ B. 有宽限期，宽限期后才算
【作答区】到期日次日。

### 问题 2：重复提醒的频率和上限？（建议由 运营 李姐 回答）
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
### 问题 2：重复提醒的频率和上限？（建议由 运营 李姐 回答）
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
        self.assertIn("不成立", out)
        self.assertIn("判为不成立 1 道", out)
        self.assertNotIn("问题 2『重复提醒的频率和上限？", out.split("== 摘要 ==")[0]
                         .replace("不成立", ""))   # 不该同时报未作答

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
            --check

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
```

- [ ] **Step 3: 说明两类测试的分工**

Modify `tests/README.md`，在开头插入：

```markdown
## 两类测试

- **`test_*.py`** — 可执行断言，CI 每次 push/PR 跑（`python3 -m unittest discover -s tests`）。
  覆盖：questionnaire.json 校验、样例数据、HTML/MD 渲染、回执机检。
- **`scenario-*.md`** — 给人读的场景剧本，用来人工回归 skill 的**判断质量**
  （成色分级、冲突检测、剥离阀门）——这些没法用断言表达，需要人读产出评估。

**CI 覆盖不到的**：模板的 JS 渲染与交互需要浏览器。每次改 `templates/questionnaire.html`
后按实施计划 Task 3 Step 6 的清单人工过一遍。
```

- [ ] **Step 4: 提交并确认 CI 绿**

```bash
git add .github/workflows/ci.yml tests/README.md
git commit -m "ci: 把机检脚本接进 push/PR 门禁

原来 CI 只在 release 时跑、且只验 frontmatter——仓库最有价值的两个机检脚本
（verify_evidence / check_questionnaire）从来没被自动验证过，tests/ 下的场景
也只是给人读的 markdown，不可执行。这半天就手工撞出三处格式契约不一致。

现在 push/PR 会跑：frontmatter 校验、单元测试、样例确认单校验与出包、样例
spec 证据核验、旧手写回执回归。JS 渲染仍需人工过浏览器清单（tests/README 已注明）。"
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

## 已知限制（P0 不做，写进 spec §11 的缺口表）

- **表格题**：原型里 AR 的"阻塞原因×责任部门"可编辑表格是项目专有题型，P0 的 schema 只支持单选／多选／文本。需要时另加 `groups[].kind: "table"`。
- **JS 渲染无自动化测试**：CI 只覆盖 Python 侧。模板改动后必须人工过 Task 3 Step 6 的清单。
- **`logic` 不受 harness 保护**：`path:line + snippet` 能被 grep 核验，但 `logic` 是开发对代码的**解读**，机器判不了它对不对。缓解只有三条：页面明写它是解读、要求列 `branches`、给业务证伪出口。
- **`code_rev` 只记不校**：回执回来时若 `code_rev` 已不是 HEAD，说明期间代码变过，需人工判断结论是否仍成立；P0 只记录不自动比对。
- **`kind:"receipt"` 非文件引用**：`verify_evidence.py` 仍校验不了，处置照 spec §9——回执归档进 `raw/` 后改真路径引用。
- **P1 延后**：`verify_evidence.py` 吃 json 与禁用措辞探测、`spec-template.md` 的 Rejected 段自动产出、`blindspot-checklist.md` 逐维度判据。
- **架构复审里另两条延后**：覆盖阈值魔数 8 与实际 12 个维度脱钩（`verify_evidence.py:110`，应改为从 checklist 动态数）；SKILL.md 拆薄壳入口（先用 skill-creator 测出触发基线再决定）。

## 自查

**Spec 覆盖**：§4 产物清单 → Task 1/3/4/5/6；§5 schema → Task 1；§6 依赖分层与两条硬约束 → Task 1（分支对称机检）+ Task 3（layer 渲染）+ Task 4（规则文档）；§7 页面行为八条 → Task 3 Step 6 验收清单逐条对应；§8 借鉴取舍 → Task 4 的 questioning-rules.md 第五条写明与 grilling 的分界；§9 三处机检缺口 → Task 5；§10 测试 → Task 1/2/3/4/5 的测试 + Task 6 的 CI；§12 P0 范围 → 全部覆盖。

**新增覆盖**：§3 的 D15/D16/D17 → Task 1（`_check_code_cites` / `_check_demo` 与 6 个测试）+ Task 2（样例桩件与真坐标核验）+ Task 3（`citeHtml` 两层渲染、`code_rev` 自动填、`demo.basis` 标注）+ Task 4（questioning-rules 第二之二节）。

**类型一致**：`validate(doc) -> list[str]`、`render_html(doc, template) -> str`、`render_md(doc) -> str`、`TEMPLATE_PATH`、`PLACEHOLDER`、`ADVICE_WORDS` 在 Task 1/3/4 间一致；`check_file` 返回值从 4 元组改 6 元组只在 Task 5 内部，`main()` 同任务同步。模板侧 `whenToDom()` 负责 schema 题号（`2=B`）到 DOM name（`q2=B`）的转换，Task 3 定义、Task 3 内自用。`_check_code_cites(ev, tier, tag)`、`_check_demo(q, ev, tag)`、`code_rev()`、`citeHtml(c)` 均在 Task 1／Task 3 内定义并调用，无跨任务悬空引用。

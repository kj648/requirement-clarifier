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
# 规则文档条目标题:允许 ## 或 ### 两级标题,分隔符允许半角/全角句号、半角/全角冒号,
# 因为不同作者写规则文档时标题层级和标点习惯不一致,死绑一种格式会让 validate_refs 误报。
RULE_ENTRY = re.compile(r"^#{2,3}\s*(?P<id>R\d+)[.．:：]\s*(?P<text>.*)$", re.M)
# when 表达式里的题号引用:  "1=B"、"4=B & 1=B"、"7.crm!=x"
WHEN_REF = re.compile(r"(?<![\w.])(\d+)\s*(?:\.\w+)?\s*(?:!=|=)")
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "questionnaire.html"
PLACEHOLDER = "__QUESTIONNAIRE_DATA__"


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

    # 类型不对就报错并提前返回,不往下走 —— 结构错误没法继续做语义校验,
    # 而 validate() 承诺不抛异常,格式错的 questionnaire.json 也要给出诊断而不是让工具崩掉。
    if not isinstance(doc["roles"], list) or any(not isinstance(r, dict) for r in doc["roles"]):
        errs.append("roles 必须是对象数组,每项至少含 id/name —— 不是自由文本列表")
    if not isinstance(doc["questions"], list) or any(not isinstance(q, dict) for q in doc["questions"]):
        errs.append("questions 必须是对象数组")
    if "links" in doc and not isinstance(doc["links"], dict):
        errs.append("links 必须是对象(键为 na/carry/clash,值为数组)")
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

        # groups/options 结构防御: validate() 承诺不抛异常, 结构坏掉时给出诊断并跳过
        # 依赖它的语义校验(建议措辞/分支对称/reveal), evidence 那几项照常做。
        gs = q.get("groups")
        if not isinstance(gs, list):
            errs.append(f"{tag}: groups 必须是数组")
            gs, opts_ok = [], False
        else:
            opts_ok = all(isinstance(g, dict) for g in gs)
            if not opts_ok:
                errs.append(f"{tag}: groups 每项必须是对象(至少含 id/options)")
        bad_grp = [str(g.get("id")) for g in (gs if opts_ok else [])
                   if not isinstance(g.get("options", []), list)
                   or any(not isinstance(o, dict) for o in g.get("options", []))]
        if bad_grp:
            errs.append(f"{tag}: 组 {'、'.join(bad_grp)} 的 options 必须是对象数组,"
                        f"每项至少含 key/label —— 不是字符串列表")
            opts_ok = False

        groups = {g.get("id"): g for g in gs if isinstance(g, dict)}
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

        if not opts_ok:
            continue        # 选项结构坏掉,建议措辞/分支对称/reveal 三项无从校验

        if not q.get("advice_allowed", False):
            for g in q.get("groups", []):
                for o in g.get("options", []):
                    # label 和 cost 都要扫 —— 只查 cost 的话,文案挪个字段就能绕过禁令。
                    for field in ("label", "cost"):
                        hit = ADVICE_WORDS.search(str(o.get(field, "")))
                        if hit:
                            errs.append(
                                f"{tag} 选项 {o.get('key')}: advice_allowed=false 却在 `{field}` "
                                f"里带建议措辞「{hit.group()}」—— 规则/账务口径题标建议等于替业务拍板")

        errs.extend(_check_branches(q, tag))
        for r in q.get("reveal", []):
            own_keys = {o.get("key") for g in q.get("groups", []) for o in g.get("options", [])}
            if str(r.get("when")) not in own_keys:
                errs.append(f"{tag}: reveal.when「{r.get('when')}」不是本题任何选项的 key")

    for kind, items in (doc.get("links") or {}).items():
        for it in items or []:
            if not isinstance(it, dict):
                errs.append(f"links.{kind}: 条目必须是对象,实际「{it!r}」")
                continue
            errs.extend(_check_link(kind, it, layer_of))

    return errs


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
    out = Path(args.out or f"confirm-{doc['doc']['id']}-r{doc['doc']['round']}.html")
    out.write_text(render_html(doc, TEMPLATE_PATH.read_text(encoding="utf-8")),
                   encoding="utf-8")
    print(f"✓ 已出包 {out}（{out.stat().st_size // 1024} KB，单文件自包含）")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""build_questionnaire.py — questionnaire.json → 单文件 HTML 确认单

用法:
  python3 scripts/build_questionnaire.py <questionnaire.json> [-o 输出.html] [--md 输出.md]
  python3 scripts/build_questionnaire.py <questionnaire.json> --check   # 只校验不出包
  只给 --md 就只出 md;给了 -o(或两个都不给)才出 HTML。

校验(全部 FAIL,不出包):
0. 必填字段与类型: doc/questions 的必填项存在性(与 questionnaire.schema.json 的
   required 对应,两处人工同步),no/layer 必须是整数,选项 key 同题内跨组唯一。
1. 决策归属: questions[].decide 必须是 biz(业务定)或 dev(开发拟定请业务过目)
   ——给谁去问是开发的事,单子不按人分区;阻塞级不许标 dev,只能推迟或升级。
2. 依赖闭环: links/reveal 的 when 引用的题必须存在,且其 layer 严格小于被约束题的 layer。
3. 分支对称: 同一 main 组内若部分选项有后续、部分没有,没有后续的必须显式标 terminal
   ——一次性发单、异步回填,中间没有 AI 追问,漏掉的分支要等一整轮才能补。
4. 建议措辞: advice_allowed=false 的题,任何选项不得出现建议措辞(防锚定替答)。
5. 业务概念层: code 引用超过 inline 阈值(分支>2 / 跨多文件 / logic 被别题复用)
   必须沉淀进 rules/<模块名>.md 并给 rules_ref —— 否则同一段逻辑抄三遍、写不一致、
   拼不出整体、读代码的理解无处沉淀。
6. 阻塞级岔口必须配 demo(跨分支演示):只画岔口不算数 = 让人凭抽象拍板。
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
DECIDE = ("biz", "dev")
ADVICE_WORDS = re.compile(r"开发建议|建议选|推荐选|我的默认建议")
# 规则文档条目标题:允许 ## 或 ### 两级标题,分隔符允许半角/全角句号、半角/全角冒号,
# 因为不同作者写规则文档时标题层级和标点习惯不一致,死绑一种格式会让 validate_refs 误报。
RULE_ENTRY = re.compile(r"^#{2,3}\s*(?P<id>R\d+)[.．:：]\s*(?P<text>.*)$", re.M)
# when 表达式里的题号引用:  "1=B"、"4=B & 1=B"、"7.crm!=x"
WHEN_REF = re.compile(r"(?<![\w.])(\d+)\s*(?:\.\w+)?\s*(?:!=|=)")
# 页面侧 meets() 只实现了「& 连接的等值判断」。设计文档许诺的 | / != / in [...] 三个算子
# 页面没有实现:前两个静默恒 false,`in [...]` 更会让 refreshAll() 抛 TypeError —— 进度条、
# 身份选择器、导出按钮一起失效,而屏幕上没有任何提示,业务连东西都交不回来。所以在出包时
# 红字拒收:失败要出现在开发面前,不要出现在业务面前。三个算子实现之后再放宽这里。
WHEN_TOKEN = re.compile(r"^\s*\d+(?:\.\w+)?\s*=\s*[^=&|!\[\]]+$")
# 选项 key 原样拼进 data-when="q<no>=<key>" 与 radio value,含算子字符会让条件引擎永不命中
KEY_BAD = re.compile(r"[=&|!\[\]\s]")
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "questionnaire.html"
PLACEHOLDER = "__QUESTIONNAIRE_DATA__"
# 必填字段与「谁在用它」。与 templates/questionnaire.schema.json 的 required 一一对应,
# 两处需人工保持同步 —— schema 只是给出题者读的契约,运行时校验在这里。
DOC_FIELDS = {
    "id": "默认输出文件名与回执文件名用它",
    "title": "HTML 抬头与 md 大标题",
    "round": "第 N 轮,抬头与回执头部都要写",
    "sent_by": "抬头『发出人』",
    "sent_on": "抬头『发出日期』,回执回来时用它对时",
    "usage": "给业务看的『你的答案会被用到哪里』,md 与 HTML 都直接渲染它",
}
Q_FIELDS = {
    "no": "题号,DOM id / data-when / 回执的『### 问题 N』全靠它",
    "layer": "依赖层级,md 排序与 links 的前置校验都用它",
    "title": "题目标题,`### 问题 N：<title>` 是机检认的契约",
    "decide": "决策归属 biz|dev,决定答案记【业务确认】还是【开发拟定】",
    "advice_allowed": "是否允许建议措辞;缺了会静默按 false 处理,该由出题者明写",
    "evidence": "依据档位,页面按它标『原话/代码/无据』",
    "groups": "选项组,至少要有 main",
}


def _is_int(v):
    """bool 是 int 的子类,但 True 当题号是错的。"""
    return isinstance(v, int) and not isinstance(v, bool)


def _cites(ev):
    """安全取 cites —— 结构坏掉时当空处理。坏结构本身由 validate() 单独报一条,
    不能让下游 `c.get(...)` 抛 AttributeError:validate() 承诺不抛异常。"""
    cs = ev.get("cites") if isinstance(ev, dict) else None
    return [c for c in cs if isinstance(c, dict)] if isinstance(cs, list) else []


def _when_refs(expr):
    """从 when 表达式里取出被引用的题号。"""
    return {int(m) for m in WHEN_REF.findall(str(expr))}


def _check_when_expr(expr, tag):
    """when 必须落在页面 meets() 实现的子集里:`&` 连接的 `<题号>[.<组id>]=<值>`。"""
    text = str(expr)
    for token in text.split("&"):
        if not WHEN_TOKEN.match(token):
            return [f"{tag}: when「{text}」用了页面未实现的算子 —— meets() 目前只支持 `&` "
                    f"连接的等值判断(如 `1=A & 2=B`)。`|`、`!=`、`in [...]` 都还没实现:"
                    f"前两个会静默恒 false,`in [...]` 会让整页 JS 抛异常瘫痪(导出按钮失效"
                    f"且无任何提示),故一律在出包时拒收"]
    return []


def _check_option_keys(gs, tag):
    """选项 key 会原样进 data-when 与 radio value,含算子字符条件显隐就永不命中;
    同一题内还必须跨组唯一 —— 页面的 whenInWords() 按 key 反查选项标签,重名时
    取到的是先出现的那一组,业务看到的矛盾提示会用错组的措辞描述自己的选择。
    不改 JS,把这个业务可见的错文案变成出包时拒收。"""
    errs, seen = [], {}
    for g in gs:
        for o in g.get("options", []):
            k = str(o.get("key", ""))
            if not k or KEY_BAD.search(k):
                errs.append(f"{tag} 组 {g.get('id')}: 选项 key「{k}」为空或含空白/算子字符"
                            f"(= & | ! [ ]) —— key 原样拼进 data-when 与 radio value,"
                            f"这类字符会让条件显隐永不命中")
                continue
            if k in seen:
                errs.append(f"{tag}: 选项 key「{k}」在组 {seen[k]} 与组 {g.get('id')} 里"
                            f"重复 —— 同一题内 key 必须跨组唯一:whenInWords() 按 key "
                            f"反查标签,重名时取先出现的那一组,业务会看到用错组的措辞"
                            f"描述的矛盾提示")
            else:
                seen[k] = g.get("id")
    return errs


def _carry_dom_id(ref):
    """links.carry 的 from/to 写作 `<题号>.<字段id>`,字段id 即该题 reveal[].when 的键;
    页面上那个输入框的 DOM id 是 rv-<题号>-<字段id>。这是 carry 唯一的落点约定。"""
    parts = str(ref).split(".")
    return f"rv-{parts[0]}-{parts[1]}" if len(parts) == 2 else None


def _check_carry_refs(doc):
    """carry 的 from/to 必须真能落到某道题的某个 reveal 输入框上 —— 落不到就是死链路:
    页面不报错、业务看不出、事实也没被传过去。"""
    errs = []
    reveal_ids = {f"rv-{q.get('no')}-{r.get('when')}"
                  for q in doc.get("questions", []) or []
                  if isinstance(q, dict)
                  for r in q.get("reveal", []) or [] if isinstance(r, dict)}
    for it in (doc.get("links") or {}).get("carry") or []:
        if not isinstance(it, dict):
            continue
        for side in ("from", "to"):
            dom = _carry_dom_id(it.get(side, ""))
            if dom is None:
                errs.append(f"links.carry: `{side}`「{it.get(side)}」格式不对,"
                            f"应为 `<题号>.<字段id>`(字段id 即该题 reveal[].when 的键)")
            elif dom not in reveal_ids:
                errs.append(f"links.carry: `{side}`「{it.get(side)}」在页面上没有对应输入框"
                            f"(找不到 {dom}) —— carry 只能落在 reveal 的输入框上,"
                            f"落不到就是死链路:不报错、不生效、也没人看得出")
    return errs


def validate(doc):
    errs = []
    for key in ("doc", "questions"):
        if key not in doc:
            errs.append(f"缺顶层字段 `{key}`")
    if errs:
        return errs

    if "roles" in doc:
        errs.append("顶层 `roles` 已废弃 —— 角色只有开发与业务两档,由每题的 decide 声明;"
                    "留着 roles 会让人以为还能按人分区(给谁是开发的事,不写进单子)")
    stale_who = [q.get("no") for q in doc.get("questions") or []
                 if isinstance(q, dict) and "who" in q]
    if stale_who:
        errs.append(f"问题 {'、'.join(str(n) for n in stale_who)} 还带着 `who` 字段 —— 已废弃,"
                    f"改标 decide: biz|dev。留着 who 会让人以为单子还会显示具体回答人,"
                    f"而它其实被静默忽略:标的人无声消失,写的人不会知道")
    if "due_days" in (doc.get("doc") or {}):
        errs.append("`doc.due_days` 已废弃 —— 单子上不写回填期限;"
                    "期限与催办是人找人的事,skill 观察不到也不该教")
    if errs:
        return errs

    # 类型不对就报错并提前返回,不往下走 —— 结构错误没法继续做语义校验,
    # 而 validate() 承诺不抛异常,格式错的 questionnaire.json 也要给出诊断而不是让工具崩掉。
    if not isinstance(doc["questions"], list) or any(not isinstance(q, dict) for q in doc["questions"]):
        errs.append("questions 必须是对象数组")
    if "links" in doc and not isinstance(doc["links"], dict):
        errs.append("links 必须是对象(键为 na/carry/clash,值为数组)")
    if errs:
        return errs

    # 必填字段存在性 —— templates/questionnaire.schema.json 的 required 不参与运行时
    # 校验(schema 全仓无代码引用),两处靠人工同步。缺这些字段时以前是 validate PASS
    # → render_md/render_html KeyError:校验说没事,出包却崩。
    d = doc["doc"]
    if not isinstance(d, dict):
        return ["`doc` 必须是对象(含 id/title/round/sent_by/sent_on/usage)"]
    for f, why in DOC_FIELDS.items():
        if f not in d or d[f] in (None, ""):
            errs.append(f"缺 `doc.{f}` —— {why}")
    for q in doc["questions"]:
        tag = f"问题 {q.get('no', '?')}"
        for f, why in Q_FIELDS.items():
            if f not in q or q[f] in (None, ""):
                errs.append(f"{tag}: 缺 `{f}` —— {why}")
    if errs:
        return errs        # 字段都不全,再往下做语义校验只会刷出一串连带报错

    for q in doc["questions"]:
        for f in ("no", "layer"):
            if not _is_int(q[f]):
                errs.append(
                    f"问题 {q.get('no')}: `{f}` 必须是整数,实际「{q[f]!r}」({type(q[f]).__name__})"
                    f" —— 页面用 `===` 严格比较题号(clash 的挂载判据就是它),"
                    f"字符串 \"1\" 与 1 不相等:clash 会静默不挂载,而它是这条通路上"
                    f"仅有的现场校验;layer 之间还要直接比大小,类型混了就没法比")
    if errs:
        return errs

    layer_of = {q.get("no"): q.get("layer", 1) for q in doc["questions"]}
    # 同一句 logic 出现在多道题里 → 该沉淀进 rules/,不该抄两遍
    logic_counts = {}
    for q in doc["questions"]:
        for c in _cites(q.get("evidence")):
            if c.get("kind") == "code" and c.get("logic"):
                k = _norm(c["logic"])
                logic_counts[k] = logic_counts.get(k, 0) + 1

    for q in doc["questions"]:
        no = q.get("no")
        tag = f"问题 {no}"

        if q.get("decide") not in DECIDE:
            errs.append(f"{tag}: decide 必须是 {'/'.join(DECIDE)},实际「{q.get('decide')}」"
                        f" —— biz=业务定(记【业务确认】),dev=开发拟定请业务过目(记【开发拟定】)")
        elif q.get("blocking") and q.get("decide") == "dev":
            errs.append(f"{tag}: 阻塞级的题不许标 decide=dev —— 【开发拟定】不得顶过阻塞级岔口,"
                        f"只能推迟开发或向拍板人升级")

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

        if opts_ok:
            errs.extend(_check_option_keys(gs, tag))

        groups = {g.get("id"): g for g in gs if isinstance(g, dict)}
        if "main" not in groups:
            errs.append(f"{tag}: 缺 main 组")

        ev = q.get("evidence") or {}
        # evidence/cites/rules_ref 的结构防御:坏结构报一条诊断,然后按空处理往下走,
        # 而不是让 `.get` 抛 AttributeError —— validate() 承诺不抛异常。
        if not isinstance(ev, dict):
            errs.append(f"{tag}: evidence 必须是对象(至少含 tier),实际「{ev!r}」")
            ev = {}
        cs = ev.get("cites")
        if cs is not None and (not isinstance(cs, list)
                               or any(not isinstance(c, dict) for c in cs)):
            errs.append(f"{tag}: evidence.cites 必须是对象数组,每项至少含 "
                        f"kind/path/line/snippet —— 不是字符串列表")
        rr = ev.get("rules_ref")
        if rr is not None and (not isinstance(rr, list)
                               or any(not isinstance(r, dict) for r in rr)):
            errs.append(f"{tag}: evidence.rules_ref 必须是对象数组,每项含 id/doc/text")
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
            if KEY_BAD.search(str(r.get("when", ""))):
                errs.append(f"{tag}: reveal.when「{r.get('when')}」含空白或算子字符 —— 它会"
                            f"原样拼进 data-when=\"q{no}=<when>\",条件显隐将永不命中")
            if str(r.get("when")) not in own_keys:
                errs.append(f"{tag}: reveal.when「{r.get('when')}」不是本题任何选项的 key")

    for kind, items in (doc.get("links") or {}).items():
        for it in items or []:
            if not isinstance(it, dict):
                errs.append(f"links.{kind}: 条目必须是对象,实际「{it!r}」")
                continue
            if it.get("when") is not None:
                errs.extend(_check_when_expr(it["when"], f"links.{kind}"))
            errs.extend(_check_link(kind, it, layer_of))
    errs.extend(_check_carry_refs(doc))

    return errs


def code_rev(root="."):
    """`root` 那个仓库的 HEAD —— 必须是 root,不是 cwd:cites 的路径行号是相对 root 解析的,
    拿 cwd 的 sha 会让抬头声称一个和被引用代码毫无关系的出处,且没有任何提示。
    单子发出到收回代码可能变过,没有 rev 就说不出『当时代码是这样的』。
    非仓库(chat/agent 环境)返回空串。"""
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def render_html(doc, template, root="."):
    """把题目数据注入模板的 qdata 块。模板不含任何项目内容,数据只此一处。
    `root` 与 CLI 的 --root 同义:cites/rules_ref 的路径相对它解析,code_rev 也取它的 HEAD。"""
    if PLACEHOLDER not in template:
        raise ValueError(f"模板缺占位符 {PLACEHOLDER}")
    doc = {**doc, "doc": {**doc["doc"],
                          "code_rev": doc["doc"].get("code_rev") or code_rev(root)}}
    # </script> 会提前闭合数据块;JSON 里的 < 一律转义,不影响 json.loads
    payload = json.dumps(doc, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, payload)


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
        # 逐条三态(对/不对/未表态),不设全局「无异议」—— 与 HTML 侧同一契约(D6)。
        # 全局「无异议」和逐条核对自相矛盾:一句话盖住所有条目,等于没核对。
        L += ["## 第一部分 · 我们理解的（请逐条核对）", "",
              "| # | 我们理解的 | 备注 | 对不对 |", "|---|---|---|---|"]
        L += [f"| {r['n']} | {r['we_understand']} | {r.get('note', '')}"
              f" | ☐ 对　☐ 不对　☐ 未表态 |" for r in doc["part1"]]
        # 提示语写在【作答区】之前,同 C1 的道理:写在标记后面的话,
        # check_questionnaire.py 的 substantive() 会把这句提示当成业务的异议说明,
        # 第一部分的兜底判据(既无「无异议」也无异议说明)就永远不触发。
        L += ["", "哪条不对、哪里不对，请写在下面：", "【作答区】", ""]

    L += ["## 第二部分 · 待确认问题（请作答）", ""]
    for q in sorted(doc["questions"], key=lambda x: (x["layer"], x["no"])):
        decide = "业务定" if q["decide"] == "biz" else "开发拟定·请过目"
        L.append(f"### 问题 {q['no']}：{q['title']}（{decide}）"
                 + ("（阻塞）" if q.get("blocking") else ""))
        if q.get("background"):
            L.append(f"背景：{q['background']}")
        # demo 与 cost 同理:HTML 渲染它、md 不渲染,就等于给打印/内网那一路的业务
        # 一张剥掉了对照表的决策单 —— 而阻塞级题的 demo 是硬要求(只画岔口不算数)。
        demo = q.get("demo") if isinstance(q.get("demo"), dict) else None
        if demo:
            note = ("；基于开发假设的算法，未从代码验证"
                    if demo.get("basis") == "assumed" else "")
            L.append(f"演示对照（演示数字，非任何选项的背书{note}）：")
            if demo.get("given"):
                L.append(f"　前提：{demo['given']}")
            for row in demo.get("rows") or []:
                opts = "／".join(str(w) for w in (row.get("when") or []))
                kv = "：".join(x for x in (row.get("k"), row.get("v")) if x)
                L.append(f"　- 选 {opts} → {kv}")
        # 只有主问给勾选框：一题一个勾选标记,否则 check_questionnaire.py 判为多选。
        main = next((g for g in q["groups"] if g.get("id") == "main"), None)
        for o in (main or {}).get("options", []):
            key = f"{o['key']}. " if re.fullmatch(r"[A-Z]\d*", str(o["key"])) else ""
            mark = "⊘ " if o.get("kind") == "nonexistent" else ""
            # cost 是「该选项的代价/影响」,与 advice_allowed(管建议措辞)是两件事。
            # 曾按 advice_allowed 过滤 cost,结果规则/账务口径题(恰恰是最需要看代价的
            # 一档)拿到的是一张剥掉了全部代价的决策单。建议措辞由 ADVICE_WORDS 拦。
            cost = f"（{o['cost']}）" if o.get("cost") else ""
            L.append(f"☐ {key}{mark}{o['label']}{cost}")
        L.append("☐ 都不是——我要选的不在这几个里（请在作答区写明实际口径）")
        for r in q.get("reveal", []):
            L.append(f"（若选 {r['when']}，请在作答区一并回答：{r['ask']}）")
        # 子问不发勾选框,改成提示行 —— 选项以「／」列出,信息不丢。
        # 提示行必须写在【作答区】之前:写在后面的话 check_questionnaire.py 的
        # substantive() 会把模板自带的提示文字当成实质作答,凡带子问组的题在 md
        # 路径上永远判为已作答 —— 阻塞级漏的是 FAIL,不是 WARN。
        # 注意这些行里不能出现「【作答区】」四字,否则又会被 split 成作答内容。
        subs = [g for g in q["groups"] if g.get("id") != "main"]
        if subs:
            L.append("（以下小问请一并写进下面的作答区：）")
        for g in subs:
            menu = "／".join(o["label"] for o in g.get("options", []))
            L.append(f"　· {g.get('ask', '该小问')}（{menu}／都不是，请写明）：")
        L.append("【作答区】")
        L.append("")

    L += ["## 填写信息",
          "填写人：____　部门：____　日期：____",
          "（留名字是为了日后能找回是谁定的；不填也能交，但只能按【开发拟定·待追认】入账）",
          "代答／转交说明：____", ""]
    return "\n".join(L)


def infer_root(json_path):
    """从 json 的位置往上找项目根 —— 含 docs/requirements/ 的那一层。

    rules_ref.doc 是相对项目根写的(如 docs/requirements/rules/payout.md),
    而 json 自己就躺在 docs/requirements/questionnaires/ 下,所以项目根一定在
    它的祖先里。不推断的话每个调用点都得记得传 --root,忘一次就报「规则文档
    不存在」—— 本任务里已经踩了两次。
    """
    p = Path(json_path).resolve()
    for d in p.parents:
        if (d / "docs" / "requirements").is_dir():
            return d
    return Path(".")


def _norm(s):
    return re.sub(r"\s+", "", str(s))


def _check_rules_threshold(ev, tag, logic_counts):
    """超过阈值的逻辑必须沉淀进 rules/,不许 inline 在题目里(D19)。"""
    code_cites = [c for c in _cites(ev) if c.get("kind") == "code"]
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
    if not isinstance(rv, dict):
        return [f"{tag}: reviewed 必须是对象(含 by/on/diffs,diffs>0 再加 note),"
                f"实际「{rv!r}」"]
    errs = [f"{tag}: reviewed 缺 `{f}`" for f in ("by", "on", "diffs")
            if rv.get(f) in (None, "")]
    if errs:
        return errs
    try:
        diffs = int(rv.get("diffs") or 0)
    except (TypeError, ValueError):
        # 「两处」这种人话会让 int() 抛 ValueError —— validate() 承诺不抛异常
        return [f"{tag}: reviewed.diffs 必须是整数(盲审发现的差异条数),"
                f"实际「{rv.get('diffs')!r}」;差异内容写进 note,不要写进 diffs"]
    if diffs > 0 and not str(rv.get("note") or "").strip():
        errs.append(f"{tag}: reviewed.diffs>0 必须写 `note` —— 盲审发现的差异怎么处理的要留痕")
    return errs


def validate_refs(doc, root):
    """摸文件系统的校验:规则文档存在、条目编号找得到、text 没和文档漂移。"""
    errs, root = [], Path(root)
    for q in doc.get("questions", []):
        ev = q.get("evidence")
        rr = ev.get("rules_ref") if isinstance(ev, dict) else None
        # 结构坏掉时不在这里报 —— validate() 已经报过,这里只负责不抛
        for r in (rr if isinstance(rr, list) else []):
            if not isinstance(r, dict):
                continue
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
    errs, code_cites = [], [c for c in _cites(ev) if c.get("kind") == "code"]
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
        # 阻塞级岔口必须配跨分支演示。SKILL.md 与 questioning-rules.md 都把它写成硬
        # 要求,但以前只在 demo 存在时校验 basis,从不检查阻塞题有没有 demo ——
        # 于是硬要求没有闸门,样例自己也两道阻塞题都没配。
        if q.get("blocking"):
            return [f"{tag}: 阻塞级的题必须配 `demo` —— 同一组输入,每个候选选项各算"
                    f"一遍摆对照表。只算一个选项 = 暗中替业务拍板;只画岔口不算数 = "
                    f"让人凭抽象拍板。数字是开发自己假设的算法就写 basis:assumed"
                    f"(页面会标注未从代码验证)"]
        return []
    if not isinstance(demo, dict):
        return [f"{tag}: demo 必须是对象(含 given/basis/rows),实际「{demo!r}」"]
    basis = demo.get("basis")
    if basis not in ("branches", "assumed"):
        return [f"{tag}: demo.basis 必须是 branches 或 assumed,实际「{basis}」"
                f" —— 演示数字得说清算法从哪来"]
    if basis == "branches":
        has = any(c.get("branches") for c in _cites(ev) if c.get("kind") == "code")
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
    ap.add_argument("-o", "--out", metavar="输出.html",
                    help="HTML 输出路径。省略且没给 --md 时用默认名 confirm-<id>-r<轮次>.html")
    ap.add_argument("--md", metavar="输出.md",
                    help="额外出一份 Markdown(打印/内网/微信场合)。只给 --md 就只出 md")
    ap.add_argument("--check", action="store_true", help="只校验不出包")
    ap.add_argument("--root", default=None,
                    help="项目根,用于解析 rules_ref 的路径。默认从 json 位置往上找"
                         "含 docs/requirements/ 的那一层;只有 json 不在项目内的"
                         "特殊场合才需要显式传")
    args = ap.parse_args()

    doc = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    root = args.root or infer_root(args.json_path)
    errs = validate(doc) + validate_refs(doc, root)
    for e in errs:
        print(f"  ✗ {e}")
    if errs:
        print(f"\n✗ 校验未通过: {len(errs)} 项。修正后重跑;不出包。")
        sys.exit(1)
    n_biz = sum(1 for q in doc["questions"] if q.get("decide") == "biz")
    n_dev = sum(1 for q in doc["questions"] if q.get("decide") == "dev")
    print(f"✓ 校验通过: {len(doc['questions'])} 道题(业务定 {n_biz} / 开发拟定 {n_dev})")
    if args.check:
        return
    # 只给 --md 就只出 md —— 以前无条件往 CWD 扔一个 67KB 的默认名 HTML,
    # 想要一份打印稿的人会莫名多出一个文件。
    if args.out or not args.md:
        out = Path(args.out or f"confirm-{doc['doc']['id']}-r{doc['doc']['round']}.html")
        out.write_text(render_html(doc, TEMPLATE_PATH.read_text(encoding="utf-8"), root),
                       encoding="utf-8")
        print(f"✓ 已出包 {out}（{out.stat().st_size // 1024} KB，单文件自包含）")
    if args.md:
        Path(args.md).write_text(render_md(doc), encoding="utf-8")
        print(f"✓ 已出 Markdown {args.md}")


if __name__ == "__main__":
    main()

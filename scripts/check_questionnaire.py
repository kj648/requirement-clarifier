#!/usr/bin/env python3
"""check_questionnaire.py — requirement-clarifier 确认单回执机检

用法:
  python3 scripts/check_questionnaire.py <回填后的确认单.md...>

定位: 阶段三"验收答案"的机械约束部分。业务回执先过本脚本,机器报完"哪些题没答、
缺什么落款",AI 再做判断题部分(成色分级、冲突检测、新需求剥离)。

──────────────────────────────────────────────────────────────────────
入口分两层(为什么: 九条规则原来全按中文字面 grep —— `### 问题 N：`、`【作答区】`、
`☒ 本题不成立`…… 一旦回执是英文的,或者 AI 应用户要求把回执翻译了,九条规则不会
报错,只是全部不触发,静默全灭。而 HTML 导出的回执末尾本来就带一个机读 JSON 区,
机检该优先吃它):

  A. 结构化路径 —— 回执带机读 JSON 区(HTML 导出的都带)→ 按 JSON 判,语言无关。
  B. 人读锚点路径 —— 没有机读区(手写单/旧回执)→ 走原来的中文锚点,一字不动。
  C. 机读区存在但解析失败(被手改坏)→ 降级走 B + 一条 WARN「机读区损坏」。
     为什么不直接 FAIL: 手改坏机读区的人多半只是在编辑器里动了正文,人读部分
     还是好的;拦下来不如降级并说清「这次是按人读文本判的」。
  B′. md 表单路径 —— `--md` 出的静态单子是**手填**的:答案落在人读文本里,机读区
     里没有也不可能有,所以它不是回执,不能按 A 判(那会把手填的答案整份吃掉、
     报「全部未答」)。它带的是一张**锚点表**(build_questionnaire.md_machine_block):
     声明这份单子的结构词是哪几个。机检据此把结构词还原成中文规范词,再原样跑 B。
     中文单子的锚点表是恒等映射 → 文本一个字符都不动,判据与结论逐字节不变;
     英文单子于是也能走 B,而 checker 里不必再养一份英文词表(那就又是两份真源)。
     另拿机读区里的题号表与文本认出的题数交叉验证:对不上就说明结构词没对上,
     报一条 WARN,而不是让机检悄悄少看几道题。

机读区结构(templates/questionnaire.html 的 buildReceipt() 是唯一真源):
  {单据,轮次,代码依据,导出时间,
   第一部分:[{条,核对,说明}],
   题目:[{题号,阻塞,主选,子项,跳过,不成立,不适用?,补充,依据,规则引用?,独立复核?}],
   矛盾:[{条件,说明}], 落款:{填写人,部门,导出时间,转交,已署名}}
键名是契约,永远是中文 —— 它由模板代码写出,不随回执正文的语言变。真正会变成英文的
是「值」(题目标题、选项 label),所以判据只许落在键和结构上,不许落在值的字面上。

──────────────────────────────────────────────────────────────────────
机判九件事,两条路径的映射:

1. 逐题作答。
   B: "### 问题 N" 块内有勾选(☑/☒/✔/✓/[x])或【作答区】有实质内容才算已答。
   A: 主选／不成立／补充／跳过／子项／不适用 任一非空即已答。
      为什么是这一串而不只是「主选」: 导出器把子项、跳过说明、不适用推导、补充
      统统写进同一行【作答区】,B 路径把它们当实质内容 → 判已答。A 路径必须跟 B
      对同一份回执给同一个结论,否则同一份中文回执在改版前后判得不一样。
      已知代价(两条路径同担): 主选没选、只填了某个小问,也会算已答 —— 页面进度条
      比这严(它只认主选)。这是老行为,本次不改,以免中文回执的结论悄悄变。
   共同: 未答 → WARN;阻塞级未答 → FAIL(A 靠 `阻塞` 字段,B 靠块内出现「阻塞」二字)。
2. 多选提示: 同题勾选 >1 项 → WARN。
   A: 不判 —— 主选组渲染成 radio(见模板 optHtml),结构上不可能多选,机读区里
      `主选` 也只有一个标量位置。这条规则在结构化路径下没有可判对象。
3. "我不清楚"台阶: 勾了"不清楚/不知道"但没给知情人 → WARN(索要真正知情人)。
   A: 优先看 `主选kind` —— 导出器把选中项 questionnaire.json 里的 `kind`
      (dontknow/nonexistent/other)原样写进机读区,这是结构判据,与 label 的语言
      无关。没有 `主选kind` 的旧回执才落回中英关键词兜底(认不出时漏报不误报)。
4. 第一部分核对: 「未表态」的条数 >0 → WARN(点出条数)。
   A: `第一部分[].核对` 是机器枚举 ok|no|mute —— 数 mute 的条数。人读表格里写的
      是 locale 词(对/不对/未表态、Yes/No/Undecided),机读区不写它们。旧回执写的
      是中文词,仍然认(空 / 命中「未表态·undecided」一类词 → 算未表态)。
   B: 三态表数行;没有三态表的手写单退回兜底判据 —— 无"无异议"且【作答区】空 → WARN。
   判据必须是数条数,不能是「这一段有没有字」—— 导出器无论核对与否都会写满该列。
5. 落款检查: 日期空缺 → FAIL(落款是溯源凭证);部门空缺 → WARN。
   A: `落款.导出时间` 空 → FAIL;`落款.部门` 空 → WARN;整个 `落款` 缺 → FAIL。
   空缺含导出器写的「（未填）」占位 —— 否则该告警是死规则。
6. 模板残留: "出题规则(给生成方"未删除 → WARN(内部注释不应发给业务)。
   两条路径共用,对全文照跑 —— 这是中文模板自己的残留物,与回执语言无关。
7. 业务证伪: 单独计数并逐条列出 —— 该题需删除或重出,不得直接合并。
   A: `不成立` 非空即计数,同时算已答(不重复计入未答)。B: `☒ 本题不成立` 行。
8. 未署名: 填写人为空或含「未署名」→ WARN + 声明须按【开发拟定·待追认】入账
   (落款可留空是刻意的:业务常需先交一半再转交;纪律靠标签降级而非拦截)。
   A: 另认 `落款.已署名 === false` —— 它是导出器写死的布尔,比字面更可靠。
9. 矛盾段: 存在矛盾 → WARN;其中未附业务说明的 → FAIL(必须回问,不得自行选一边)。
   A: 数 `矛盾[]` 长度;`说明` 去掉括号占位后为空即「未说明」。用结构而非字面 ——
      英文导出会写 "(not explained)",占位词中英各认一组。

两条路径共用同一套输出与摘要格式(check_file 的 6 元组签名不变),存在 FAIL → 退出码 1。
"""
import json, re, sys
from pathlib import Path

CHECKED = re.compile(r'[☑☒✔✓]|\[[xX]\]')
UNCHECKED = "☐"
QHEAD = re.compile(r'^###\s*问题\s*(?P<no>\S+?)[:：]\s*(?P<title>.*)$')
ANSWER_MARK = "【作答区】"
DONT_KNOW = re.compile(r'不清楚|不知道|不了解')
DENIED = re.compile(r'^☒\s*本题不成立[^：:]*[：:]\s*(?P<why>.*)$', re.M)
UNSIGNED = re.compile(r'未署名')
CLASH_HEAD = re.compile(r'^##\s*⚠?\s*填写时暴露的矛盾.*?$(?P<body>.*?)(?=^##\s|\Z)', re.M | re.S)
# 逐条矛盾的稳定锚点是导出器必写的「业务说明：」标签行,不是给业务读的人话正文
# (人话措辞会变;条件表达式只在机读区保留)
CLASH_ITEM = re.compile(r'^\s*业务说明[：:]', re.M)
NO_EXPLAIN = re.compile(r'业务说明[：:]\s*（未说明）')
# 第一部分「未表态」有两种落法,都要认:
# ① HTML 导出器的一态一格表:`| 1 | 未表态 |  |`
# ② md 模板的同格三态:`| 1 | … | ☑ 未表态 |`(勾中才算;未勾选的 ☐ 未表态 是「完全没动」,
#   由下面「既无无异议也无说明」的兜底判据管,不在这里计数——否则空白单每行都自带
#   未勾选的 ☐ 未表态,会让每份没动过的单子都误报)。
# 判据必须是数条数,不能是「这一段有没有字」—— 导出器无论核对与否都会把该列写满。
P1_MUTE_ROW = re.compile(r'^\|[^|\n]*\|\s*未表态\s*\||[☑✔✓]\s*未表态', re.M)

# ── 结构化路径:值一侧不得不做的关键词兜底(见 docstring 规则 3／4／9) ────────
JSON_FENCE = re.compile(r'^```[ \t]*json[ \t]*\r?\n(?P<body>.*?)^```[ \t]*$', re.M | re.S)
J_MUTE = re.compile(r'未表态|undecided|not\s+stated|no\s+position', re.I)
J_DONT_KNOW = re.compile(r"不清楚|不知道|不了解|don'?t\s+know|do\s+not\s+know"
                         r"|not\s+sure|no\s+idea|unclear", re.I)
J_PLACEHOLDER = re.compile(r'未说明|未填|未写|待补|not\s+explained|no\s+explanation'
                           r'|not\s+specified|n/?a|tbd|unknown', re.I)


def substantive(text: str) -> bool:
    """作答区内容去掉模板占位(<...>、下划线)后是否还有实质内容。"""
    t = re.sub(r'<[^>]*>|＿+|_{2,}', '', text)
    return bool(t.strip())

FIELD_KEYS = "填写人|部门|日期|代答|转交"

def field_value(section: str, key: str) -> str:
    """取落款字段值。

    值捕获必须在下一个字段名处截断 —— 早先的 `[^\\s:：]*` 会让空字段捕获到
    下一个字段的标签名(如 填写人 捕获到 '部门'),于是空落款被当成已署名,
    未署名告警静默失效。
    另用 re.M 让 `$` 落在行尾:一行一组字段,而 HTML 导出的落款后面还跟着
    机读 JSON 块,不锚行尾的话最后一个字段(日期)会一路匹配不到而误报缺失。
    """
    m = re.search(
        rf'{key}\s*[:：][ \t]*(.*?)(?=[　\s]*(?:{FIELD_KEYS})\s*[:：]|$)',
        section, re.M)
    if not m: return ""
    v = re.sub(r'＿+|_{2,}', '', m.group(1)).strip()
    # 导出器对空字段写「（未填）」占位 —— 当成空,否则部门告警是死规则。
    # 注意「（未署名·导出自 HTML 确认单）」不归为空:它要被 UNSIGNED 匹配到,
    # 两条路径(手写空落款 / HTML 导出无署名)最终触发同一条 WARN。
    return "" if v in ("（未填）", "(未填)") else v


# ══ 机读区 ══════════════════════════════════════════════════════════
def machine_block(text: str):
    """从回执里取机读区。返回 (J, broken)。

    - J 是解析出来的 dict,None 表示没有可用的机读区;
    - broken=True 表示「有 json 围栏但解析不出来」→ 调用方降级走锚点路径并告警。

    检测本身必须语言无关: 认的是 ```json 围栏 + 中文键(键由模板代码写出,不随
    回执语言变),不认那句「机读区（供 …解析）」注释 —— 注释是人话,会被翻译掉。
    从后往前找:导出器把机读区写在文件末尾,而正文里可能另有无关的 json 代码块。
    解析得出但不像回执(没有 题目／落款 键)的块视为「别人的 json」,静默跳过,
    不报「损坏」—— 手写单里贴段配置不该触发本脚本的告警。
    """
    broken = False
    for m in reversed(list(JSON_FENCE.finditer(text))):
        try:
            obj = json.loads(m.group("body"))
        except (ValueError, TypeError):
            broken = True
            continue
        if isinstance(obj, dict) and ("题目" in obj or "落款" in obj):
            return obj, False
    return None, broken


def _blank(v) -> bool:
    """JSON 字段是否算空 —— null／空串／纯括号占位都算。

    判据是结构(剥掉括号后还剩不剩东西)+ 中英各一组占位词,不是某句中文字面:
    导出器写「（未说明）」「（未填）」,英文回执常写 "(not explained)"。
    """
    if v is None: return True
    if isinstance(v, (list, dict)): return not v
    s = re.sub(r'^[（(\[【]+\s*|\s*[)）\]】]+$', '', str(v).strip()).strip()
    return not s or bool(J_PLACEHOLDER.fullmatch(s))


def _filled(rec: dict, key: str) -> bool:
    return not _blank(rec.get(key))


# 第一部分核对的机器枚举 —— 导出器写它,不写 locale 词(见 docstring 规则 4)。
P1_ENUM = {"ok": False, "no": False, "mute": True}


def _p1_is_mute(rec: dict) -> bool:
    """这一条算不算「未表态」。

    先认机器枚举(语言无关),再落回旧回执的中文/英文词。判据必须是数条数,不能是
    「这一段有没有字」—— 导出器无论核对与否都会把该列写满。
    """
    v = rec.get("核对")
    if isinstance(v, str) and v in P1_ENUM:
        return P1_ENUM[v]
    return _blank(v) or bool(J_MUTE.search(str(v)))


def _is_dont_know(rec: dict, main: str) -> bool:
    """主选是不是「我不清楚」那一档。

    `主选kind` 是导出器从 questionnaire.json 的选项 kind 原样带出来的结构标记,
    有它就不必猜 label 的字面 —— 英文单子写 "I don't know" 还是 "No idea" 都一样。
    判据是**键在不在**,不是值真不真:键在就说明这份回执是新导出器出的、它一路
    跟着选项的语义档,值为 null 就是「这个选项没有语义档」——此时不该再拿关键词
    去猜,否则一道正常选项只因 label 里带了「不清楚」三个字就被误报。
    只有键整个不在(旧回执)才落回中英关键词:认不出时漏报,不误报。
    """
    if "主选kind" in rec:
        return rec.get("主选kind") == "dontknow"
    return bool(J_DONT_KNOW.search(main))


def _extra(rec: dict) -> bool:
    """主选以外还有没有实质内容 —— 子项／跳过／不适用／补充。

    对应 B 路径里【作答区】那一行的其余部分:导出器把这四类东西拼进同一行,
    所以两条路径必须一起认,否则同一份中文回执改版前后判得不一样。
    """
    return any(_filled(rec, k) for k in ("子项", "跳过", "不适用", "补充"))


def _titles(text: str) -> dict:
    """题号→标题,只为把告警里的题号变得好认;判定一律来自机读区。

    英文回执认不出这个中文锚点 → 退化成只报题号,不影响任何结论。
    """
    out = {}
    for line in text.splitlines():
        m = QHEAD.match(line.strip())
        if m: out[str(m["no"])] = m["title"]
    return out


def check_json(J: dict, text: str, warns: list, fails: list):
    """结构化路径:九条规则的 JSON 映射(逐条理由见模块 docstring)。"""
    titles = _titles(text)
    def unanswered_msg(no, blocking):
        t = titles.get(str(no), "")
        head = f"问题 {no}『{t[:30]}』未作答" if t else f"问题 {no} 未作答"
        return head + ("(阻塞级)" if blocking else "")

    # 4. 第一部分核对
    p1 = J.get("第一部分") or []
    if isinstance(p1, list) and p1:
        n_mute = sum(1 for r in p1 if isinstance(r, dict) and _p1_is_mute(r))
        if n_mute:
            warns.append(f"第一部分有 {n_mute} 条『未表态』—— 这些条目不得视为业务已认可,"
                         f"须逐条核对完再入账(导出器无论核对与否都会写满该列,"
                         f"只看『有没有字』永远查不出没核对)")

    # 1、3、7. 逐题
    qs = J.get("题目") or []
    if not isinstance(qs, list): qs = []
    unanswered, denied = [], []
    for rec in qs:
        if not isinstance(rec, dict): continue
        no = rec.get("题号", "?")
        blocking = bool(rec.get("阻塞"))
        answered = (_filled(rec, "主选") or _filled(rec, "不成立") or _extra(rec))
        if not answered:
            unanswered.append((no, blocking))
            (fails if blocking else warns).append(unanswered_msg(no, blocking))
        main = "" if _blank(rec.get("主选")) else str(rec["主选"])
        if main and _is_dont_know(rec, main) and not _extra(rec):
            warns.append(f"问题 {no} 勾了『不清楚』但作答区未提供知情人,请索要真正知情人")
        if _filled(rec, "不成立"):
            why = str(rec["不成立"]).strip()
            denied.append((no, why))
            warns.append(f"问题 {no} 被业务判为不成立：{why[:40]}"
                         f" —— 该题需删除或重出,不得直接合并")
    if not qs:
        warns.append("机读区里没有任何题目 —— 回执结构与模板不符,机检未覆盖,请人工核对")

    # 5、8. 落款
    sign = J.get("落款")
    if isinstance(sign, dict):
        name = sign.get("填写人")
        if (sign.get("已署名") is False or _blank(name)
                or UNSIGNED.search(str(name or ""))):
            warns.append("回执未署名 —— 不得记为【业务确认】,须按【开发拟定·待追认】入账,"
                         "补落款后才能转正")
        if _blank(sign.get("导出时间")):
            fails.append("落款缺『日期』(导出时自动填入,缺失说明回执被手改过)")
        if _blank(sign.get("部门")):
            warns.append("落款缺『部门』")
    else:
        fails.append("缺少『## 填写信息』落款区 —— 无落款的回答不得标【业务确认】")

    # 9. 矛盾
    clashes = J.get("矛盾") or []
    if not isinstance(clashes, list): clashes = []
    n_clash = len(clashes)
    if n_clash:
        warns.append(f"回执含 {n_clash} 处填写时暴露的矛盾,须优先处理")
        n_mute_clash = sum(1 for c in clashes
                           if not isinstance(c, dict) or _blank(c.get("说明")))
        if n_mute_clash:
            fails.append(f"{n_mute_clash} 处矛盾业务未给说明 —— 必须回问,不得自行选一边")

    return len(qs), len(unanswered), len(denied), n_clash


# ══ md 表单:锚点归一(见 docstring 路径 B′)══════════════════════════════
# 「机检认的中文规范词」→ 它在中文单子里长什么样。英文单子的对应词由单子自己的
# 机读区声明,不在这里写死 —— 在 checker 里养一份英文词表就又是两份真源了。
CANON = {"问题": "问题", "作答区": ANSWER_MARK, "第一部分": "第一部分",
         "第二部分": "第二部分", "填写信息": "填写信息", "阻塞": "阻塞",
         "未表态": "未表态", "填写人": "填写人", "部门": "部门", "日期": "日期"}


def md_form(text: str):
    """取 md 静态表单的机读区。回执的机读区有 题目/落款,表单的顶层键是 `表单`
    —— 两者必须分得开:表单里没有答案(答案在人读文本里),按回执判会报「全部未答」。"""
    for m in reversed(list(JSON_FENCE.finditer(text))):
        try:
            obj = json.loads(m.group("body"))
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and obj.get("表单") == "md":
            return obj
    return None


def canonicalize(text: str, anchors: dict) -> str:
    """把 md 表单的结构词还原成机检认的中文规范词,再交给原样的锚点路径。

    恒等映射(中文单子)直接原样返回 —— 保证中文这一路一个字符都不被动过。
    替换按行定界(标题行只动标题词、表格行只动三态词、落款行只动字段名),不做
    全文无差别替换:题目内容是自由文本,英文里 "Question"/"blocking" 也可能出现在
    正文中,盲替会改坏业务写的话。误伤的方向也是保守的 —— 多认出一个「阻塞」只会
    让漏答从 WARN 升成 FAIL,不会放人过去。

    `anchors` 不是 dict(被手改成字符串/列表,或 AI 重出时写错类型)一律当没有锚点表
    处理 —— md 这一路的定位就是「手填、可能被改坏」,机读区 JSON 整个坏掉都只是降级
    加一条 WARN,没有道理唯独锚点表的类型错误让 CLI 整个 traceback 崩掉。告警由调用方
    出(见 check_file),这里只负责不抛。
    """
    if not isinstance(anchors, dict):
        anchors = {}
    a = {k: str(anchors.get(k) or v) for k, v in CANON.items()}
    if a == CANON:
        return text
    out = []
    sign_head = re.compile(rf'^\s*{re.escape(a["填写人"])}\s*[:：]')
    for line in text.split("\n"):
        s = line
        if s.startswith("###"):
            # count=1:只还原行首那个标题词,题目标题里再出现同一个词不动它
            s = s.replace(a["问题"], CANON["问题"], 1).replace(a["阻塞"], CANON["阻塞"])
        elif s.startswith("##"):
            for k in ("第一部分", "第二部分", "填写信息"):
                s = s.replace(a[k], CANON[k])
        elif s.lstrip().startswith("|"):
            s = s.replace(a["未表态"], CANON["未表态"])
        if sign_head.match(s):
            for k in ("填写人", "部门", "日期"):
                s = re.sub(rf'{re.escape(a[k])}(\s*[:：])', CANON[k] + r'\1', s)
        out.append(s.replace(a["作答区"], CANON["作答区"]))
    return "\n".join(out)


# ══ 人读锚点路径(兼容层,判据一字不动)══════════════════════════════════
def check_anchors(text: str, warns: list, fails: list):
    """没有机读区的手写单/旧回执走这里。中文锚点判据保持原样,不得改动。"""
    # 切分区段
    def section(name):
        m = re.search(rf'^##\s*{name}.*?$(.*?)(?=^##\s|\Z)', text, re.M | re.S)
        return m.group(1) if m else None

    part1 = section("第一部分")
    part2 = section("第二部分")
    signoff = section("填写信息")

    # 4. 第一部分核对
    if part1 is not None:
        ans = " ".join((seg.strip().splitlines() or [""])[0]
                       for seg in part1.split(ANSWER_MARK)[1:])
        n_mute = len(P1_MUTE_ROW.findall(part1))
        if n_mute:
            warns.append(f"第一部分有 {n_mute} 条『未表态』—— 这些条目不得视为业务已认可,"
                         f"须逐条核对完再入账(导出器无论核对与否都会写满该列,"
                         f"只看『有没有字』永远查不出没核对)")
        elif "无异议" not in part1 and not substantive(ans):
            warns.append("第一部分(已确认事项)未核对: 既无『无异议』也无异议说明")

    # 1-3、7. 逐题检测
    unanswered, denied, n_q = [], [], 0
    if part2 is not None:
        blocks = re.split(r'(?=^###\s*问题)', part2, flags=re.M)
        for blk in blocks:
            m = QHEAD.match(blk.strip().splitlines()[0]) if blk.strip() else None
            if not m: continue
            n_q += 1
            no, title = m["no"], m["title"]
            checked_lines = [l for l in blk.splitlines() if CHECKED.search(l)]
            answer_text = "\n".join(seg for seg in blk.split(ANSWER_MARK)[1:])
            answered = bool(checked_lines) or substantive(answer_text)
            blocking = "阻塞" in blk
            if not answered:
                unanswered.append((no, title, blocking))
                (fails if blocking else warns).append(
                    f"问题 {no}『{title[:30]}』未作答" + ("(阻塞级)" if blocking else ""))
            if len(checked_lines) > 1:
                warns.append(f"问题 {no} 勾选了 {len(checked_lines)} 项,请确认该题是否允许多选")
            if any(DONT_KNOW.search(l) for l in checked_lines) and not substantive(answer_text):
                warns.append(f"问题 {no} 勾了『不清楚』但作答区未提供知情人,请索要真正知情人")
            m_deny = DENIED.search(blk)
            if m_deny:
                denied.append((no, m_deny.group("why").strip()))
                warns.append(f"问题 {no} 被业务判为不成立：{m_deny.group('why').strip()[:40]}"
                             f" —— 该题需删除或重出,不得直接合并")
    if n_q == 0:
        warns.append("未识别到任何『### 问题 N』块 —— 回执格式与模板不符,机检未覆盖,请人工核对")

    # 5、8. 落款
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

    # 9. 矛盾段
    m_clash = CLASH_HEAD.search(text)
    n_clash = n_mute = 0
    if m_clash:
        body = m_clash.group("body")
        n_clash = len(CLASH_ITEM.findall(body))
        n_mute = len(NO_EXPLAIN.findall(body))
        warns.append(f"回执含 {n_clash} 处填写时暴露的矛盾,须优先处理")
        if n_mute:
            fails.append(f"{n_mute} 处矛盾业务未给说明 —— 必须回问,不得自行选一边")

    return n_q, len(unanswered), len(denied), n_clash


def check_file(fp: str):
    text = Path(fp).read_text(encoding="utf-8", errors="replace")
    warns, fails = [], []
    print(f"\n== 机检 {fp} ==")

    J, broken = machine_block(text)
    if J is not None:
        print("  · 按机读区判(结构化,与回执语言无关)")

    # 6. 模板残留 —— 两条路径共用:这是中文模板自己的残留物,与回执语言无关
    if "出题规则(给生成方" in text or "出题规则（给生成方" in text:
        warns.append("模板内部注释『出题规则(给生成方…)』未删除,不应出现在发给业务的正式单里")

    if broken:
        warns.append("机读区损坏(```json 块解析失败)—— 已按人读文本机检,"
                     "结论可能不全;请重新从 HTML 确认单导出一份")

    if J is not None:
        n_q, n_un, n_den, n_clash = check_json(J, text, warns, fails)
    else:
        # md 表单是手填的,答案只在人读文本里 —— 机读区给的是锚点表,不是答案。
        form = md_form(text)
        if form is not None:
            print("  · 按 md 表单机读区的锚点表归一后判(答案在人读文本里)")
            anchors = form.get("锚点")
            if not isinstance(anchors, dict):
                warns.append("机读区的锚点表损坏(不是对象)—— 已按中文规范词判定,"
                             "若这是一份非中文的单子,结论会不全;"
                             "请重新出一份 md")
            text = canonicalize(text, anchors)
        n_q, n_un, n_den, n_clash = check_anchors(text, warns, fails)
        declared = form.get("题") if isinstance(form, dict) else None
        if isinstance(declared, list) and declared and n_q != len(declared):
            warns.append(f"机读区声明本单共 {len(declared)} 题,人读文本只认出 {n_q} 道"
                         f" —— 结构词与锚点表对不上(单子被改写过?),机检可能少看了题,"
                         f"请人工核对")

    for msg in fails: print(f"  ✗ {msg}")
    for msg in warns: print(f"  △ {msg}")
    if not fails and not warns: print("  ✓ 全部题目已作答,落款完整")
    return n_q, n_un, n_den, n_clash, warns, fails

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

if __name__ == "__main__":
    main()

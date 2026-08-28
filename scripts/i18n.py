#!/usr/bin/env python3
"""i18n.py — 确认单「页面外壳」的唯一字符串表

定位(issue #1 收敛后的结论):
- **内容语言零工作**。题目标题、选项 label、背景、weak 说明……都由 AI 按交互语言
  直接写进 questionnaire.json,不经过这张表。语言切换是模型的自带能力。
- **协议词汇不翻译**。机读区的 JSON 键名(题号／主选／矛盾……)、三档来源标签
  (【业务确认】/【开发拟定】/【假设】)是协议,像 HTTP 头,业务不读它们。
- 真正需要一张表的只有**页面外壳**(chrome):抬头、表头、按钮、提示、回执骨架词。

一份表两端同源:
  build_questionnaire.py  → render_md 的骨架词 + 注入 HTML 的 doc._i18n
  templates/questionnaire.html → 从 DATA.doc._i18n 取,不再在 JS 里写死任何文案
check_questionnaire.py **不读这张表** —— 回执带机读区时机检按结构判,与语言无关;
md 表单则自带一张锚点表(见 build_questionnaire.MD_ANCHORS)。

改这里的规矩:
1. 键只增不改。键名是模板与 render_md 的契约,改名会让页面上出现光秃秃的键名。
   删键只在**整个功能被拆除**时做(如落款仪式整体拆除),且必须两门语言
   同时删、连同它的所有引用一起删 —— 剩一处引用就是页面上一个光秃秃的键名。
2. 占位符统一写 `{name}`;Python 侧 `.format(**kw)`,JS 侧 `fmt()` 做同样的替换。
3. en 不是逐字直译 —— 语气与中文版对齐:用后果说话,不用术语。
"""

LANGS = ("zh", "en")

STRINGS = {
    "zh": {
        # ── 结构词(md 锚点表的原料,见 anchors())────────────────
        # 单独立键是为了让 md 机读区能声明「这份单子的结构词是哪几个」,
        # 而不是让机检去猜或再维护一份英文词表。它们同时被下面的长句复用,
        # 一致性由 tests 盯着 —— 两处漂移就等于机检认错锚点。
        "w_question": "问题",
        "w_blocking": "阻塞",
        "w_part1": "第一部分",
        "w_part2": "第二部分",
        "w_signoff": "填写信息",

        # ── 抬头 ────────────────────────────────────────────────
        "kicker": "需求确认单 · 第 {round} 轮",
        "sent_by": "发出人",
        "sent_on": "发出日期",
        "q_count": "本轮共 <b>{n} 道</b>待确认问题{first}。",
        "q_count_first": "，其中 <b>问题 {list}</b> 请先答",
        "rev_note": "代码依据取自 {rev} —— 这之后代码若有变动，结论需重新确认",
        "seal_total": "共 {n} 题",
        "page_title": "需求确认单 · {title}",
        "howto": "第一部分请<b>逐条核对</b>；第二部分请<b>点选</b>选项、必要处补充说明。"
                 "标「业务定」的题必须您自己拍板；标「开发拟定 · 请过目」的题开发已给默认规则，"
                 "<b>过目一下有无异议</b>即可——不确定该找谁定，先转给知情的人。"
                 "答不了的题可以留空先发，剩下的转交别人接着填。填完点底部<b>导出回执</b>发回即可。",

        # ── 第一部分 ────────────────────────────────────────────
        "p1_title": "第一部分 · 我们理解的",
        "p1_hint": "请逐条核对，不对的地方写在旁边",
        "p1_col_item": "我们理解的",
        "p1_col_note": "备注",
        "p1_col_check": "对不对",
        "p1_ok": "对",
        "p1_no": "不对",
        "p1_mute": "未表态",
        "p1_cell": "☐ {ok}　☐ {no}　☐ {mute}",
        "p1_why_ph": "哪里不对",
        "p1_extra": "上面之外，还想让我们知道的（选填）",

        # ── 第二部分 ────────────────────────────────────────────
        "p2_title": "第二部分 · 待确认问题",
        "p2_hint": "{n} 题",
        "layer_gate": "下面这些要等前面定了才有意义",
        "layer_why": "（{why}）",

        # ── 档位与标签 ──────────────────────────────────────────
        "tier_src": "原话",
        "tier_code": "代码",
        "tier_guess": "无据 · 请证伪",
        "decide_biz": "业务定",
        "decide_dev": "开发拟定 · 请过目",
        "decide_dev_md": "开发拟定·请过目",
        "tag_first": "请先答",
        "tag_done": "已答",
        "tag_denied": "不成立",

        # ── 依据区 ──────────────────────────────────────────────
        "ev_more": "这道题的依据",
        "ev_none": "这道题没有任何来源引用——纯粹是开发从盲区清单推的。",
        "evidence_word": "证据",
        "logic_lead": "我们查代码看到系统现在是这么做的：",
        "logic_note": "（这是开发读代码得出的理解，不是您说过的话——不对请直接指出）",
        "rules_lead": "系统现在的规则是：",
        "rules_note": "（引自规则文档 {id}，由开发读代码逆向、交规则 owner 验真——不对请直接指出）",
        "rules_doc_summary": "规则文档位置（开发看）",
        "coords_summary": "代码位置与分支（开发看）",
        "entry_label": "入口：",
        "branches_partial": "⚠ 分支未读完，本题依据已降为「无据」处理",
        "unreviewed": "未经独立复核——上面这段理解只有一个人读过代码",
        "reviewed": "已独立盲审（{on}，发现 {diffs} 处差异{handled}）",
        "reviewed_handled": "，已处置",
        "deny_label": "这题不成立：场景不存在，或问错了",
        "deny_ph": "为什么不成立——写清楚我们就删题，不用勉强在错的选项里挑一个",

        # ── 演示数字 ────────────────────────────────────────────
        "demo_lb": "演示数字",
        "demo_result": "结果",
        "demo_assumed": "演示数字基于开发假设的算法，未从代码验证——"
                        "如果实际不是这么算的，请在补充说明里写明",
        "md_demo_head": "演示对照（演示数字，非任何选项的背书{note}）：",
        "md_demo_assumed": "；基于开发假设的算法，未从代码验证",
        "md_demo_given": "　前提：{given}",
        "md_demo_row": "　- 选 {opts} → {kv}",

        # ── 条件块 / 兜底出口 / 联动 ────────────────────────────
        "cond_hd": "因您选了 {key}，还要定一件事",
        "other_label": "都不是（实际口径见作答区）",
        "other_opt": "⊕ 都不是——我要选的不在这几个里",
        "other_ask": "实际的口径是",
        "other_cond_hd": "那实际是怎样？照实写，别在上面几个里勉强挑一个",
        "other_ph": "实际的口径／做法",
        "na_note": "<b>本小问不适用</b>——{note}。回执里会写成这句推导，不算漏答。",
        "carry_hint": "沿用 {src} 填的「{v}」，不对可以直接改",
        "clash_lead": "这两个选择打架了。",
        "clash_ph": "写明怎么处理，或回去改一个选择",
        "when_pick": "问题 {no} 选「{label}」",
        "when_join": "，且 ",
        # 拼接用的标点。中英不同 —— 英文单子里冒出全角「；」是最扎眼的中文残留。
        "sep_kv": "：",
        "sep_or": "／",
        "sep_semi": "；",
        "sep_list": "、",
        "paren": "（{v}）",
        "answer_label": "补充说明（选填）",

        # ── 进度条 / 导出条 / 弹窗 / 索引 ───────────────────────
        "status_init": "尚未开始",
        "jump_next": "跳到下一道未答",
        "rail_title": "题号索引",
        "rail_open": "题号索引 ▶",
        "rail_close": "◀ 收起",
        "st_sep": "　·　",
        "st_done": "已答 <span class=\"num\">{done}</span> / <span class=\"num\">{total}</span>",
        "st_p1_mute": "<span class=\"amb\">核对未表态 {n} 条</span>",
        "st_p1": "核对 <span class=\"num\">{done}</span> / <span class=\"num\">{total}</span>",
        "st_denied": "<span class=\"warn\">{n} 题被判不成立</span>",
        "st_must": "<span class=\"warn\">问题 {list} 请先答</span>",
        "st_clash": "<span class=\"warn\">{n} 处选择互相打架，请看红框</span>",
        "dock_left": "还有 {n} 题没答，也可以先导出、剩下的转交别人",
        "export": "导出回执",
        "print": "打印／存 PDF",
        "dlg_title": "发回之前，请过一眼",
        "dlg_close": "关闭",
        "dlg_raw": "查看要发回给开发的原始文本（技术细节，不看也没关系）",
        "dlg_note": "「复制回执」复制的是给 AI 的机读回执——粘贴到您和开发的对话里发回即可；"
                    "要留一份完整存档再点「下载 .md 文件」。",
        "copy": "复制回执",
        "copied": "已复制 ✓",
        "copy_manual": "已选中，请按 ⌘C",
        "download": "下载 .md 文件",
        "filter_lead": "先看",
        "filter_all": "全部",
        "filter_biz": "必须业务定",
        "filter_dev": "只需过目",

        # ── 填写信息（只剩导出时间 + 给开发的补充）──────────────
        # 填写人／部门已整体拆除:找谁确认是开发者自己知道的事,回执本身就是结论。
        "sign_title": "填写信息",
        "sign_date": "导出时间（自动）",
        "sign_relay": "补充给开发的说明（选填）",
        "sign_relay_ph": "例：问题 1、3 已跟王芳电话对过；问题 2 我不清楚，已转给李姐",

        # ── 回执骨架 ────────────────────────────────────────────
        "rc_title": "# 需求确认单回执：{title}（第 {round} 轮）",
        "rc_meta": "> 导出于 {now}（页面自动记录）· 发出 {sent_on} · 发出人 {sent_by}",
        "rc_grade": "> 回执成色：已答 {done}/{total}",
        "rc_grade_denied": " · 判为不成立 {n} 题（问题 {list}）",
        "rc_grade_unans": " · 未答 {n} 题（问题 {list}）",
        "rc_grade_p1": " · 第一部分核对 {done}/{total}",
        "rc_grade_clash": " · ⚠ {n} 处矛盾",
        "rc_split": "> 分档：业务定 {biz} 题（已答 {biz_done}）"
                    " · 开发拟定 {dev} 题（已过目 {dev_done}）",
        "rc_clash_head": "## ⚠ 填写时暴露的矛盾（请开发优先处理）",
        "rc_clash_item": "- {when} —— 两者同时成立：{text}…",
        "rc_clash_note": "  业务说明：{v}",
        "rc_not_explained": "（未说明）",
        "rc_p1_head": "## 第一部分 · 已确认事项（请核对）",
        "rc_p1_cols": "| # | 核对 | 说明 |",
        "rc_p1_no_reason": "（未写原因）",
        "rc_p1_all_ok": "{n} 条全部核对为「对」，无异议",
        "rc_p1_each": "逐条核对：",
        "rc_p1_extra": "；其他补充：{v}",
        "rc_p2_head": "## 第二部分 · 待确认问题（请作答）",
        "rc_qhead": "### 问题 {no}：{title}（{decide}）{blocking}",
        "rc_blocking": "（阻塞）",
        "rc_denied_line": "☒ 本题不成立（业务证伪）：{why}",
        "rc_denied_inline": "本题不成立：{why}",
        "rc_no_reason": "（未写原因）",
        "rc_na": "不适用（{note}）",
        "rc_skip": "因问题 {no} 选 {v}，本题下属小问自动跳过（不算漏答）",
        "answer_mark": "【作答区】",
        # 作答区标记后面直接接内容时用它。中文靠【】自带分隔,英文得补一个空格,
        # 否则回执里是「[Answer]line by line: …」。锚点表认的是 answer_mark,
        # 而它是本键的前缀,所以归一照样命中。
        "answer_mark_inline": "【作答区】",
        "rc_sign_head": "## 填写信息",
        "rc_sign_line": "导出时间：{date}",
        "rc_relay": "补充给开发的说明：{v}",
        "rc_machine_note": "<!-- 机读区（供 check_questionnaire.py / AI 解析，业务无需理会） -->",
        "rc_file_word": "确认单回执",

        # ── 人读回执预览 ────────────────────────────────────────
        "pv_answered": "已答",
        "pv_checked": "核对",
        "pv_denied": "判为不成立",
        "pv_unanswered": "没答",
        "pv_clash": "矛盾",
        "pv_exported_at": "导出于 {now}",
        "pv_clash_head": "⚠ 有一处选择互相打架",
        "pv_clash_said": "您的说明是「{v}」，会一起发给开发。",
        "pv_clash_none": "您还没写怎么处理——建议回去补一句，否则开发只能再来问一轮。",
        "pv_denied_ans": "本题不成立：{why}",
        "pv_no_reason": "（没写原因）",
        "pv_other": "都不是，实际是：{v}",
        "pv_other_none": "（还没写实际口径）",
        "pv_unans": "还没答",
        "pv_unans_first": "（这题标了「请先答」，后面的题要等它定）",

        # ── md 专用骨架 ────────────────────────────────────────
        "md_title": "# 需求确认单：{title}（第 {round} 轮）",
        "md_meta": "> 第 {round} 轮 · {sent_on} · 发出人：{sent_by} · 共 {n} 题",
        "md_howto": "填写说明：第一部分请逐条核对；第二部分请在 ☐ 打勾、【作答区】作答。"
                    "标「业务定」的题必须您自己拍板；标「开发拟定」的是我们已经拟好的默认规则，"
                    "请过目，无异议即生效。填完发回即可。",
        "md_p1_head": "## 第一部分 · 我们理解的（请逐条核对）",
        "md_p1_cols": "| # | 我们理解的 | 备注 | 对不对 |",
        "md_p1_hint": "哪条不对、哪里不对，请写在下面：",
        "md_p2_head": "## 第二部分 · 待确认问题（请作答）",
        "md_bg": "背景：{v}",
        "md_other_opt": "☐ 都不是——我要选的不在这几个里（请在作答区写明实际口径）",
        "md_reveal": "（若选 {when}，请在作答区一并回答：{ask}）",
        "md_subs_hint": "（以下小问请一并写进下面的作答区：）",
        "md_sub_line": "　· {ask}（{menu}／都不是，请写明）：",
        "md_sub_fallback": "该小问",
        "md_sign_head": "## 填写信息",
        "md_sign_line": "日期：____",
        "md_relay": "补充给开发的说明：____",
    },

    "en": {
        # ── structural words (raw material for the md anchor table) ──
        "w_question": "Question",
        "w_blocking": "blocking",
        "w_part1": "Part 1",
        "w_part2": "Part 2",
        "w_signoff": "Sign-off",

        # ── masthead ───────────────────────────────────────────
        "kicker": "Confirmation sheet · round {round}",
        "sent_by": "Sent by",
        "sent_on": "Sent on",
        "q_count": "<b>{n}</b> question(s) to confirm this round{first}.",
        "q_count_first": ", and <b>question {list}</b> should be answered first",
        "rev_note": "Code evidence read at {rev} — if the code changed after that, "
                    "these answers need confirming again",
        "seal_total": "{n} questions",
        "page_title": "Confirmation sheet · {title}",
        "howto": "In part 1, please <b>check every line</b>. In part 2, <b>pick an option</b> "
                 "and add a note where it matters. Questions marked “You decide” are yours to "
                 "settle; the ones marked “Dev proposal · please review” already have a default "
                 "rule — <b>just look it over</b>. If you are not the right person to decide, "
                 "pass the sheet to whoever knows. You can leave questions blank and send what "
                 "you have. When you are done, hit <b>Export receipt</b> at the bottom.",

        # ── part 1 ─────────────────────────────────────────────
        "p1_title": "Part 1 · What we understand",
        "p1_hint": "Check each line; write down anything that is wrong",
        "p1_col_item": "What we understand",
        "p1_col_note": "Note",
        "p1_col_check": "Correct?",
        "p1_ok": "Yes",
        "p1_no": "No",
        "p1_mute": "Undecided",
        "p1_cell": "☐ {ok}   ☐ {no}   ☐ {mute}",
        "p1_why_ph": "What is wrong",
        "p1_extra": "Anything else we should know (optional)",

        # ── part 2 ─────────────────────────────────────────────
        "p2_title": "Part 2 · Open questions",
        "p2_hint": "{n} questions",
        "layer_gate": "These only make sense once the questions above are settled",
        "layer_why": " ({why})",

        # ── tiers and tags ─────────────────────────────────────
        "tier_src": "Your words",
        "tier_code": "Code",
        "tier_guess": "No evidence · please disprove",
        "decide_biz": "You decide",
        "decide_dev": "Dev proposal · please review",
        "decide_dev_md": "Dev proposal · please review",
        "tag_first": "Answer first",
        "tag_done": "Answered",
        "tag_denied": "Does not apply",

        # ── evidence ───────────────────────────────────────────
        "ev_more": "What this question rests on",
        "ev_none": "This question has no source at all — we derived it from our blind-spot "
                   "checklist, nothing more.",
        "evidence_word": "evidence",
        "logic_lead": "Reading the code, here is what the system does today:",
        "logic_note": "(this is a developer's reading of the code, not something you said — "
                      "say so if it is wrong)",
        "rules_lead": "The rule the system follows today:",
        "rules_note": "(quoted from rule doc {id}, reverse-engineered from code by a developer "
                      "and verified with the rule owner — say so if it is wrong)",
        "rules_doc_summary": "Rule doc location (for developers)",
        "coords_summary": "Code location and branches (for developers)",
        "entry_label": "Entry point: ",
        "branches_partial": "⚠ Branches not read to the end — this question is treated as "
                            "having no evidence",
        "unreviewed": "Not independently reviewed — only one person has read this code",
        "reviewed": "Independently reviewed ({on}, {diffs} difference(s) found{handled})",
        "reviewed_handled": ", all handled",
        "deny_label": "This question does not hold: the situation never happens, or we asked "
                      "the wrong thing",
        "deny_ph": "Why it does not hold — tell us and we drop the question, so you never have "
                   "to pick the least-wrong option",

        # ── worked example ─────────────────────────────────────
        "demo_lb": "Worked example",
        "demo_result": "Result",
        "demo_assumed": "These numbers come from an algorithm the developers assumed; they were "
                        "not verified against the code — if that is not how it actually works, "
                        "please say so in the notes",
        "md_demo_head": "Worked example (illustrative numbers, not an endorsement of any "
                        "option{note}):",
        "md_demo_assumed": "; based on an algorithm the developers assumed, not verified "
                           "against the code",
        "md_demo_given": "  Given: {given}",
        "md_demo_row": "  - choose {opts} → {kv}",

        # ── conditionals / fallback exit / cross-question ──────
        "cond_hd": "Because you chose {key}, one more thing to settle",
        "other_label": "None of these (see the answer box)",
        "other_opt": "⊕ None of these — what I need is not on the list",
        "other_ask": "What it actually is",
        "other_cond_hd": "So how does it actually work? Write it as it is, rather than forcing "
                         "a fit with one of the options above",
        "other_ph": "The actual rule / practice",
        "na_note": "<b>This sub-question does not apply</b> — {note}. The receipt will record "
                   "that reasoning; it does not count as unanswered.",
        "carry_hint": "Carried over from {src}: “{v}” — change it if that is not right",
        "clash_lead": "These two choices contradict each other. ",
        "clash_ph": "Tell us how to handle it, or go back and change one of the choices",
        "when_pick": "question {no} = “{label}”",
        "when_join": " and ",
        "sep_kv": ": ",
        "sep_or": " / ",
        "sep_semi": "; ",
        "sep_list": ", ",
        "paren": " ({v})",
        "answer_label": "Anything to add (optional)",

        # ── status bar / dock / dialog / index ─────────────────
        "status_init": "Not started",
        "jump_next": "Jump to next unanswered",
        "rail_title": "Question index",
        "rail_open": "Questions ▶",
        "rail_close": "◀ Hide",
        "st_sep": " · ",
        "st_done": "Answered <span class=\"num\">{done}</span> / <span class=\"num\">{total}</span>",
        "st_p1_mute": "<span class=\"amb\">{n} line(s) not yet checked</span>",
        "st_p1": "Checked <span class=\"num\">{done}</span> / <span class=\"num\">{total}</span>",
        "st_denied": "<span class=\"warn\">{n} question(s) marked as not applicable</span>",
        "st_must": "<span class=\"warn\">Question {list} first, please</span>",
        "st_clash": "<span class=\"warn\">{n} contradiction(s) — see the red boxes</span>",
        "dock_left": "{n} question(s) still unanswered — you can export now and pass the rest on",
        "export": "Export receipt",
        "print": "Print / save PDF",
        "dlg_title": "Before you send it back, take a look",
        "dlg_close": "Close",
        "dlg_raw": "See the raw text that goes back to the developers (technical; you can skip it)",
        "dlg_note": "“Copy receipt” copies the machine-readable receipt meant for the AI — "
                    "paste it back into your chat with the developers. Hit “Download .md” "
                    "if you also want the full archive copy.",
        "copy": "Copy receipt",
        "copied": "Copied ✓",
        "copy_manual": "Selected — press ⌘C",
        "download": "Download .md",
        "filter_lead": "Show",
        "filter_all": "All",
        "filter_biz": "Yours to decide",
        "filter_dev": "Just review",

        # ── fill-in info (export time + a note for the developers) ──
        "sign_title": "Sign-off",
        "sign_date": "Export time (automatic)",
        "sign_relay": "Anything to tell the developers (optional)",
        "sign_relay_ph": "e.g. questions 1 and 3 were checked with Wang Fang by phone; "
                         "I do not know question 2, passed it to Li",

        # ── receipt skeleton ───────────────────────────────────
        "rc_title": "# Confirmation receipt: {title} (round {round})",
        "rc_meta": "> Exported {now} (recorded by the page) · sent {sent_on} · sent by {sent_by}",
        "rc_grade": "> Completeness: answered {done}/{total}",
        "rc_grade_denied": " · {n} marked not applicable (question {list})",
        "rc_grade_unans": " · {n} unanswered (question {list})",
        "rc_grade_p1": " · part 1 checked {done}/{total}",
        "rc_grade_clash": " · ⚠ {n} contradiction(s)",
        "rc_split": "> Split: {biz} for you to decide ({biz_done} answered)"
                    " · {dev} dev proposals ({dev_done} reviewed)",
        "rc_clash_head": "## ⚠ Contradictions surfaced while filling (developers: handle first)",
        "rc_clash_item": "- {when} — both hold at once: {text}…",
        "rc_clash_note": "  Business note: {v}",
        "rc_not_explained": "(not explained)",
        "rc_p1_head": "## Part 1 · Already agreed (please verify)",
        "rc_p1_cols": "| # | Verified | Note |",
        "rc_p1_no_reason": "(no reason given)",
        "rc_p1_all_ok": "all {n} line(s) confirmed correct, no objection",
        "rc_p1_each": "line by line: ",
        "rc_p1_extra": "; also: {v}",
        "rc_p2_head": "## Part 2 · Open questions (please answer)",
        "rc_qhead": "### Question {no}: {title} ({decide}){blocking}",
        "rc_blocking": " (blocking)",
        "rc_denied_line": "☒ This question does not hold (says the business): {why}",
        "rc_denied_inline": "this question does not hold: {why}",
        "rc_no_reason": "(no reason given)",
        "rc_na": "does not apply ({note})",
        "rc_skip": "because question {no} = {v}, the sub-questions here are skipped "
                   "automatically (not counted as unanswered)",
        "answer_mark": "[Answer]",
        "answer_mark_inline": "[Answer] ",
        "rc_sign_head": "## Sign-off",
        "rc_sign_line": "Exported at: {date}",
        "rc_relay": "Note for the developers: {v}",
        "rc_machine_note": "<!-- machine-readable block (for check_questionnaire.py / AI; "
                           "you can ignore it) -->",
        "rc_file_word": "receipt",

        # ── human-readable receipt preview ─────────────────────
        "pv_answered": "answered",
        "pv_checked": "checked",
        "pv_denied": "not applicable",
        "pv_unanswered": "unanswered",
        "pv_clash": "contradictions",
        "pv_exported_at": "exported {now}",
        "pv_clash_head": "⚠ Two of your choices contradict each other",
        "pv_clash_said": "Your note — “{v}” — goes back with the receipt.",
        "pv_clash_none": "You have not said how to handle it. Better to add a line, or the "
                         "developers have to come back and ask all over again.",
        "pv_denied_ans": "This question does not hold: {why}",
        "pv_no_reason": "(no reason given)",
        "pv_other": "None of these; it actually is: {v}",
        "pv_other_none": "(the actual rule is not written yet)",
        "pv_unans": "not answered yet",
        "pv_unans_first": " (marked “answer first” — the later questions wait on it)",

        # ── md-only skeleton ───────────────────────────────────
        "md_title": "# Requirement confirmation sheet: {title} (round {round})",
        "md_meta": "> Round {round} · {sent_on} · sent by {sent_by} · {n} questions",
        "md_howto": "How to fill this in: check every line of part 1; in part 2 tick a ☐ and "
                    "write under [Answer]. Questions marked “You decide” are yours to settle; "
                    "the ones marked “Dev proposal” already have a default rule — look it over, "
                    "and it stands unless you object. Send it back when you are done.",
        "md_p1_head": "## Part 1 · What we understand (please check every line)",
        "md_p1_cols": "| # | What we understand | Note | Correct? |",
        "md_p1_hint": "Which line is wrong, and how — please write it below:",
        "md_p2_head": "## Part 2 · Open questions (please answer)",
        "md_bg": "Background: {v}",
        "md_other_opt": "☐ None of these — what I need is not on the list "
                        "(write the actual rule in the answer box)",
        "md_reveal": "(if you choose {when}, please also answer in the answer box: {ask})",
        "md_subs_hint": "(please answer the sub-questions below inside the answer box:)",
        "md_sub_line": "  · {ask} ({menu} / none of these, please write it out):",
        "md_sub_fallback": "this sub-question",
        "md_sign_head": "## Sign-off",
        "md_sign_line": "Date: ____",
        "md_relay": "Note for the developers: ____",
    },
}


# md 锚点表:「机检认的中文规范词」→「这份单子实际用的结构词」。
# 中文单子是恒等映射(所以中文路径逐字节不变);英文单子靠它把结构词还原成规范词,
# 机检的人读锚点判据一字不动地照跑。表本身写进 md 末尾的机读区 —— 判据来自单子
# 自己,而不是在 checker 里再养一份英文词表(那就又是两份真源)。
ANCHOR_KEYS = {
    "问题": "w_question", "作答区": "answer_mark", "第一部分": "w_part1",
    "第二部分": "w_part2", "填写信息": "w_signoff", "阻塞": "w_blocking",
    "未表态": "p1_mute",
}


def anchors(lang="zh"):
    tbl = STRINGS.get(lang) or STRINGS["zh"]
    return {canon: tbl[key] for canon, key in ANCHOR_KEYS.items()}


def strings(lang="zh"):
    """取某个语言的整份外壳字符串表。未知语言在 validate() 就被拒了,这里再兜一层。"""
    return dict(STRINGS.get(lang) or STRINGS["zh"])


def t(lang, key, **kw):
    """取一条并做占位替换。键不存在时返回键名本身 —— 页面上出现光秃秃的键名是
    刺眼的失败,好过静默留白让人以为这里本来就没字。"""
    s = STRINGS.get(lang, STRINGS["zh"]).get(key, key)
    return s.format(**kw) if kw else s


def missing_keys():
    """两份表的键必须一一对应 —— 少一条,那门语言的页面上就会冒出一个键名。
    返回 {lang: 缺的键集合}。由测试盯着。"""
    all_keys = set().union(*(set(v) for v in STRINGS.values()))
    return {lang: all_keys - set(tbl) for lang, tbl in STRINGS.items()}

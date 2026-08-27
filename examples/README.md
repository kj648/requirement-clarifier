# 完整走查案例:逾期提醒

`demo-project/` 是一个缩微但完整的闭环:一句微信语音进来,一份可开工、可核验、可追责的规格出去。**按下面顺序读**,每一步对应 SKILL.md 模式 A 的一个阶段。

## 走查顺序

| 步骤 | 文件 | 演示什么 |
|---|---|---|
| 1. 原话落盘 | [raw/2026-07-10-李姐微信语音转述.md](demo-project/docs/requirements/raw/2026-07-10-李姐微信语音转述.md) | 逐字归档,不改写。注意原话里全是模糊点:"提醒一下""别太勤""过几天" |
| 2. 挑漏洞 → 出确认单 | [raw/2026-07-14-确认单v1-回执.md](demo-project/docs/requirements/raw/2026-07-14-确认单v1-回执.md) | 选择题化、每题标 `decide`（业务定／开发拟定，**不标具体回答人**——给谁去问是开发的事）、给"我不清楚"台阶、阻塞级标注。此文件是**业务回填后的回执**。注意它是 2026-07-14 的历史归档，逐题还写着"建议由 XX 回答"——那是当时的做法，原样保留（改它等于伪造归档）；现行做法见 `templates/questionnaire.schema.json` 的 `decide` |
| 3. 验收答案 | 同上,细看 3 个作答区 | 回答的典型脏法:问题 1 混入新需求(周报表);问题 2 只给方向("看着办");落款是李姐代签 |
| 4. 成型 | [specs/逾期提醒.md](demo-project/docs/requirements/specs/逾期提醒.md) | 三档标签各就各位:干净回答→【业务确认】带日期;"看着办"→【开发拟定】送过目;开发自己的记忆→【假设】待验证。每条决定带证据引用,末尾贴核验摘要 |
| 5. 沉淀 | [context.md](demo-project/docs/requirements/context.md) / [changes.md](demo-project/docs/requirements/changes.md) / [parking.md](demo-project/docs/requirements/parking.md) | 黑话、干系人、代签风险入 context;剥离的周报表进停车场而不是无声合并进 spec |

## 亲手跑一遍机检

在 `examples/demo-project/` 目录下(脚本路径按你的实际安装位置调整):

```bash
# 1. 回执机检:未答题/缺落款/模板残留(机械约束,先于 AI 验收)
python3 ../../scripts/check_questionnaire.py docs/requirements/raw/2026-07-14-确认单v1-回执.md
# 预期:✓ 机检通过(注意:机检通过 ≠ 验收完成,新需求混入、"看着办"这类判断题留给 AI)

# 2. 证据核验:spec 里每条引用真实可查
python3 ../../scripts/verify_evidence.py docs/requirements/specs/逾期提醒.md --root .
# 预期:7 PASS / 0 FAIL,并列出 4 处【假设】提醒不得作为开发依据
# 为什么是 4 处而不是 2 处:真正的假设条目只有 2 条(决定 5 的站内信通道、待办里
# 对它的验证项),另外 2 处是 spec 末尾那份核验摘要自己写着"【假设】×2"和
# "以下【假设】不得作为开发依据"——摘要贴回文档后被下一次扫描再次命中。
# 这是脚本按字面 grep 的已知代价,不是漏报:多报比漏报安全,故不加特例。
```

## 这个案例故意留的"活口"

真实项目永远收不干净,示例也如实呈现:

- **代签风险**:决定 1、2 的规则 owner 是王芳,但落款是李姐——spec 待办里挂着"请王芳本人补落款",没有假装闭环。
- **未验证假设**:"站内信通道可复用"标着【假设】,harness 会一直点名它,直到查码核实。

这正是铁律 2(暴露未知 > 假装完整)的样子。

## 关于 `app/reminder_rules.py`

这是**桩件**,不是 skill 的目录约定。它存在的唯一目的是让样例确认单能演示
`code` 档证据——`logic`(白话逻辑)／`entry`(页面入口)／`branches`(分支),
以及测试如何逐条核验这些坐标是真的。真实项目里对应的是你自己的代码。

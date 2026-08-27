# Requirement confirmation receipt: Expense payout (round 1)
> Exported 2026-08-27 23:50 (recorded by the page) · Sent 2026-07-11 · Sent by Dev
> Completeness: answered 3/4 · Part 1 verified 1/3 · 1 conflict

<!-- 全英文回执。人读部分的结构词（Part 1 / Question / Answer / Signature）
     一个都不匹配中文锚点 —— 老机检在这份单子上九条规则全部静默不触发。
     结论必须全部来自末尾机读区（键名恒为中文，由模板代码写出，不随正文语言变）。 -->

## Conflicts surfaced while filling (please handle first)

- Question 3 chose "Pause and route to manual review" while Question 2 chose "One batch per day, auto-retry up to 3 times" — both hold at once.
  Business note: (not explained)

## Part 1 — Already agreed (please verify)

| # | Verified | Note |
|---|---|---|
| 1 | Yes |  |
| 2 | undecided |  |
| 3 |  |  |

Answer: item 1 confirmed; items 2 and 3 not reviewed yet.

## Part 2 — Open questions (please answer)

### Question 1: From which node is a bill "payable"? (business decides) (blocking)
[ ] A. Payable once approval passes
[ ] B. Needs a finance double-check first
[ ] I don't know
[ ] None of these (see answer below)
Answer:

### Question 2: How does the payout batch run? (dev proposal — please review)
[x] C. I don't know — you should ask the finance team
Answer:

### Question 3: Partially rejected bills — pay automatically? (business decides)
[x] This question does not apply (business says so): Never happens here, finance never rejects part of a bill
Answer: This question does not apply.

### Question 4: What counts as "payout completed"? (business decides)
[x] A. Mark completed as soon as the transfer is initiated
Answer: Mark completed as soon as the transfer is initiated.

## Signature
Filled by: Wang Fang　Department: Finance　Date: 2026-08-27 23:50

<!-- machine-readable block (for check_questionnaire.py / AI) -->
```json
{"单据":"Expense payout","轮次":1,"代码依据":"515940005dd6c40f36b88ed17f4077578b408df9","导出时间":"2026-08-27 23:50","第一部分":[{"条":1,"核对":"Yes","说明":""},{"条":2,"核对":"undecided","说明":""},{"条":3,"核对":"","说明":""}],"题目":[{"题号":"1","阻塞":true,"主选":null,"子项":{},"跳过":[],"不成立":null,"补充":"","依据":["> evidence: docs/requirements/raw/2026-07-10-voice-note.md:4 | \"just pay it once the bill is approved\""],"独立复核":null},{"题号":"2","阻塞":false,"主选":"C. I don't know — you should ask the finance team","子项":{},"跳过":[],"不成立":null,"补充":"","依据":[],"独立复核":null},{"题号":"3","阻塞":false,"主选":null,"子项":{},"跳过":[],"不成立":"Never happens here, finance never rejects part of a bill","补充":"","依据":[],"独立复核":null},{"题号":"4","阻塞":false,"主选":"A. Mark completed as soon as the transfer is initiated","子项":{},"跳过":[],"不成立":null,"补充":"","依据":[],"独立复核":null}],"矛盾":[{"条件":"q3=B & q2=A","说明":"(not explained)"}],"落款":{"填写人":"","部门":"","导出时间":"2026-08-27 23:50","转交":"","已署名":false}}
```

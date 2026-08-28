# Confirmation receipt: Expense payout (round 1)
> Exported 2026-08-28 10:52 (recorded by the page) · sent 2026-07-11 · sent by Dev
> Completeness: answered 4/4 · 1 marked not applicable (question 4) · part 1 checked 1/2 · ⚠ 1 contradiction(s)
> Split: 3 for you to decide (3 answered) · 1 dev proposals (1 reviewed)
> ⚠ Unsigned: this receipt cannot be booked as business-confirmed. It can only be booked as a dev default awaiting sign-off, and it turns into a confirmed answer once a name is added.

## ⚠ Contradictions surfaced while filling (developers: handle first)

- question 3 = “Pause and hand it to a person” and question 2 = “One batch a day, auto-retry up to 3 times” — both hold at once: These two choices contradict each other. Question 2 option A means a daily job sweeps up claims and pays them out; question 3 option B means…
  Business note: (not explained)

## Part 1 · Already agreed (please verify)

| # | Verified | Note |
|---|---|---|
| 1 | Yes |  |
| 2 | Undecided |  |

[Answer] line by line: 1 Yes; 2 Undecided

## Part 2 · Open questions (please answer)

### Question 1: From which point is a claim "payable"? (You decide) (blocking)
☐ A. Payable as soon as approval passes
☐ B. Finance has to check it first
☑ I don't know
☐ None of these (see the answer box)
[Answer] 

### Question 4: What counts as "paid"? (You decide)
☒ This question does not hold (says the business): Never happens here: finance says a payment has never been bounced back.
☐ A. Mark it paid as soon as the transfer is initiated (what the code does today; nothing to change)
☐ B. Mark it paid only once the bank confirms (bounced claims go back to unpaid)
☐ None of these (see the answer box)
[Answer] this question does not hold: Never happens here: finance says a payment has never been bounced back.

### Question 3: A claim only partly approved — do we still pay it automatically? (You decide) (blocking)
☐ A. Pay the approved amount
☑ B. Pause and hand it to a person
☐ None of these (see the answer box)
[Answer] 

### Question 2: How does the payout batch run? (Dev proposal · please review)
☑ A. One batch a day, auto-retry up to 3 times
☐ B. One batch a week, triggered by hand
☐ None of these (see the answer box)
[Answer] 

## Sign-off
Filled by: (unsigned · exported from the HTML sheet)   Department: (not filled)   Date: 2026-08-28 10:52

<!-- machine-readable block (for check_questionnaire.py / AI; you can ignore it) -->
```json
{"单据":"expense-payout","轮次":1,"代码依据":"2beadcbdb8e64d5b041922729dffa27eca821670","导出时间":"2026-08-28 10:52","第一部分":[{"条":1,"核对":"ok","说明":""},{"条":2,"核对":"mute","说明":""}],"题目":[{"题号":"1","阻塞":true,"主选":"I don't know","主选kind":"dontknow","子项":{},"跳过":[],"不成立":null,"补充":"","依据":["> evidence: docs/requirements/raw/2026-07-10-voice-note.md:4 | \"just pay it once the claim is approved\""],"独立复核":null},{"题号":"4","阻塞":false,"主选":null,"主选kind":null,"子项":{},"跳过":[],"不成立":"Never happens here: finance says a payment has never been bounced back.","补充":"","依据":["> evidence: app/payout_rules.py:18 | \"if bill.paid_amount >= bill.approved_amount:\"","app/payout_rules.py:15","app/payout_rules.py:19","app/payout_rules.py:20"],"独立复核":"未复核"},{"题号":"3","阻塞":true,"主选":"B. Pause and hand it to a person","主选kind":null,"子项":{},"跳过":[],"不成立":null,"补充":"","依据":[],"独立复核":null},{"题号":"2","阻塞":false,"主选":"A. One batch a day, auto-retry up to 3 times","主选kind":null,"子项":{},"跳过":[],"不成立":null,"补充":"","依据":["> evidence: docs/requirements/raw/2026-07-10-voice-note.md:6 | \"don't pay several times a day\"","> evidence: docs/requirements/raw/2026-07-10-voice-note.md:7 | \"run it again a few days later\""],"独立复核":null}],"矛盾":[{"条件":"q3=B & q2=A","说明":""}],"落款":{"填写人":"","部门":"","导出时间":"2026-08-28 10:52","转交":"","已署名":false}}
```

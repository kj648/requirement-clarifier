"""报销单自动打款的现有判定逻辑。

demo 桩件：让样例确认单能演示 code 档证据（logic / entry / branches）。
真实项目里这里是你自己的代码。
"""
MAX_RETRY = 3


def is_payable(bill):
    if bill.status != 'approved':      # 没审批通过的单子不进打款队列
        return False
    return bill.approved_amount > 0


def should_payout(bill, sent_times):
    if not is_payable(bill):
        return False
    if bill.paid_amount >= bill.approved_amount:   # 发起成功即计入已打,不等银行回单
        return False
    return sent_times < MAX_RETRY       # 最多重试 3 次

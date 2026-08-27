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

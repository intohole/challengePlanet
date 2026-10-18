from __future__ import annotations

from datetime import datetime, timedelta

from app.core.datetime_utils import now_china

_DATE_FMT = "%Y-%m-%d"
MAX_MISSED_LISTED = 14


def today_str() -> str:
    return now_china().strftime(_DATE_FMT)


def week_key_of(dt: datetime | None = None) -> str:
    current = dt or now_china()
    iso = current.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_dates_of(dt: datetime | None = None) -> list[str]:
    current = (dt or now_china()).date()
    monday = current - timedelta(days=current.weekday())
    return [(monday + timedelta(days=i)).strftime(_DATE_FMT) for i in range(7)]


def month_prefix_of(dt: datetime | None = None) -> str:
    return (dt or now_china()).strftime("%Y-%m")


def shift_date(date_str: str, days: int) -> str:
    base = datetime.strptime(date_str, _DATE_FMT).date()
    return (base + timedelta(days=days)).strftime(_DATE_FMT)


def calc_streak(valid_dates: set[str], today: str) -> int:
    yesterday = shift_date(today, -1)
    if today in valid_dates:
        cursor = today
    elif yesterday in valid_dates:
        cursor = yesterday
    else:
        return 0
    streak = 0
    while cursor in valid_dates:
        streak += 1
        cursor = shift_date(cursor, -1)
    return streak


def streak_before(valid_dates: set[str], from_date: str) -> int:
    cursor = shift_date(from_date, -1)
    streak = 0
    while cursor in valid_dates:
        streak += 1
        cursor = shift_date(cursor, -1)
    return streak


def silent_kept_of(
    valid_dates: set[str], checkin_dates: set[str], today: str,
) -> int:
    """当前 streak 窗口内「静默守」的天数：valid 但无打卡记录（今天不计）。

    cap 补齐口径下没记录=没超上限=守住（缺席披露：连续数字不因缺勤虚涨，
    但静默守的部分如实披露——「连续 10 天（含 3 天静默守）」）。
    """
    yesterday = shift_date(today, -1)
    cursor = today if today in valid_dates else yesterday
    if cursor not in valid_dates:
        return 0
    silent = 0
    while cursor in valid_dates:
        if cursor != today and cursor not in checkin_dates:
            silent += 1
        cursor = shift_date(cursor, -1)
    return silent


def trailing_kept_from_valid(
    valid_dates: set[str], today: str, start_date: str, end_date: str,
) -> int:
    """journey「连续守住」口径对齐：从昨天往回数 valid 连续天数（补齐口径）。

    与 trailing_guard_days（记录口径，没记录即断）的区别：静默守也计入——
    减量挑战的本质是「不超上限」不是「必须记录」（r21 口径统一收口）。
    """
    cursor = shift_date(today, -1)
    count = 0
    while cursor >= start_date and (not end_date or cursor <= end_date):
        if cursor not in valid_dates:
            break
        count += 1
        cursor = shift_date(cursor, -1)
    return count


def list_missed_dates(
    start_date: str,
    end_date: str,
    valid_dates: set[str],
    today: str,
) -> list[str]:
    if not valid_dates:
        return []
    start = datetime.strptime(start_date, _DATE_FMT).date()
    last = min(
        datetime.strptime(end_date, _DATE_FMT).date(),
        datetime.strptime(shift_date(today, -1), _DATE_FMT).date(),
    )
    missed: list[str] = []
    cursor = last
    while cursor >= start and len(missed) < MAX_MISSED_LISTED:
        day = cursor.strftime(_DATE_FMT)
        if day not in valid_dates:
            missed.append(day)
        cursor -= timedelta(days=1)
    missed.reverse()
    return missed


def day_number_of(start_date: str, target_date: str) -> int:
    start = datetime.strptime(start_date, _DATE_FMT).date()
    target = datetime.strptime(target_date, _DATE_FMT).date()
    return (target - start).days + 1

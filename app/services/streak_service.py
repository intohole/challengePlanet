from __future__ import annotations

from datetime import date, datetime, timedelta

_DATE_FMT = "%Y-%m-%d"
MAX_MISSED_LISTED = 14


def today_str() -> str:
    return datetime.now().strftime(_DATE_FMT)


def week_key_of(dt: datetime | None = None) -> str:
    current = dt or datetime.now()
    iso = current.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_dates_of(dt: datetime | None = None) -> list[str]:
    current = (dt or datetime.now()).date()
    monday = current - timedelta(days=current.weekday())
    return [(monday + timedelta(days=i)).strftime(_DATE_FMT) for i in range(7)]


def month_prefix_of(dt: datetime | None = None) -> str:
    return (dt or datetime.now()).strftime("%Y-%m")


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


def list_missed_dates(
    start_date: str,
    end_date: str,
    valid_dates: set[str],
    today: str,
) -> list[str]:
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

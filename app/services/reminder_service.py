from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.audience import sendable_users
from nexus.notify import get_notify_client
from nexus.logging import get_logger

from app.core.datetime_utils import now_china
from app.db.database import async_session
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.models.reminder import ReminderPref
from app.repositories.checkin_repository import CheckInRepository
from app.services.absence_service import collect_absence_items, mark_absence_sent
from app.services.companion_service import assess_risk, companion_text
from app.services.goal_rule_service import is_cap_mode
from app.services.mercy_service import load_valid_dates
from app.services.rescue_service import collect_rescue_items, mark_rescue_sent
from app.services.streak_service import calc_streak, today_str

logger = get_logger("challengePlanet.reminder")

DEFAULT_REMIND_HOUR = 20
MAX_SENDS_PER_USER_PER_DAY = 3


def _reminder_content(risk: dict[str, object], total: int = 1) -> str:
    level = str(risk.get("level", "low"))
    head = f"你有 {total} 个挑战今天还没打卡，" if total > 1 else "今天还没打卡，"
    if level == "high":
        return f"{head}我注意到你最近节奏有些波动，这最容易松懈。{companion_text(risk)}"
    if level == "medium":
        return f"{head}记得留点时间完成它们。{companion_text(risk)}"
    return f"{head}别让连击断在这里！{companion_text(risk)}"


async def _get_unchecked_challenges(session: AsyncSession) -> list[Challenge]:
    today = today_str()
    result = await session.execute(
        select(Challenge).where(Challenge.status == "active")
    )
    all_active: list[Challenge] = list(result.scalars().all())
    unchecked: list[Challenge] = []
    for challenge in all_active:
        start = str(getattr(challenge, "start_date", "") or "")
        end = str(getattr(challenge, "end_date", "") or "")
        if (start and start > today) or (end and end < today):
            continue
        if is_cap_mode(challenge):
            continue
        checkin_result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge.id,
                CheckIn.date == today,
            ).limit(1)
        )
        if checkin_result.scalar_one_or_none() is None:
            unchecked.append(challenge)
    return unchecked


async def _load_prefs(session: AsyncSession) -> dict[str, ReminderPref]:
    result = await session.execute(select(ReminderPref))
    return {pref.user_id: pref for pref in result.scalars().all()}


def _prefers_now(pref: ReminderPref | None, current_hour: int) -> bool:
    if pref is not None and not pref.enabled:
        return False
    hour = pref.remind_hour if pref is not None else DEFAULT_REMIND_HOUR
    return int(hour) == current_hour


async def send_checkin_reminders(current_hour: int | None = None) -> None:
    try:
        current = current_hour if current_hour is not None else now_china().hour
        async with async_session() as session:
            unchecked = await _get_unchecked_challenges(session)
            active_result = await session.execute(
                select(Challenge).where(Challenge.status == "active")
            )
            absence_items = await collect_absence_items(session, list(active_result.scalars().all()))
            if not unchecked and not absence_items:
                logger.info("No unchecked challenges found, skipping reminders.")
                return
            prefs = await _load_prefs(session)

            def _pref_group(user_id: str) -> bool:
                return _prefers_now(prefs.get(user_id), current)

            grouped: dict[str, list[Challenge]] = {}
            for challenge in unchecked:
                if _pref_group(str(challenge.user_id)):
                    grouped.setdefault(str(challenge.user_id), []).append(challenge)
            absence_by_user: dict[str, list[dict[str, object]]] = {}
            for entry in absence_items:
                if _pref_group(str(entry["user_id"])):
                    absence_by_user.setdefault(str(entry["user_id"]), []).append(entry)
            if not grouped and not absence_by_user:
                logger.info("No users preferring hour=%s, skipping.", current)
                return
            sendable = await sendable_users(set(grouped) | set(absence_by_user))
            skipped = (set(grouped) | set(absence_by_user)) - sendable
            if skipped:
                logger.info(
                    "audience guard: %d users skipped (orphan/test/disabled)", len(skipped),
                )
            grouped = {u: cs for u, cs in grouped.items() if u in sendable}
            absence_by_user = {u: es for u, es in absence_by_user.items() if u in sendable}
            if not grouped and not absence_by_user:
                logger.info("All candidates filtered by audience guard, skipping.")
                return
            logger.info(
                "Sending reminders to %d users at hour=%s (%d absence)...",
                len(grouped), current, len(absence_by_user),
            )
            client = get_notify_client()
            checkins_repo = CheckInRepository()
            rescue_items = await collect_rescue_items(session, [c for cs in grouped.values() for c in cs])
            normal_items: list[dict[str, object]] = []
            for user_id, challenges in grouped.items():
                representative = challenges[0]
                checkins = await checkins_repo.get_by_challenge(session, representative.id)
                valid = await load_valid_dates(session, representative.id)
                streak = calc_streak(valid, today_str())
                risk = assess_risk(checkins, valid, streak, today_str())
                content = _reminder_content(risk, len(challenges))
                if len(challenges) > 1:
                    title = f"{len(challenges)} 个挑战待打卡"
                else:
                    title = f"「{representative.title}」打卡提醒"
                priority = 4 if risk["level"] == "high" else 3
                normal_items.append(
                    {
                        "user_id": user_id,
                        "title": title,
                        "content": content,
                        "type": "task",
                        "priority": priority,
                        "app_id": "challengePlanet",
                        "channels": ["in_app", "email"],
                        "link": "/challengePlanet/",
                        "data": {"challenge_count": len(challenges)},
                    }
                )
            absence_flat = [e for entries in absence_by_user.values() for e in entries]
            sent_counter = {"rescue": 0, "normal": 0, "absence": 0}
            gate_counter: dict[str, int] = {}
            for kind_name, entries in (
                ("rescue", rescue_items), ("absence", absence_flat),
            ):
                for entry in entries:
                    gate_counter[str((entry.get("gate") or {}).get("action", kind_name))] = (
                        gate_counter.get(str((entry.get("gate") or {}).get("action", kind_name)), 0) + 1
                    )
            per_user_budget: dict[str, int] = {}

            def _budget_left(user_id: str) -> int:
                return MAX_SENDS_PER_USER_PER_DAY - per_user_budget.get(str(user_id), 0)

            def _spend(user_id: str) -> None:
                per_user_budget[str(user_id)] = per_user_budget.get(str(user_id), 0) + 1

            rescue_ok: list[dict[str, object]] = []
            for entry in rescue_items:
                if _budget_left(str(entry["user_id"])) <= 0:
                    logger.warning("daily send budget exhausted for user %s — rescue held", entry["user_id"])
                    continue
                rescue_ok.append(entry)
                _spend(str(entry["user_id"]))
            absence_ok: list[dict[str, object]] = []
            for entry in absence_flat:
                if _budget_left(str(entry["user_id"])) <= 0:
                    logger.warning("daily send budget exhausted for user %s — absence held", entry["user_id"])
                    continue
                absence_ok.append(entry)
                _spend(str(entry["user_id"]))
            normal_ok: list[dict[str, object]] = []
            for item in normal_items:
                if _budget_left(str(item["user_id"])) <= 0:
                    logger.warning("daily send budget exhausted for user %s — reminder held", item["user_id"])
                    continue
                normal_ok.append(item)
                _spend(str(item["user_id"]))

            if rescue_ok:
                rescue_results = await client.send_many([e["payload"] for e in rescue_ok])
                rescued_users: set[str] = set()
                for entry, result in zip(rescue_ok, rescue_results):
                    status = result.get("status") if isinstance(result, dict) else None
                    if status == "sent":
                        rescued_users.add(str(entry["user_id"]))
                        sent_counter["rescue"] += 1
                        await mark_rescue_sent(
                            session, int(entry["challenge_id"]), str(entry["user_id"]),
                            int(entry["missed_days"]), gate=entry.get("gate"),
                            notif_id=int(result.get("id") or 0),
                        )
                    else:
                        logger.warning(
                            "rescue not sent for challenge %s: %s — normal reminder keeps this user covered",
                            entry["challenge_id"],
                            status if isinstance(result, dict) else result,
                        )
                await session.commit()
                if rescued_users:
                    normal_items = [i for i in normal_items if str(i["user_id"]) not in rescued_users]
                    normal_ok = [i for i in normal_ok if str(i["user_id"]) not in rescued_users]
            if normal_ok:
                results = await client.send_many(normal_ok)
                for item, result in zip(normal_ok, results):
                    status = result.get("status") if isinstance(result, dict) else None
                    if status == "sent":
                        sent_counter["normal"] += 1
            if absence_ok:
                results = await client.send_many([e["payload"] for e in absence_ok])
                for entry, result in zip(absence_ok, results):
                    status = result.get("status") if isinstance(result, dict) else None
                    if status == "sent":
                        sent_counter["absence"] += 1
                        await mark_absence_sent(
                            session, int(entry["challenge_id"]), str(entry["user_id"]),
                            entry["absence"], gate=entry.get("gate"),
                            notif_id=int(result.get("id") or 0),
                        )
                    else:
                        logger.warning(
                            "absence care not sent for challenge %s: %s — mark skipped",
                            entry["challenge_id"],
                            status if isinstance(result, dict) else result,
                        )
                await session.commit()
            logger.info(
                "Check-in reminders processed: %d rescue + %d normal + %d absence for %d users; gates=%s",
                sent_counter["rescue"], sent_counter["normal"], sent_counter["absence"],
                len(grouped) + len(absence_by_user),
                gate_counter or {},
            )
    except Exception as e:
        logger.error("Check-in reminder task failed: %s", e)

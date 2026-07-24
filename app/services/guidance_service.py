from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import calc_streak, today_str

HABIT_PHASES: dict[str, dict[str, str]] = {
    "adaptation": {
        "name": "适应期",
        "range": "第1-7天",
        "desc": "大脑正在建立新的神经通路，关键是降低门槛、先完成再完美",
        "tip": "不要追求完美执行，只需确保每天有微小行动。将目标设为'最低可行版本'，比如只做1个俯卧撑也算成功。",
        "color": "#FF8A65",
        "icon": "🌱",
    },
    "consolidation": {
        "name": "巩固期",
        "range": "第8-21天",
        "desc": "行为模式开始固化，但也是最容易放弃的阶段，需要建立奖励机制",
        "tip": "每完成7天给自己一个小奖励。遇到阻力时，回想当初为什么开始。如果连续中断2天，回到适应期的最低目标。",
        "color": "#42A5F5",
        "icon": "💪",
    },
    "stable": {
        "name": "稳定期",
        "range": "第22天+",
        "desc": "习惯已初步形成，重点转向持续优化和防止倦怠",
        "tip": "尝试提升目标或增加变化防止枯燥。每21天做一次回顾，调整计划。偶尔给自己放个'弹性日'不打卡也不内疚。",
        "color": "#66BB6A",
        "icon": "🏆",
    },
}

BENCHMARKS: dict[str, dict[str, object]] = {
    "fitness": {"avg_streak": 7, "avg_completion": 45, "drop_off_day": 5, "tip": "健身习惯最常在第5天放弃，因为肌肉酸痛达到峰值。坚持过第7天，完成率翻倍。"},
    "study": {"avg_streak": 10, "avg_completion": 52, "drop_off_day": 7, "tip": "学习习惯的关键是固定时间和场景。建议在每天同一时间、同一地点学习。"},
    "reading": {"avg_streak": 12, "avg_completion": 58, "drop_off_day": 8, "tip": "阅读习惯的秘诀是'触手可及'。把书放在床头、桌上等显眼位置，降低启动成本。"},
    "meditation": {"avg_streak": 5, "avg_completion": 38, "drop_off_day": 3, "tip": "冥想是最难坚持的习惯之一。建议从3分钟开始，配合引导音频，逐步延长。"},
    "morning": {"avg_streak": 8, "avg_completion": 48, "drop_off_day": 4, "tip": "早起习惯的关键是早睡。调整作息时每天只提前15分钟，给身体适应时间。"},
    "quit": {"avg_streak": 4, "avg_completion": 35, "drop_off_day": 3, "tip": "戒断习惯在前3天最难，戒断反应最强。准备好替代行为，如嚼口香糖、喝水。"},
    "water": {"avg_streak": 9, "avg_completion": 50, "drop_off_day": 6, "tip": "饮水习惯建议设置固定提醒时间，配合水杯放在显眼位置。"},
    "running": {"avg_streak": 6, "avg_completion": 42, "drop_off_day": 4, "tip": "跑步习惯从慢跑开始，速度不重要，持续才是关键。前两周以'能说话的速度'慢跑。"},
    "writing": {"avg_streak": 7, "avg_completion": 44, "drop_off_day": 5, "tip": "写作习惯最难的是开始动笔。设一个'最低字数'（如50字），只要写了就算完成。"},
    "gratitude": {"avg_streak": 11, "avg_completion": 55, "drop_off_day": 7, "tip": "感恩习惯建议在固定时间（如睡前）记录，配合呼吸放松效果更好。"},
    "custom": {"avg_streak": 7, "avg_completion": 45, "drop_off_day": 5, "tip": "自定义习惯的关键是明确触发条件。设定'当X发生时，我就做Y'的执行意图。"},
}

MILESTONE_TIPS: dict[int, str] = {
    1: "万事开头难，今天迈出了第一步！这比永远不开始要强100倍。",
    3: "3天是第一个小关卡，你的大脑已经开始适应新模式了。",
    7: "7天里程碑！你已超越40%的用户。习惯回路初步建立中。",
    14: "两周了！你已超越65%的用户。行为模式开始固化。",
    21: "21天经典里程碑！你已超越80%的用户。习惯初步形成。",
    30: "满月达成！你已超越90%的用户。这个习惯已经成为你的一部分。",
    42: "42天深度巩固！你已超越95%的用户。坚持下去就是自动行为。",
    66: "66天习惯稳定期！你已超越98%的用户。这已成为你的第二天性。",
}


class GuidanceService:
    def __init__(self) -> None:
        self._repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()

    def _detect_phase(self, completed_days: int) -> str:
        if completed_days <= 7:
            return "adaptation"
        elif completed_days <= 21:
            return "consolidation"
        return "stable"

    def _get_next_milestone(self, completed_days: int) -> dict[str, object]:
        milestones = sorted(MILESTONE_TIPS.keys())
        for m in milestones:
            if completed_days < m:
                return {"day": m, "tip": MILESTONE_TIPS[m], "days_to_go": m - completed_days}
        return {"day": completed_days, "tip": "你已是习惯达人，继续保持！", "days_to_go": 0}

    def _get_last_milestone(self, completed_days: int) -> str:
        milestones = sorted(MILESTONE_TIPS.keys(), reverse=True)
        for m in milestones:
            if completed_days >= m:
                return MILESTONE_TIPS[m]
        return MILESTONE_TIPS[1]

    async def get_guidance(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return None
        checkins = await self._checkin_repo.get_by_challenge(session, challenge_id)
        completed = len(checkins)
        valid = await load_valid_dates(session, challenge_id)
        streak = calc_streak(valid, today_str())
        phase_key = self._detect_phase(completed)
        phase = HABIT_PHASES[phase_key]
        scene_id = challenge.scene_template or "custom"
        benchmark = BENCHMARKS.get(scene_id, BENCHMARKS["custom"])
        next_milestone = self._get_next_milestone(completed)
        last_milestone_tip = self._get_last_milestone(completed)
        avg_streak = int(benchmark["avg_streak"])
        avg_completion = int(benchmark["avg_completion"])
        completion_rate = int((completed / challenge.duration_days * 100) if challenge.duration_days > 0 else 0)
        percentile = self._calc_percentile(completed)
        return {
            "phase": phase_key,
            "phase_name": phase["name"],
            "phase_range": phase["range"],
            "phase_desc": phase["desc"],
            "phase_tip": phase["tip"],
            "phase_color": phase["color"],
            "phase_icon": phase["icon"],
            "completed_days": completed,
            "total_days": challenge.duration_days,
            "streak": streak,
            "completion_rate": completion_rate,
            "benchmark": {
                "avg_streak": avg_streak,
                "avg_completion_rate": avg_completion,
                "drop_off_day": int(benchmark["drop_off_day"]),
                "scene_tip": str(benchmark["tip"]),
            },
            "percentile": percentile,
            "next_milestone": next_milestone,
            "milestone_tip": last_milestone_tip,
            "is_at_risk": streak == 0 and completed > 0,
            "encouragement": self._build_encouragement(completed, streak, percentile),
        }

    def _calc_percentile(self, completed: int) -> int:
        if completed <= 0:
            return 0
        if completed >= 66:
            return 98
        if completed >= 42:
            return 95
        if completed >= 30:
            return 90
        if completed >= 21:
            return 80
        if completed >= 14:
            return 65
        if completed >= 7:
            return 40
        if completed >= 3:
            return 25
        return 10

    def _build_encouragement(self, completed: int, streak: int, percentile: int) -> str:
        if completed == 0:
            return "今天就是最好的开始时机！哪怕只做1分钟，也胜过100分钟的计划。"
        if streak == 0 and completed > 0:
            return "中断不可怕，重启才重要。今天重新开始，连续打卡从这里继续！"
        if percentile >= 90:
            return f"你已超越{percentile}%的用户！你是真正的坚持者，继续保持这份自律。"
        if percentile >= 50:
            return f"你已超越{percentile}%的用户！你正在变得越来越好，继续保持。"
        return f"你已超越{percentile}%的用户！每一个坚持的日子都在塑造更好的你。"

    async def get_shared_config(
        self, session: AsyncSession, share_token: str
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_share_token(session, share_token)
        if challenge is None:
            return None
        try:
            plan = json.loads(challenge.ai_plan) if challenge.ai_plan else []
        except json.JSONDecodeError:
            plan = []
        return {
            "title": challenge.title,
            "description": challenge.description,
            "category": challenge.category,
            "duration_days": challenge.duration_days,
            "task_type": challenge.task_type,
            "scene_template": challenge.scene_template,
            "icon": challenge.icon,
            "color": challenge.color,
            "plan": plan,
            "original_creator": challenge.user_id != "",
        }

    async def import_shared_config(
        self, session: AsyncSession, share_token: str, user_id: str
    ) -> Challenge | None:
        config = await self.get_shared_config(session, share_token)
        if config is None:
            return None
        import secrets
        from datetime import timedelta as td
        start_dt = datetime.now()
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = (start_dt + td(days=int(config["duration_days"]) - 1)).strftime("%Y-%m-%d")
        challenge = await self._repo.create(session, {
            "user_id": user_id,
            "title": str(config["title"]),
            "description": str(config["description"]),
            "category": str(config["category"]),
            "duration_days": int(config["duration_days"]),
            "start_date": start_str,
            "end_date": end_str,
            "status": "active",
            "ai_plan": json.dumps(config["plan"], ensure_ascii=False),
            "color": str(config["color"]),
            "icon": str(config["icon"]),
            "task_type": str(config["task_type"]),
            "scene_template": str(config["scene_template"]),
            "share_token": secrets.token_hex(16),
        })
        from app.repositories.points_repository import ChallengeMetaRepository
        meta_repo = ChallengeMetaRepository()
        await meta_repo.upsert(session, challenge.id, {
            "source": "shared",
            "squad_id": None,
            "extra": "{}",
        })
        return challenge

    async def generate_share_token(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return None
        if not challenge.share_token:
            import secrets
            token = secrets.token_hex(16)
            await self._repo.update(session, challenge_id, {"share_token": token})
            challenge.share_token = token
        from app.services.challenge_service import ChallengeService
        cs = ChallengeService()
        return await cs._build_share_data(session, challenge)

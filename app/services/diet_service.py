from __future__ import annotations

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.repositories.weight_repository import WeightRepository
from app.services.ai_service import AIService

logger = get_logger("challengePlanet.diet")

ACTIVITY_FACTORS: dict[int, float] = {
    1: 1.2, 2: 1.375, 3: 1.55, 4: 1.725, 5: 1.9,
}

KCAL_PER_KG = 7700.0
MIN_SAFE_DEFICIT = 300.0
MAX_SAFE_DEFICIT = 500.0
MIN_SAFE_INTAKE = 1200.0
TOLERANCE = 0.1


def calc_bmr(gender: str, age: int, height_cm: float, weight_kg: float) -> float:
    if str(gender).lower() in ("女", "female", "f", "w"):
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5


def calc_daily_target(
    gender: str, age: int, height_cm: float, weight_kg: float,
    goal_weight: float, activity_level: int, duration_days: int,
) -> dict[str, float]:
    bmr = calc_bmr(gender, age, height_cm, weight_kg)
    tdee = bmr * ACTIVITY_FACTORS.get(int(activity_level or 2), 1.375)
    deficit = 0.0
    if goal_weight > 0 and weight_kg > goal_weight and duration_days > 0:
        total_loss = weight_kg - goal_weight
        deficit = total_loss * KCAL_PER_KG / duration_days
        deficit = max(MIN_SAFE_DEFICIT, min(deficit, MAX_SAFE_DEFICIT))
    target = max(MIN_SAFE_INTAKE, tdee - deficit)
    return {
        "target_kcal": round(target),
        "deficit_kcal": round(deficit),
        "tdee_kcal": round(tdee),
        "bmr_kcal": round(bmr),
    }


def assess_calorie(value: float, target: float) -> dict[str, object]:
    if target <= 0:
        return {"status": "unknown", "label": "暂无目标", "percent": 100.0}
    ratio = value / target
    if 1 - TOLERANCE <= ratio <= 1 + TOLERANCE:
        return {"status": "ok", "label": "在范围内", "percent": 100.0}
    if ratio < 1 - TOLERANCE:
        return {"status": "under", "label": "摄入偏少", "percent": round(ratio * 100, 1)}
    pct = round(max(0.0, (2 - ratio) * 100), 1)
    return {"status": "over", "label": "摄入偏多", "percent": pct}


MAX_IMAGE_CHARS = 6_000_000


def normalize_image(image: str) -> str:
    image = (image or "").strip()
    if not image:
        raise ValueError("先拍一张照片，或描述这一餐吃了什么")
    if len(image) > MAX_IMAGE_CHARS:
        raise ValueError("照片太大了，请压缩后重试")
    return image if image.startswith("data:image/") else f"data:image/jpeg;base64,{image}"


class DietService:
    def __init__(self) -> None:
        self._weights = WeightRepository()
        self._ai = AIService()

    async def estimate_calories(
        self, challenge: object, description: str = "", image: str = "",
        today_intake: float = 0.0,
    ) -> dict[str, object]:
        if image:
            try:
                result = await self._ai.estimate_diet_calories_from_photo(normalize_image(image))
            except ValueError:
                raise
            except Exception as e:
                logger.warning("diet photo estimate failed: %s", e)
                raise ValueError("照片识别失败了，请重试或直接描述这一餐")
        else:
            result = await self._ai.estimate_diet_calories(description)
        target = float(getattr(challenge, "daily_calorie_target", 0) or 0)
        total = float(result.get("total_kcal", 0) or 0)
        cumulative = max(0.0, float(today_intake or 0)) + total
        result["today_intake"] = round(max(0.0, float(today_intake or 0)), 1)
        result["meal_kcal"] = round(total, 1)
        result["assessment"] = assess_calorie(cumulative, target) if target > 0 and total > 0 else {
            "status": "unknown", "label": "暂无目标", "percent": 100.0,
        }
        cal = calc_daily_target(
            str(getattr(challenge, "gender", "") or ""),
            int(getattr(challenge, "age", 0) or 0),
            float(getattr(challenge, "height_cm", 0) or 0),
            float(getattr(challenge, "weight_kg", 0) or 0),
            float(getattr(challenge, "goal_weight", 0) or 0),
            int(getattr(challenge, "activity_level", 2) or 2),
            int(getattr(challenge, "duration_days", 30) or 30),
        )
        result["target_kcal"] = float(cal["target_kcal"])
        result["deficit_kcal"] = float(cal["deficit_kcal"])
        result["tdee_kcal"] = float(cal["tdee_kcal"])
        result["bmr_kcal"] = float(cal["bmr_kcal"])
        return result

    async def record_weight(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        weight_kg: float, date: str | None = None,
    ) -> dict[str, object]:
        date = date or now_china().strftime("%Y-%m-%d")
        existing = await self._weights.get_by_date(session, challenge_id, date)
        if existing is not None:
            await self._weights.update(session, existing, weight_kg)
            return {"id": existing.id, "date": date, "weight_kg": weight_kg, "updated": True}
        record = await self._weights.create(session, {
            "challenge_id": challenge_id, "user_id": user_id,
            "date": date, "weight_kg": weight_kg,
        })
        return {"id": record.id, "date": date, "weight_kg": weight_kg, "updated": False}

    async def get_weight_trend(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> dict[str, object]:
        records = await self._weights.get_by_challenge(session, challenge_id)
        trend: list[dict[str, object]] = []
        for i, rec in enumerate(records):
            window = [r.weight_kg for r in records[max(0, i - 6):i + 1]]
            avg = round(sum(window) / len(window), 2)
            delta = round(rec.weight_kg - records[0].weight_kg, 2) if i > 0 else 0.0
            trend.append({
                "date": rec.date, "weight_kg": rec.weight_kg,
                "avg7": avg, "delta": delta,
            })
        latest = trend[-1] if trend else None
        return {"records": trend, "latest": latest, "count": len(trend)}

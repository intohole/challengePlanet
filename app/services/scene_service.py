from __future__ import annotations

from dataclasses import dataclass

from nexus.logging import get_logger

logger = get_logger("challengePlanet.scene")


@dataclass
class SceneTemplate:
    scene_id: str
    name: str
    icon: str
    color: str
    description: str
    task_type: str
    default_target: float
    unit: str
    steps: list[str]
    difficulty_curve: str
    sample_prompts: list[str]


_TEMPLATES: dict[str, SceneTemplate] = {
    "fitness": SceneTemplate(
        scene_id="fitness",
        name="健身",
        icon="💪",
        color="#f59e0b",
        description="力量与有氧训练打卡，支持俯卧撑、仰卧起坐等计数目标，渐进式难度递增",
        task_type="counter",
        default_target=30.0,
        unit="个",
        steps=["热身", "训练", "拉伸"],
        difficulty_curve="渐进式递增，起始50%基础量，第80%天数达到100%",
        sample_prompts=[
            "30天每天30个俯卧撑",
            "21天腹肌撕裂者计划",
            "我要坚持每天做50个深蹲",
        ],
    ),
    "study": SceneTemplate(
        scene_id="study",
        name="学习",
        icon="📚",
        color="#6366f1",
        description="按页数或章节累计学习进度，预习-学习-复习-输出四步法",
        task_type="counter",
        default_target=20.0,
        unit="页",
        steps=["预习", "学习", "复习", "输出"],
        difficulty_curve="渐进式递增，学习量逐步提升至满负荷",
        sample_prompts=[
            "30天每天读20页专业书",
            "考研复习66天计划",
            "每天学完一个章节",
        ],
    ),
    "reading": SceneTemplate(
        scene_id="reading",
        name="阅读",
        icon="📖",
        color="#10b981",
        description="按页数累计阅读量，培养长期阅读习惯",
        task_type="counter",
        default_target=30.0,
        unit="页",
        steps=[],
        difficulty_curve="周期累计，阅读量稳定增长",
        sample_prompts=[
            "一年读完50本书",
            "每天阅读30页",
            "21天养成阅读习惯",
        ],
    ),
    "meditation": SceneTemplate(
        scene_id="meditation",
        name="冥想",
        icon="🧘",
        color="#8b5cf6",
        description="计时冥想练习，记录练习前后情绪状态",
        task_type="timer",
        default_target=10.0,
        unit="分钟",
        steps=[],
        difficulty_curve="渐进式递增，时长从短到长平稳过渡",
        sample_prompts=[
            "每天冥想10分钟",
            "21天正念冥想入门",
            "坚持每天15分钟静坐",
        ],
    ),
    "morning": SceneTemplate(
        scene_id="morning",
        name="早起",
        icon="🌅",
        color="#f97316",
        description="记录每日起床时间，培养规律作息",
        task_type="timer",
        default_target=7.0,
        unit="点",
        steps=[],
        difficulty_curve="稳定目标，逐步提前起床时间",
        sample_prompts=[
            "30天早起6点起床",
            "坚持每天7点前起床",
            "21天养成早起习惯",
        ],
    ),
    "quit": SceneTemplate(
        scene_id="quit",
        name="戒断",
        icon="🚭",
        color="#ef4444",
        description="戒除坏习惯的传统打卡，每日成功或失败",
        task_type="binary",
        default_target=1.0,
        unit="次",
        steps=[],
        difficulty_curve="维持戒断状态，天数累计即为成就",
        sample_prompts=[
            "我要戒烟30天",
            "戒掉熬夜66天",
            "21天戒糖计划",
        ],
    ),
    "custom": SceneTemplate(
        scene_id="custom",
        name="自定义",
        icon="🎯",
        color="#8b5cf6",
        description="完全自定义的打卡挑战，灵活适配任意目标",
        task_type="binary",
        default_target=1.0,
        unit="次",
        steps=[],
        difficulty_curve="用户自定义，无固定难度曲线",
        sample_prompts=[
            "自定义我的挑战",
            "坚持每天做一件好事",
            "30天不喝奶茶",
        ],
    ),
}


class SceneService:
    def __init__(self) -> None:
        self._templates = _TEMPLATES

    def list_scenes(self) -> list[SceneTemplate]:
        return list(self._templates.values())

    def get_scene(self, scene_id: str) -> SceneTemplate | None:
        return self._templates.get(scene_id)

    def get_progressive_target(
        self, scene_id: str, day: int, duration_days: int
    ) -> float:
        template = self._templates.get(scene_id)
        if template is None:
            logger.warning("progressive target requested for unknown scene: %s", scene_id)
            return 0.0
        base = template.default_target
        if duration_days <= 0:
            return round(base, 2)
        ramp_end = duration_days * 0.8
        if ramp_end <= 1.0:
            return round(base, 2)
        if day >= ramp_end:
            factor = 1.0
        else:
            factor = 0.5 + 0.5 * ((day - 1) / (ramp_end - 1.0))
        factor = max(0.5, min(1.0, factor))
        return round(base * factor, 2)

    def build_plan_hint(self, scene_id: str, duration: int) -> str:
        template = self._templates.get(scene_id)
        if template is None:
            return ""
        checkpoints = sorted({1, max(2, duration // 4), max(3, duration // 2), max(4, duration * 3 // 4), duration})
        targets = [f"第{d}天={self.get_progressive_target(scene_id, d, duration)}{template.unit}" for d in checkpoints]
        steps_hint = f"\n步骤参考: {'→'.join(template.steps)}" if template.steps else ""
        return (
            f"\n场景: {template.name}({template.icon})\n"
            f"打卡类型: {template.task_type} 单位: {template.unit}\n"
            f"渐进难度: {template.difficulty_curve}\n"
            f"渐进目标参考: {'; '.join(targets)}\n"
            f"每天JSON需包含 task_type=\"{template.task_type}\", target_value(数值), unit=\"{template.unit}\""
            f"{steps_hint}"
        )

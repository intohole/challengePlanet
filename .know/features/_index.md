# features Index
> Total: 6 entries

- feat-detect-plan-deterministic | 原 nl-create 让 LLM 流式生成66天完整计划JSON(PLAN_SYSTEM 数千token/数十秒)；改为一次结构化解析(参数+description≤30字产品文案)→plan_builder纯函数合成逐日计划(ladder递减目标/难度梯度/里程碑日/场景steps)→apply_numeric_adjust正则处理调整。LLM调用从2次降到1次short JSON，token/耗时大幅下降，数值完全可控 | 2026-09-15
- feat-forecast-prediction | 预测三层收归: NudgeService(纯函数确定性预测,星期权重/区间置信度/依据文案/increase达标时刻/ladder终点展望) + ForecastService(编排+回测校准闭环) + 前端节奏仪表盘; 零LLM, 预测带依据才可信, 回测校准形成数据飞轮 | 2026-09-19
- feat-insight-on-demand-stream | 周报洞察原先打卡后每7天后台生成+页面每次load预拉weekly-report(无效LLM+请求)。改为：页面加载零洞察请求；切到洞察tab才POST /challenges/{id}/insight/stream(SSE逐字渲染)；本周内已有缓存直接done(cached)，可force重新生成；生成max_tokens 512→256更简洁；移除打卡自动周报后台任务 | 2026-09-15
- feat-period-sport-dual-goal | 打卡域抽象收归：Judge窗口化+Metric派生+Target周排程，运动/阅读计时自动记录、周目标独立判定、MET自动折算千卡 | 2026-09-11
- feat-quit-gradient-tally | 产品范式: 用户设定 当前每天量→目标每天量, 系统按天数自动生成每日递减配额曲线; 用户只点我抽了一根(+1), 系统自动累计当日用量对比配额, 超限温和提醒不惩罚, 误点可撤销; 数值参数用确定性正则提取, LLM 仅承担语义理解 | 2026-09-09
- feat-reminder-aggregate |  | 

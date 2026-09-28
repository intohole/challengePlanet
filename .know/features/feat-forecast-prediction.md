---
id: feat-forecast-prediction
title: 挑战星球预测能力:确定性引擎+场景门禁+静默门槛(2026-09-28 重构)
summary: 预测三层收归: NudgeService(纯函数确定性预测, 0-24 时作息画像/星期权重/区间置信度/依据文案/increase达标时刻/ladder终点展望) + ForecastService(编排+情境归因) + 前端节奏仪表盘; 零LLM; 2026-09-28 重构: 画像纳入凌晨时段(修正睡眠跨零点用户翻倍失准)、夜间与低样本静默、场景门禁、移除失效回测校准
type: feature
project: challengePlanet
date: 2026-09-28
tags: [feature, dev]
scope: project
related: [bp-forecast-scope-and-quiet, bp-forecast-forward-looking, bp-forecast-trust-calibration]
---

# 挑战星球预测能力:确定性引擎+场景门禁+静默门槛

需求
挑战星球核心是"实时纠偏": 把习惯反馈周期从"天"压到"当下"。原实现只有一层外推, 并在 2026-09-28 被用户抓到两处硬伤: 10点已记4根却预计18根/触顶13:09; 凌晨时段给出无意义断言。

方案(当前)
1. NudgeService(纯函数, 零LLM):
   - 作息画像覆盖 0-24 时(与自然日计数口径同源), 星期权重(_blend_profile: 今日星期60%+全量40%, 活跃≥3时段才启用)
   - project_day_total = 已记量 / 分母, 分母 = day_progress = max(画像已流逝占比, 时间占比, 0.15)
   - 预测区间(置信度越高越窄)、置信度(_confidence_of 活跃时段≥10高/≥4中/否则低)、依据文案(_basis_of)
   - 前瞻窗口: 取"当前时刻之后"权重峰值及连续区间; 20点后可跨夜(给出 01:00-02:00 这类凌晨高危窗口); 单点峰值显示"20:00"不再出现"20:00-20:00"
   - 触顶时刻只在"预计会超"风险下给出; increase 给出"按今日速度预计X点达标"
   - ladder 终点展望(_ladder_outlook: 近7日均值 vs 阶梯计划, 讲"跟不跟得上计划")
2. 静默门槛(display_ready): hour<6 或 (今日记录<2 且时间进度<0.25) → 不出预计数字/触顶/依据, 只保留"已记/还可 X"+前瞻窗口; quiet 字段下发给前端
3. 场景门禁(forecast_scope.supports_forecast): 只有 counter 与时长类 timer 预测; binary/text/word/recite/diet/step/time_slot 直接返回禁用
4. ForecastService(编排): 门禁 → 取数(14天全量小时分布+今日星期小时分布+近7日均值+今日笔数) → NudgeService.evaluate → 情境归因(窗口内 context_tag 主导场景/条件模式)
5. 提示阶梯: 逼近(1) → 已到上限(1, 不弹toast) → 已超上限(2, 升级提醒)

关键代码
- app/services/forecast_math.py: hour_profile(0-24)/blend_profile/day_progress/project_day_total/forward_window(可跨夜)/window_parts/display_ready/merge_context_totals
- app/services/nudge_service.py: evaluate(...today_count) / _decrease_forecast / _increase_forecast
- app/services/forecast_scope.py: supports_forecast
- app/services/forecast_service.py: build() / _attach_context
- app/repositories/checkin_repository.py: count_by_date / get_hourly_distribution(取数不筛时段)
- static/js/views/home-task.js: _remainHint 节奏仪表盘(静默态只留额度与窗口)

验证
tests/test_nudge_service.py 64例 + tests/test_forecast_service.py 23例(含门禁/静默) + test_forecast_alert 14例 + e2e_forecast_dashboard 45例(含凌晨静默态) + 线上真实数据脚本核对(戒烟挑战10点4根→9.6根, 无触顶, 窗口20:00)

已移除(2026-09-28)
- 回测校准 bias 与预测快照: 快照按"当日首次打卡时刻"落库却与全天实际比对, 产生 ±40% 错偏(实测 09-27 将预测压到 0.6、09-28 抬到 1.4), 且同日第二次预测起静默失效; 预测快照无任何消费方, 一并删除

遗留
星期权重系数(0.6/0.3)、MIN_ELAPSED(0.15)、MIN_SAMPLE(2)/MIN_PROGRESS(0.25) 为经验值, 待真实数据积累后调优; 若日后要重做校准, 应按"固定时刻快照 vs 同日实际"同刻比对
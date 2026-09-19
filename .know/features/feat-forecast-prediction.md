---
id: feat-forecast-prediction
title: 挑战星球预测能力:确定性引擎+回测校准+节奏仪表盘
summary: 预测三层收归: NudgeService(纯函数确定性预测,星期权重/区间置信度/依据文案/increase达标时刻/ladder终点展望) + ForecastService(编排+回测校准闭环) + 前端节奏仪表盘; 零LLM, 预测带依据才可信, 回测校准形成数据飞轮
type: feature
project: challengePlanet
date: 2026-09-19
tags: [feature, dev]
scope: project
related: []
---

# 挑战星球预测能力:确定性引擎+回测校准+节奏仪表盘

需求
挑战星球核心是"实时纠偏": 把习惯反馈周期从"天"压到"当下"。原预测仅一层(NudgeService直接调用), 只覆盖decrease方向, 输出无区间/无置信度/无依据, 前端仅一行灰字, 用户感知不到"预测"能力。

方案
三层收归:
1. NudgeService(纯函数, 零LLM): decrease 叠加星期权重(_blend_profile: 今日星期分布60%+全量40%, 活跃≥3时段才启用)+预测区间(_interval: 置信度越高区间越窄)+置信度(_confidence_of: 活跃时段≥10高/≥4中/否则低)+依据文案(_basis_of); increase 新增"按今日速度预计X点达标"(reach_at); ladder 新增终点展望(_ladder_outlook: 按近7日均值判断结束时能否到目标)
2. ForecastService(编排): 统一取数(14天全量小时分布+今日星期小时分布+近7日均值) → NudgeService.evaluate → apply_bias → 快照落库(insight_type=forecast, 同日去重)
3. 回测校准闭环: 次日读昨日快照 predicted vs 实际 actual → bias=(actual-projected)*0.5 → apply_bias 夹在 [0.6x,1.4x] 防跑偏 → calibrated标记

关键代码
- app/services/nudge_service.py: evaluate(..., weekday_dist, day_number, recent_avg) / apply_bias(forecast, bias)
- app/services/forecast_service.py: build() / _calibration_bias() / _upsert_forecast()
- app/repositories/checkin_repository.py: get_hourly_distribution_by_weekday() 用 func.strftime("%w", timestamp) 而非 extract("weekday") —— SQLite不支持extract weekday
- static/js/views/home-task.js: _remainHint 升级为 .cp-dash 节奏仪表盘

验证
tests/test_nudge_service.py 40例 + tests/test_forecast_service.py 12例(含校准闭环) + tests/e2e_forecast_dashboard.py 13例, 全绿

遗留
预测快照写入今天维度(get_today_task 已 commit); 星期权重系数(0.6/0.3)与校准阻尼(0.5)为经验值, 待真实数据积累后调优

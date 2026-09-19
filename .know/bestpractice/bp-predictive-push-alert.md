---
id: bp-predictive-push-alert
title: 预测驱动主动提醒:预警早于行为窗口+按挑战同日去重+复用通知中间件
summary: 预测不只在页面上展示,还要主动送达: 扫描活跃对象→预测风险(risk_level≥1)→复用统一通知中间件推送; 关键三条: 预警时间设在行为高峰之前(如18:30预警20:00后的风险窗口)、按对象+日期去重防打扰、文案直接用预测里最可行动的那句(优先coach_nudge兜底risk_window_msg)
type: bestpractice
project: challengePlanet
date: 2026-09-19
tags: [bestpractice, pattern]
scope: project
related: []
---

# 预测驱动主动提醒:预警早于行为窗口+按挑战同日去重+复用通知中间件

场景
已有"实时预测"能力后, 用户不打开页面就享受不到。需要把预测转成主动提醒(push), 但容易做成骚扰。

做法
1. 触发条件收敛为"预测显示会失控": 只在该对象 risk_level>=1(按当前节奏将超目标)时推送, risk_level=0(稳)绝不打扰
2. 时间点设在行为高峰之前: challengePlanet 的打卡提醒在20:00, 预测预警设在18:30 —— 在晚间风险窗口(20-22点)到来前给用户留出调整时间。预警必须早于它预警的那件事
3. 按"对象+日期"去重: 用 AIInsight(insight_type=forecast_alert, content={date}) 记录当日已推送, 同一对象一天最多一条; 聚合到用户维度合并为一条消息
4. 文案复用预测里最可行动的一句: 优先 coach_nudge("按现在节奏预计11根会超3, 下一次推迟到16:40之后"), 兜底 risk_window_msg
5. 复用统一通知中间件(nexus.notify), 不自己写SMTP/短信; 渠道 in_app+email, 高风险 priority=4

原因
- 预测的价值在于"在破戒之前", 而用户不一定主动打开app; 主动送达才能闭环
- 预警时间早于行为窗口才有调整空间; 事后提醒=马后炮
- 去重是防打扰的生命线: 没有去重的预测推送会每天刷屏, 用户很快关闭通知
- 文案直接用预测输出, 避免"提醒文案"与"页面文案"两套口径不一致

反例
- 每有风险就推 → 一天多条, 用户关闭通知
- 预警时间和风险窗口同一时刻 → 来不及调整
- 重新写一套提醒文案 → 与页面预测口径不一致, 用户困惑
- 自己直连SMTP → 违反"通知统一出口"铁律

验证
challengePlanet: tests/test_forecast_alert.py 13例(风险触发/标题聚合/渠道/优先级/同日去重/低风险不打扰)全绿; 部署后 /health 显示 scheduler running (2 jobs)

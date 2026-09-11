---
id: rf-checkin-review-round2
title: 二轮评审修复：千卡死锁/秒表假运行/周期可配性
summary: 运动类型强制转计时模式解除计数场景千卡死锁，秒表失败续走表，period_days前端可配
type: refactor
project: challengePlanet
date: 2026-09-11
tags: [refactor, architecture]
scope: project
related: []
---

# 二轮评审修复：千卡死锁/秒表假运行/周期可配性

动机: 二轮代码评审发现6个问题(1 major/5 minor)
改动: 1)create.js confirmCreate选运动类型(sportMet>0)时强制task_type=timer/unit=分钟并同步plan, 解除健身(running counter/公里)场景千卡周目标永不达标死锁(此前fix2禁非时间类折算+fix5强制千卡口径组合成死锁); 2)stopwatchToggle失败分支重启interval继续走表, 消除假运行状态与"记录失败"误报文案; 3)step空分步清单主按钮disabled; 4)创建表单新增周期天数periodDays输入, confirm提交可配period_days; 5)_periodCard文案按period_days动态(7=本周/其他=每N天); 6)period_fields移除冗余week_target字段及schema
验证: 线上e2e 6/6(14天窗口/无week_target/343千卡/周目标达成) + 全量回归17+10+11全过, 部署64a304b
教训: 派生指标(卡路里)与单位口径的守护条件(fix2)可能与其他强制转换(fix5)组合成死锁, 跨fix审查必须走完整数据流; 前端选型应同步锁定数据语义(选运动类型=计时模式)而非仅改展示

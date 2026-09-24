---
id: bp-single-target-resolver
title: 同一业务量的目标口径必须收归单一入口供读写路径共用
summary: 今日目标在读取视图/打卡判定/预测三处各有一份实现(窗口含不含今天、回退值不同)会造成进度条与达标判定分裂；应收归 target_service 一个 resolver，读写路径同源
type: bestpractice
project: challengePlanet
date: 2026-09-24
tags: [bestpractice, pattern]
scope: project
related: []
---

# 同一业务量的目标口径必须收归单一入口供读写路径共用

## 场景
"今日目标/当日上限"这类既用于展示又用于判定与预测的核心数值，出现在多个 service 里。
## 做法
建单一 resolver(TargetService.resolve)，内部按 task_type/goal_rule 分支(fixed→静态值, adaptive→动态基线, ladder→当日梯度, sub_goal/time_slot→时段值)，读取视图与打卡写入共用同一调用；基线算法只保留一个纯函数(dynamic_baseline_from)供报表复用。
## 原因
challengePlanet 原有 4 份动态基线(其中 live 路径用滚动时间窗含今天、报表用自然日不含今天)、2 份阶梯公式(plan_builder 与 goal_rule_service)，导致同一时刻进度条按基线、settled/还差多少按静态目标、打卡判定又按基线，三方不一致；target 还会随用户今天打卡而漂移。
## 反例
在展示层"顺手"再算一遍目标；或让 GET 视图与 POST 判定各自解析参数。
## 验证
替换后 HTTP 断言: /today 的 today_target、/checkin 的 today_target、进度条分母三者一致(8杯水=8)；静态挑战不再受动态基线漂移影响。

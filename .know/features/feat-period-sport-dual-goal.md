---
id: feat-period-sport-dual-goal
title: 计时场景周维度双强目标与运动卡路里自动折算
summary: 打卡域抽象收归：Judge窗口化+Metric派生+Target周排程，运动/阅读计时自动记录、周目标独立判定、MET自动折算千卡
type: feature
project: challengePlanet
date: 2026-09-11
tags: [feature, dev]
scope: project
related: []
---

# 计时场景周维度双强目标与运动卡路里自动折算

需求: 运动/阅读计时场景，用户点开始→结束自动记录分钟；每日强目标+每周强目标双考核；目标可阶梯递增/递减；用户只管记录系统自动判
抽象: 1)Judge窗口化 is_settled→judge_mode(record_done/target_met/cap_kept)+is_win_settled, 新增is_period_settled(challenge,task_type,period_total,period_target) 同模式跑日/周两个窗口; 2)Metric派生 sport_metrics.py MET×体重×分钟/60→千卡, do_checkin按sport_met自动落库calories; 3)Target周排程 challenges新增period_days/period_target/period_unit/sport_met字段, /today聚合week_total/week_settled/calories_*
关键实现: period_service.week_aggregates按week_dates_of()范围取checkins; period_fields按period_unit识别千卡口径(用calories_week)vs分钟口径(用week_total)换算判定; 前端秒表(cp-stopwatch)结束自动doFastTap入账分钟, 今日页_periodCard周进度+_calorieCard千卡; 创建表单运动类型选择+每周目标(分钟/千卡), create-extra.js抽出方法控行数
遗留: 阶梯递增/递减复用既有ladder(interval=7即每周调档)未新增; 周目标独立展示不改变每日settled与streak/mercy/squad
验证: 线上e2e 17项全过: 计时自动入账/343千卡折算/日达标/周千卡与分钟口径判定/今日页周卡展示; text/step/word回归全过
坑: 并行Edit致create_with_plan签名参数与period_service import丢失→500, 需全量审计引用

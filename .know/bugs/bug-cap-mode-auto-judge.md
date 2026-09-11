---
id: bug-cap-mode-auto-judge
title: 戒断计数（戒烟一根一点）完成判定收敛：系统按记录自动判定，去掉「守住今日」手动声明
summary: counter/timer+decrease（cap型上限目标）场景下，每日完成与否应以「当日已记量 vs 当日上限」自动判定：1)主CTA的「守住今日/今日完成」会提交value=0空声明，把完成判定丢回用户记忆；2)settled当天按total<=cap运行中翻True/False横跳；3)completed_days=len(checkins)一根烟算一天；4)零记录好日子streak断签。统一收敛为cap-mode：当天不判定、次日零点按cap自动判定（含零记录=守住），超限日=断签
type: bug
project: challengePlanet
date: 2026-09-11
tags: [bug, fix]
scope: project
related: [feat-quit-gradient-tally]
---

# 戒断计数（戒烟一根一点）完成判定收敛：系统按记录自动判定

报错现象: 戒烟阶梯挑战里用户一根一根点烟记账，页面仍把「完成目标」当作需要用户手动声明/记忆的二元动作：大按钮显示「守住今日｜不超X即达标」，点了只产生一条value=0的记录，超限后按钮永远点不动；一根烟算一天（"已打卡8/30天"）；今天一根没抽=没记录，第二天提示断签
根因分析: 1)_mainCTA对decrease无条件渲染「守住今日」声明CTA，doMainCheckin对decrease提交value=0；2)is_settled的cap_kept模式为has_record>0且total<=target，当天运行中即判完成（total<=cap就"今日已完成"），超限后翻回；3)get_challenge_stats.completed_days=len(checkins)按记录条数而非天数；4)load_valid_dates仅记录作为有效日，零记录好日子不计数
修复方法: 定义cap-mode=direction decrease且task_type counter/timer；1)is_settled cap_kept改为当天不回（day_open时时False），次日零点按total<=target自动判定，binary+decrease保留手动声明(record_done)；2)is_period_settled以day_open=False判定周期窗口；3)load_valid_dates对cap-mode按「当日总记录 vs 当日上限」判定有效日：未超限/零记录=守住，超限日剔除，当天不纳入；4)completed_days按实际天数（cap-mode=过去守住天数，其余=distinct日期）；5)前端cap-mode主CTA改为点烟记账台（+1大按钮+预设+撤销+余量三态），extras/待打卡badge/pendingCount移除cap-mode的声明入口与催卡
防范: 定量上限类(递减计数/计时)目标=系统按记录自动判定完成，用户只负责记账；任何「声明式」入口（守住今日/value=0）只保留给binary递减；当天结果次日零点按cap落定，避免运行中横跳
验证: tests/test_cap_mode.py新增3条：戒烟阶梯场景（超限日剔除/零记录日自动守住/当天不入/streak断在超限日/当天settled=False）、binary递减仍声明、increase计数completed_days按天数；全量15 tests通过；node render级校验cap-mode CTA三态与doMainCheckin守卫
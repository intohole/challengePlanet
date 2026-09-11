---
id: bug-word-checkin-settlement
title: 背词打卡结算失效+词卡字母序双修复
summary: 刷词模式手动提交value=1而word目标=20致is_settled永不达标，根因是打卡值与目标脱钩；改为刷完词卡按当日词量自动打卡结算，词卡会话内Fisher-Yates打乱
type: bug
project: challengePlanet
date: 2026-09-11
tags: [bug, fix]
scope: project
related: []
---

# 背词打卡结算失效+词卡字母序双修复

报错现象: word场景(英语背词)刷完当日20张词卡后仍需手动点「完成今日背词」, 且提交value=1 vs 目标20, today_total永远>=不过target, settled恒为false, 用户无法完成今日挑战
根因分析: is_settled(word)=today_total>=today_target(20), 而前端背词完成按钮doCheckin('full')固定提交value=1.0; 词卡评分process全部本地, 与后端打卡记录脱钩; 且每日词卡按vocab.json字母序切片展示
修复方法: 1) learn-checkin.js 最后一张卡评分后自动POST /checkin value=当日词卡数(20), 系统按is_settled自动判定达标, 删除手动「完成今日背词」按钮; 2) _loadWordCards加载词库后先做会话级Fisher-Yates打乱(jsonCache['vocab.shuffled']缓存), 再按day_number推进切片; 3) wordUI加wordCardsDay按天刷新防跨天残留, home-checkin.js word主CTA改为打开刷词面板
防范: 打卡结算必须让「记录值」与「目标单位」同量纲, 或judgment用has_record语义; 每日任务交互内的完成动作应收归系统自动判断, 用户仅记录
验证: 线上e2e(9/11 commit 795bbfc+fe9d101) 11项全过: 词卡非字母序、刷完自动settled=true/total=20、无手动按钮、主按钮变今日已完成

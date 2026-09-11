---
id: bug-checkin-manual-vs-auto
title: 打卡全类型结算收敛：text必填内容、step按勾选判定
summary: text类型空reflection也可达标、step主按钮绕过勾选清单、doMultiCheckin用checked_in拦截致未达标无法追加，三处与「系统按记录判断」相悖，统一修复
type: bug
project: challengePlanet
date: 2026-09-11
tags: [bug, fix]
scope: project
related: []
---

# 打卡全类型结算收敛：text必填内容、step按勾选判定

报错现象: 1)text(写作/感恩)不写内容点主按钮也提交value=1达标, CTA还承诺「目标3件」但结算只看有记录; 2)step主按钮直接提交全部steps数绕过勾选; 3)step部分勾选提交后checked_in=true无法再追加, 而counter/timer等可追加
根因分析: doMainCheckin对text空textValue时走默认value=1 fallthrough; 后端CheckInCreate.reflection可选无校验; _mainCTA对step无条件全量提交; doMultiCheckin guard用checked_in而非settled
修复方法: 1)doMainCheckin text分支显式校验空值toast返回, 后端do_checkin对task_type=text且reflection空raise; 2)text CTA改为openText(面板输入后提交)文案「写下几句即自动完成」; 3)step有task_steps时CTA改openStep, 勾选后doMultiCheckin提交勾选数由系统判定; 4)doMultiCheckin guard checked_in改settled, 未达标可持续追加
防范: 打卡结算语义=用户提交「记录内容」, 系统按is_settled判定; 所有绕过真实记录的「自动全量」入口应改为引导用户记录后再判定; 前端拦截与后端必填校验双保险
验证: 线上e2e(9/11 commit 0e7ba1c+c6054b0) 10项全过: 空reflection被拦截/带内容达标/step勾选2未达标可续/补齐达标

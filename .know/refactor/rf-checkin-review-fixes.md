---
id: rf-checkin-review-fixes
title: 代码评审7项修复：text微打卡/卡路里单位/period_days/interval泄漏等
summary: 评审发现的可见路径错误与配置死字段全部修复并回归通过
type: refactor
project: challengePlanet
date: 2026-09-11
tags: [refactor, architecture]
scope: project
related: []
---

# 代码评审7项修复：text微打卡/卡路里单位/period_days/interval泄漏等

动机: 代码评审发现7个问题(2 major/5 minor)
改动: 1)text类型_exxtras去掉微打卡按钮(doCheckin('mini')无reflection后端必拦); 2)checkin_service卡路里折算增加is_time_based校验(task_type==timer或分钟类unit), 健身(个/公里)不再折算; 3)period_service._window_dates: period_days==7用自然周, 其他滚动N天窗口, period_days从死字段变生效; 4)learn-checkin暴露cpClearLearnTimers, home.js切换挑战时清理_stIv/_pmIv防泄漏; 5)create-extra.selectSport选中运动类型即强制periodUnit='千卡'; 6)doMainCheckin step空清单拦截; 7)doFastTap返回成功标志, stopwatchToggle await成功才清零, 失败保留计时
验证: 本地单测(窗口/千卡时间类校验)+线上e2e回归全过(period-sport 17/17, text/step 10/10, word 11/11), 部署54b617e
教训: 后端必填校验与前端入口要双向对齐(text微打卡); 派生指标(卡路里)必须校验输入语义(时间类)否则数值虚高; 存储了但不用配置是误导, 要么生效要么删除

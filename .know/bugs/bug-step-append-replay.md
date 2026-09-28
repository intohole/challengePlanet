---
id: bug-step-append-replay
title: 分步挑战当日补齐被"当日重放"静默丢弃
summary: 分步(step)挑战 UI 允许一天内多次打开清单补齐未勾选项, 但后端 is_repeatable 只认 counter/timer, 第二次提交走进"当日已有记录→重放上一条"分支, 用户补齐的第3项被静默丢弃(total 停在2); step 属于可多笔记录的分步清单玩法, 纳入 is_repeatable 后追加生效
type: bug
project: challengePlanet
date: 2026-09-28
tags: [bug, fix]
scope: project
related: [bug-checkin-manual-vs-auto, bug-count-tally-unify]
---

# 分步挑战当日补齐被"当日重放"静默丢弃

报错现象
分步挑战(step)先勾选 2/3 提交, 再打开清单补齐第 3 项提交后, 今日累计仍是 2, 系统判定永不达标(settled 恒 False), 页面无任何报错。

根因分析
1. checkin_service.do_checkin: `if today_checkins and not is_repeatable(challenge): return _replay_checkin(...)` —— 当日已有记录且"不可重复"时直接重放旧记录
2. goal_rule_service.is_repeatable 只认 counter/timer(及 time_slot), 未含 step; 而前端分步清单(_stepPanel/doMultiCheckin)设计上支持一天内多次提交补齐
3. 两处口径矛盾: UI 邀请追加, 后端静默丢弃, 用户无从察觉

修复方法
1. is_repeatable 纳入 step: 分步挑战当日可多笔提交, 每笔 value=本次勾选项数, 今日累计=各笔之和, 达标由 target_met 自动判定
2. 顺带: 该场景今日视图会出现进度条与"还差X达标"(与其它多笔场景一致)

防范
凡"UI 支持一天内多次提交"的玩法, 必须同时满足 is_repeatable(后端不重放) 与 judge_mode(按记录自动判定); 新增玩法时两处分级要一起对照, 否则出现"点了没反应"的静默黑洞。

验证
tests/e2e_checkin_types.py 线上 10/10(勾选2/3可继续追加 → 补齐后系统判定达标); 本地全量回归绿
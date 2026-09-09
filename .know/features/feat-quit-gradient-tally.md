---
id: feat-quit-gradient-tally
title: 戒断挑战梯度减量+一键点烟自动记账（挑战星球）
summary: 产品范式: 用户设定 当前每天量→目标每天量, 系统按天数自动生成每日递减配额曲线; 用户只点'我抽了一根'(+1), 系统自动累计当日用量对比配额, 超限温和提醒不惩罚, 误点可撤销; 数值参数用确定性正则提取, LLM 仅承担语义理解
type: feature
project: challengePlanet
date: 2026-09-09
tags: [feature, dev]
scope: project
related: []
---

# 戒断挑战梯度减量+一键点烟自动记账（挑战星球）

需求: 用户自己计数=系统没有价值; 系统承担梯度计算与自动记账, 用户只有一次点击
方案: scene quit 默认 goal_rule=ladder + direction=decrease + goal_type=soft + task_type=counter; 配额公式 ladder_cap=max(goal, start-floor((day-1)/interval)*step); 前端点烟记账台(大按钮+1/撤销上一笔/上限余量/达标超限三态); 创建页'当前每天/目标每天'语义+曲线预览(目标=0=完全戒断)
关键实现: prompts.py PARSE_SYSTEM 指示 LLM 输出 ladder 梯度; api._apply_quit_ladder 正则兜底(从X到Y / 每天最多X); ladder_out 用 model_fields_set 防默认值覆盖
验证: E2E 第21天梯度上限自动=0、多次点击累计/撤销正确; 浏览器实测'我抽了一根'记账与撤销 0 报错（2026-09-09 已验证）

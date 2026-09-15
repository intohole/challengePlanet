---
id: feat-detect-plan-deterministic
title: 挑战计划函数化生成：LLM只做语义参数识别+产品描述，计划正文由确定性代码合成
summary: 原 nl-create 让 LLM 流式生成66天完整计划JSON(PLAN_SYSTEM 数千token/数十秒)；改为一次结构化解析(参数+description≤30字产品文案)→plan_builder纯函数合成逐日计划(ladder递减目标/难度梯度/里程碑日/场景steps)→apply_numeric_adjust正则处理调整。LLM调用从2次降到1次short JSON，token/耗时大幅下降，数值完全可控
type: feature
project: challengePlanet
date: 2026-09-15
tags: [feature, dev, llm-cost, refactor]
scope: project
related: [feat-insight-on-demand-stream]
---

# 挑战计划函数化生成：LLM只做语义识别，计划正文由代码合成

背景: nl-create 原链路两次 LLM 调用：①PARSE_SYSTEM 解析结构化参数(合理) ②PLAN_SYSTEM 流式生成 Step 逐天计划 JSON(66天×对象=数千token，耗时数十秒，数值可能漂移)
方案: ①新增 app/services/plan_builder.py 纯函数 build_plan(title,duration,task_type,target_value,unit,direction,goal_rule,ladder_*,steps)：ladder 目标用 _ladder_cap 逐日递减/递增、里程碑日(7/14/21/28/末日)为阶段小结、难度按天梯度、阶段重心文案轮换(FILL_VARIANTS)；②PARSE_SYSTEM 增加 description 字段(面向用户≤30字产品文案，如'每天跑3公里，用30天养成跑步习惯')与天数约束(≥7、勿与目标值混淆)；③ai_service.generate_challenge_plan 也改确定性(兼容 LifeCompass create_from_decision，用 _infer_daily_target 正则从描述提目标)；④删除 generate_challenge_plan_stream/parse_plan_text/_build_plan_system/_fit_plan_length/PLAN_SYSTEM 整条链与 PLANING_TEMPERATURE/LLM_MAX_TOKENS 配置；⑤adjust 走 apply_numeric_adjust(正则"减半/提高30%/(改成N)")不再调 LLM
关键实现: build_plan 天数值需 int(parsed.get("duration_days") or 30) 兜底(LLM 曾把"减到0"的目标量误当天数输出0→plan 变 1 天)
验证: tests/test_plan_builder.py 19/19(ladder递减2、0不越界/固定目标/难度梯度/里程碑/steps透传)；线上 API 实测戒烟30天 ladder 20→0 秒回(events 仅 parsing/parsed/preview 无 token/day)、阅读66天每天30页；单次 LLM 调用耗时~9s 为主导延迟
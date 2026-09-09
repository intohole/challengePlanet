---
id: bug-pydantic-default-overrides
title: Pydantic 字段默认值静默覆盖下行推导: request.goal_rule or parsed.goal_rule 被默认 'fixed' 截胡
summary: 根因: NLCreateRequest.goal_rule=Field('fixed'), 路由用 request.goal_rule or parsed.goal_rule, 客户端未传时默认值永远优先, 把 LLM/正则推导的 ladder 覆盖成 fixed; 修复: 用 model_fields_set 判断显式传入, 仅显式优先, 推导兜底
type: bug
project: challengePlanet
date: 2026-09-09
tags: [bug, fix]
scope: project
related: []
---

# Pydantic 字段默认值静默覆盖下行推导: request.goal_rule or parsed.goal_rule 被默认 'fixed' 截胡

报错现象: 输入'从每天20根戒到0'解析结果 goal_rule 恒为 fixed, 但探针 ladder_applied=true 显示推导函数已设置 ladder
根因分析: pydantic v2 非可选字段默认值会在反序列化时填上, 'request.goal_rule or parsed.goal_rule' 语义变成 默认'fixed' 优先; 前端 nl-create 只传 raw_input 必然踩中
修复方法: fields_set=getattr(request,'model_fields_set',None); client_rule=str(request.goal_rule) if (fields_set and 'goal_rule' in fields_set) else ''; rule=client_rule or parsed.get('goal_rule') or 'fixed'
防范: 凡'客户端可选意图参数+服务端推导兜底'配合处, 一律用 model_fields_set 区分显式传入与默认填充（2026-09-09 已验证）

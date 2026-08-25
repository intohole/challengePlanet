---
id: opt-stop-llm-unused-field
title: LLM不产出前端未展示字段(description)削减外部调用成本
summary: 大模型每次调用都是昂贵外部资源, 不输出前端未使用的字段可省token
type: optimization
project: challengePlanet
date: 2026-08-25
tags: [optimization, performance]
scope: project
related: []
---

# LLM不产出前端未展示字段(description)削减外部调用成本

背景: nl-create解析挑战时, PARSE_SYSTEM prompt要求LLM生成description字段, 但前端挑战卡/详情页从未展示description。
决策: 从PARSE_SYSTEM的输出JSON schema与ai_service.parse_challenge_input默认dict中移除description字段, LLM不再生成该字段。
理由: 内部不展示的内容由LLM产出=纯浪费外部调用token(用户画像: 每次LLM调用是昂贵外部资源消耗, 必须极致优化减少无效调用); 字段未被前端消费属于死数据。
做法: 新增任何"会由LLM产出的字段"前必须确认前端是否真的展示; 不展示则移出prompt的JSON schema与默认解析。
验证: 端到端删/del在静态mock下全绿, 后端无description字段后仍正常解析。

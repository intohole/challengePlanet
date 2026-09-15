---
id: feat-insight-on-demand-stream
title: 洞察改为按需生成(打开洞察才跑)并实时流式输出(挑战星球)
summary: 周报洞察原先打卡后每7天后台生成+页面每次load预拉weekly-report(无效LLM+请求)。改为：页面加载零洞察请求；切到洞察tab才POST /challenges/{id}/insight/stream(SSE逐字渲染)；本周内已有缓存直接done(cached)，可force重新生成；生成max_tokens 512→256更简洁；移除打卡自动周报后台任务
type: feature
project: challengePlanet
date: 2026-09-15
tags: [feature, dev, llm-cost]
scope: project
related: [feat-quit-gradient-tally]
---

# 洞察改为按需生成(打开洞察才跑)并实时流式输出

背景: 周报洞察是 LLM 产物，原先打卡每7天/末天后台 fire_and_forget 生成，且首页 load() 每次预拉 /weekly-report——用户不打开洞察也在白白消耗 LLM 与请求
方案: ①进入页面 load() 不再拉 weekly-report；②切到洞察 tab 时 ensureInsight() 自动触发 POST /challenges/{id}/insight/stream；③端点 SSE 流式输出 token 事件(逐字渲染)+done；本周内已有缓存直接 `{"type":"done","cached":true}` 不调 LLM；force=true 强制重生成并落库(ai_insights 插新行，get_latest_weekly 取最新)；④stream_ask(max_tokens=256, prompt 保持≤100字)替代 ask(512)；⑤移除打卡自动周报后台任务(generate_weekly_report_task 及其调用链，防死代码全删)
关键实现: 前端 _weeklyCard 三态(流式中/缓存+重新生成/骨架)；home.js data 加 insightRunning/insightText；ensureInsight guard(insightRunning||weekly)；nexus LLMService.stream_ask 是 AsyncGenerator
验证: 本地 mock e2e 9/9(进入页无weekly请求/切tab触发/流式完成/重新生成force=true)；线上 API 实测 SSE 逐 token 输出84字含①②；二次请求 done cached 不再调LLM；清理冒烟数据后服务健康
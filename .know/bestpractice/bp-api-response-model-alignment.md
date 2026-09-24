---
id: bp-api-response-model-alignment
title: 接口对齐审查必须比对 response_model schema 而非只比对路径
summary: FastAPI response_model 会静默丢弃 schema 未声明的返回字段，服务端一直返回但前端永远 undefined；对齐审查要三方比对 路由路径/schema 字段/前端读取字段
type: bestpractice
project: challengePlanet
date: 2026-09-24
tags: [bestpractice, pattern]
scope: project
related: []
---

# 接口对齐审查必须比对 response_model schema 而非只比对路径

## 场景
前后端接口对齐审查(宣称"路径全对上"却仍有字段错位)时。
## 做法
比对三层而非只看路径：①路由路径 ②后端 response_model schema 声明字段 ③前端实际读取字段。服务层 build 出的 dict 若不在 schema 中声明，会被 pydantic 静默剥离。
## 原因
challengePlanet 实测：TodayTaskResponse 缺 repeatable/not_started 声明、CheckInResponse 缺 status 声明，service 一直返回这三个字段，前端 `!!t.repeatable`、`c.status`、`t.not_started` 恒 undefined，逻辑走 fallback 分支多年无感。修复=补 schema 声明(1行)后前端立刻生效。
## 反例
只看"前端调用的 URL 都 200"就判定对齐完成；或反向改前端适配(丢掉后端口径)，导致同一语义两套 truth。
## 验证
HTTP 层断言: /today 返回 not_started/repeatable 字段、/checkins 返回 status；补声明前断言均失败。

---
id: adr-challenge-end-delete
title: 挑战结束/删除方案：软删保留战绩+0记录真删
summary: 有打卡记录挑战
type: architecture
project: challengePlanet
date: 2026-08-25
tags: [architecture, design]
scope: project
related: []
---

# 挑战结束/删除方案：软删保留战绩+0记录真删

背景: 用户希望在主页删除不再想要的挑战, 但challengePlanet数据(打卡记录)是用户战绩, 直接物理删除会造成不可恢复丢失, 违背"数据极其重要"约束。
方案对比:
1. 纯物理删除: 满足用户"删除"诉求, 但丢失全部打卡记录/战绩, 用户后悔无法恢复
2. 纯软删(status=ended): 数据安全, 但挑战仍占用列表且无法清理误建的无意义挑战
3. 结束+真删(选定): 按打卡记录数分派——有记录(completed_days>0)→软删为ended保留战绩不在首页展示; 0记录/从未开始的挑战→物理级联删除并清理所有关联表
决策理由: 平衡"用户删除诉求"与"战绩数据安全"; 有战绩的挑战是用户努力成果应留存(结束后可重新开始), 空壳挑战无价值可安全清除; 单条SQL按挑战id级联清理CheckIn/SubGoal/AIInsight/StreakAction/ChallengeMeta/AdaptiveSuggestion, 避免残留脏数据
影响: 前端me.js挑战行按completed_days渲染旗子(结束)/垃圾桶(删除)图标, 点击先confirm再调 DELETE /api/v1/challenges/{id}; 后端根据记录数返回{deleted,status,message}
遗留: 软删为ended的挑战不可恢复为active(如需可后续加"重新开始"通过复制或状态迁移支持)

---
id: bp-prompt-prefix-cache-order
title: prompt 静态段在前动态段在后以命中前缀缓存
summary: system 内把心情/场景等动态段放在静态基础段之前会让整段 system 缓存失效；正确排列是静态基础段+动态段，user 消息内也按挑战稳定字段→当次变化字段排序
type: bestpractice
project: challengePlanet
date: 2026-09-24
tags: [bestpractice, pattern]
scope: project
related: []
---

# prompt 静态段在前动态段在后以命中前缀缓存

## 场景
同一任务类型的 prompt 会被高频重复调用(打卡反馈、陪伴话术、预测解读)，希望命中模型侧前缀缓存降本提速。
## 做法
system = 静态基础段(规则/语言规范/结构) + 动态段(按心情拼接的差异块)；user = 挑战级稳定字段(标题/总天数/方向/目标) → 当次变化字段(第几天/心情/本次值/心得/记忆)。动态事实只放事实，指令留在静态段。
## 原因
前缀缓存按最长公共前缀命中，动态段前置会把公共前缀砍到 0；challengePlanet 原实现 `get_mood_aware_prefix(mood) + FEEDBACK_SYSTEM` 恰好把最长的静态段推到动态段之后。同时原本把"这个时段对你特别难/没关系记录本身就是进步"等指令同时写在 system 与 user 尾部(重复 2 份)，改为 user 只给事实(本次已超过软目标)后 prompt 更短。
## 反例
把待办、时间戳、随机 id 塞在 prompt 开头；在每个分支里复制一份完整规则文本。
## 验证
调整后同心情段缓存可复用静态前缀；打卡反馈/陪伴/周报等调用点的 system 常量未变，sanitize_coach_text 回显检测仍通过。

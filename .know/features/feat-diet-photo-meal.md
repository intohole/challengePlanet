---
id: feat-diet-photo-meal
title: 减重场景: 拍照识别这一餐热量 + 每餐记一笔累计摄入
summary: 饮食记录从"一句话描述全天"升级为"每餐记一笔": 拍照经视觉网关(nexus.vision, GLM-4.6V)认出食物与份量并估算这一餐热量, 前端canvas压缩为dataURL直传, 记账后今日摄入=各餐之和并按累计量评估是否在目标区间; 视觉与文字两条入口共用同一响应结构
type: feature
project: challengePlanet
date: 2026-09-28
tags: [feature, dev]
scope: project
related: [bp-forecast-scope-and-quiet]
---

# 减重场景: 拍照识别这一餐热量 + 每餐记一笔累计摄入

需求
用户反馈"卡路里场景适合拍照: 拍照识别食物→算出卡路里"。原饮食流程要求一次性描述全天饮食再提交一条全天总量, 与"拍一张照片就能记一餐"的使用方式冲突。

方案
1. 拍照链路(零存储): 前端 input[capture=environment] 选拍 → canvas 压到最长边1280/JPEG 0.82 的 dataURL → POST /diet/estimate {image} → `nexus.get_vision_service().review(DIET_VISION_SYSTEM, prompt, data_url)` → 严格JSON(总热量+食物明细+置信度) → 复用 AIService._normalize_diet_result 归一。文字入口保持原 LLM 路径, 两条入口返回同一结构
2. 每餐一笔(复用事件流水范式): goal_rule_service.is_repeatable 增加 diet → 同一挑战当日可多笔; checkin 的 value=这一餐热量; 今日摄入=当日各笔之和; 完成度与"是否超量"按**累计量**评估(assess_calorie(prior+value, target)); 前端结果卡展示"这一餐约X千卡 · 今日累计 / 目标 · 还可吃/超出"; 今日饮食记录列表可逐笔撤销
3. 边界: 图片超过 6M 字符(base64)直接400; 视觉调用失败明确报"照片识别失败, 请重试或直接描述"(不做静默兜底); diet 场景不参与节奏预测(见 bp-forecast-scope-and-quiet)
4. 样式: 补齐此前完全缺失的 cp-diet-* 样式(饮食面板/拍照入口/结果卡/餐次列表), 移动端 flex 自适应

关键代码
- app/services/diet_service.py: estimate_calories(challenge, description, image, today_intake) / normalize_image
- app/services/ai_service.py: estimate_diet_calories_from_photo
- app/services/prompts.py: DIET_VISION_SYSTEM(份量识别+常见热量参考表)
- app/api/diet.py + schemas/diet.py: image 入参, 返回 meal_kcal/today_intake
- app/services/checkin_service.py: diet 累计口径(completion_pct/soft_exceeded 用 prior+value)
- static/js/views/home-diet.js: _compressImage/onDietPhoto/_runDietEstimate/_dietMeals

验证
tests/e2e_diet.py 39例(拍照返回这一餐热量/累计评估/多笔不重放/撤销后累计回落/饮食不做预测)、tests/e2e_diet_view.py 23例(拍照file→dataURL上传→结果渲染); 线上用工作区生图网关生成餐食照片实测: 识别"白米饭一大碗200+红烧肉250+可乐150=620千卡(置信0.9)", 两餐累计1220/1905

遗留
单餐可含多道菜但不拆分餐次(早/午/晚)标签; 照片不落盘(仅识别不存档)
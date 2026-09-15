---
id: bug-quit-create-binary
title: 戒断(戒烟)模板创建仍产出 binary「已完成」，未走一根一点记账
summary: 前端创建管线三处 bug 叠合导致戒烟挑战变每日打卡：quit 场景默认 task_type=binary；create-direct.js/create.js/playMode/ladderDir 用 scene.task_type==='quit' 判定永不命中（应为 scene.id）致 direction 恒 increase；直接创建跳过「当前每天/目标每天」梯度输入且 ladder 全 0。修复=quit 场景改 counter/根、scene.id 判定、step1 增加数量面板、confirmCreate/confirmDirect 强制 counter+decrease+soft+ladder
type: bug
project: challengePlanet
date: 2026-09-15
tags: [bug, fix]
scope: project
related: [feat-quit-gradient-tally, bug-cap-mode-auto-judge, bug-count-tally-unify]
---

# 戒断(戒烟)模板创建仍产出 binary「已完成」，未走一根一点记账

报错现象: 首页点「戒烟挑战」模板 → 直接创建/AI生成 → 打卡页只有「今日完成/今日已完成」按钮，与「抽一根记一根、系统自动记账」产品语义完全不符；DB 实测 challenge(戒烟挑战)=binary|increase|fixed|hard|unit=次
根因分析: ①`app.js` cpScenes.quit `task_type:'binary'`（后端 scene_service 同为 binary，只 servir AI hint，非直接 create 真源）；②create-direct.js L62 / create.js confirmCreate / playMode / create-extra.ladderDir 一律 `scene.task_type==='quit'` 判定，而 quit 场景 task_type 是 binary→判定永不命中→direction=increase；③confirmDirect 直接创建绕过「当前每天/目标每天」阶梯输入，ladder 参数全 0、goal_rule=fixed；④AI 路径 confirmCreate 被 `p.goal_rule||'fixed'` 兜死不读表单已填梯度
修复方法: ①quit 场景 task_type=counter、unit=根，模板文案「抽一根记一根」；②所有 quit 判定改 `scene.id==='quit'`，quit direction 强制 decrease；③create 页 step1 增加 quit 数量面板（当前每天/目标每天/每隔/每次递减），`applySceneLadder` 在 open() 时应用(interval=1/step=1)；④`canDirect()` quit 需 ladderStart>0；⑤confirmDirect/confirmCreate 对 quit 强制 task_type=counter、direction=decrease、goal_type=soft、goal_rule=ladder、goal_mode=ceiling、unit=根，ladder_start/goal 从表单/parsed 取值，未填当前每天则前端拦截（error 文案）；⑥syncLadder 对 quit 不回退已填梯度；⑦「记一根」按钮文案按 scene_template==='quit'
防范: 场景判定一律用 scene.id 而非 scene.task_type（task_type 是产物不是身份）；创建参数必须「表单态 > LLM parsed > 场景默认」而非「LLM parsed 默认值吞表单」；bump 指纹 v=20260915a
验证: tests/verify_quit_create.js(node) 全过：open 默认梯度、canDirect 拦截、buildPlan counter/根/20、confirmDirect/AI confirm 输出 counter+decrease+ladder+soft 参数正确、reading 等场景不受影响
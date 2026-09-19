# bestpractice Index
> Total: 6 entries

- bp-context-gated-prediction | 把用户填写的可选情境(context_tag)用于预测时, 数据必然稀疏; 必须用样本量门槛保护: 主导情境需≥3次才展示, 条件模式需≥2天且差异≥1.5倍才输出, 否则静默省略。原则是宁可不说, 不可瞎猜——预测一旦被用户发现不准, 信任崩塌 | 2026-09-19
- bp-forecast-forward-looking | 多数预测其实是回溯外推(用已发生的数据推算今日终值), 仍在描述过去; 真正前瞻是回答接下来什么时候危险/状态最好。做法: 在小时分布中取当前时刻之后权重最高且连续的时段作为前瞻窗口, 文案走被理解感(这段对你来说最难)而非评判, 且样本不足(置信度<0.45)时不出窗口避免瞎猜 | 2026-09-19
- bp-forecast-trust-calibration | 【2026-09-19 认知纠正】原以为给区间(±)才可信, 实际做错:预警不是报表, 用户要的是一眼看懂+立刻行动而非统计精度。正确做法=单个预计数字(整数)+一句依据+定性把握(高/中/低)。区间只在真正做分析的产品里才需要 | 2026-09-19
- bp-minideploy-master-api | master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03 | 2026-08-27
- bp-predictive-push-alert | 预测不只在页面上展示,还要主动送达: 扫描活跃对象→预测风险(risk_level≥1)→复用统一通知中间件推送; 关键三条: 预警时间设在行为高峰之前(如18:30预警20:00后的风险窗口)、按对象+日期去重防打扰、文案直接用预测里最可行动的那句(优先coach_nudge兜底risk_window_msg) | 2026-09-19
- bp-single-focal-data-card | 数据密集卡片(仪表盘)打磨三步: ①先查重复渲染(同一指标被两个函数各画一遍,如进度条) ②立一个签名可视化承载核心判断(如节奏轨:已记填充+上限刻度+预计标记同轨,一眼看出是否会超) ③建立三层信息梯度(关键指标16px > 可行动提示12px主色 > 元信息12px muted+chip), 状态用色只在标记上而非卡片底 | 2026-09-19

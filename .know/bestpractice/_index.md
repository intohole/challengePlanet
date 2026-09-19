# bestpractice Index
> Total: 3 entries

- bp-forecast-forward-looking | 多数预测其实是回溯外推(用已发生的数据推算今日终值), 仍在描述过去; 真正前瞻是回答接下来什么时候危险/状态最好。做法: 在小时分布中取当前时刻之后权重最高且连续的时段作为前瞻窗口, 文案走被理解感(这段对你来说最难)而非评判, 且样本不足(置信度<0.45)时不出窗口避免瞎猜 | 2026-09-19
- bp-forecast-trust-calibration | 预测功能要可信必须三要素齐全: 给区间而非单点(置信度越高区间越窄)、给一句依据文案(用户知道为什么)、给置信度; 并用预测快照落库→次日比对实际→自适应bias形成校准闭环, 让预测随数据积累变准 | 2026-09-19
- bp-minideploy-master-api | master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03 | 2026-08-27

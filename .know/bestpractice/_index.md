# bestpractice Index
> Total: 2 entries

- bp-forecast-trust-calibration | 预测功能要可信必须三要素齐全: 给区间而非单点(置信度越高区间越窄)、给一句依据文案(用户知道为什么)、给置信度; 并用预测快照落库→次日比对实际→自适应bias形成校准闭环, 让预测随数据积累变准 | 2026-09-19
- bp-minideploy-master-api | master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03 | 2026-08-27

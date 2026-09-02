# Knowledge Index
> Project: challengePlanet | Updated: 2026-08-27 | Total: 6 entries

## architecture
- adr-challenge-end-delete | 有打卡记录挑战 | 2026-08-25
- adr-notify-email-channel-boundary |  | 

## bestpractice
- bp-minideploy-master-api | master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03 | 2026-08-27

## bugs
- bug-cp-e2e-selectors | 根因: 登录页已迁移nexus-ui(nux-input/nux-login-submit), 旧.cp-login-input不存在; SPA站点reload禁用networkidle会永超时, 用domcontentloaded+等待appState.booted | 2026-08-27

## features
- feat-reminder-aggregate |  | 

## optimization
- opt-stop-llm-unused-field | 大模型每次调用都是昂贵外部资源, 不输出前端未使用的字段可省token | 2026-08-25

# Knowledge Index
> Project: challengePlanet | Updated: 2026-09-11 | Total: 12 entries

## architecture
- adr-challenge-end-delete | 有打卡记录挑战 | 2026-08-25
- adr-notify-email-channel-boundary |  | 

## bestpractice
- bp-minideploy-master-api | master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03 | 2026-08-27

## bugs
- bug-checkin-manual-vs-auto | text类型空reflection也可达标、step主按钮绕过勾选清单、doMultiCheckin用checked_in拦截致未达标无法追加，三处与「系统按记录判断」相悖，统一修复 | 2026-09-11
- bug-cp-e2e-selectors | 根因: 登录页已迁移nexus-ui(nux-input/nux-login-submit), 旧.cp-login-input不存在; SPA站点reload禁用networkidle会永超时, 用domcontentloaded+等待appState.booted | 2026-08-27
- bug-pydantic-default-overrides | 根因: NLCreateRequest.goal_rule=Field(fixed), 路由用 request.goal_rule or parsed.goal_rule, 客户端未传时默认值永远优先, 把 LLM/正则推导的 ladder 覆盖成 fixed; 修复: 用 model_fields_set 判断显式传入, 仅显式优先, 推导兜底 | 2026-09-09
- bug-word-checkin-settlement | 刷词模式手动提交value=1而word目标=20致is_settled永不达标，根因是打卡值与目标脱钩；改为刷完词卡按当日词量自动打卡结算，词卡会话内Fisher-Yates打乱 | 2026-09-11

## features
- feat-period-sport-dual-goal | 打卡域抽象收归：Judge窗口化+Metric派生+Target周排程，运动/阅读计时自动记录、周目标独立判定、MET自动折算千卡 | 2026-09-11
- feat-quit-gradient-tally | 产品范式: 用户设定 当前每天量→目标每天量, 系统按天数自动生成每日递减配额曲线; 用户只点我抽了一根(+1), 系统自动累计当日用量对比配额, 超限温和提醒不惩罚, 误点可撤销; 数值参数用确定性正则提取, LLM 仅承担语义理解 | 2026-09-09
- feat-reminder-aggregate |  | 

## optimization
- opt-stop-llm-unused-field | 大模型每次调用都是昂贵外部资源, 不输出前端未使用的字段可省token | 2026-08-25

## refactor
- rf-checkin-review-fixes | 评审发现的可见路径错误与配置死字段全部修复并回归通过 | 2026-09-11

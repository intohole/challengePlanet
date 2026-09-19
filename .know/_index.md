# Knowledge Index
> Project: challengePlanet | Updated: 2026-09-19 | Total: 20 entries

## architecture
- adr-challenge-end-delete | 有打卡记录挑战 | 2026-08-25
- adr-notify-email-channel-boundary |  | 

## bestpractice
- bp-forecast-trust-calibration | 预测功能要可信必须三要素齐全: 给区间而非单点(置信度越高区间越窄)、给一句依据文案(用户知道为什么)、给置信度; 并用预测快照落库→次日比对实际→自适应bias形成校准闭环, 让预测随数据积累变准 | 2026-09-19
- bp-minideploy-master-api | master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03 | 2026-08-27

## bugs
- bug-cap-mode-auto-judge | counter/timer+decrease（cap型上限目标）场景下，每日完成与否应以「当日已记量 vs 当日上限」自动判定：1)主CTA的「守住今日/今日完成」会提交value=0空声明，把完成判定丢回用户记忆；2)settled当天按total<=cap运行中翻True/False横跳；3)completed_days=len(checkins)一根烟算一天；4)零记录好日子streak断签。统一收敛为cap-mode：当天不判定、次日零点按cap自动判定（含零记录=守住），超限日=断签 | 2026-09-11
- bug-checkin-manual-vs-auto | text类型空reflection也可达标、step主按钮绕过勾选清单、doMultiCheckin用checked_in拦截致未达标无法追加，三处与「系统按记录判断」相悖，统一修复 | 2026-09-11
- bug-count-tally-unify | counter/timer（递增）主按钮完成今日目标会提交 target-today_total 补齐差额造假；companion_phase/诊断天数/周报完成率用 len(checkins)条数当天数；递减目标超限单笔completion_pct<100扣积分，与超限不惩罚矛盾。统一为：定量记录类一律记一笔+系统自动判定达标，天数字面全走distinct days，递减单笔恒100 | 2026-09-11
- bug-cp-e2e-selectors | 根因: 登录页已迁移nexus-ui(nux-input/nux-login-submit), 旧.cp-login-input不存在; SPA站点reload禁用networkidle会永超时, 用domcontentloaded+等待appState.booted | 2026-08-27
- bug-pydantic-default-overrides | 根因: NLCreateRequest.goal_rule=Field(fixed), 路由用 request.goal_rule or parsed.goal_rule, 客户端未传时默认值永远优先, 把 LLM/正则推导的 ladder 覆盖成 fixed; 修复: 用 model_fields_set 判断显式传入, 仅显式优先, 推导兜底 | 2026-09-09
- bug-quit-create-binary | 前端创建管线三处 bug 叠合导致戒烟挑战变每日打卡：quit 场景默认 task_type=binary；create-direct.js/create.js/playMode/ladderDir 用 scene.task_type===quit 判定永不命中（应为 scene.id）致 direction 恒 increase；直接创建跳过「当前每天/目标每天」梯度输入且 ladder 全 0。修复=quit 场景改 counter/根、scene.id 判定、step1 增加数量面板、confirmCreate/confirmDirect 强制 counter+decrease+soft+ladder | 2026-09-15
- bug-word-checkin-settlement | 刷词模式手动提交value=1而word目标=20致is_settled永不达标，根因是打卡值与目标脱钩；改为刷完词卡按当日词量自动打卡结算，词卡会话内Fisher-Yates打乱 | 2026-09-11

## features
- feat-detect-plan-deterministic | 原 nl-create 让 LLM 流式生成66天完整计划JSON(PLAN_SYSTEM 数千token/数十秒)；改为一次结构化解析(参数+description≤30字产品文案)→plan_builder纯函数合成逐日计划(ladder递减目标/难度梯度/里程碑日/场景steps)→apply_numeric_adjust正则处理调整。LLM调用从2次降到1次short JSON，token/耗时大幅下降，数值完全可控 | 2026-09-15
- feat-forecast-prediction | 预测三层收归: NudgeService(纯函数确定性预测,星期权重/区间置信度/依据文案/increase达标时刻/ladder终点展望) + ForecastService(编排+回测校准闭环) + 前端节奏仪表盘; 零LLM, 预测带依据才可信, 回测校准形成数据飞轮 | 2026-09-19
- feat-insight-on-demand-stream | 周报洞察原先打卡后每7天后台生成+页面每次load预拉weekly-report(无效LLM+请求)。改为：页面加载零洞察请求；切到洞察tab才POST /challenges/{id}/insight/stream(SSE逐字渲染)；本周内已有缓存直接done(cached)，可force重新生成；生成max_tokens 512→256更简洁；移除打卡自动周报后台任务 | 2026-09-15
- feat-period-sport-dual-goal | 打卡域抽象收归：Judge窗口化+Metric派生+Target周排程，运动/阅读计时自动记录、周目标独立判定、MET自动折算千卡 | 2026-09-11
- feat-quit-gradient-tally | 产品范式: 用户设定 当前每天量→目标每天量, 系统按天数自动生成每日递减配额曲线; 用户只点我抽了一根(+1), 系统自动累计当日用量对比配额, 超限温和提醒不惩罚, 误点可撤销; 数值参数用确定性正则提取, LLM 仅承担语义理解 | 2026-09-09
- feat-reminder-aggregate |  | 

## optimization
- opt-stop-llm-unused-field | 大模型每次调用都是昂贵外部资源, 不输出前端未使用的字段可省token | 2026-08-25

## refactor
- rf-checkin-review-fixes | 评审发现的可见路径错误与配置死字段全部修复并回归通过 | 2026-09-11
- rf-checkin-review-round2 | 运动类型强制转计时模式解除计数场景千卡死锁，秒表失败续走表，period_days前端可配 | 2026-09-11

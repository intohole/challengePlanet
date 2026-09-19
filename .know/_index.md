# Knowledge Index
> Project: challengePlanet | Updated: 2026-09-19 | Total: 25 entries

## architecture
- adr-challenge-end-delete | 有打卡记录挑战 | 2026-08-25
- adr-notify-email-channel-boundary |  | 

## bestpractice
- bp-context-gated-prediction | 把用户填写的可选情境(context_tag)用于预测时, 数据必然稀疏; 必须用样本量门槛保护: 主导情境需≥3次才展示, 条件模式需≥2天且差异≥1.5倍才输出, 否则静默省略。原则是宁可不说, 不可瞎猜——预测一旦被用户发现不准, 信任崩塌 | 2026-09-19
- bp-forecast-forward-looking | 多数预测其实是回溯外推(用已发生的数据推算今日终值), 仍在描述过去; 真正前瞻是回答接下来什么时候危险/状态最好。做法: 在小时分布中取当前时刻之后权重最高且连续的时段作为前瞻窗口, 文案走被理解感(这段对你来说最难)而非评判, 且样本不足(置信度<0.45)时不出窗口避免瞎猜 | 2026-09-19
- bp-forecast-trust-calibration | 【2026-09-19 认知纠正】原以为给区间(±)才可信, 实际做错:预警不是报表, 用户要的是一眼看懂+立刻行动而非统计精度。正确做法=单个预计数字(整数)+一句依据+定性把握(高/中/低)。区间只在真正做分析的产品里才需要 | 2026-09-19
- bp-minideploy-master-api | master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03 | 2026-08-27
- bp-outlook-answer-user-question | 预测文案最大的坑不是措辞难懂, 而是回答了错的问题。我的阶梯预测按现在的水平,结束时约18根,离目标还差17根被用户说看不懂——根因是它把当前量直接外推为终值, 完全忽略了阶梯计划本身(系统每天在下调上限), 等于说你的习惯永远不会降; 又拿当前量比最终目标, 只给恐慌不给信息。正确做法: 先问用户此刻真正想知道什么, 再设计指标。阶梯用户想知道的是我有没有跟上计划, 所以应对比实际 vs 计划上限, 而不是实际 vs 最终目标 | 2026-09-19
- bp-predictive-push-alert | 预测不只在页面上展示,还要主动送达: 扫描活跃对象→预测风险(risk_level≥1)→复用统一通知中间件推送; 关键三条: 预警时间设在行为高峰之前(如18:30预警20:00后的风险窗口)、按对象+日期去重防打扰、文案直接用预测里最可行动的那句(优先coach_nudge兜底risk_window_msg) | 2026-09-19
- bp-single-focal-data-card | 数据密集卡片(仪表盘)打磨三步: ①先查重复渲染(同一指标被两个函数各画一遍,如进度条) ②立一个签名可视化承载核心判断(如节奏轨:已记填充+上限刻度+预计标记同轨,一眼看出是否会超) ③建立三层信息梯度(关键指标16px > 可行动提示12px主色 > 元信息12px muted+chip), 状态用色只在标记上而非卡片底 | 2026-09-19

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

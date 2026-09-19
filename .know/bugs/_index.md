# bugs Index
> Total: 7 entries

- bug-cap-mode-auto-judge | counter/timer+decrease（cap型上限目标）场景下，每日完成与否应以「当日已记量 vs 当日上限」自动判定：1)主CTA的「守住今日/今日完成」会提交value=0空声明，把完成判定丢回用户记忆；2)settled当天按total<=cap运行中翻True/False横跳；3)completed_days=len(checkins)一根烟算一天；4)零记录好日子streak断签。统一收敛为cap-mode：当天不判定、次日零点按cap自动判定（含零记录=守住），超限日=断签 | 2026-09-11
- bug-checkin-manual-vs-auto | text类型空reflection也可达标、step主按钮绕过勾选清单、doMultiCheckin用checked_in拦截致未达标无法追加，三处与「系统按记录判断」相悖，统一修复 | 2026-09-11
- bug-count-tally-unify | counter/timer（递增）主按钮完成今日目标会提交 target-today_total 补齐差额造假；companion_phase/诊断天数/周报完成率用 len(checkins)条数当天数；递减目标超限单笔completion_pct<100扣积分，与超限不惩罚矛盾。统一为：定量记录类一律记一笔+系统自动判定达标，天数字面全走distinct days，递减单笔恒100 | 2026-09-11
- bug-cp-e2e-selectors | 根因: 登录页已迁移nexus-ui(nux-input/nux-login-submit), 旧.cp-login-input不存在; SPA站点reload禁用networkidle会永超时, 用domcontentloaded+等待appState.booted | 2026-08-27
- bug-pydantic-default-overrides | 根因: NLCreateRequest.goal_rule=Field(fixed), 路由用 request.goal_rule or parsed.goal_rule, 客户端未传时默认值永远优先, 把 LLM/正则推导的 ladder 覆盖成 fixed; 修复: 用 model_fields_set 判断显式传入, 仅显式优先, 推导兜底 | 2026-09-09
- bug-quit-create-binary | 前端创建管线三处 bug 叠合导致戒烟挑战变每日打卡：quit 场景默认 task_type=binary；create-direct.js/create.js/playMode/ladderDir 用 scene.task_type===quit 判定永不命中（应为 scene.id）致 direction 恒 increase；直接创建跳过「当前每天/目标每天」梯度输入且 ladder 全 0。修复=quit 场景改 counter/根、scene.id 判定、step1 增加数量面板、confirmCreate/confirmDirect 强制 counter+decrease+soft+ladder | 2026-09-15
- bug-word-checkin-settlement | 刷词模式手动提交value=1而word目标=20致is_settled永不达标，根因是打卡值与目标脱钩；改为刷完词卡按当日词量自动打卡结算，词卡会话内Fisher-Yates打乱 | 2026-09-11

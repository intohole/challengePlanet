# bugs Index
> Total: 6 entries

- bug-count-tally-unify | counter/timer 统一记账台（去掉补齐式声明）、companion/诊断/周报天数收敛为distinct days、递减超限单笔恒100不扣积分 | 2026-09-11
- bug-cap-mode-auto-judge | 戒断计数（戒烟一根一点）完成判定收敛：cap-mode（decrease+counter/timer）每日完成按「当日记录 vs 上限」自动判定，去掉守住今日声明；completed_days按天数；零记录日=守住 | 2026-09-11
- bug-checkin-manual-vs-auto | text类型空reflection也可达标、step主按钮绕过勾选清单、doMultiCheckin用checked_in拦截致未达标无法追加，三处与「系统按记录判断」相悖，统一修复 | 2026-09-11
- bug-cp-e2e-selectors | 根因: 登录页已迁移nexus-ui(nux-input/nux-login-submit), 旧.cp-login-input不存在; SPA站点reload禁用networkidle会永超时, 用domcontentloaded+等待appState.booted | 2026-08-27
- bug-pydantic-default-overrides | 根因: NLCreateRequest.goal_rule=Field(fixed), 路由用 request.goal_rule or parsed.goal_rule, 客户端未传时默认值永远优先, 把 LLM/正则推导的 ladder 覆盖成 fixed; 修复: 用 model_fields_set 判断显式传入, 仅显式优先, 推导兜底 | 2026-09-09
- bug-word-checkin-settlement | 刷词模式手动提交value=1而word目标=20致is_settled永不达标，根因是打卡值与目标脱钩；改为刷完词卡按当日词量自动打卡结算，词卡会话内Fisher-Yates打乱 | 2026-09-11

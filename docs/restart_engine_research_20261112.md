# 回流重启引擎深研——业界已验证 vs 本项目现状（r27 定案底稿）

2026-11-12 · deep-research 4 轮检索 · 生产取证 edge-04 challenge.db + journalctl

## 生产实锤（机会点）

1. **lxz 今晨回流 17 秒不转化**：11-12 08:33:39 打开 app（recall-track.js 拉取）→回归卡渲染上报（recall_events seen 段 uid=2 真命中，全史第 2 条）→一次 LLM 调用→08:33:56 离开。**零打卡 API 调用**。上一条 seen=10-26 20:18 同样零打卡。**回流→当日打卡转化 0/2**。
2. **不可能任务量化**：ch101（戒断阶梯 12→3，10-09 起步，10-14 换挡+2）阶梯毕业日 10-29 已过（缺席中），今日日历 cap=**3 根**；他缺口前最后记录（10-16）=7 根且守住（≤9）。缺席 27 天回来第一眼的任务是「上限 3 根」=上次真实量的 43%。
3. **身份双轨矛盾**：触达面 11-04 发「毕业证书在等你」、11-11 发 REVIVE「门一直开着」（gate 日志实锤）；app 内 status=active（end_date 12-13 未到）任务卡照跑「今天上限 3 根」。回归用户同时收到四个矛盾指令。
4. **adaptive_suggestions 全史 0 行**：唯一触发链 evaluate_after_bad_mood_task 条件=连续 2 条 mood=bad，生产 mood 填充率 1/23→触发条件结构性不可达→引擎 26 轮空转（表+模型+service 全在，产出恒零）。

## 业界差距表

| 业界模式 | 代表/证据 | 本项目现状 | 判定 |
|---|---|---|---|
| recommit 重启：reset 锚点但保留终身累计 | Smoke Free「Change Smoking Data」改 quit date；quitSTART「recover from slips」（CDC/NIH） | r26 revive 只覆盖 resting 态；active 缺席中（本例）无重启通道，日历 cap 原样继续 | P0 缺口 |
| revival 交换：用一次当下可完成的小挑战换回全部历史 | Duolingo Streak Revival（2025-06 起，≥30 天历史回归者单次会话 3 课复活 streak） | 无。micro_target=cap 的 1/5（1 根）与阶梯脱钩，完成它不改变「明天 cap 还是 3」 | P0 缺口 |
| AVE 缓冲：非审判框架+保留成就；抹进度触发复发雪崩 | Marlatt & Gordon 复发模型；Gowarty 2021（QuitGuide/quitSTART 可用性） | r18 反 AVE 文案在；但「毕业推送 vs 上限 3 根任务卡」双轨=结构性 AVE 触发器 | P0 缺口 |
| comeback 庆祝：庆祝回归本身，衡量回来速度而非 streak 长度 | Nudge comeback badge/Kintsu「Your comeback does」/NonZero comeback metrics | 回归卡有「走过的天都算数」无庆祝动作 | P1 |
| fresh start 时标：时标给「重置许可」 | Dai/Milkman/Riis 2014（Management Science） | 「回来第 N 天」已有雏形未接结构性重置 | 已有半边 |
| 渐进难度重入：生成 smaller restart 计划而非原难度 | Discy AI smaller restart/Aavni PM win-back 案例 | 无，ai_plan 原计划照跑 | 同 P0 |

Sources: smokefreeapp.com/faq · smokefree.gov/tools-tips/quitstart · PMC8295834 · duolingo.com/streak-revival（Fast Company/CNET 报道）· Dai et al. 2014 · gamification meta（tobaccoinduceddiseases.org）

## 定案（产品三问）

- **核心痛点**：戒断/减量人群「破戒/失踪→回来→面对做不到的进度→再逃走」循环。lxz 是活样本。
- **能力怎么解决它**：回归第一屏从「今天上限 3 根」变成「重启方案：离开 27 天，阶梯按日历走到了 3 根——太陡了。上次你守在 7 根，从 7 根重新出发？走过的一天都算数」。一键接受→阶梯重锚（cap 从 7 重新递减，毕业日重算 8 天后），可完成度结构性质变。
- **鸡肋下刀**：mood 连续 bad 减负触发链（生产 26 轮零产出+输入面结构性枯竭）当轮退役；AdaptiveSuggestion 表复用为重启建议承载（kind="restart"）。

## 技术定案

- **重锚单源**：`goal_rule_service.ladder_cap_with` 叠加 restart anchor（challenges.ladder_restart 新列，`_ensure_column` 幂等迁移）：day≥anchor_day 后以 anchor 日为新 day 1、anchor.cap 为新 start 走原 interval/step；anchor 前曲线字节级不变；`ladder_goal_day` 同函数族自动重算毕业日——today 卡/reminder 上限/slip 判定/进度/毕业判定全链一处生效。
- **建议引擎**：`adaptive_service.evaluate_restart_on_return` 纯确定性（不上 LLM，遵守「数据薄不上模型」纪律）：restart_cap=缺口前最近一次记录值（clamp ≤ladder_start）；幂等=pending 在场跳过+同 episode 已答复不再问。
- **接受动作**：复用 AdaptiveSuggestion.respond 通道扩 kind="restart" 分支——写 ladder_restart 列，曲线立即生效。
- **回归窗**：gap≥7 才出重启建议（短缺口回归卡 micro_target 已够用，10-14 回流案例佐证）；建议有效期=回归窗 3 天。

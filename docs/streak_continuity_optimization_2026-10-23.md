# 断签继续机制深度优化方案（2026-10-23）

> 定位：断签宽容是本产品的护城河而非漏洞，不动摇。本轮优化目标是把「允许继续」升级为「可控的动机系统」：
> 宽容不流失（触达治理）· 回流有承接（fresh start）· 凭证不通胀（毕业保真）。

## 一、现状事实（代码盘点）

- 挑战无失败态：断签不关闭挑战，回来直接继续；当前 streak 清零但历史保留 last_streak（`streak_service.py:36-48`）
- 四层宽限：补签（月 2 免费超 50 分）、冻结（周 1 免费超 20 分）、修复（昨日断日免费）、里程碑护盾 7/14/30/66 天各+1（`mercy_service.py`、`shield_service.py`）
- 断签触达三通道：rescue 分级（≤1 静默/3 首发/4-6 隔日/≥7 每周二五）、absence care（≥2 天）、slip care（`rescue_service.py:22-48`）
- 诚实披露在位：救援卡"断了N天"、静默守披露、AI 报告写中断、提示词禁评判词
- 毕业只看日历：`day_number >= goal_day`，与行为密度无关（`challenge_service.py:132-149`）→ 凭证可能低密度毕业
- **触达治理轮子全空白**：nexus.touch / notifyCenter read-status / scheduler_gate / KeyedRateLimiter 均未接入；`main.py:100` 裸调 `scheduler.start()`（auto 不设防，LifeCompass r8 判例的隐患形态）
- 已接：nexus.audience、nexus.notify、nexus.scheduler；自有四段召回漏斗（recall_service，工作区最完整）

## 二、外部研究结论

| 主题 | 结论 | 来源 |
|---|---|---|
| Duolingo streak | freeze 须提前装备（保险非事后）；用后连续回流会回填 freeze（奖励恢复行为本身）；repair 限 48h；streak 使日留存翻倍，freeze 是"防永久流失"的强化层 | Duolingo Help/Blog、Deconstructor of Fun |
| 行业宽容派 | Finch 温和 check-in 被誉；Loop Habit Tracker 用户呼吁 skip day 不破链；羞辱式清零伤留存 | everyday.app、Productive Fish、uhabits#88 |
| 行为科学 | never miss twice：错过一次是意外，回应方式决定习惯存亡；relapse prevention：单次 lapse 的解读（abstinence violation effect）预测长期维持 | Atomic Habits、Melemis |
| fresh start effect | 时间地标创造"新心理账户期"把过去失败归入过去，因果证据充分；适用于 app 回流动线（NN/g） | Dai/Milkman/Wharton 2014/2015、NN/g |
| 推送疲劳 | 频率上限+个性化是最一致推荐解法；无上限催促→关通知→永久流失 | Courier、ContextSDK |
| 中文产品 | 契约金返现模式（薄荷阅读）已被微信治理+退费投诉，行业从"金钱惩罚契约"迁向"社交+权益激励"；微信读书挑战赛按周期分档返权益 | 人人都是产品经理、微信治理公告 |

反面观点（已收录）：Duolingo 徽章被批评为 FOMO/多巴胺操纵——荣誉设计须做加法（奖励高密度）不做减法（不羞辱低密度）。

## 三、工作区可复用轮子（不重复造轮）

- `nexus.touch`（`nexus/touch/__init__.py`）：内容指纹+五态决策机 SEND/SILENCE/REVIVE/SUNSET，revive 7 天/sunset 30 天诚实退场——正是"≥7 天无限期催促"缺的退场语义。判例：adSmart、codeBlock、truemirror
- notifyCenter read-status（nexus 1.92.1）：未读才升级/重推。范本：travelMate `touch_support.py:60-75`
- `nexus.scheduler_gate`：一行接入（对照 geniusStudent/travelMate/codeBlock）
- `nexus.rate_limit` KeyedRateLimiter：频控兜底。范本：goldenStock touch_service
- 兑现模式：LifeCompass 节点兑现 K/N 三出口（honored=诚实下界）、goldenStock T+5 定格结算+先验——供凭证保真期参考
- 回流首战降门槛：codeBlock variant/hint_ladder 思路（诊断服务已有 micro/lighten3 可复用）
- 凭证展示：truemirror share_page OG 模式 + 自有 share_service 数据
- 凭证类无现成轮子，需新建但积木齐全

## 四、发散记录（SCAMPER，12 项收敛前）

1. 回流首战降配（S）2. 断签徽标→回归计数徽标重构框定（S）3. fresh start 回归页+回归小周期（C）4. 预冻结/周计划 freeze（A）5. 修复后连续回流 3 天回填免费卡（A）6. 毕业凭证带质量数据（M）7. 漏斗驱动文案分流 seen≠acted 换道（P）8. nexus.touch 直替+退场语义（E）9. 荣誉毕业做加法（R）10. 频控兜底+调度门禁（卫生）11. 推送↔站内同源钩子（verseCraft 模式）12. 用户自选承诺模式（保守搁置）

## 五、ICE 收敛 Top 3

| 排名 | 方案 | I | C | E | ICE |
|---|---|---|---|---|---|
| 1 | 触达层收归（touch 五态+回执升级+频控+门禁） | 3 | 0.8 | 高 | 2.4 |
| 2 | 回归体验（回归页+回归计数+首战降配+回填） | 3 | 0.8 | 中高 | 2.2 |
| 3 | 毕业凭证保真（荣誉加法+质量数据，先观测后动） | 2 | 0.7 | 中 | 1.4 |

## 六、分期落地

### C0 卫生债（~0.5 天）
- `main.py:100` scheduler_gate `mode="gated"` 一行接入
- KeyedRateLimiter 接 rescue/absence 兜底频控（上游任何回归不再变轰炸）

### C1 触达层收归（~1 天）
- nexus.touch 直替 rescue/absence：内容指纹防重复、REVIVE 7 天"门开着"变体、SUNSET 30 天诚实退场（现状 ≥7 天每周二五无限催促是唯一缺口）
- read-status：未读才升级通道/重推；已读未行动降频换道
- 观测：notifyCenter sent/suppressed、REVIVE/SUNSET 首例、≥7 天催促已读率前后对比

### C2 回归体验（~1.5 天）
- 深链落地"回归页"（?ch=&rc=absence 已存在）：离开 N 天的事实+走过天数都在+今日最小动作（诊断服务 micro/lighten 降配）+回归第 N 天计数
- 徽标重构：⚡断N天 → 回流后显示「回来第 N 天」（同一数据，正向框定，abstinence violation effect 对冲）
- 回填机制：修复/回流后连续 3 天打卡回赠一张免费补签卡（Duolingo 回填模式，奖励恢复行为）

### C3 凭证保真（先观测后动，0.5 天观测+按需实现）
- 先拉数：①毕业样本有效密度分布（通胀是否实锤）②断签回流者后续 7 日打卡率 vs 连续者（宽容是否在救行为）
- 数据支持再动：荣誉毕业（密度 ≥80% 凭证加荣誉标记，只加不减）+ share 凭证带质量行（有效天数/中断次数/streak_best）
- 永不做：低密度毕业的负面标记、断签即失败、契约金式金钱惩罚（行业已证伪+合规风险）

## 七、风险与预防（Pre-Mortem）

1. 改了触达没改文案→催促感仍在→关通知。预防：直替同时重写 REVIVE/SUNSET 文案（absence care"门开着"文案为底）
2. 荣誉标记被解读为羞辱低密度用户。预防：只做加法；低密度凭证照常；沿用"中断不评判"提示词纪律
3. 凭证分级在无数据时拍脑袋上→误伤。预防：C3 严格数据先行，无证据不动
4. 并行会话撞仓。预防：外科指定文件提交、小步提交锁 HEAD

## 八、关键假设与验证

| 假设 | 等级 | 验证 |
|---|---|---|
| 断签回流者后续行为密度接近连续者（宽容在救行为） | 致命 | C3 ①②数据 |
| ≥7 天催促已读率低（touch 收归收益实） | 关键 | notifyCenter stats 前后对比 |
| 回流页提升当日打卡转化 | 关键 | recall 漏斗 acted 前后对比 |

## 参考

- Duolingo: duolingo.com/help/what-is-a-streak、blog.duolingo.com、deconstructoroffun.com/mechanics/streaks
- 行为科学: Dai, Milkman & Riis (Wharton 2014/2015)、NN/g fresh-start-effect、Atomic Habits never-miss-twice、Melemis relapse prevention
- 疲劳治理: courier.com、contextsdk.com（频控 caps 共识）
- 中文模式: woshipm.com/pd/5403736、微信《利诱分享朋友圈打卡处理公告》、zhuanlan.zhihu.com/p/158939721

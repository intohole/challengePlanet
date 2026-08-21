# 打卡玩法体系 V3 — 兼容十几种真实打卡玩法 + 阶梯式目标引擎

> 版本：v3 | 日期：2026-08-21 | 定位：打卡星球/星轨挑战(challengePlanet) 玩法体系升级
> 承接：docs/playmode/`brainstorm-tier2.md`、`product-plan-tier2.md`。V2 已落地"一天多次打卡、时段分解、软目标、动态基准线"；V3 补齐"**阶梯式目标(递增/递减直达目标)**"并沉淀"**统一玩法引擎**"，让系统天然兼容并组合各种真实打卡玩法——这是本产品的差异特色。
> 方法论：deep-research（3 路并行）+ SCAMPER 脑暴 + product-manager 收敛 + OST

---

## 一、一句话定位

> **每次做该行为，就记一笔打卡；目标可以是「固定」「自适应」或「阶梯式」（戒烟：当前 20 支 → 每隔几天减 1 支 → 目标 5 支）。一套引擎，兼容所有打卡玩法，越用越懂你的节奏。**

用户价值公式（俞军）：`新体验(阶梯+每次打卡+宽容) − 旧体验(固定目标+每天一次+失败归零) − 切换成本(点一下就记) > 0`。对戒烟/戒糖等"减少型"习惯，核心价值是**实时纠偏 + 目标可逐级逼近 + 破戒不被惩罚**。

---

## 二、从真实场景梳理出的 12 种打卡玩法

（每种统一用"参数原语"表达，"参数→达标逻辑"全部由同一个引擎计算，前端只凭参数渲染）

| # | 玩法 | task_type | direction | goal_rule | goal_mode | 每日本可 | 真实场景 | 达标逻辑 | 代表产品佐证 |
|---|------|-----------|-----------|-----------|-----------|----------|---------|----------|--------------|
| 1 | 习惯开关 | binary | none | fixed | floor | 单次 | 21 天未碰烟、早睡 | 当日完成 1 次即达标 | 小日常、Streaks、滴答清单 |
| 2 | 每日计数 | counter | increase | fixed | floor | 多次 | 30 个俯卧撑、8 杯水 | 今日累计 ≥ 目标 | 滴答自动记录、WaterMinder |
| 3 | 计时累计 | timer | increase | fixed | floor | 多次 | 冥想 10 分钟、阅读 30 分钟 | 累计时长 ≥ 目标 | Forest、Habitify |
| 4 | 分步/时段 | counter | increase | fixed | floor | 多次 | 晨间/午后/晚间分时段 | 每时段各自 ≥ 时段目标 | 跬步 V2 time_slot |
| 5 | **事件流水** | counter | increase | fixed | floor | 不限 | 每次喝水 tap、每抽一根 tap | 每次记一笔，实时累计 | Smoless、减烟记 |
| 6 | **递减阶梯⭐** | counter | decrease | **ladder** | ceiling | 不限 | 戒烟：20→5 支，隔 3 天减 1 | 今日累计 ≤ 当日上限 | Smoless、戒烟助手Pro、QuitNic |
| 7 | **递增阶梯⭐** | counter | increase | **ladder** | floor | 多次 | 跑步每周 +0.5km→5km | 今日累计 ≥ 当日下限 | Fabulous 渐进、按周加量 |
| 8 | 上限红线 | counter | decrease | fixed | ceiling | 不限 | 今天最多抽 8 支/刷手机 2h | 今日累计 ≤ 上限（只记录不惩罚） | James Clear 上限目标 |
| 9 | 区间保持 | timer/counter | none | fixed | range | 多次 | 睡眠 7–9h、体重区间 | 下限 ≤ 实际 ≤ 上限 | 临床健康管理 |
| 10 | 自适应顺应 | counter | either | **adaptive** | auto | 多次 | AI 按你近 7 天节奏定目标 | 今日累计 对标 动态基线 | 跬步 V2 动态基准线 |
| 11 | 选择判断 | choice | none | fixed | none | 多次 | 记录每次选择+情境标签 | 记录一条即可 | 一体化情境记录 |
| 12 | 文字流淌 | text | none | fixed | floor | 单次 | 晨间日记、感恩 3 件 | 当日有记录即达标 | Fabulous、感恩 App |

> 命中"核心特色"的玩法用 ⭐ 标注：**每一次行为记一笔（事件流水/事件式）+ 目标阶梯递变 + 上限/下限达标**。这 12 种只是参数原语的低阶组合，用户可再组合出上百种（如"戒烟阶梯 + 情境标签"）。

---

## 三、统一玩法引擎（核心抽象）

### 3.1 参数原语

| 原语 | 取值 | 作用 |
|------|------|------|
| `task_type` | binary / counter / timer / text / choice | 怎么记（是否/计数/计时/文字/选择） |
| `direction` | increase / decrease / none | 目标趋势（越多好 / 越少好 / 无方向） |
| `goal_rule` | **fixed / adaptive / ladder** | 目标怎么定（固定 / 自适应比昨日 / 阶梯式）——V3 新增核心 |
| `goal_mode` | **ceiling / floor / range / auto** | 怎么判达标（上限 / 下限 / 区间 / 由 direction 推导） |
| `multiple_per_day` | single / multi / unlimited | 一天能不能重复记（事件式=unlimited） |
| `unit` | 字符串 | 单位（根/杯/分钟/公里） |
| `goal_type` | soft / hard | 超出后是否惩罚（软=督促不惩罚 / 硬=底线）——V2 已有 |
| `decompose_mode` | none / time_slot | 是否按时段拆（V2 已有） |

### 3.2 达标与目标计算（统一伪代码）

```
daily_target(challenge, day):           # 当日上限/下限（阶梯玩法最关键）
  if goal_rule == 'fixed':   return target_value
  if goal_rule == 'adaptive':return _adaptive_baseline(challenge)   # V2 已有，比昨日 ±10%
  if goal_rule == 'ladder':  return _ladder_target(challenge, day)  # V3 新增

_ladder_target(c, day):                  # 阶梯核心公式（扣减/累加直到目标）
  elapsed = (day - 1) // c.ladder_interval         # 已过了几个阶梯段
  delta = elapsed * c.ladder_step
  if c.direction == 'decrease':
    return max(c.ladder_goal, c.ladder_start - delta)   # 只降不升，保底目标
  else:  # increase
    return min(c.ladder_goal, c.ladder_start + delta)   # 只升不降,到顶目标

is_goal_met(challenge, today_total, day):
  t = daily_target(challenge, day)
  mode = resolve_goal_mode(challenge)    # decrease→ceiling, increase→floor
  if mode == 'ceiling': return today_total <= t   # 上限：不超即达标
  if mode == 'floor':   return today_total >= t   # 下限：达到即达标
  if mode == 'range':   return lo <= today_total <= hi
```

**关键设计**：
- **阶梯"只进不退"**：递减步只取 `max(goal, start - delta)`，绝不因某天超了而回弹升高（对齐 Smoless 的 "goal is never raised back up"）。
- **阶梯参数友好**：用户只填 4 个数——`当前值(20 支)`、`目标值(5 支)`、`每隔(3)天减`、`每次减(1) 支`，系统自动生成每一天的上限并**可视化阶段性落到目标**。
- **自适应与阶梯可切换**：都是 `goal_rule` 的枚举值，一个字段切换，前端按同一接口渲染，天然兼容。

---

## 四、旗舰玩法：阶梯式递减 / 递增详细设计

### 4.1 戒烟阶梯（用户示例直接命中）

用户输入：**当前每天 20 支 → 目标 5 支 → 每隔 3 天减 1 支**，周期 45 天。

```
每日上限(支)：20 20 20 | 19 19 19 | 18 18 18 | ... | 5 5 5  (只降不升)
团队关键指标：阶梯完成天数、剩余天数、">目标值"触发 AI 温和建议(不惩罚)
```

**每天用户视角**：打开 → 看到"今天上限 19 支 · 已记 8 支 · 还可 11 支"，每抽一根就 `＋1` 记一笔（事件流水），进度条实时趋向上限；今天满 8 支还 OK、抽第 20 支也只是"记录 + 温和提醒 + 建议替代行为"，**不断 streak、不扣分**。

### 4.2 递增阶梯（培养类）

当前每天 1km → 目标 5km → 每隔 3 天 +0.5km。每日下限型，今天至少跑到 `1+⌊(d-1)/3⌋×0.5` km 即达标。

### 4.3 递减节奏建议（研究佐证，仅作默认值）

| 依赖度 | 建议递减边界 | 依据 |
|--------|--------------|------|
| 轻（<10 支/天） | 每 3–5 天减 1–2 支 | 渐进减量适用 |
| 中（10–20 支/天） | 每 3–7 天减 1–2 支，4–6 周结构计划 | NCSCT CDTS |
| 重（>20 支/天） | 每 3–5 天减 2–3 支，建议配合专业戒断支持 | NCSCT + 注意补偿性吸烟 |

> 说明：领域内无"每几天减几支"唯一最优解的统一结论，故**默认值由 AI 场景解析按上述区间给出，用户可自由改**（NCSCT CDTS；"上限式目标"见 James Clear）。

---

## 五、宽容式激励（"只记录、不惩罚"）设计原则

研究一致指向戒断类产品应**宽容**（SobrTrack/Orlyn/Habitify 均"progress, not perfection"）：

| 机制 | 递减阶梯/上限玩法 | 递增/培养玩法 |
|------|------------------|---------------|
| 超目标 | 记录 + 温和提醒 + AI 替代建议，不扣分不断 streak | — |
| 断签 | 补签/冻结/修复（V2 已有 mercy） | 同左 |
| streak 保护 | 只加不减趋势心 | 同左 |
| AI 语言 | "这个时段对你比较难，我们一起想办法"（拒绝"你破戒了"） | "今天比昨天多 X，趋势很好" |

> V3 不新增惩罚机制，沿用 V2 的"软目标不惩罚 + 硬目标底线 + mercy 修复"；重点是**对所有 ladder/event 玩法统一套用这套宽容语义**。

---

## 六、系统升级方案（落地）

### 6.1 数据模型（Challenge 新增字段，纯增量、可迁移）

```python
# app/models/challenge.py 追加（database.py run_migrations 补列）
goal_rule:        Mapped[str]  # "fixed" | "adaptive" | "ladder"，默认适配现有行为
ladder_start:     Mapped[float]# 阶梯起点（当前值），如 20 支
ladder_goal:      Mapped[float]# 阶梯目标值，如 5 支
ladder_interval:  Mapped[int]  # 每隔 N 天变化一次，默认 1
ladder_step:      Mapped[float]# 每次变化量，默认 1
goal_mode:        Mapped[str]  # "ceiling" | "floor" | "range" | "auto"，auto=按 direction 推导
```
> 说明：`goal_mode` 用 `auto` 兜底（decrease→ceiling、increase→floor），仅需要 range 时显式声明，避免冗余。V2 已落地的 `target_value/direction/goal_type/decompose_mode` 全部保留，兼容既有挑战。

### 6.2 新增/改造服务

- 新增 `app/services/goal_rule_service.py`（SRP）：暴露 `daily_target(challenge, day)` 与 `is_goal_met(...)`，**供 checkin_service 与 challenge_service 复用**，杜绝两处重复算法（收归沉淀）。
- `checkin_service._compute_target_snapshot`：命中 `goal_rule=ladder` 时改用 goal_rule_service 当日上限。
- `challenge_service._build_today_response`：返回 `goal_rule`、`today_cap(ladder 当日上限/下限)`、`ladder_start/goal/interval/step`、`ladder_progress_pct`(起点→目标的完成度)、`remaining`.
- `api/challenge.py` confirm 与 nl-create：透传上述新字段，AI 场景解析戒烟时自动给出阶梯建议。

### 6.3 API/Schema

- `ChallengeResponse` / `TodayTaskResponse` / `ChallengeConfirmRequest` / `NLCreateRequest` 增补上述字段（默认值保持向后兼容）。

### 6.4 前端（Vue3 CDN + 复用 `/nexus-ui/js/components/nux-checkin.js`）

- **创建流程** `create.js`：当 `direction=decrease`（戒除类）时，展示"阶梯玩法"配置卡片（当前值/目标值/每隔几天/每次减），实时预览"第 n 天上限=xx"阶梯行。
- **今日打卡**：
  - 递减阶梯：大标题"今天上限 **19** 支 · 已记 **8** 支 · 还可 **11** 支"；`＋1` 快速记一笔（事件流水）；进度条趋向上限；超过上限仍可记录（宽容）。
  - 递增阶梯："今天目标 **x** · 已 **y**"；`＋1` 累计。
  - main 视图统一按 `goal_rule + goal_mode` 渲染，不再写死具体玩法（兼容 12 种）。
- **报表** `home-reports.js`：阶梯玩法增加"阶梯进度"（起点→目标 / 今日上限）与"剩余天数降到目标"。

### 6.5 验收要点（Test-as-Intended，严禁 mock）

1. 新建"戒烟"挑战：当前 20、目标 5、隔 3 天、每次 1，生成 45 天上限序列正确。
2. 递减阶梯某天超上限：仍可记录、streak 不断、不扣分、收到温和 AI 建议。
3. 递增阶梯：未至目标显示未达标，达成当日变绿。
4. 既有 fixed / adaptive / binary 挑战行为不变（回归）。

---

## 七、MVP 落地范围（本轮）

| 项 | 内容 | 优先级 |
|----|------|--------|
| 后端 | Challenge 4 阶梯字段 + goal_rule + goal_mode 迁移 | 必做 |
| 后端 | goal_rule_service（fixed/adaptive/ladder 统一计算，复用） | 必做 |
| 后端 | checkin/today/schema/API 接入 ladder | 必做 |
| 前端 | create.js 阶梯配置卡片 + 预览 | 必做 |
| 前端 | home.js 今日上限/已记/还可 + ＋1 事件流水 | 必做 |
| 前端 | nux-checkin 组件支持 ladder ceiling（上限达标） | 必做 |
| 前端 | AI 场景解析戒烟自动给阶梯默认值 | 建议 |
| 前端 | 阶梯进度报表 | 建议 |
| 回归 | 12 种玩法参数化兼容 & 既有挑战不回归 | 必做 |

> 不做：range 区间玩法可视化、AI 自动调整阶梯、社交（本轮）。一次做对核心 6 项，避免过度设计。

---

## 八、参考文献

1. NCSCT (2025) Cut Down to Stop briefing — https://www.ncsct.co.uk/index.php/library/view/pdf/Cut-Down-to-Stop-Briefing.pdf
2. Chen et al. Self-Monitoring review — https://www.oap-onlinejournals.org/behavior-therapy-and-mental-health/article/386
3. James Clear. Goal-setting (Upper-Bound) — https://jamesclear.com/goal-setting#Set-an-Upper-Bound
4. Fogg Tiny Habits / B=MAP — https://goalsandprogress.com/tiny-habits-fogg-behavior-model-explained/
5. Smoless（事件式打卡 + 渐进减量） — https://smoless.app/
6. 主要竞品打卡玩法拆解（Habitica / 小日常 / 滴答 / Streaks / Fabulous / WaterMinder / 戒烟类 / Forest）— 见 research-tier2-checkin.md 及本轮 deep-research 三路报告

---

> 文档结束 | 下一步：按"七、MVP 落地范围"开始开发，遵守分层架构 + 单文件 <300 行 + 端到端测试 + Git 提交
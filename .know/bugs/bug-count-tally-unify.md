---
id: bug-count-tally-unify
title: 计数/计时打卡统一「记账台」：去掉补齐式声明，三天数字面收敛
summary: counter/timer（递增）主按钮"完成今日目标"会提交 target-today_total 补齐差额造假；companion_phase/诊断天数/周报完成率用 len(checkins)条数当天数；递减目标超限单笔completion_pct<100扣积分，与"超限不惩罚"矛盾。统一为：定量记录类一律记一笔+系统自动判定达标，天数字面全走distinct days，递减单笔恒100
type: bug
project: challengePlanet
date: 2026-09-11
tags: [bug, fix]
scope: project
related: [bug-cap-mode-auto-judge, feat-quit-gradient-tally]
---

# 计数/计时打卡统一「记账台」：去掉补齐式声明，三天数字面收敛

报错现象: 1)counter/timer递增(俯卧撑/喝水/跑步/冥想)主按钮"完成今日目标"点击提交value=target-today_total，系统替用户编造差额假数据；2)一天多条记录时 companion 阶段/诊断done_days/周报累计记录率 把记录条数当天数(点8下=8天)；3)递减目标单笔超限时 completion_pct<100，积分被打折，但产品语义"超限温和提醒不惩罚"
根因分析: 1)doMainCheckin 对 counter/timer 用补齐式计算value；2)companion_service._detect_phase/assess_risk/load_challenge_state、diagnosis_service.done_days、ai_analysis_service.done_rate 均 len(checkins)；3)checkin_service._calc_completion_pct 递减超限返回target 比例进度
修复方法: 1)记账台统一(_tallyCta)：counter/timer 主CTA=记一笔(+1/预设/撤销/三态)，递增未达标显示"已记X/目标Y还差Z"、达标即"今日已完成"+extras提供"记实际值"超额入口；doMainCheckin 对 counter/timer 一律守卫拦截声明式补齐；2)companion/diagnosis/ai_analysis 天数一律 len({date}) distinct；3)_calc_completion_pct 递减恒100.0(诚实记录不因超限扣积分，达标与否由日期判定)
验证: test_cap_mode.py 新增 test_decrease_completion_pct_not_punished；全量16 tests通过；node render级校验递增/递减记账台、达标完成态、记实际值入口、binary/text/word不受影响
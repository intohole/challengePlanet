;(function () {
  const V = window.cpViews.home

  V._taskArea = function (s) {
    const ch = s.current
    const d = this.data
    const t = d.today
    let html = ''
    if (ch.status !== 'active') return '<div class="glass-card cp-task-card"><p class="cp-task-title">' + (ch.status === 'completed' ? '🎉 挑战完成，太棒了！' : '挑战已结束，打卡战绩已保留') + '</p><p class="cp-task-desc">可在「我的」页创建新挑战，继续保持节奏。</p></div>'
    if (!t) {
      if (ch.start_date && ch.start_date > window.cpTodayStr()) return '<div class="glass-card cp-task-card"><p class="cp-task-title">挑战尚未开始</p><p class="cp-task-desc">将于 ' + ch.start_date + ' 正式开始，先去准备一下吧。</p></div>'
      return ''
    }
    const tt = t.task_type || ch.task_type || 'binary'
    const ttLabel = window.cpTaskTypeLabel(tt) || '打卡'
    const isDiet = tt === 'diet' || ch.task_type === 'diet'
    const isMultiMode = !!t.repeatable || ch.decompose_mode === 'time_slot' || ch.task_type === 'counter' || ch.task_type === 'timer' || tt === 'counter' || tt === 'timer'
    const baseline = t.dynamic_baseline || 0
    const isDecrease = ch.direction === 'decrease'
    html += '<div class="glass-card cp-task-card"><div class="cp-task-head"><span class="cp-task-day"><i class="fas fa-flag"></i>已打卡 ' + (ch.completed_days || 0) + '/' + (ch.total_days || 0) + ' 天</span><div class="cp-task-head-right"><span class="cp-task-type-badge">' + ttLabel + '</span><span class="cp-task-pct">' + (t.progress_pct || 0) + '% 完成</span></div></div><p class="cp-task-title">' + window.cpEsc(t.task_title || '完成今日打卡') + '</p>'
    if (t.task_description) html += '<p class="cp-task-desc">' + window.cpEsc(t.task_description) + '</p>'
    if (isDiet) {
      html += this._dietTargetPanel(t, ch)
    } else if (t.goal_rule === 'ladder' && t.today_total !== undefined) {
      html += this._ladderBlock(t, ch)
    } else if (baseline > 0 && ((t.day_number || 1) > 1 || (ch.completed_days || 0) > 0)) {
      const unit = window.cpEsc(t.task_unit || '')
      const mainText = isDecrease ? '比昨天少 <b>' + baseline.toFixed(1) + '</b> ' + unit : '比昨天多 <b>' + baseline.toFixed(1) + '</b> ' + unit
      html += '<div class="cp-task-target"><i class="fas fa-bullseye"></i> ' + mainText + '</div>'
    } else if (t.task_target && t.task_target > 0) {
      html += '<div class="cp-task-target"><i class="fas fa-bullseye"></i> 今日目标 <b>' + t.task_target + '</b> ' + window.cpEsc(t.task_unit || '') + '</div>'
    }
    if ((isMultiMode || isDecrease) && t.today_total !== undefined) {
      if (t.goal_rule !== 'ladder') {
        const staticTarget = t.today_target || 1
        let pct, barColor
        if (baseline > 0) {
          if (isDecrease) {
            const reached = t.today_total <= baseline
            if (reached) { pct = 100; barColor = 'var(--emerald)' }
            else { pct = baseline > 0 ? Math.min(100, Math.round((t.today_total / baseline) * 100)) : 100; barColor = 'var(--amber)' }
          } else {
            const ratio = baseline > 0 ? t.today_total / baseline : 0
            pct = Math.round(Math.min(100, ratio * 100))
            barColor = ratio >= 1 ? 'var(--emerald)' : (ratio >= 0.8 ? 'var(--amber)' : 'var(--primary)')
          }
        } else {
          pct = staticTarget > 0 ? Math.min(100, Math.round(t.today_total / staticTarget * 100)) : 0
          barColor = t.today_total >= staticTarget ? 'var(--emerald)' : 'var(--primary)'
        }
        html += '<div class="cp-task-progress"><div class="cp-task-progress-bar"><div class="cp-task-progress-fill" style="width:' + pct + '%;background:' + barColor + '"></div></div>'
        html += '<div class="cp-task-progress-info"><span style="color:' + barColor + '">' + t.today_total + '</span><span class="cp-task-progress-sep">/</span><span>' + (t.today_target || t.task_target || staticTarget) + ' ' + window.cpEsc(t.unit || ch.unit || '') + '</span></div></div>'
      }
      const hint = this._remainHint(t, ch, isDecrease)
      if (hint) html += hint
    }
    if (t.sub_goals && t.sub_goals.length) html += this._subGoalProgress(t.sub_goals, ch)
    if (t.period_target && t.period_target > 0) html += this._periodCard(t)
    if ((t.calories_week || 0) > 0 || (t.calories_today || 0) > 0) html += this._calorieCard(t)
    html += '</div>'
    if (isDiet) {
      html += this._dietArea(t, ch, (d.today && d.today.checkins_date))
    } else {
      html += this._checkinArea(tt, t, ch)
      html += this._afterCheckin(tt, t, ch)
    }
    return html
  }

  V._afterCheckin = function (tt, t, ch) {
    const d = this.data
    if (!t.checked_in) return ''
    let html = ''
    if (tt === 'text' && t.checkin_data && t.checkin_data.reflection) {
      html += '<div class="glass-card cp-text-display"><div class="cp-text-display-head"><i class="fas fa-quote-left"></i> 今日记录</div><p class="cp-text-display-body">' + window.cpEsc(t.checkin_data.reflection) + '</p></div>'
    }
    if (d.declaration) html += '<div class="cp-declare">🔥 ' + window.cpEsc(d.declaration) + '</div>'
    const plan = ch.ai_plan || []
    const next = plan[t.day_number]
    if (next && next.title) {
      html += '<div class="cp-tomorrow-enhanced"><div class="cp-tomorrow-icon">🌅</div><div class="cp-tomorrow-body"><div class="cp-tomorrow-label">明日预告</div><div class="cp-tomorrow-title">' + window.cpEsc(next.title) + '</div>' + (next.description ? '<div class="cp-tomorrow-desc">' + window.cpEsc(next.description) + '</div>' : '') + '</div></div>'
    }
    if (d.lastFeedback) {
      html += '<div class="cp-ai-card"><div class="cp-ai-head"><i class="fas fa-robot"></i> AI 教练反馈<span class="cp-ai-badge">今日陪伴</span></div><div class="cp-md nx-md" id="' + this._pushMd(d.lastFeedback) + '"></div>'
      if (d.chest) html += '<span class="cp-chest-tag">🎁 惊喜宝箱 +' + d.chest + ' 分</span>'
      html += '</div>'
    } else if (d.chest) {
      html += '<div class="cp-ai-card"><span class="cp-chest-tag">🎁 惊喜宝箱 +' + d.chest + ' 分</span></div>'
    }
    html += '<div class="cp-sub-actions"><button class="cp-btn-ghost" onclick="cpViews.home.openReflection()"><i class="fas fa-pen"></i> ' + ((t.checkin_data && t.checkin_data.reflection) ? '查看/改心得' : '写心得') + '</button><button class="cp-btn-ghost" onclick="cpOpenShare()"><i class="fas fa-share-nodes"></i> 分享海报</button></div>'
    return html
  }

  V._remainHint = function (t, ch, isDecrease) {
    if (t.settled) return ''
    const unit = window.cpEsc(t.unit || ch.unit || '')
    const target = (t.today_target || t.task_target || ch.target_value || 1)
    const total = (t.today_total || 0)
    const fc = (t.forecast) || {}
    if (isDecrease) {
      if (total > (t.today_target || 0)) return '<div class="cp-remain-hint over"><i class="fas fa-circle-exclamation"></i>已超今日上限 ' + target + ' ' + unit + '，明天梯度会更低，稳住</div>'
      if (fc.enabled && fc.projected > 0) {
        const range = fc.projected_high > fc.projected ? '±' + (fc.projected_high - fc.projected) : ''
        let cells = '<span class="cp-dash-cell"><b>' + total + '</b> 已记</span><span class="cp-dash-cell">预计 <b>' + fc.projected + range + '</b> ' + unit + '</span>'
        if (fc.touch_at) cells += '<span class="cp-dash-cell">触顶 <b>' + fc.touch_at + '</b></span>'
        if (fc.remaining_units > 0) cells += '<span class="cp-dash-cell">还可 <b>' + fc.remaining_units + '</b> ' + unit + '</span>'
        const cal = fc.calibrated ? '<span class="cp-dash-chip cal"><i class="fas fa-scale-balanced"></i>已校准</span>' : ''
        const ladder = fc.ladder_outlook && fc.ladder_outlook.message ? '<div class="cp-dash-panel ladder"><i class="fas fa-stairs"></i><span>' + window.cpEsc(fc.ladder_outlook.message) + '</span></div>' : ''
        const ctx = fc.risk_window_context ? '<span class="cp-dash-chip ctx"><i class="fas fa-location-dot"></i>' + window.cpEsc(fc.risk_window_context) + '</span>' : ''
        const pattern = fc.context_pattern ? '<div class="cp-dash-panel pattern"><i class="fas fa-chart-simple"></i><span>' + window.cpEsc(fc.context_pattern) + '</span></div>' : ''
        const windowLine = fc.risk_window_msg ? '<div class="cp-dash-window"><i class="fas fa-route"></i>' + window.cpEsc(fc.risk_window_msg) + '</div>' : ''
        const basis = fc.basis ? '<div class="cp-dash-meta">' + window.cpEsc(fc.basis) + (fc.confidence_label ? ' · ' + fc.confidence_label + '把握' : '') + cal + ctx + '</div>' : '<div class="cp-dash-meta">' + cal + ctx + '</div>'
        return '<div class="cp-dash"><div class="cp-dash-metrics">' + cells + '</div>' + windowLine + basis + ladder + pattern + '</div>'
      }
      return '<div class="cp-remain-hint"><i class="fas fa-bullseye"></i>守住 ' + target + ' ' + unit + ' 以内即为今日达标</div>'
    }
    if ((t.remaining || 0) <= 0) return ''
    const winInc = fc.risk_window_msg ? '<div class="cp-dash-window"><i class="fas fa-route"></i>' + window.cpEsc(fc.risk_window_msg) + '</div>' : ''
    const patInc = fc.context_pattern ? '<div class="cp-dash-panel pattern"><i class="fas fa-chart-simple"></i><span>' + window.cpEsc(fc.context_pattern) + '</span></div>' : ''
    if (fc.enabled && (fc.reach_at || winInc || patInc)) {
      const basis = fc.basis ? '<div class="cp-dash-meta">' + window.cpEsc(fc.basis) + (fc.confidence_label ? ' · ' + fc.confidence_label + '把握' : '') + '</div>' : ''
      const reachCell = fc.reach_at
        ? '<span class="cp-dash-cell">预计 <b>' + fc.reach_at + '</b> 达标</span>'
        : '<span class="cp-dash-cell">还差 <b>' + t.remaining + '</b> ' + unit + '</span>'
      return '<div class="cp-dash"><div class="cp-dash-metrics"><span class="cp-dash-cell">已记 <b>' + total + '</b> / ' + target + '</span>' + reachCell + '</div>' + winInc + basis + patInc + '</div>'
    }
    return '<div class="cp-remain-hint"><i class="fas fa-bullseye"></i>还差 <b>' + t.remaining + '</b> ' + unit + ' 达标</div>'
  }

  V._periodCard = function (t) {
    const total = (t.period_total !== undefined ? t.period_total : t.week_total) || 0
    const target = t.period_target || 0
    const pct = Math.min(100, Math.round(total / target * 100))
    const unit = window.cpEsc(t.period_unit || '')
    const days = t.period_days || 7
    const label = days === 7 ? '本周' : '每' + days + '天'
    const done = !!t.week_settled
    const color = done ? 'var(--emerald)' : 'var(--primary)'
    let h = '<div class="cp-task-target"><i class="fas fa-calendar-week"></i> ' + label + '目标 <b>' + target + '</b> ' + unit + (done ? ' <span style="color:var(--emerald)">✓ 已达成</span>' : '') + '</div>'
    h += '<div class="cp-task-progress"><div class="cp-task-progress-bar"><div class="cp-task-progress-fill" style="width:' + pct + '%;background:' + color + '"></div></div>'
    h += '<div class="cp-task-progress-info"><span style="color:' + color + '">' + total + '</span><span class="cp-task-progress-sep">/</span><span>' + target + ' ' + unit + '</span></div></div>'
    if (!done) h += '<div class="cp-remain-hint"><i class="fas fa-bullseye"></i>还差 <b>' + Math.max(0, target - total) + '</b> ' + unit + ' 达成' + label + '目标</div>'
    return h
  }

  V._calorieCard = function (t) {
    return '<div class="cp-task-target"><i class="fas fa-fire" style="color:var(--amber)"></i> 卡路里 <b>' + (t.calories_today || 0) + '</b> 今日 · <b>' + (t.calories_week || 0) + '</b> 本周 千卡</div>'
  }

  V._paceRail = function (total, projected, cap, unit, state) {
    const hasProj = projected > 0
    const scale = Math.max(cap, total, hasProj ? projected : 0, 1) * 1.12
    const fillPct = Math.min(100, total / scale * 100)
    const capPct = Math.min(100, cap / scale * 100)
    const projPct = hasProj ? Math.min(100, projected / scale * 100) : 0
    const color = state === 'over' ? 'var(--red)' : (state === 'warn' ? 'var(--amber)' : 'var(--emerald)')
    const label = '已记 ' + total + (hasProj ? '，预计 ' + projected : '') + '，目标 ' + cap + ' ' + unit
    let h = '<div class="cp-rail" role="img" aria-label="' + window.cpEsc(label) + '"><div class="cp-rail-track">'
    h += '<div class="cp-rail-fill" style="width:' + fillPct + '%;background:' + color + '"></div>'
    h += '<div class="cp-rail-cap" style="left:' + capPct + '%"></div>'
    if (hasProj) h += '<div class="cp-rail-proj" style="left:' + projPct + '%;background:' + color + '"></div>'
    return h + '</div></div>'
  }

  V._ladderBlock = function (t, ch) {
    const cap = Number(t.today_cap) || Number(t.today_target) || 0
    const total = Number(t.today_total) || 0
    const unit = window.cpEsc(t.unit || ch.unit || '')
    const isDesc = ch.direction === 'decrease' || String(t.direction) === 'decrease'
    const fc = t.forecast || {}
    const state = total > cap ? 'over' : (fc.enabled && fc.risk_level === 1 ? 'warn' : 'ok')
    const label = isDesc ? '今日上限' : '今日目标'
    let html = '<div class="cp-ladder-daily"><div class="cp-ladder-daily-head"><span>' + label + '</span>'
    if (t.ladder_goal && t.ladder_start) {
      html += '<span class="cp-ladder-daily-path">' + Number(t.ladder_start) + '→' + Number(t.ladder_goal) + ' <i class="fas fa-stairs" style="font-size:11px"></i> 阶梯</span>'
    }
    html += '</div>'
    html += this._paceRail(total, Number(fc.projected) || 0, cap, unit, state)
    return html + '</div>'
  }
})()
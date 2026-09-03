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
    const slipBinary = !isDiet && !isMultiMode && (ch.direction === 'decrease' || ch.category === 'quit')
    html += '<div class="glass-card cp-task-card"><div class="cp-task-head"><span class="cp-task-day"><i class="fas fa-flag"></i>第 ' + (t.day_number || 1) + ' 天 · ' + (t.date || '') + '</span><div class="cp-task-head-right"><span class="cp-task-type-badge">' + ttLabel + '</span><span class="cp-task-pct">' + (t.progress_pct || 0) + '%</span></div></div><p class="cp-task-title">' + window.cpEsc(t.task_title || '完成今日打卡') + '</p>'
    if (t.task_description) html += '<p class="cp-task-desc">' + window.cpEsc(t.task_description) + '</p>'
    const baseline = t.dynamic_baseline || 0
    const isDecrease = ch.direction === 'decrease'
    if (isDiet) {
      html += this._dietTargetPanel(t, ch)
    } else if (baseline > 0) {
      const unit = window.cpEsc(t.task_unit || '')
      const mainText = isDecrease ? '比昨天少 <b>' + baseline.toFixed(1) + '</b> ' + unit + ' 就行' : '比昨天多 <b>' + baseline.toFixed(1) + '</b> ' + unit + ' 就行'
      const refText = (t.task_target && t.task_target > 0) ? '<span class="cp-task-target-ref">目标 ' + t.task_target + ' ' + unit + '（参考）</span>' : ''
      html += '<div class="cp-task-target"><i class="fas fa-bullseye"></i> ' + mainText + refText + '</div>'
    } else if (t.task_target && t.task_target > 0) {
      html += '<div class="cp-task-target"><i class="fas fa-bullseye"></i> 今日目标 <b>' + t.task_target + '</b> ' + window.cpEsc(t.task_unit || '') + '</div>'
    }
    if ((isMultiMode || slipBinary) && t.today_total !== undefined) {
      const staticTarget = t.today_target || 1
      let pct, barColor
      if (baseline > 0) {
        if (isDecrease) {
          const reached = t.today_total <= baseline
          if (reached) { pct = 100; barColor = 'var(--emerald)' }
          else {
            const overRatio = baseline > 0 ? Math.min(1, (t.today_total - baseline) / baseline) : 0
            pct = Math.round(80 + overRatio * 20)
            barColor = overRatio < 0.2 ? 'var(--amber)' : 'var(--red)'
          }
        } else {
          const ratio = baseline > 0 ? t.today_total / baseline : 0
          pct = Math.round(Math.min(100, ratio * 100))
          if (ratio >= 1) barColor = 'var(--emerald)'
          else if (ratio >= 0.8) barColor = 'var(--amber)'
          else barColor = 'var(--primary)'
        }
      } else {
        pct = staticTarget > 0 ? Math.min(100, Math.round(t.today_total / staticTarget * 100)) : 0
        const overTarget = isDecrease ? t.today_total > staticTarget : t.today_total < staticTarget
        barColor = overTarget ? 'var(--red)' : 'var(--emerald)'
      }
      html += '<div class="cp-task-progress"><div class="cp-task-progress-bar"><div class="cp-task-progress-fill" style="width:' + pct + '%;background:' + barColor + '"></div></div>'
      html += '<div class="cp-task-progress-info"><span style="color:' + barColor + '">' + t.today_total + '</span><span class="cp-task-progress-sep">/</span><span>' + staticTarget + ' ' + window.cpEsc(t.unit || ch.unit || '') + '</span>'
      if (baseline > 0) html += '<span class="cp-task-progress-baseline">基准 ' + baseline.toFixed(1) + '</span>'
      html += '</div></div>'
    }
    if (t.goal_rule === 'ladder' && t.today_total !== undefined) html += this._ladderBlock(t, ch)
    if (t.sub_goals && t.sub_goals.length) html += this._subGoalProgress(t.sub_goals, ch)
    if (t.task_tip) html += '<p class="cp-task-tip"><i class="fas fa-lightbulb"></i><span>' + window.cpEsc(t.task_tip) + '</span></p>'
    if (t.task_steps && t.task_steps.length) html += '<div class="cp-task-steps-preview">' + t.task_steps.map(st => '<span class="cp-step-preview-tag">' + window.cpEsc(st) + '</span>').join('') + '</div>'
    html += '</div>'
    if (isDiet) {
      html += this._dietArea(t, ch, (d.today && d.today.checkins_date))
    } else if (isMultiMode || slipBinary) {
      html += this._multiCheckinArea(tt, t, ch, slipBinary)
    } else if (!t.checked_in) {
      html += this._checkinArea(tt, t)
    } else {
      html += '<button class="cp-btn-checkin done"><i class="fas fa-circle-check"></i> 今日已完成</button>'
    }
    html += '<div id="cp-nux-checkin"></div>'
    if (t.checked_in) {
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
    }
    return html
  }

  V._ladderBlock = function (t, ch) {
    const cap = Number(t.today_cap) || Number(t.today_target) || 0
    const total = Number(t.today_total) || 0
    const remaining = Number(t.remaining)
    const unit = window.cpEsc(t.unit || ch.unit || '')
    const isDesc = ch.direction === 'decrease' || String(t.direction) === 'decrease'
    const over = isDesc ? total > cap : total < cap
    const ratio = cap > 0 ? Math.min(100, Math.round(total / cap * 100)) : 0
    const barColor = over ? 'var(--red)' : 'var(--emerald)'
    const label = isDesc ? '今日上限' : '今日目标'
    const remainTxt = remaining !== undefined && remaining >= 0 ? '还可 ' + remaining + ' ' + unit : ''
    let html = '<div class="cp-ladder-daily"><div class="cp-ladder-daily-head"><span>' + label + '</span>'
    if (t.ladder_goal && t.ladder_start) {
      const cur = Number(t.ladder_start)
      const end = Number(t.ladder_goal)
      html += '<span class="cp-ladder-daily-path">' + (isDesc ? (cur + '→' + end) : (cur + '→' + end)) + ' <i class="fas fa-stairs" style="font-size:11px"></i> 阶梯</span>'
    }
    html += '</div>'
    html += '<div class="cp-ladder-daily-bar"><div class="cp-ladder-daily-fill" style="width:' + ratio + '%;background:' + barColor + '"></div></div>'
    html += '<div class="cp-ladder-daily-stats">'
    html += '<div class="cp-ladder-daily-stat"><b style="color:' + barColor + '">' + total + '</b><span>已记 ' + unit + '</span></div>'
    html += '<div class="cp-ladder-daily-stat"><b>' + cap + '</b><span>' + (isDesc ? '上限' : '目标') + ' ' + unit + '</span></div>'
    if (remainTxt) html += '<div class="cp-ladder-daily-stat right"><b>' + remaining + '</b><span>' + unit + ' 余量</span></div>'
    html += (over ? '<div class="cp-ladder-daily-tip warn">' + (isDesc ? '已超过今日上限，放慢一点，明天继续' : '还没到目标，再努一把') + '</div>' : '<div class="cp-ladder-daily-tip ok">' + (isDesc ? '控制在范围内，很好' : '今天达标，继续保持') + '</div>')
    html += '</div></div>'
    return html
  }
})()

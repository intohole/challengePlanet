;(function () {
  const V = window.cpViews.home

  V._subGoalProgress = function (subGoals, ch) {
    if (!subGoals || !subGoals.length) return ''
    let html = '<div class="cp-subgoals">'
    subGoals.forEach(sg => {
      const pct = sg.progress_pct || 0
      const isDecrease = ch.direction === 'decrease'
      const isSoft = sg.goal_type === 'soft'
      const overTarget = isDecrease ? sg.today_value > sg.target_value : sg.today_value < sg.target_value
      const colorClass = sg.target_value > 0 && sg.today_value > 0 && overTarget ? (isSoft ? 'warn' : 'over') : 'ok'
      html += '<div class="cp-subgoal ' + colorClass + '">'
      html += '<div class="cp-subgoal-head"><span class="cp-subgoal-title">' + window.cpEsc(sg.title) + '</span>'
      if (sg.time_window_start && sg.time_window_end) html += '<span class="cp-subgoal-time">' + sg.time_window_start + '-' + sg.time_window_end + '</span>'
      html += '</div>'
      html += '<div class="cp-subgoal-bar"><div class="cp-subgoal-fill" style="width:' + Math.min(pct, 100) + '%"></div></div>'
      html += '<div class="cp-subgoal-info"><span>' + sg.today_value + ' / ' + sg.target_value + ' ' + window.cpEsc(ch.unit || '') + '</span>'
      if (sg.today_checkin_count > 0) html += '<span class="cp-subgoal-cnt">' + sg.today_checkin_count + ' 次</span>'
      html += '</div></div>'
    })
    html += '</div>'
    return html
  }

  V._todayTimeline = function (s) {
    const ch = s.current
    const d = this.data
    const t = d.today
    if (!t) return ''
    const checkins = t.today_checkins || []
    if (!checkins.length) return ''
    let html = '<div class="glass-card cp-timeline"><div class="cp-section-title"><i class="fas fa-list-check" style="color:var(--primary-light)"></i> 今日记录（' + checkins.length + '次）</div>'
    html += '<div class="cp-timeline-list">'
    checkins.slice().reverse().forEach((c, i) => {
      const time = (c.timestamp || '').slice(11, 16)
      const subGoal = (t.sub_goals || []).find(sg => sg.id === c.sub_goal_id)
      const isSoftExceeded = c.target_value > 0 && c.value > c.target_value && (c.goal_type === 'soft')
      const isHardExceeded = c.target_value > 0 && c.value > c.target_value && (c.goal_type === 'hard')
      let valueColor = 'var(--emerald)'
      if (isSoftExceeded) valueColor = 'var(--amber)'
      if (isHardExceeded) valueColor = 'var(--red)'
      html += '<div class="cp-timeline-item' + (i === 0 ? ' latest' : '') + '">'
      html += '<div class="cp-timeline-time">' + time + '</div>'
      html += '<div class="cp-timeline-dot" style="background:' + valueColor + '"></div>'
      html += '<div class="cp-timeline-body">'
      html += '<div class="cp-timeline-val" style="color:' + valueColor + '">' + c.value + ' ' + window.cpEsc(c.unit || ch.unit || '') + '</div>'
      if (subGoal) html += '<div class="cp-timeline-sub">' + window.cpEsc(subGoal.title) + '</div>'
      if (c.mood) html += '<div class="cp-timeline-mood">' + ({ good: '😊', normal: '😐', bad: '😔' }[c.mood] || '') + '</div>'
      if (c.reflection) html += '<div class="cp-timeline-reflection">' + window.cpEsc(c.reflection) + '</div>'
      if (c.ai_feedback) html += '<div class="cp-timeline-feedback"><i class="fas fa-robot"></i> ' + window.cpEsc(c.ai_feedback) + '</div>'
      html += '</div></div>'
    })
    html += '</div></div>'
    return html
  }

  V._multiCheckinArea = function (tt, t, ch) {
    const d = this.data
    const dis = d.checking ? 'disabled' : ''
    const subGoals = t.sub_goals || []
    const unit = window.cpEsc(t.unit || ch.unit || '')
    if (d.showQuickForm) return this._quickForm(tt, t, ch, dis)
    let html = '<div class="cp-quick-checkin">'
    html += '<button class="cp-btn-primary cp-quick-btn" ' + dis + ' onclick="cpViews.home.openQuickForm()"><i class="fas fa-plus"></i> 记录一次</button>'
    if (subGoals.length) {
      html += '<div class="cp-quick-subgoals">'
      subGoals.forEach(sg => {
        const isCurrent = this._isCurrentSlot(sg)
        const cls = isCurrent ? ' current' : ''
        const pct = sg.progress_pct || 0
        html += '<button class="cp-quick-sg' + cls + '" ' + dis + ' onclick="cpViews.home.openQuickForm(' + sg.id + ')">'
        html += '<div class="cp-quick-sg-title">' + window.cpEsc(sg.title) + '</div>'
        html += '<div class="cp-quick-sg-val">' + sg.today_value + '/' + sg.target_value + ' ' + unit + '</div>'
        html += '<div class="cp-quick-sg-bar"><div class="cp-quick-sg-fill" style="width:' + Math.min(pct, 100) + '%"></div></div>'
        html += '</button>'
      })
      html += '</div>'
    }
    html += '</div>'
    return html
  }

  V._isCurrentSlot = function (sg) {
    if (!sg.time_window_start || !sg.time_window_end) return false
    const now = new Date()
    const hhmm = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0')
    return hhmm >= sg.time_window_start && hhmm < sg.time_window_end
  }

  V._quickForm = function (tt, t, ch, dis) {
    const d = this.data
    const unit = window.cpEsc(t.unit || ch.unit || '')
    const subGoals = t.sub_goals || []
    let html = '<div class="glass-card cp-quick-form"><div class="cp-quick-form-head"><span><i class="fas fa-pen"></i> 记录一次</span><button class="cp-quick-form-close" onclick="cpViews.home.closeQuickForm()"><i class="fas fa-xmark"></i></button></div>'
    if (subGoals.length) {
      html += '<div class="cp-quick-form-row"><label class="cp-label">时段</label><div class="cp-quick-form-sgs">'
      const currentSg = subGoals.find(sg => this._isCurrentSlot(sg))
      const defaultId = d.quickSubGoalId || (currentSg && currentSg.id) || subGoals[0].id
      subGoals.forEach(sg => {
        const sel = sg.id === defaultId ? ' active' : ''
        html += '<button class="cp-pick-btn' + sel + '" onclick="cpViews.home.setQuickSubGoal(' + sg.id + ')">' + window.cpEsc(sg.title) + '</button>'
      })
      html += '</div></div>'
    }
    html += '<div class="cp-quick-form-row"><label class="cp-label">数量</label>'
    html += '<div class="cp-counter-row">'
    html += '<button class="cp-counter-btn" ' + dis + ' onclick="cpViews.home.adjustQuick(-1)">−1</button>'
    html += '<div class="cp-counter-display"><span class="cp-counter-val">' + d.quickValue + '</span><span class="cp-counter-target">' + unit + '</span></div>'
    html += '<button class="cp-counter-btn" ' + dis + ' onclick="cpViews.home.adjustQuick(1)">+1</button></div>'
    html += '<div class="cp-counter-quick">'
    ;[1, 2, 3, 5].forEach(v => { html += '<button class="cp-quick-btn-input" ' + dis + ' onclick="cpViews.home.setQuick(' + v + ')">' + v + '</button>' })
    html += '</div></div>'
    html += '<div class="cp-quick-form-row"><label class="cp-label">情境（选填）</label><div class="cp-pick-btns">'
    const tags = [{ k: '', l: '不选' }, { k: 'home', l: '🏠 家' }, { k: 'work', l: '💼 工作' }, { k: 'social', l: '👥 社交' }, { k: 'stress', l: '😰 压力' }]
    tags.forEach(tg => {
      const sel = d.quickMood === tg.k ? ' active' : ''
      html += '<button class="cp-pick-btn' + sel + '" onclick="cpViews.home.setQuickContext(\'' + tg.k + '\')">' + tg.l + '</button>'
    })
    html += '</div></div>'
    html += '<div class="cp-quick-form-row"><label class="cp-label">心得（选填）</label>'
    html += '<textarea class="cp-text-input" ' + dis + ' placeholder="这一刻的感受..." oninput="cpViews.home.setQuickReflection(this.value)" style="resize:none;font-size:14px;min-height:60px">' + window.cpEsc(d.quickReflection || '') + '</textarea></div>'
    html += '<button class="cp-btn-primary" ' + dis + ' onclick="cpViews.home.doQuickCheckin()"><i class="fas fa-check"></i> ' + (d.checking ? '记录中...' : '记录') + '</button>'
    html += '</div>'
    return html
  }
})()

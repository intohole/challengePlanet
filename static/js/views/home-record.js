;(function () {
  const V = window.cpViews.home

  V.openQuickForm = function (subGoalId) {
    const d = this.data
    d.showQuickForm = true
    d.quickValue = 1
    d.quickReflection = ''
    d.quickMood = ''
    if (subGoalId) d.quickSubGoalId = subGoalId
    else d.quickSubGoalId = null
    this.rerender()
  }

  V.closeQuickForm = function () {
    this.data.showQuickForm = false
    this.rerender()
  }

  V.adjustQuick = function (delta) {
    const d = this.data
    d.quickValue = Math.max(0, d.quickValue + delta)
    this.rerender()
  }

  V.setQuick = function (val) {
    this.data.quickValue = Math.max(0, val)
    this.rerender()
  }

  V.setQuickSubGoal = function (id) {
    this.data.quickSubGoalId = id
    this.rerender()
  }

  V.setQuickContext = function (tag) {
    this.data.quickMood = tag
    this.rerender()
  }

  V.setQuickReflection = function (val) {
    this.data.quickReflection = val || ''
  }

  V.doQuickCheckin = async function () {
    const s = window.appState
    const ch = s.current
    const d = this.data
    const t = d.today
    if (!ch || !t || d.checking) return
    if (d.quickValue <= 0) { window.cpToast('请输入数量'); return }
    d.checking = true
    this.rerender()
    try {
      const payload = {
        value: d.quickValue,
        sub_goal_id: d.quickSubGoalId,
        context_tag: d.quickMood,
        reflection: d.quickReflection || '',
      }
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', payload)
      const r = res.data || res
      window.cpCelebrate('记录成功 +' + (r.points_earned || 0) + ' 分')
      d.showQuickForm = false
      d.quickValue = 1
      d.quickReflection = ''
      d.quickMood = ''
      d.lastFeedback = r.ai_feedback || d.lastFeedback
      d.chest = r.chest_points || 0
      d.shields = r.shields || 0
      await this.load()
      await window.cpLoadChallenges()
      if (r.is_soft_exceeded) {
        setTimeout(() => window.cpToast('这个时段对你来说特别难，记录下就好', 3200), 1300)
      }
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '记录失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V._multiCheckinArea = function (tt, t, ch, slipBinary) {
    const d = this.data
    const dis = d.checking ? 'disabled' : ''
    const subGoals = t.sub_goals || []
    const unit = window.cpEsc(t.unit || ch.unit || '')
    if (d.showQuickForm) return this._quickForm(tt, t, ch, dis)
    const isTimer = tt === 'timer'
    const stepVal = isTimer ? 5 : 1
    const presets = isTimer ? [5, 10, 15, 20, 30] : [1, 2, 3, 5]
    let html = '<div class="cp-quick-checkin">'
    html += '<button class="cp-big-tap" ' + dis + ' onclick="cpViews.home.doFastTap(' + stepVal + ')"><i class="fas fa-hand-pointer"></i><span>记一笔</span><em>+' + (isTimer ? stepVal + '分' : stepVal + ' ' + unit) + '</em></button>'
    html += '<p class="cp-slip-note">' + (t.checked_in ? '状态有变？如实补记就好' : (slipBinary ? '没忍住？抽一根记一根，如实记录' : '做一次记一次')) + '</p>'
    html += '<div class="cp-tap-row">'
    presets.forEach(v => {
      const label = isTimer ? '+' + v + '分' : '+' + v
      html += '<button class="cp-tap-chip" ' + dis + ' onclick="cpViews.home.doFastTap(' + v + ')"><i class="fas fa-plus"></i>' + label + '</button>'
    })
    html += '<button class="cp-tap-chip ghost" ' + dis + ' onclick="cpViews.home.openQuickForm()"><i class="fas fa-sliders"></i> 自定义</button></div>'
    if (!t.checked_in) html += slipBinary
      ? '<button class="cp-mini-link" ' + dis + ' onclick="cpViews.home.doCheckin(\'full\')">今天做到了？点亮今日打卡</button>'
      : this._miniLink(dis)
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
      html += '<div class="cp-timeline-valrow"><div class="cp-timeline-val" style="color:' + valueColor + '">' + c.value + ' ' + window.cpEsc(c.unit || ch.unit || '') + '</div>'
      html += '<button class="cp-timeline-del" onclick="cpViews.home.removeTodayRecord(' + c.id + ')"><i class="fas fa-trash-can"></i> 撤销</button></div>'
      if (subGoal) html += '<div class="cp-timeline-sub">' + window.cpEsc(subGoal.title) + '</div>'
      if (c.mood) html += '<div class="cp-timeline-mood">' + ({ good: '😊', normal: '😐', bad: '😔' }[c.mood] || '') + '</div>'
      if (c.reflection) html += '<div class="cp-timeline-reflection">' + window.cpEsc(c.reflection) + '</div>'
      html += '</div></div>'
    })
    html += '</div></div>'
    return html
  }

  V.removeTodayRecord = async function (checkinId) {
    const ch = window.appState.current
    if (!ch) return
    if (!window.confirm('撤销这条打卡记录？撤销后不可恢复。')) return
    try {
      await window.api.delete('/challenges/' + ch.id + '/checkins/' + checkinId)
      window.cpToast('已撤销该条打卡')
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '撤销失败')) }
  }

  V._adaptiveCard = function (a) {
    let html = '<div class="cp-adapt-card"><div class="cp-adapt-head"><i class="fas fa-sliders"></i> 教练为你调整了计划</div><p class="cp-adapt-reason">' + window.cpEsc(a.reason || '') + '</p>'
    if (a.task && a.task.title) {
      html += '<div class="cp-adapt-task"><span class="cp-adapt-day">第 ' + (a.target_day || a.task.day || '?') + ' 天新任务</span><b>' + window.cpEsc(a.task.title) + '</b>'
      if (a.task.description) html += '<p>' + window.cpEsc(a.task.description) + '</p>'
      if (a.task.tip) html += '<p>💡 ' + window.cpEsc(a.task.tip) + '</p>'
      html += '</div>'
    }
    html += '<div class="cp-sub-actions" style="margin-top:10px"><button class="cp-btn-ghost" onclick="cpViews.home.respondAdaptive(false)">保持原计划</button><button class="cp-btn-primary" onclick="cpViews.home.respondAdaptive(true)"><i class="fas fa-check"></i> 采纳调整</button></div></div>'
    return html
  }

  V._diagEntry = function (missedCount) {
    return '<div class="cp-adapt-card" style="border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.07)"><div class="cp-adapt-head" style="color:var(--red)"><i class="fas fa-stethoscope"></i> 断签了？AI 帮你找原因</div><p class="cp-adapt-reason">已有 ' + missedCount + ' 天缺失。断签不是失败，找不到原因才是。AI 分析打卡记录，为你定制重启方案。</p><div class="cp-sub-actions" style="margin-top:0"><button class="cp-btn-ghost" onclick="cpOpenShare(\'flop\')"><i class="fas fa-share-nodes"></i> 翻车复盘海报</button><button class="cp-btn-primary" onclick="cpViews.home.doDiagnose()"><i class="fas fa-wand-magic-sparkles"></i> 一键诊断重启</button></div></div>'
  }

  V.respondAdaptive = async function (accept) {
    const ch = window.appState.current
    const a = this.data.adaptive
    if (!ch || !a) return
    try {
      await window.api.post('/challenges/' + ch.id + '/adaptive/' + a.id + '/respond', { accept: !!accept })
      window.cpToast(accept ? '已采纳新任务，即刻生效' : '好的，保持原计划')
      this.data.adaptive = null
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '操作失败')) }
  }

  V.doDiagnose = async function () {
    const ch = window.appState.current
    if (!ch) return
    const dg = window.appState.diagnosis
    dg.show = true
    dg.loading = true
    dg.report = null
    dg.applying = false
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/diagnose', {})
      dg.report = res.data || res
    } catch (e) {
      dg.show = false
      window.cpToast(window.cpErrMsg(e, '诊断失败，请稍后再试'))
    } finally { dg.loading = false }
  }

  V.applyDiagnosis = async function (action) {
    const ch = window.appState.current
    const dg = window.appState.diagnosis
    if (!ch || dg.applying) return
    dg.applying = true
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/diagnose/apply', { action: action || 'keep' })
      const r = res.data || res
      window.cpToast(r.message || '已应用方案')
      dg.show = false
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '应用失败')) }
    finally { dg.applying = false }
  }
})()
;(function () {
  const V = window.cpViews.home

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

  V.igniteDown = function (e) {
    const d = this.data
    if (d.checking || (d.today && d.today.checked_in)) return
    if (e.cancelable) e.preventDefault()
    const btn = e.currentTarget
    if (!btn || btn.disabled) return
    this.igniteUp()
    const ig = { btn, start: Date.now(), raf: 0, done: false }
    this._ignite = ig
    btn.classList.add('charging')
    const tick = () => {
      if (this._ignite !== ig || ig.done) return
      const p = Math.min(1, (Date.now() - ig.start) / 1000)
      ig.btn.style.setProperty('--p', p.toFixed(3))
      if (p >= 1) {
        ig.done = true
        this._ignite = null
        ig.btn.classList.remove('charging')
        this.doCheckin('full')
        return
      }
      ig.raf = requestAnimationFrame(tick)
    }
    ig.raf = requestAnimationFrame(tick)
  }

  V.igniteUp = function () {
    const ig = this._ignite
    if (!ig) return
    ig.done = true
    cancelAnimationFrame(ig.raf)
    if (ig.btn) {
      ig.btn.classList.remove('charging')
      ig.btn.style.setProperty('--p', 0)
    }
    this._ignite = null
  }

  V.doMini = function () { this.doCheckin('mini') }

  V.doFastTap = async function (value) {
    const ch = window.appState.current
    const d = this.data
    const t = d.today
    if (!ch || !t || d.checking) return
    const v = Number(value) || 1
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', { value: v })
      const r = res.data || res
      const total = r.today_total || 0
      const target = (t.today_target || ch.target_value || 1)
      if (t.goal_rule === 'ladder' && ch.direction === 'decrease') {
        const rem = Math.max(0, (r.remaining !== undefined ? r.remaining : (target - total)))
        window.cpCelebrate('已记录 +' + v + ' ' + (ch.unit || '') + ' · 还可 ' + rem + (ch.unit || ''))
      } else {
        window.cpCelebrate('已记录 +' + v + ' ' + (ch.unit || '') + ' · 今日 ' + total + '/' + target)
      }
      await this._finishCheckin(r, ch, d, t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '记录失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.adjustCount = function (delta) {
    const d = this.data
    d.taskValue = Math.max(0, d.taskValue + delta)
    this.rerender()
  }

  V.setCount = function (val) {
    this.data.taskValue = Math.max(0, val)
    this.rerender()
  }

  V.setText = function (val) {
    this.data.textValue = val || ''
  }

  V.toggleStep = function (stepEncoded) {
    const d = this.data
    const step = decodeURIComponent(stepEncoded)
    const idx = d.taskSteps.indexOf(step)
    if (idx >= 0) d.taskSteps.splice(idx, 1)
    else d.taskSteps.push(step)
    this.rerender()
  }

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

  V._finishCheckin = async function (r, ch, d, dateStr) {
    d.lastFeedback = r.ai_feedback || d.lastFeedback
    d.chest = r.chest_points || 0
    d.declaration = r.declaration || ''
    d.shields = r.shields || 0
    if (d.declaration && dateStr) {
      try { localStorage.setItem('cp_decl_' + ch.id + '_' + dateStr, d.declaration) } catch (e) {}
    }
    await this.load()
    await window.cpLoadChallenges()
    if (!r.ai_feedback && dateStr && window.cpPollTodayAi) window.cpPollTodayAi(ch.id, dateStr, 3)
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

  V.doMultiCheckin = async function () {
    const s = window.appState
    const ch = s.current
    const d = this.data
    const t = d.today
    if (!ch || !t || d.checking || t.checked_in) return
    const tt = t.task_type || ch.task_type || 'binary'
    const payload = { value: 1.0, reflection: '' }
    if (tt === 'counter' || tt === 'timer') {
      if (d.taskValue <= 0 && tt === 'counter') { window.cpToast('请输入完成数量'); return }
      payload.value = d.taskValue
    } else if (tt === 'step') {
      payload.value = d.taskSteps.length
      payload.reflection = d.taskSteps.join('；')
    } else if (tt === 'text') {
      if (!d.textValue.trim()) { window.cpToast('请写点什么再提交'); return }
      payload.value = d.textValue.length
      payload.reflection = d.textValue
    }
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', payload)
      const r = res.data || res
      window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
      d.taskValue = 0
      d.taskSteps = []
      d.textValue = ''
      await this._finishCheckin(r, ch, d, t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.doCheckin = async function (checkinType) {
    const s = window.appState
    const ch = s.current
    const d = this.data
    if (!ch || d.checking || (d.today && d.today.checked_in)) return
    d.checking = true
    this.rerender()
    try {
      const payload = { value: checkinType === 'mini' ? 0.5 : 1.0 }
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', payload)
      const r = res.data || res
      window.cpCelebrate((checkinType === 'mini' ? '微打卡 · 节奏守住 +' : '打卡成功 +') + (r.points_earned || 0) + ' 分')
      await this._finishCheckin(r, ch, d, d.today && d.today.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V._checkinArea = function (tt, t) {
    const d = this.data
    const dis = d.checking ? 'disabled' : ''
    if (tt === 'counter') return this._counterUI(t, dis)
    if (tt === 'timer') return this._timerUI(t, dis)
    if (tt === 'step') return this._stepUI(t, dis)
    if (tt === 'text') return this._textUI(t, dis)
    return this._binaryUI(dis)
  }

  V._counterUI = function (t, dis) {
    const d = this.data
    const target = t.task_target || 1
    const unit = window.cpEsc(t.task_unit || '')
    let h = '<div class="cp-checkin-box"><div class="cp-counter-row">'
    h += '<button class="cp-counter-btn" ' + dis + ' onclick="cpViews.home.adjustCount(-5)">−5</button>'
    h += '<div class="cp-counter-display"><span class="cp-counter-val">' + d.taskValue + '</span><span class="cp-counter-target">/ ' + target + ' ' + unit + '</span></div>'
    h += '<button class="cp-counter-btn" ' + dis + ' onclick="cpViews.home.adjustCount(5)">+5</button></div>'
    h += '<div class="cp-counter-quick">'
    ;[0.25, 0.5, 0.75, 1].forEach(p => { const v = Math.round(target * p); h += '<button class="cp-quick-btn" ' + dis + ' onclick="cpViews.home.setCount(' + v + ')">' + v + '</button>' })
    h += '</div>' + this._submitBtn(dis) + this._miniLink(dis) + '</div>'
    return h
  }

  V._timerUI = function (t, dis) {
    const d = this.data
    const target = t.task_target || 10
    let h = '<div class="cp-checkin-box"><div class="cp-timer-display"><span class="cp-timer-val">' + this._fmtTime(d.taskValue) + '</span><span class="cp-timer-target">/ ' + target + ' ' + window.cpEsc(t.task_unit || '分钟') + '</span></div>'
    h += '<div class="cp-timer-presets">'
    ;[5, 10, 15, 20, 30].filter(p => p <= target * 1.5).forEach(p => { h += '<button class="cp-preset-btn" ' + dis + ' onclick="cpViews.home.setCount(' + p + ')">' + p + '分</button>' })
    h += '</div>' + this._submitBtn(dis) + this._miniLink(dis) + '</div>'
    return h
  }

  V._stepUI = function (t, dis) {
    const d = this.data
    const steps = t.task_steps || []
    let h = '<div class="cp-checkin-box"><div class="cp-step-list">'
    steps.forEach(st => {
      const done = d.taskSteps.includes(st)
      h += '<div class="cp-step-item' + (done ? ' done' : '') + '" onclick="cpViews.home.toggleStep(\'' + encodeURIComponent(st) + '\')"><span class="cp-step-check">' + (done ? '✓' : '○') + '</span><span class="cp-step-text">' + window.cpEsc(st) + '</span></div>'
    })
    h += '</div><button class="cp-btn-primary" ' + dis + ' onclick="cpViews.home.doMultiCheckin()"><i class="fas fa-check"></i> 提交打卡 (' + d.taskSteps.length + '/' + steps.length + ')</button>'
    h += this._miniLink(dis) + '</div>'
    return h
  }

  V._textUI = function (t, dis) {
    const d = this.data
    const target = t.task_target || 0
    const unit = window.cpEsc(t.task_unit || '字')
    const len = (d.textValue || '').length
    let h = '<div class="cp-checkin-box"><div class="cp-text-area">'
    h += '<textarea class="cp-text-input" ' + dis + ' placeholder="记录你的想法、感受或今天的收获..." oninput="cpViews.home.setText(this.value)" style="resize:none;font-size:15px;line-height:1.6;min-height:120px">' + window.cpEsc(d.textValue || '') + '</textarea>'
    if (target > 0) h += '<div class="cp-text-counter"><span class="cp-text-count' + (len >= target ? ' done' : '') + '">' + len + '</span> / ' + target + ' ' + unit + '</div>'
    else h += '<div class="cp-text-counter"><span class="cp-text-count">' + len + '</span> 字</div>'
    h += '</div>'
    h += '<button class="cp-btn-primary" ' + dis + ' onclick="cpViews.home.doMultiCheckin()"><i class="fas fa-feather"></i> 提交记录</button>'
    h += this._miniLink(dis) + '</div>'
    return h
  }

  V._binaryUI = function (dis) {
    const d = this.data
    return '<div class="cp-ignite-wrap"><button class="cp-ignite-btn" ' + dis + ' onpointerdown="cpViews.home.igniteDown(event)" onpointerup="cpViews.home.igniteUp()" onpointerleave="cpViews.home.igniteUp()" onpointercancel="cpViews.home.igniteUp()" oncontextmenu="return false"><i class="fas fa-fire"></i><span>' + (d.checking ? '点燃中' : '长按点火') + '</span></button><span class="cp-ignite-hint">按住 1 秒点燃今日，松手取消</span>' + this._miniLink(dis) + '</div>'
  }

  V._submitBtn = function (dis) {
    return '<button class="cp-btn-primary" ' + dis + ' onclick="cpViews.home.doMultiCheckin()"><i class="fas fa-check"></i> 提交打卡</button>'
  }

  V._miniLink = function (dis) {
    return '<button class="cp-mini-link" ' + dis + ' onclick="cpViews.home.doMini()">今天太累？5分钟微打卡守住节奏</button>'
  }

  V._fmtTime = function (min) { return Math.floor(min / 60) + ':' + String(min % 60).padStart(2, '0') }

  V.doNuxSubmit = async function (payload) {
    const ch = window.appState.current
    const d = this.data
    const t = d.today
    if (!ch || !t || d.checking) return
    const tt = t.task_type || ch.task_type || 'binary'
    const data = { value: payload.value || 0, reflection: payload.reflection || '', context_tag: '', sub_goal_id: null }
    if (tt === 'counter' && data.value <= 0) { window.cpToast('请输入完成数量'); return }
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', data)
      const r = res.data || res
      window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
      await this._finishCheckin(r, ch, d, t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }
})()

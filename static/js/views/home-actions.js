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
})()

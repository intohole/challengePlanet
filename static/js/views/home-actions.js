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

  V.doCheckin = async function (checkinType) {
    const s = window.appState
    const ch = s.current
    const d = this.data
    if (!ch || d.checking || (d.today && d.today.checked_in)) return
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', { checkin_type: checkinType || 'full' })
      const r = res.data || res
      window.cpCelebrate((checkinType === 'mini' ? '微打卡 · 节奏守住 +' : '打卡成功 +') + (r.points_earned || 0) + ' 分')
      d.lastFeedback = r.ai_feedback || d.lastFeedback
      d.chest = r.chest_points || 0
      d.declaration = r.declaration || ''
      d.shields = r.shields || 0
      if (d.declaration && d.today && d.today.date) {
        try { localStorage.setItem('cp_decl_' + ch.id + '_' + d.today.date, d.declaration) } catch (e) {}
      }
      await this.load()
      await window.cpLoadChallenges()
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.doRepair = async function () {
    const ch = window.appState.current
    if (!ch) return
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/repair', {})
      const r = res.data || res
      window.cpToast(r.message || '已修复！偶尔断签没关系，重要的是继续前进')
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '修复失败')) }
  }

  V.openDayDetail = function (ds) {
    const ch = window.appState.current
    const rec = this.data.checkins.find(c => c.date === ds)
    if (!rec) return
    const plan = (ch.ai_plan || [])[(rec.day_number || 1) - 1] || {}
    window.appState.dayDetail = {
      date: ds,
      day: rec.day_number || 1,
      status: rec.status || 'checked',
      taskTitle: plan.title || '',
      mood: rec.mood || '',
      reflection: rec.reflection || '',
      aiFeedback: rec.ai_feedback || '',
    }
  }
  V.closeDayDetail = function () { window.appState.dayDetail = null }

  V.openMend = function () {
    const m = this.data.mercy
    if (!m) return
    window.appState.mend = { show: true, dates: m.missed_dates || [], left: m.mend_left_this_month || 0, busy: false }
  }
  V.doMend = async function (ds) {
    const ch = window.appState.current
    const md = window.appState.mend
    if (!ch || md.busy) return
    md.busy = true
    try {
      await window.api.post('/challenges/' + ch.id + '/mend', { date: ds })
      window.cpToast('补签成功！又补上了一块拼图')
      md.show = false
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '补签失败')) }
    finally { md.busy = false }
  }

  V.openFreeze = function () {
    const ch = window.appState.current
    const m = this.data.mercy
    if (!ch) return
    const today = window.cpTodayStr()
    const end = ch.end_date || window.cpAddDays(today, 7)
    const dates = []
    for (let i = 1; i <= 7; i++) {
      const ds = window.cpAddDays(today, i)
      if (ds > end) break
      dates.push(ds)
    }
    window.appState.freeze = { show: true, dates, left: (m && m.freeze_left_this_week) || 0, busy: false }
  }
  V.doFreeze = async function (ds) {
    const ch = window.appState.current
    const fz = window.appState.freeze
    if (!ch || fz.busy) return
    fz.busy = true
    try {
      await window.api.post('/challenges/' + ch.id + '/freeze', { date: ds })
      window.cpToast('已冻结 ' + ds + '，该日不计断签')
      fz.show = false
      await this.load()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '冻结失败')) }
    finally { fz.busy = false }
  }

  V.openReflection = function () {
    const t = this.data.today
    const cd = (t && t.checkin_data) || {}
    window.appState.reflection = { show: true, mood: cd.mood || 'good', content: cd.reflection || '', busy: false }
  }
  V.saveReflection = async function () {
    const ch = window.appState.current
    const rf = window.appState.reflection
    if (!ch || rf.busy) return
    rf.busy = true
    try {
      const res = await window.api.patch('/challenges/' + ch.id + '/checkin/today', { mood: rf.mood, reflection: rf.content })
      const r = res.data || res
      if (r.ai_feedback) this.data.lastFeedback = r.ai_feedback
      window.cpToast('心得已保存')
      rf.show = false
      await this.load()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '保存失败')) }
    finally { rf.busy = false }
  }
})()

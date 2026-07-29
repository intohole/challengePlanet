;(function () {
  const V = window.cpViews.home

  V.doRepair = async function () {
    const ch = window.appState.current
    if (!ch) return
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/repair', {})
      const r = res.data || res
      window.cpToast(r.message || '已修复！偶尔断签没关系，重要的是继续前进')
      await this.load()
      await window.cpLoadChallenges()
      this.data.justRepaired = true
      this.rerender()
      setTimeout(() => { this.data.justRepaired = false; this.rerender() }, 3000)
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

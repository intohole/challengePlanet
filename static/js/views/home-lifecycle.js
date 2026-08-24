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
    setTimeout(() => {
      const box = document.getElementById('cp-dd-ai')
      if (!box || !rec.ai_feedback) return
      if (window.NexusMarkdown) window.NexusMarkdown.renderToAsync(box, rec.ai_feedback).catch(() => { box.textContent = rec.ai_feedback })
      else box.textContent = rec.ai_feedback
    }, 0)
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
      if (window.cpPollTodayAi && this.data.today) window.cpPollTodayAi(ch.id, this.data.today.date, 3)
      window.cpToast('心得已保存')
      rf.show = false
      await this.load()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '保存失败')) }
    finally { rf.busy = false }
  }

  if (window.cpNuxMounted) return
  window.cpNuxMounted = true

  let _app = null

  window.cpNuxTeardown = function () {
    if (_app) {
      try { _app.unmount() } catch (e) {}
      _app = null
    }
  }

  window.cpNuxMount = function (el) {
    window.cpNuxTeardown()
    if (!el || !window.NuxCheckin) return
    const s = window.appState
    if (!s || !V || !s.current) return
    const ch = s.current
    const d = V.data
    const t = d.today
    const mercy = d.mercy || {}
    const tt = (t && t.task_type) || ch.task_type || 'binary'
    const active = ch.status === 'active'
    const isDeco = ch.decompose_mode === 'time_slot' || (t && t.sub_goals && t.sub_goals.length) || tt === 'step' || tt === 'counter' || tt === 'timer'
    const props = {
      title: ch.title || '',
      icon: ch.icon || '🔥',
      taskType: isDeco ? '' : tt,
      taskTitle: (t && t.task_title) || '',
      taskDesc: (t && t.task_description) || '',
      taskTarget: (t && t.task_target) || 1,
      unit: (t && t.task_unit) || ch.unit || '',
      direction: ch.direction || 'increase',
      baseline: (t && t.dynamic_baseline) || 0,
      checkedIn: !!(t && t.checked_in),
      todayTotal: (t && t.today_total) || 0,
      todayTarget: (t && t.today_target) || 1,
      streak: ch.streak || 0,
      prevStreak: ch.prev_streak || 0,
      completedDays: ch.completed_days || 0,
      totalDays: ch.total_days || 0,
      startDate: active ? (ch.start_date || '') : '',
      endDate: ch.end_date || '',
      records: d.checkins || [],
      shields: mercy.shields || d.shields || 0,
      mendLeft: mercy.mend_left_this_month || 0,
      freezeLeft: mercy.freeze_left_this_week || 0,
      missedDates: mercy.missed_dates || [],
      loading: d.loading && !d.today,
      celebrateText: (s.celebrate && s.celebrateText) || '',
      task: !isDeco
    }
    const api = { checkin: p => V.doCheckin(p && p.value >= 1 ? 'full' : 'mini'), 'quick-checkin': p => V.doNuxSubmit(p), mend: () => V.openMend(), freeze: () => V.openFreeze(), repair: () => V.doRepair(), 'open-day': ds => V.openDayDetail(ds) }
    const handlers = {}
    Object.keys(api).forEach(k => {
      const cased = k.replace(/^./, c => c.toUpperCase()).replace(/-([a-z])/g, (m, c) => c.toUpperCase())
      handlers['on' + cased] = api[k]
    })
    _app = Vue.createApp({
      components: { NuxCheckin: window.NuxCheckin },
      setup() { return { props, handlers } },
      template: '<NuxCheckin v-bind="props" @checkin="handlers.onCheckin" @quickCheckin="handlers.onQuickCheckin" @mend="handlers.onMend" @freeze="handlers.onFreeze" @repair="handlers.onRepair" @openDay="handlers.onOpenDay"></NuxCheckin>'
    })
    try { _app.mount(el) } catch (e) { window.cpNuxTeardown() }
  }
})()
;(function () {
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
    const V = window.cpViews.home
    if (!s || !V || !s.current) return
    const ch = s.current
    const d = V.data
    const t = d.today
    const mercy = d.mercy || {}
    const tt = (t && t.task_type) || ch.task_type || 'binary'
    const active = ch.status === 'active'
    const isDeco = ch.decompose_mode === 'time_slot' || (t && t.sub_goals && t.sub_goals.length) || tt === 'step'
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
    Object.keys(api).forEach(k => { handlers['on' + k.replace(/-([a-z])/g, (m, c) => c.toUpperCase())] = api[k] })
    _app = Vue.createApp({
      components: { NuxCheckin: window.NuxCheckin },
      setup() { return { props, handlers } },
      template: '<NuxCheckin v-bind="props" @checkin="handlers.onCheckin" @quickCheckin="handlers.onQuickCheckin" @mend="handlers.onMend" @freeze="handlers.onFreeze" @repair="handlers.onRepair" @openDay="handlers.onOpenDay"></NuxCheckin>'
    })
    try { _app.mount(el) } catch (e) { window.cpNuxTeardown() }
  }
})()
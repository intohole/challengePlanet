window.cpPrefix = window.PATH_PREFIX || ''
window.api = new NexusApi({
  baseUrl: window.cpPrefix + '/api/v1',
  tokenKey: 'uc_access_token',
  onUnauthorized: () => {
    ['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(k => localStorage.removeItem(k))
    window.location.href = window.cpPrefix + '/login'
  }
})

const { createApp, reactive } = Vue

window.cpApi = {
  unwrap: p => p.then(r => (r && r.data !== undefined ? r.data : r)),
  get: url => window.cpApi.unwrap(window.api.get(url)),
  post: (url, payload) => window.cpApi.unwrap(window.api.post(url, payload || {})),
  patch: (url, payload) => window.cpApi.unwrap(window.api.patch(url, payload || {})),
  put: (url, payload) => window.cpApi.unwrap(window.api.put(url, payload || {})),
  today: id => window.cpApi.get('/challenges/' + id + '/today'),
  checkins: id => window.cpApi.get('/challenges/' + id + '/checkins').then(d => Array.isArray(d) ? d : ((d && d.items) || [])),
  checkin: (id, payload) => window.cpApi.post('/challenges/' + id + '/checkin', payload),
  deleteCheckin: (id, checkinId) => window.cpApi.unwrap(window.api.delete('/challenges/' + id + '/checkins/' + checkinId)),
  patchCheckinMeta: (id, checkinId, patch) => window.cpApi.patch('/challenges/' + id + '/checkins/' + checkinId + '/meta', patch || {}),
  deleteChallenge: (id, mode) => window.cpApi.unwrap(window.api.delete('/challenges/' + id + (mode === 'purge' ? '?mode=purge' : ''))),
  archives: () => window.cpApi.get('/archives'),
  archiveSummary: () => window.cpApi.get('/archives/summary'),
}

const state = reactive({
  view: 'home',
  booted: false,
  nickname: localStorage.getItem('cp_nickname') || '挑战者',
  userId: localStorage.getItem('cp_user_id') || '',
  challenges: [],
  current: null,
  pendingCount: 0,
  loadError: '',
  celebrate: false,
  celebrateText: '',
  stars: [],
  create: { show: false, step: 1, rawInput: '', startMode: 'today', customDate: '', startDate: '', sceneTemplate: '', phase: 'idle', parsed: null, editTitle: '', editDays: 66, editCategory: 'build', editDesc: '', plan: [], suggestions: [], error: '', saving: false, source: 'web', genTotal: 0, genTitle: '', startedAt: 0, genTick: 0, adjustHint: '', adjusting: false },
  dayDetail: null,
  mend: { show: false, dates: [], left: 0, busy: false },
  freeze: { show: false, dates: [], left: 0, busy: false },
  reflection: { show: false, mood: '', content: '', busy: false },
  share: { show: false, url: '', loading: false, mode: 'win' },
  sharedConfig: { show: false, loading: false, config: null, importing: false, token: '' },
  diagnosis: { show: false, loading: false, report: null, applying: false },
  reportView: { show: false, tab: 'overview', loading: false, overview: null, hourly: null, trend: null, heatmap: null, completion: null },
  companion: { show: false, sessions: false },
  companionMeta: {},
  companionQueue: { position: 0, wait: 0 },
  endModal: { show: false, id: 0, title: '', busy: false },
  archiveView: { show: false, data: null },
})
window.appState = state

window.cpEsc = s => window.NexusUtils.escapeHtml(s)

window.cpFmtInt = v => window.NexusUtils.formatNumber(v, 0)

window.cpFmtNum = v => {
  const n = Number(v) || 0
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10)
}

window.cpOpenArchive = function (id) {
  const a = (window.cpArchiveCache || []).find(x => String(x.id) === String(id))
  if (!a) return
  state.archiveView = { show: true, data: a }
}
window.cpCloseArchive = function () {
  state.archiveView = { show: false, data: null }
}

window.cpTitleClean = s => String(s == null ? '' : s).replace(/[，,、]\s*(当前|进行中|打卡中|现在|目前)\s*$/, '').trim()

window.cpMd = s => {
  if (window.NexusMarkdown && window.NexusMarkdown.render) return window.NexusMarkdown.render(String(s == null ? '' : s))
  return window.cpEsc(s)
}
if (window.NexusMarkdown && window.NexusMarkdown.injectLibs) window.NexusMarkdown.injectLibs()

window.cpTodayStr = () => window.NexusUtils.cnTodayStr()
window.cpDateStr = d => window.NexusUtils.formatDateShort(d).replace(/\//g, '-')
window.cpAddDays = (ds, n) => {
  const d = new Date(ds + 'T00:00:00')
  d.setDate(d.getDate() + n)
  return window.cpDateStr(d)
}

let _cpToastLast = { msg: '', at: 0 }
window.cpToast = (msg, ms = 2600) => {
  const now = Date.now()
  if (msg && msg === _cpToastLast.msg && now - _cpToastLast.at < 4000) return
  _cpToastLast = { msg: msg || '', at: now }
  if (typeof window.showToast === 'function') window.showToast(msg, 'info', ms)
}
window.cpCelebrate = text => {
  state.celebrateText = text || '打卡成功！'
  state.stars = Array.from({ length: 14 }, (_, i) => {
    const angle = (Math.PI * 2 * i) / 14 + Math.random() * 0.5
    const dist = 90 + Math.random() * 130
    return { dx: Math.cos(angle) * dist + 'px', dy: Math.sin(angle) * dist + 'px', size: 12 + Math.random() * 14 + 'px', delay: Math.random() * 0.25 + 's' }
  })
  state.celebrate = true
  setTimeout(() => { state.celebrate = false }, 1250)
}
window.cpErrMsg = (e, fallback) => {
  if (window.mapHttpError && e && e.name === 'NexusApiError') return window.mapHttpError(e)
  if (window.NexusErrorText) {
    const mapped = window.NexusErrorText.fromError(e, fallback || '操作失败，请稍后重试')
    return mapped.message || mapped.title
  }
  return (e && e.message) || fallback || '操作失败，请稍后重试'
}
window.cpCopy = text => {
  NexusUtils.copyText(text, { success: '已复制，发给好友组队打卡' })
}

async function loadChallenges() {
  try {
    const res = await window.api.get('/challenges')
    const d = res.data || res
    state.challenges = Array.isArray(d) ? d : (d.items || d.challenges || [])
    state.loadError = ''
  } catch (e) {
    if (!state.challenges.length) state.challenges = []
    state.loadError = window.cpErrMsg(e, '加载失败，请稍后重试')
  }
  const prevId = state.current && state.current.id
  const active = state.challenges.find(c => c.status === 'active') || state.challenges[0] || null
  state.current = (prevId && state.challenges.find(c => c.id === prevId)) || active
  state.pendingCount = state.challenges.filter(c => c.status === 'active' && !c.today_checked && !(c.direction === 'decrease' && (c.task_type === 'counter' || c.task_type === 'timer'))).length
  return state.challenges
}
window.cpLoadChallenges = loadChallenges

window.cpSelectChallenge = id => {
  id = Number(id)
  const ch = state.challenges.find(c => c.id === id)
  if (!ch) return
  state.current = ch
  switchView('home')
}

function switchView(v) {
  state.view = v
  const el = document.getElementById('view-root')
  const view = window.cpViews && window.cpViews[v]
  if (el && view) {
    view.render(el)
    if (view.onShow) view.onShow()
  }
}

function handleQuery() {
  try {
    const q = new URLSearchParams(window.location.search)
    if (q.get('shared')) {
      const token = q.get('shared')
      state.sharedConfig = { show: true, loading: true, config: null, importing: false, token }
      window.api.get('/challenges/shared/' + token).then(res => {
        const d = res.data || res
        state.sharedConfig.config = d
        state.sharedConfig.loading = false
      }).catch(() => {
        state.sharedConfig.loading = false
        state.sharedConfig.config = null
      })
      window.history.replaceState({}, '', window.cpPrefix + '/')
    }
    if (q.get('from') === 'decision' && q.get('title')) {
      const title = q.get('title') || ''
      const desc = q.get('desc') || ''
      const days = parseInt(q.get('days') || '0', 10)
      window.cpCreate.open({ rawInput: desc ? title + '，' + desc : title, days: days || 0, source: 'lifecompass' })
      window.history.replaceState({}, '', window.cpPrefix + '/')
    }
    const chParam = q.get('ch')
    if (chParam) {
      const target = state.challenges.find(c => String(c.id) === chParam)
      if (target) {
        state.current = target
        const gradParam = q.get('grad')
        state.slipDeeplink = q.get('slip') === '1' ? target.id : null
        window.cpToast(gradParam
          ? '🎓 减量阶梯毕业，来看看你的旅程'
          : (q.get('rescue') ? '来看看「' + (window.cpTitleClean(target.title) || '') + '」，星轨还在' : '已切换到「' + (window.cpTitleClean(target.title) || '') + '」'))
      }
      window.history.replaceState({}, '', window.cpPrefix + '/')
    }
  } catch (e) {}
}

async function importShared() {
  if (!state.sharedConfig.token || state.sharedConfig.importing) return
  state.sharedConfig.importing = true
  try {
    await window.api.post('/challenges/import/' + state.sharedConfig.token, {})
    state.sharedConfig.show = false
    window.cpToast('导入成功！开始你的挑战吧')
    await loadChallenges()
    switchView('home')
  } catch (e) {
    window.cpToast(window.cpErrMsg(e, '导入失败'))
  } finally {
    state.sharedConfig.importing = false
  }
}

function gradJourneyOf() {
  const home = window.cpViews && window.cpViews.home
  const t = home && home.data && home.data.today
  const j = t && t.journey
  return (j && j.graduation) ? j : null
}

async function openShare(mode) {
  if (!state.current) return
  const gradMode = mode === 'grad'
  if (gradMode) {
    const j = gradJourneyOf()
    if (!j) { window.cpToast('减量阶梯挑战才有毕业证书'); return }
    if (j.graduation.state !== 'graduated') { window.cpToast('走完阶梯那天证书就会生成'); return }
  }
  state.share.show = true
  state.share.loading = true
  state.share.url = ''
  state.share.mode = mode === 'flop' ? 'flop' : (gradMode ? 'grad' : 'win')
  try {
    state.share.url = state.share.mode === 'flop'
      ? await window.cpSharePoster.generateFlop(state.current)
      : state.share.mode === 'grad'
        ? await window.cpGradCert.generate(gradJourneyOf(), state.current)
        : await window.cpSharePoster.generate(state.current)
  } catch (e) {
    state.share.show = false
    window.cpToast(window.cpErrMsg(e, '海报生成失败'))
  } finally {
    state.share.loading = false
  }
}
window.cpOpenShare = openShare
window.cpShareGradAvailable = function () {
  const j = gradJourneyOf()
  return !!(j && j.graduation && j.graduation.state === 'graduated')
}
function saveShareImage() {
  if (!state.share.url) return
  const tag = state.share.mode === 'flop' ? '翻车复盘_' : (state.share.mode === 'grad' ? '毕业证书_' : '')
  const a = document.createElement('a')
  a.href = state.share.url
  a.download = '星轨挑战_' + tag + (state.current.title || '分享') + '.png'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.cpToast('图片已保存，快去分享吧')
}
function copyShareText() {
  const c = state.current
  if (!c) return
  const url = window.location.origin + window.cpPrefix
  const text = state.share.mode === 'flop'
    ? '我在星轨挑战「' + c.title + '」翻车后回来了！\n断签不可怕，可怕的是不再开始。已完成 ' + (c.completed_days || 0) + '/' + c.total_days + ' 天\n来星轨挑战，真实打卡，允许翻车\n' + url
    : state.share.mode === 'grad'
      ? '我在星轨挑战的「' + c.title + '」减量阶梯毕业了！🎓\n累计少抽 ' + ((gradJourneyOf() || {}).cigarettes_avoided || 0) + ' 根，减量 ' + (((gradJourneyOf() || {}).reduction_pct) || 0) + '%\n来星轨挑战，每一根没抽的烟都算数\n' + url
      : '我在星轨挑战参加「' + c.title + '」挑战！\n已完成 ' + (c.completed_days || 0) + '/' + c.total_days + ' 天，连续打卡 ' + (c.streak || 0) + ' 天\n来星轨挑战，和我一起变得更好！\n' + url
  window.cpCopy(text)
}
function logout() {
  ;['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(k => localStorage.removeItem(k))
  window.location.href = window.cpPrefix + '/login'
}

const cpApp = createApp({
  setup() {
    const companionChatRef = Vue.ref(null)
    window.cpCompanionChatRef = companionChatRef
    const companionQuickReplies = [
      { icon: '💪', text: '今天有点不想坚持了' },
      { icon: '📊', text: '帮我看看我的进度' },
      { icon: '🔥', text: '给我点鼓励' },
      { icon: '🧭', text: '我该怎么做才能坚持' },
    ]
    const riskLabel = l => ({ high: '高风险', medium: '需留意', low: '节奏稳定' }[l] || '节奏稳定')
    const titleClean = t => window.cpTitleClean(t)
    const genRatio = () => {
        const c = state.create
        const elapsed = (Date.now() - (c.startedAt || Date.now())) / 1000
        return Math.min(0.92, Math.max(0.05, elapsed / 6))
      }
      setInterval(() => {
        const c = state.create
        if (c.show && (c.phase === 'parsing' || c.phase === 'planning')) c.genTick += 1
      }, 400)
      return {
      state,
      cpScenes: window.cpScenes,
      cpTaskTypeLabel: window.cpTaskTypeLabel,
      home: window.cpViews.home,
      cr: window.cpCreate,
      cpCompanion: window.cpCompanion,
      companionChatRef,
      companionQuickReplies,
      riskLabel,
      titleClean,
      switchView,
      openShare,
      cpShareGradAvailable: window.cpShareGradAvailable,
      saveShareImage,
      copyShareText,
      importShared,
      logout,
      openCreate: () => window.cpCreate.open(),
      endJourneyArchive: window.cpEndJourneyArchive,
      endJourneyPurge: window.cpEndJourneyPurge,
      closeArchive: window.cpCloseArchive,
      cpFmtNum: window.cpFmtNum,
      archiveMilestones: a => {
        const labels = { 50: '累计少抽 50 根', 100: '累计少抽 100 根', 200: '累计少抽 200 根', 500: '累计少抽 500 根', 1000: '累计少抽 1000 根' }
        return (a.milestones || []).map(k => ({ key: k, label: labels[String(k).replace('avoided_', '')] || String(k) }))
      },
      archivePct: a => {
        const b = Number(a.baseline) || 0
        const f = Number(a.final_cap) || 0
        return b > 0 && f < b ? Math.max(1, Math.round((b - f) / b * 100)) : 0
      },
      genRatio,
      genStatus: () => {
        const total = state.create.genTotal || 0
        const r = genRatio()
        if (r < 0.3) return '正在理解你的目标，设计专属计划…'
        if (r < 0.7) return '正在编排' + (total ? ' ' + total + ' 天' : '') + '的逐日节奏…'
        if (r < 0.9) return '正在安排稳扎稳打的巩固期…'
        return '正在收尾，准备出发'
      },
      milestoneNodes: () => {
        const c = state.create
        const days = c.editDays || c.genTotal || (c.plan.length ? c.plan[c.plan.length - 1].day : 0)
        if (!days || days < 7) return days === 1 ? [{ day: 1, label: '出发' }] : []
        const all = []
        for (let d = 7; d < days; d += 7) all.push(d)
        let picked = all
        if (all.length > 6) {
          const gap = Math.ceil(all.length / 6)
          picked = all.filter((_, i) => i % gap === 0)
        }
        const nodes = picked.map(d => ({ day: d, label: '回顾·盘点' }))
        nodes.unshift({ day: 1, label: '出发' })
        if (days > 1) nodes.push({ day: days, label: '收官冲刺' })
        return nodes
      },
    }
  },
  mounted() {
    if (!window.NexusUtils.createDualStorage().getItem('uc_access_token')) {
      window.location.href = window.cpPrefix + '/login'
      return
    }
    switchView('home')
    loadChallenges().then(() => {
      state.booted = true
      switchView(state.view)
      handleQuery()
    }).catch(e => {
      state.booted = true
      switchView(state.view)
      window.cpToast(window.cpErrMsg(e, '加载失败，请下拉刷新或稍后再试'))
    })
  }
})
NexusComponents.register(cpApp)
cpApp.mount('#app')

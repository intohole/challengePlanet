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

const state = reactive({
  view: 'home',
  booted: false,
  nickname: localStorage.getItem('cp_nickname') || '挑战者',
  userId: localStorage.getItem('cp_user_id') || '',
  challenges: [],
  current: null,
  pendingCount: 0,
  toast: '',
  celebrate: false,
  celebrateText: '',
  stars: [],
  create: { show: false, step: 1, rawInput: '', startMode: 'today', customDate: '', startDate: '', phase: 'idle', parsed: null, editTitle: '', editDays: 66, editCategory: 'build', editDesc: '', planText: '', plan: [], suggestions: [], error: '', saving: false, source: 'web' },
  dayDetail: null,
  mend: { show: false, dates: [], left: 0, busy: false },
  freeze: { show: false, dates: [], left: 0, busy: false },
  reflection: { show: false, mood: 'good', content: '', busy: false },
  share: { show: false, url: '', loading: false },
})
window.appState = state

window.cpTemplates = [
  { title: '戒烟挑战', category: 'quit', days: 42, icon: '🚭', desc: '告别香烟，找回健康呼吸' },
  { title: '每天读书30分钟', category: 'learn', days: 66, icon: '📚', desc: '用66天养成终身阅读习惯' },
  { title: '坚持跑步', category: 'fitness', days: 21, icon: '🏃', desc: '每天跑起来，激活身体' },
  { title: '早睡早起', category: 'build', days: 21, icon: '🌙', desc: '21天重建作息节律' },
  { title: '学习Python编程', category: 'learn', days: 42, icon: '💻', desc: '42天从零到能写项目' },
  { title: '每日冥想', category: 'mind', days: 21, icon: '🧘', desc: '每天10分钟正念练习' },
]

window.cpCategoryMap = {
  build: { icon: 'fa-seedling', color: '#34d399', label: '习惯养成' },
  quit: { icon: 'fa-ban', color: '#f87171', label: '戒除' },
  learn: { icon: 'fa-book', color: '#818cf8', label: '学习' },
  fitness: { icon: 'fa-dumbbell', color: '#fbbf24', label: '运动' },
  mind: { icon: 'fa-brain', color: '#c084fc', label: '心灵' },
  other: { icon: 'fa-star', color: '#635bff', label: '其他' },
}
window.cpCat = cat => window.cpCategoryMap[cat] || window.cpCategoryMap.other

window.cpEsc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')

window.cpTodayStr = () => {
  const d = new Date()
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
}
window.cpDateStr = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
window.cpAddDays = (ds, n) => {
  const d = new Date(ds + 'T00:00:00')
  d.setDate(d.getDate() + n)
  return window.cpDateStr(d)
}

let toastTimer = null
window.cpToast = (msg, ms = 2600) => {
  state.toast = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { state.toast = '' }, ms)
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
  return (e && e.message) || fallback || '操作失败，请稍后重试'
}
window.cpCopy = text => {
  const done = () => window.cpToast('已复制，发给好友组队打卡')
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => { window.cpCopyFallback(text); done() })
  } else { window.cpCopyFallback(text); done() }
}
window.cpCopyFallback = text => {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy') } catch (e) {}
  document.body.removeChild(ta)
}

async function loadChallenges() {
  const res = await window.api.get('/challenges')
  const d = res.data || res
  state.challenges = Array.isArray(d) ? d : (d.items || d.challenges || [])
  const prevId = state.current && state.current.id
  const active = state.challenges.find(c => c.status === 'active') || state.challenges[0] || null
  state.current = (prevId && state.challenges.find(c => c.id === prevId)) || active
  state.pendingCount = state.challenges.filter(c => c.status === 'active' && !c.today_checked).length
  return state.challenges
}
window.cpLoadChallenges = loadChallenges

window.cpSelectChallenge = id => {
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
    if (q.get('from') === 'decision' && q.get('title')) {
      const title = q.get('title') || ''
      const desc = q.get('desc') || ''
      const days = parseInt(q.get('days') || '0', 10)
      window.cpCreate.open({ rawInput: desc ? title + '，' + desc : title, days: days || 0, source: 'lifecompass' })
      window.history.replaceState({}, '', window.cpPrefix + '/')
    }
  } catch (e) {}
}

async function openShare() {
  if (!state.current) return
  state.share.show = true
  state.share.loading = true
  state.share.url = ''
  try {
    state.share.url = await window.cpSharePoster.generate(state.current)
  } catch (e) {
    state.share.show = false
    window.cpToast(window.cpErrMsg(e, '海报生成失败'))
  } finally {
    state.share.loading = false
  }
}
window.cpOpenShare = openShare
function saveShareImage() {
  if (!state.share.url) return
  const a = document.createElement('a')
  a.href = state.share.url
  a.download = '挑战星球_' + (state.current.title || '分享') + '.png'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.cpToast('图片已保存，快去分享吧')
}
function copyShareText() {
  const c = state.current
  if (!c) return
  const text = '我在挑战星球参加「' + c.title + '」挑战！\n已完成 ' + (c.completed_days || 0) + '/' + c.total_days + ' 天，连续打卡 ' + (c.streak || 0) + ' 天\n来挑战星球，和我一起变得更好！\n' + window.location.origin + window.cpPrefix
  window.cpCopy(text)
}
function logout() {
  ;['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(k => localStorage.removeItem(k))
  window.location.href = window.cpPrefix + '/login'
}

createApp({
  setup() {
    return {
      state,
      home: window.cpViews.home,
      cr: window.cpCreate,
      switchView,
      openShare,
      saveShareImage,
      copyShareText,
      logout,
      openCreate: () => window.cpCreate.open(),
    }
  },
  mounted() {
    if (!localStorage.getItem('uc_access_token')) {
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
}).mount('#app')

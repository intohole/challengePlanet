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
  create: { show: false, step: 1, rawInput: '', startMode: 'today', customDate: '', startDate: '', sceneTemplate: '', phase: 'idle', parsed: null, editTitle: '', editDays: 66, editCategory: 'build', editDesc: '', planText: '', plan: [], suggestions: [], error: '', saving: false, source: 'web' },
  dayDetail: null,
  mend: { show: false, dates: [], left: 0, busy: false },
  freeze: { show: false, dates: [], left: 0, busy: false },
  reflection: { show: false, mood: 'good', content: '', busy: false },
  share: { show: false, url: '', loading: false, mode: 'win' },
  diagnosis: { show: false, loading: false, report: null, applying: false },
})
window.appState = state

window.cpTemplates = [
  { title: '戒烟挑战', category: 'quit', days: 42, icon: '🚭', desc: '告别香烟，找回健康呼吸', scene: 'quit' },
  { title: '每天读书30分钟', category: 'learn', days: 66, icon: '📚', desc: '用66天养成终身阅读习惯', scene: 'reading' },
  { title: '坚持跑步', category: 'fitness', days: 21, icon: '🏃', desc: '从1公里到5公里，循序渐进', scene: 'running' },
  { title: '早睡早起', category: 'build', days: 21, icon: '🌙', desc: '21天重建作息节律', scene: 'morning' },
  { title: '每日冥想', category: 'mind', days: 21, icon: '🧘', desc: '每天10分钟正念练习', scene: 'meditation' },
  { title: '每日感恩', category: 'mind', days: 21, icon: '🙏', desc: '每天记录3件感恩的事', scene: 'gratitude' },
]

window.cpScenes = [
  { id: 'fitness', name: '健身', icon: '💪', color: '#f59e0b', task_type: 'counter', unit: '个', samples: ['30天每天30个俯卧撑', '21天腹肌撕裂者计划'] },
  { id: 'running', name: '跑步', icon: '🏃', color: '#f43f5e', task_type: 'counter', unit: '公里', samples: ['42天从0到5公里跑步计划', '每天跑步3公里'] },
  { id: 'study', name: '学习', icon: '📚', color: '#6366f1', task_type: 'counter', unit: '页', samples: ['30天每天读20页专业书', '考研复习66天计划'] },
  { id: 'reading', name: '阅读', icon: '📖', color: '#10b981', task_type: 'counter', unit: '页', samples: ['每天阅读30页', '21天养成阅读习惯'] },
  { id: 'meditation', name: '冥想', icon: '🧘', color: '#8b5cf6', task_type: 'timer', unit: '分钟', samples: ['每天冥想10分钟', '21天正念冥想入门'] },
  { id: 'morning', name: '早起', icon: '🌅', color: '#f97316', task_type: 'timer', unit: '点', samples: ['30天早起6点起床', '坚持每天7点前起床'] },
  { id: 'writing', name: '写作', icon: '✍️', color: '#8b5cf6', task_type: 'text', unit: '篇', samples: ['30天每日写作打卡', '21天晨间日记'] },
  { id: 'gratitude', name: '感恩', icon: '🙏', color: '#fbbf24', task_type: 'text', unit: '件', samples: ['21天感恩日记', '每天记录3件感恩的事'] },
  { id: 'water', name: '饮水', icon: '💧', color: '#06b6d4', task_type: 'counter', unit: '杯', samples: ['30天每天喝够8杯水', '21天养成喝水习惯'] },
  { id: 'quit', name: '戒断', icon: '🚭', color: '#ef4444', task_type: 'binary', unit: '次', samples: ['我要戒烟30天', '戒掉熬夜66天'] },
  { id: 'custom', name: '自定义', icon: '🎯', color: '#8b5cf6', task_type: 'binary', unit: '次', samples: ['自定义我的挑战', '30天不喝奶茶'] },
]
window.cpSceneMap = {}
window.cpScenes.forEach(s => { window.cpSceneMap[s.id] = s })

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

async function openShare(mode) {
  if (!state.current) return
  state.share.show = true
  state.share.loading = true
  state.share.url = ''
  state.share.mode = mode === 'flop' ? 'flop' : 'win'
  try {
    state.share.url = state.share.mode === 'flop'
      ? await window.cpSharePoster.generateFlop(state.current)
      : await window.cpSharePoster.generate(state.current)
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
  a.download = '挑战星球_' + (state.share.mode === 'flop' ? '翻车复盘_' : '') + (state.current.title || '分享') + '.png'
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
    ? '我在挑战星球「' + c.title + '」翻车后回来了！\n断签不可怕，可怕的是不再开始。已完成 ' + (c.completed_days || 0) + '/' + c.total_days + ' 天\n来挑战星球，真实打卡，允许翻车\n' + url
    : '我在挑战星球参加「' + c.title + '」挑战！\n已完成 ' + (c.completed_days || 0) + '/' + c.total_days + ' 天，连续打卡 ' + (c.streak || 0) + ' 天\n来挑战星球，和我一起变得更好！\n' + url
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
      cpScenes: window.cpScenes,
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

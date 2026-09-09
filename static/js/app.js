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
  loadError: '',
  toast: '',
  celebrate: false,
  celebrateText: '',
  stars: [],
  create: { show: false, step: 1, rawInput: '', startMode: 'today', customDate: '', startDate: '', sceneTemplate: '', phase: 'idle', parsed: null, editTitle: '', editDays: 66, editCategory: 'build', editDesc: '', planText: '', plan: [], suggestions: [], error: '', saving: false, source: 'web', genDay: 0, genTotal: 0, startedAt: 0, adjustHint: '', adjusting: false },
  dayDetail: null,
  mend: { show: false, dates: [], left: 0, busy: false },
  freeze: { show: false, dates: [], left: 0, busy: false },
  reflection: { show: false, mood: 'good', content: '', busy: false },
  share: { show: false, url: '', loading: false, mode: 'win' },
  sharedConfig: { show: false, loading: false, config: null, importing: false, token: '' },
  diagnosis: { show: false, loading: false, report: null, applying: false },
  reportView: { show: false, tab: 'overview', loading: false, overview: null, hourly: null, trend: null, heatmap: null, completion: null },
  companion: { show: false, sessions: false },
  companionMeta: {},
  companionQueue: { position: 0, wait: 0 },
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
  { id: 'fitness', name: '健身', icon: '💪', color: '#f59e0b', task_type: 'counter', unit: '个', desc: '力量与有氧，目标逐日加量', default_target: 30, samples: ['30天每天30个俯卧撑', '21天腹肌撕裂者计划'], steps: ['热身3分钟', '完成今日训练', '记录完成个数'] },
  { id: 'running', name: '跑步', icon: '🏃', color: '#f43f5e', task_type: 'counter', unit: '公里', desc: '从1公里逐步跑到5公里', default_target: 3, samples: ['42天从0到5公里跑步计划', '每天跑步3公里'], steps: ['换上跑鞋', '按计划跑完目标公里数', '拉伸放松'] },
  { id: 'study', name: '学习', icon: '📚', color: '#6366f1', task_type: 'counter', unit: '页', desc: '按页数稳步推进学习进度', default_target: 20, samples: ['30天每天读20页专业书', '考研复习66天计划'], steps: ['翻开教材/资料', '读完目标页数', '写下3个要点'] },
  { id: 'reading', name: '阅读', icon: '📖', color: '#10b981', task_type: 'counter', unit: '页', desc: '每天读一点，长期积累', default_target: 30, samples: ['每天阅读30页', '21天养成阅读习惯'], steps: ['挑选一本书', '静心阅读目标页数', '记录一句感悟'] },
  { id: 'meditation', name: '冥想', icon: '🧘', color: '#8b5cf6', task_type: 'timer', unit: '分钟', desc: '每天静心几分钟，稳定心境', default_target: 10, samples: ['每天冥想10分钟', '21天正念冥想入门'], steps: ['找个安静的地方', '闭眼专注呼吸', '完成目标时长'] },
  { id: 'morning', name: '早起', icon: '🌅', color: '#f97316', task_type: 'timer', unit: '点', desc: '规律起床，重建作息节律', default_target: 7, samples: ['30天早起6点起床', '坚持每天7点前起床'], steps: ['设定闹钟', '闹钟响后起床洗漱', '记录起床时间'] },
  { id: 'writing', name: '写作', icon: '✍️', color: '#8b5cf6', task_type: 'text', unit: '篇', desc: '记录思考，沉淀每日成长', default_target: 1, samples: ['30天每日写作打卡', '21天晨间日记'], steps: ['打开文档', '写下今日主题', '完成300字'] },
  { id: 'gratitude', name: '感恩', icon: '🙏', color: '#fbbf24', task_type: 'text', unit: '件', desc: '每天记3件感恩的小事', default_target: 3, samples: ['21天感恩日记', '每天记录3件感恩的事'], steps: ['回想今天的美好瞬间', '写下3件感恩的小事'] },
  { id: 'water', name: '饮水', icon: '💧', color: '#06b6d4', task_type: 'counter', unit: '杯', desc: '每天喝够8杯水，规律补水', default_target: 8, samples: ['30天每天喝够8杯水', '21天养成喝水习惯'], steps: ['准备一个水杯', '分时段喝完8杯水', '记录杯数'] },
  { id: 'diet', name: '减重', icon: '⚖️', color: '#0ea5e9', task_type: 'diet', unit: '千卡', desc: '控制每日摄入，科学减重', default_target: 300, samples: ['30天减重3公斤', '66天饮食控制科学减脂'], steps: ['记录三餐', '控制摄入在目标内', '记录体重变化'] },
  { id: 'quit', name: '戒断', icon: '🚭', color: '#ef4444', task_type: 'binary', unit: '次', desc: '戒除坏习惯，目标逐日递减', default_target: 0, samples: ['我要戒烟30天', '戒掉熬夜66天'], steps: ['识别触发场景', '用替代动作应对', '完成今日零接触'] },
  { id: 'english', name: '英语', icon: '🔤', color: '#3b82f6', task_type: 'word', unit: '词', desc: '每日背单词，内置四级高频词库', default_target: 20, samples: ['30天每天背20个英语单词', '14天掌握高频核心词'], steps: ['看释义', '记例句', '自测默写'] },
  { id: 'poem', name: '古诗', icon: '📜', color: '#b45309', task_type: 'recite', unit: '首', desc: '每日背一首唐诗，朗读到默写', default_target: 1, samples: ['30天背30首唐诗', '每天背一首古诗词'], steps: ['朗读全诗', '理解大意', '背诵全诗'] },
  { id: 'pomodoro', name: '番茄', icon: '🍅', color: '#ef4444', task_type: 'timer', unit: '分钟', desc: '番茄工作法，25分钟专注打卡', default_target: 25, samples: ['每天4个番茄钟专注', '25分钟专注学习'], steps: ['设定任务', '专注25分钟', '休息5分钟'] },
  { id: 'custom', name: '自定义', icon: '🎯', color: '#8b5cf6', task_type: 'binary', unit: '次', desc: '完全按你的想法来', default_target: 1, samples: ['30天不喝奶茶', '每天给家人打个电话'], steps: [] },
]
window.cpSceneMap = {}
window.cpScenes.forEach(s => { window.cpSceneMap[s.id] = s })

window.cpTaskTypeLabel = tt => ({ counter: '计数', timer: '计时', text: '记录', step: '分步', diet: '减重', binary: '打卡', word: '背词', recite: '背诵' })[tt] || '打卡'

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

window.cpTitleClean = s => String(s == null ? '' : s).replace(/[，,、]\s*(当前|进行中|打卡中|现在|目前)\s*$/, '').trim()

window.cpMd = s => {
  if (window.NexusMarkdown && window.NexusMarkdown.render) return window.NexusMarkdown.render(String(s == null ? '' : s))
  return window.cpEsc(s)
}
if (window.NexusMarkdown && window.NexusMarkdown.injectLibs) window.NexusMarkdown.injectLibs()

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
  if (window.NexusErrorText) {
    const mapped = window.NexusErrorText.fromError(e, fallback || '操作失败，请稍后重试')
    return mapped.message || mapped.title
  }
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
  state.pendingCount = state.challenges.filter(c => c.status === 'active' && !c.today_checked).length
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
  a.download = '星轨挑战_' + (state.share.mode === 'flop' ? '翻车复盘_' : '') + (state.current.title || '分享') + '.png'
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
      saveShareImage,
      copyShareText,
      importShared,
      logout,
      openCreate: () => window.cpCreate.open(),
      genRatio: () => {
        const c = state.create
        if (c.genTotal > 0) return Math.max(0.05, Math.min(1, (c.genDay || 0) / c.genTotal))
        return 0.05
      },
      genStatus: () => {
        const c = state.create
        const total = c.genTotal || 0
        const day = c.genDay || 0
        if (!total || !day) return '正在理解你的目标，设计专属计划…'
        const r = day / total
        if (r < 0.2) return '正在设计适应期的小目标'
        if (r < 0.6) return '正在铺开逐天进阶曲线'
        if (r < 0.85) return '正在安排稳扎稳打的巩固期'
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
})
if (window.NuxAiChat) cpApp.component('nux-ai-chat', NuxAiChat)
if (window.NuxConversationList) cpApp.component('nux-conversation-list', NuxConversationList)
cpApp.mount('#app')

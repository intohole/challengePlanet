window.api = new NexusApi({
  baseUrl: (window.PATH_PREFIX || '') + '/api/v1',
  tokenKey: 'uc_access_token',
  onUnauthorized: () => {
    localStorage.removeItem('uc_access_token')
    localStorage.removeItem('uc_refresh_token')
    localStorage.removeItem('lc_user_id')
    window.location.href = '/login'
  }
})
const { createApp, reactive, computed, onMounted } = Vue
const state = reactive({
  currentView: 'home', user_id: '', challenges: [], currentChallenge: null, todayTask: null,
  checkins: [], insights: null, showCreate: false, showReflection: false, shareCard: null,
  shareCanvasUrl: '', reflectionForm: { content: '', mood: 'good' },
  createForm: { rawInput: '', startDateMode: 'today', startDate: '', customDate: '' },
  loading: false, generating: false, error: null, aiFeedback: null, genProgress: '',
})
window.appState = state

const nickname = computed(() => localStorage.getItem('lc_nickname') || '用户')
const hasChallenge = computed(() => state.challenges.length > 0)
const progressPercent = computed(() => {
  const c = state.currentChallenge
  return (c && c.total_days) ? Math.min(100, Math.round(((c.completed_days || 0) / c.total_days) * 100)) : 0
})
const ringCircumference = 2 * Math.PI * 52
const ringOffset = computed(() => ringCircumference - (ringCircumference * progressPercent.value / 100))
const todayCheckedIn = computed(() => state.todayTask?.checked_in === true || state.todayTask?.status === 'completed')
const streakDays = computed(() => state.currentChallenge?.streak || 0)
const totalCheckins = computed(() => state.currentChallenge?.completed_days || 0)
const insightsText = computed(() => {
  if (!state.insights || !state.insights.length) return ''
  return state.insights.map(i => i.content || i.text || i.message || '').filter(Boolean).join('\n')
})
const heatmapDays = computed(() => {
  const checkedSet = new Set((state.checkins || []).map(c => c.date))
  const days = [], today = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today); d.setDate(d.getDate() - i)
    const ds = d.toISOString().split('T')[0]
    days.push({ date: ds, checked: checkedSet.has(ds), isToday: i === 0 })
  }
  return days
})

const categoryMap = { build: { icon: 'fa-seedling', color: '#10b981' }, quit: { icon: 'fa-ban', color: '#ef4444' }, learn: { icon: 'fa-book', color: '#635bff' }, fitness: { icon: 'fa-dumbbell', color: '#f59e0b' }, mind: { icon: 'fa-brain', color: '#818cf8' }, other: { icon: 'fa-star', color: '#635bff' } }
function categoryIcon(cat) { return categoryMap[cat]?.icon || 'fa-star' }
function categoryColor(cat) { return categoryMap[cat]?.color || '#635bff' }

const dateOptions = [{ key: 'today', label: '今天' }, { key: 'tomorrow', label: '明天' }, { key: 'custom', label: '自定义' }]
const moodOptions = [{ k: 'good', l: '好', i: 'fa-face-smile' }, { k: 'normal', l: '一般', i: 'fa-face-meh' }, { k: 'bad', l: '差', i: 'fa-face-frown' }]

function _err(e, fallback) { state.error = typeof e?.message === 'string' ? e.message : (e?.detail || fallback) }
function _feedback(msg, ms = 3000) { state.aiFeedback = msg; setTimeout(() => { state.aiFeedback = null }, ms) }
function todayStr() { return new Date().toISOString().split('T')[0] }

function setStartDate(mode) {
  state.createForm.startDateMode = mode
  const d = new Date()
  if (mode === 'today') state.createForm.startDate = d.toISOString().split('T')[0]
  else if (mode === 'tomorrow') { d.setDate(d.getDate() + 1); state.createForm.startDate = d.toISOString().split('T')[0] }
  else if (mode === 'custom' && state.createForm.customDate) state.createForm.startDate = state.createForm.customDate
}

async function loadChallenges() {
  state.loading = true
  try {
    const res = await window.api.get(`/challenges/${state.user_id}`)
    const d = res.data || res
    state.challenges = d.items || d.challenges || d || []
    if (state.challenges.length > 0) {
      const active = state.challenges.find(c => c.status === 'active') || state.challenges[0]
      if (state.currentChallenge) {
        state.currentChallenge = state.challenges.find(c => c.id === state.currentChallenge.id) || active
      } else {
        state.currentChallenge = active
        await loadTodayTask()
        await loadInsights()
        await loadCheckins()
      }
    }
  } catch (e) { _err(e, '加载挑战列表失败') }
  finally { state.loading = false }
}

async function createChallengeNL() {
  const raw = state.createForm.rawInput.trim()
  if (!raw) return
  state.generating = true; state.error = null
  state.genProgress = 'AI正在理解你的目标...'
  let saved = null
  try {
    await window.api.streamPost('/challenges/nl-create', {
      user_id: state.user_id, raw_input: raw, start_date: state.createForm.startDate,
    }, {
      onEvent: (event, data) => {
        if (!data) return
        if (data.step === 'parsing') state.genProgress = 'AI正在理解你的目标...'
        if (data.step === 'parsed') state.genProgress = data.message || '已识别目标'
        if (data.step === 'generating') state.genProgress = data.message || '正在生成详细计划...'
        if (data.step === 'done') state.genProgress = '计划生成完成，正在保存...'
        if (data.step === 'saved') saved = data.challenge || null
        if (data.step === 'error') _err(new Error(data.message), '创建失败')
      },
      onError: (msg) => _err(new Error(msg), '创建挑战失败'),
      timeout: 120000,
    })
  } catch (e) { _err(e, '创建挑战失败') }
  finally {
    state.generating = false; state.genProgress = ''
    state.showCreate = false; state.createForm.rawInput = ''
  }
  await loadChallenges()
  if (saved) {
    state.currentChallenge = saved
    await loadTodayTask(); await loadInsights(); await loadCheckins()
  }
}

async function loadTodayTask() {
  if (!state.currentChallenge) return
  try {
    const res = await window.api.get(`/challenges/${state.currentChallenge.id}/today`)
    state.todayTask = res.data || res
  } catch (e) { state.todayTask = null }
}

async function loadCheckins() {
  if (!state.currentChallenge) return
  try {
    const res = await window.api.get(`/challenges/${state.currentChallenge.id}/checkins`)
    state.checkins = Array.isArray(res) ? res : (res.data || res || [])
  } catch (e) { state.checkins = [] }
}

async function loadInsights() {
  if (!state.currentChallenge) return
  try {
    const res = await window.api.get(`/challenges/${state.currentChallenge.id}/insights`)
    const d = res.data || res
    state.insights = Array.isArray(d) ? d : (d.items || [])
  } catch (e) { state.insights = null }
}

async function doCheckin() {
  if (!state.currentChallenge || !state.todayTask) return
  state.loading = true; state.error = null
  try {
    const res = await window.api.post(`/challenges/${state.currentChallenge.id}/checkin`, {
      user_id: state.user_id, reflection: state.reflectionForm.content, mood: state.reflectionForm.mood,
    })
    const d = res.data || res
    state.showReflection = false; state.reflectionForm = { content: '', mood: 'good' }
    if (d.ai_feedback || d.feedback) _feedback(d.ai_feedback || d.feedback, 8000)
    await loadTodayTask(); await loadChallenges(); await loadCheckins(); await loadInsights()
  } catch (e) { _err(e, '打卡失败') }
  finally { state.loading = false }
}

function selectChallenge(ch) {
  state.currentChallenge = ch; state.todayTask = null; state.insights = null; state.checkins = []
  loadTodayTask(); loadInsights(); loadCheckins()
}

function openCreate() {
  state.createForm = { rawInput: '', startDateMode: 'today', startDate: new Date().toISOString().split('T')[0], customDate: '' }
  state.showCreate = true
}
function openReflection() { state.reflectionForm = { content: '', mood: 'good' }; state.showReflection = true }
function switchView(v) { state.currentView = v }
function closeFeedback() { state.aiFeedback = null }

function shareChallenge() {
  if (!state.currentChallenge) return
  state.shareCanvasUrl = generateShareCanvas()
  state.shareCard = true
}

function generateShareCanvas() {
  const c = state.currentChallenge
  if (!c) return ''
  const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d')
  canvas.width = 750; canvas.height = 420
  const grad = ctx.createLinearGradient(0, 0, 750, 420)
  grad.addColorStop(0, '#0a0a1a'); grad.addColorStop(1, '#1a1b3a')
  ctx.fillStyle = grad; ctx.fillRect(0, 0, 750, 420)
  ctx.fillStyle = '#f1f5f9'; ctx.font = 'bold 32px -apple-system, sans-serif'; ctx.textAlign = 'center'
  ctx.fillText(c.title || '我的挑战', 375, 70)
  const cx = 375, cy = 200, r = 70
  ctx.strokeStyle = 'rgba(255,255,255,0.1)'; ctx.lineWidth = 12
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke()
  const pct = (c.completed_days || 0) / (c.total_days || 1)
  ctx.strokeStyle = '#635bff'
  ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * pct); ctx.stroke()
  ctx.fillStyle = '#f1f5f9'; ctx.font = 'bold 36px sans-serif'
  ctx.fillText(Math.round(pct * 100) + '%', cx, cy + 12)
  const stats = [{ num: c.completed_days || 0, label: '已完成', color: '#10b981' }, { num: c.total_days || 0, label: '总天数', color: '#818cf8' }, { num: c.streak || 0, label: '连续打卡', color: '#f59e0b' }]
  stats.forEach((s, i) => {
    const x = 180 + i * 195
    ctx.fillStyle = s.color; ctx.font = 'bold 28px sans-serif'; ctx.fillText(String(s.num), x, 330)
    ctx.fillStyle = '#94a3b8'; ctx.font = '14px sans-serif'; ctx.fillText(s.label, x, 355)
  })
  ctx.fillStyle = '#635bff'; ctx.font = '14px sans-serif'
  ctx.fillText('挑战星球 · AI打卡教练', 375, 400)
  return canvas.toDataURL('image/png')
}

function saveShareImage() {
  if (!state.shareCanvasUrl) return
  const a = document.createElement('a')
  a.href = state.shareCanvasUrl
  a.download = '挑战星球_' + (state.currentChallenge?.title || '分享') + '.png'
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  _feedback('图片已保存！')
}

function copyShareText() {
  const c = state.currentChallenge
  if (!c) return
  const text = `我在挑战星球参加了「${c.title}」挑战！\n已完成 ${c.completed_days || 0}/${c.total_days} 天，连续打卡 ${c.streak || 0} 天\n来挑战星球，和我一起变得更好！`
  navigator.clipboard.writeText(text).then(() => _feedback('分享文案已复制到剪贴板！'))
    .catch(() => {
      const ta = document.createElement('textarea'); ta.value = text
      document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta)
      _feedback('分享文案已复制！')
    })
}

function logout() {
  localStorage.removeItem('uc_access_token'); localStorage.removeItem('uc_refresh_token')
  localStorage.removeItem('lc_user_id'); localStorage.removeItem('lc_nickname')
  window.location.href = '/login'
}

const app = createApp({
  setup() {
    onMounted(() => {
      const uid = localStorage.getItem('lc_user_id')
      if (!uid) { window.location.href = '/login'; return }
      state.user_id = uid
      setStartDate('today')
      loadChallenges()
    })
    return {
      state, nickname, hasChallenge, progressPercent, ringCircumference, ringOffset,
      todayCheckedIn, streakDays, totalCheckins, insightsText, heatmapDays,
      dateOptions, moodOptions, categoryIcon, categoryColor, todayStr, setStartDate,
      loadChallenges, createChallengeNL, loadTodayTask, doCheckin, loadInsights,
      shareChallenge, saveShareImage, copyShareText, logout, selectChallenge,
      openCreate, openReflection, switchView, closeFeedback,
    }
  }
})
app.mount('#app')

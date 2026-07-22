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
  currentView: 'home',
  user_id: '',
  challenges: [],
  currentChallenge: null,
  todayTask: null,
  checkins: [],
  showCreate: false,
  showReflection: false,
  reflectionForm: { content: '', mood: 'good' },
  createForm: { title: '', duration: 30, category: 'build' },
  loading: false,
  generating: false,
  error: null,
  shareCard: null,
  insights: null,
  aiFeedback: null,
  genProgress: '',
})
window.appState = state

const nickname = computed(() => localStorage.getItem('lc_nickname') || '用户')
const hasChallenge = computed(() => state.challenges.length > 0)
const progressPercent = computed(() => {
  if (!state.currentChallenge) return 0
  const c = state.currentChallenge
  if (!c.total_days || c.total_days === 0) return 0
  return Math.min(100, Math.round(((c.completed_days || 0) / c.total_days) * 100))
})
const ringCircumference = 2 * Math.PI * 52
const ringOffset = computed(() => ringCircumference - (ringCircumference * progressPercent.value / 100))
const todayCheckedIn = computed(() => {
  if (!state.todayTask) return false
  return state.todayTask.checked_in === true || state.todayTask.status === 'completed'
})
const streakDays = computed(() => state.currentChallenge?.streak || 0)
const totalCheckins = computed(() => state.currentChallenge?.completed_days || 0)

const categoryMap = {
  build: { label: '习惯养成', icon: 'fa-seedling', color: '#10b981' },
  quit: { label: '戒除坏习惯', icon: 'fa-ban', color: '#ef4444' },
  learn: { label: '学习技能', icon: 'fa-book', color: '#6366f1' },
  fitness: { label: '运动健身', icon: 'fa-dumbbell', color: '#f59e0b' },
  mind: { label: '心智成长', icon: 'fa-brain', color: '#8b5cf6' },
}
function categoryLabel(cat) { return categoryMap[cat]?.label || '其他' }
function categoryIcon(cat) { return categoryMap[cat]?.icon || 'fa-star' }
function categoryColor(cat) { return categoryMap[cat]?.color || '#6366f1' }

function _err(e, fallback) {
  const msg = e?.message || e?.detail || fallback
  state.error = typeof msg === 'string' ? msg : JSON.stringify(msg)
}

function formatDate(date) {
  if (!date) return ''
  const d = new Date(date)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}
function todayStr() { return new Date().toISOString().split('T')[0] }
function daysBetween(start, end) {
  if (!start || !end) return 0
  const ms = new Date(end).getTime() - new Date(start).getTime()
  return Math.max(0, Math.floor(ms / 86400000))
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
        const updated = state.challenges.find(c => c.id === state.currentChallenge.id)
        state.currentChallenge = updated || active
      } else {
        state.currentChallenge = active
        await loadTodayTask()
        await loadInsights()
      }
    }
  } catch (e) { _err(e, '加载挑战列表失败') }
  finally { state.loading = false }
}

async function createChallenge() {
  if (!state.createForm.title.trim()) return
  state.generating = true
  state.error = null
  state.genProgress = 'AI正在生成挑战计划...'
  try {
    let created = null
    await window.api.streamPost('/challenges', {
      user_id: state.user_id,
      title: state.createForm.title,
      duration_days: state.createForm.duration,
      category: state.createForm.category,
    }, {
      onEvent: (event, data) => {
        if (!data) return
        if (data.step === 'thinking' || data.step === 'generating') {
          state.genProgress = data.message || 'AI正在生成挑战计划...'
        }
        if (data.step === 'saved') {
          created = data.challenge || null
          state.genProgress = '挑战创建成功！'
        }
        if (data.step === 'error' || event === 'error') {
          _err(new Error(data.message || '创建失败'), '创建挑战失败')
        }
      },
      onError: (msg) => _err(new Error(msg), '创建挑战失败'),
      timeout: 120000,
    })
    state.showCreate = false
    state.createForm = { title: '', duration: 30, category: 'build' }
    await loadChallenges()
    if (created) {
      state.currentChallenge = created
      await loadTodayTask()
      await loadInsights()
    }
  } catch (e) { _err(e, '创建挑战失败') }
  finally { state.generating = false; state.genProgress = '' }
}

async function loadTodayTask() {
  if (!state.currentChallenge) return
  try {
    const res = await window.api.get(`/challenges/${state.currentChallenge.id}/today`)
    state.todayTask = res.data || res
  } catch (e) { state.todayTask = null }
}

async function doCheckin() {
  if (!state.currentChallenge || !state.todayTask) return
  state.loading = true
  state.error = null
  try {
    const res = await window.api.post(`/challenges/${state.currentChallenge.id}/checkin`, {
      user_id: state.user_id,
      reflection: state.reflectionForm.content,
      mood: state.reflectionForm.mood,
    })
    const d = res.data || res
    state.showReflection = false
    state.reflectionForm = { content: '', mood: 'good' }
    if (d.ai_feedback || d.feedback) {
      state.aiFeedback = d.ai_feedback || d.feedback
      setTimeout(() => { state.aiFeedback = null }, 8000)
    }
    await loadTodayTask()
    await loadChallenges()
    await loadInsights()
  } catch (e) { _err(e, '打卡失败') }
  finally { state.loading = false }
}

async function loadInsights() {
  if (!state.currentChallenge) return
  try {
    const res = await window.api.get(`/challenges/${state.currentChallenge.id}/insights`)
    const d = res.data || res
    state.insights = d.insights || d.items || d
  } catch (e) { state.insights = null }
}

async function shareChallenge() {
  if (!state.currentChallenge) return
  state.loading = true
  try {
    const res = await window.api.get(`/challenges/${state.currentChallenge.id}/share`)
    state.shareCard = res.data || res
  } catch (e) { _err(e, '获取分享数据失败') }
  finally { state.loading = false }
}

function selectChallenge(ch) {
  state.currentChallenge = ch
  state.todayTask = null
  state.insights = null
  loadTodayTask()
  loadInsights()
}

function openCreate() {
  state.createForm = { title: '', duration: 30, category: 'build' }
  state.showCreate = true
}
function openReflection() {
  state.reflectionForm = { content: '', mood: 'good' }
  state.showReflection = true
}
function switchView(view) { state.currentView = view }
function closeFeedback() { state.aiFeedback = null }

function generateShareText() {
  if (!state.currentChallenge) return ''
  const c = state.currentChallenge
  let text = `我在挑战星球参加了「${c.title}」挑战！\n`
  text += `已完成 ${c.completed_days || 0}/${c.total_days} 天`
  if (c.streak) text += `，连续打卡 ${c.streak} 天`
  text += `\n来挑战星球，和我一起变得更好！`
  return text
}

function copyShareText() {
  const text = generateShareText()
  navigator.clipboard.writeText(text).then(() => {
    state.error = null
    state.aiFeedback = '分享文案已复制到剪贴板！'
    setTimeout(() => { state.aiFeedback = null }, 3000)
  }).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    state.aiFeedback = '分享文案已复制！'
    setTimeout(() => { state.aiFeedback = null }, 3000)
  })
}

function logout() {
  localStorage.removeItem('uc_access_token')
  localStorage.removeItem('uc_refresh_token')
  localStorage.removeItem('lc_user_id')
  localStorage.removeItem('lc_nickname')
  window.location.href = '/login'
}

const app = createApp({
  setup() {
    onMounted(() => {
      const uid = localStorage.getItem('lc_user_id')
      if (!uid) {
        window.location.href = '/login'
        return
      }
      state.user_id = uid
      loadChallenges()
    })
    return {
      state, nickname, hasChallenge, progressPercent, ringCircumference, ringOffset,
      todayCheckedIn, streakDays, totalCheckins,
      formatDate, todayStr, categoryLabel, categoryIcon, categoryColor,
      loadChallenges, createChallenge, loadTodayTask, doCheckin,
      loadInsights, shareChallenge, logout, selectChallenge,
      openCreate, openReflection, switchView, closeFeedback,
      generateShareText, copyShareText,
    }
  }
})
app.mount('#app')

window.cpCreate = (function () {
  function st() { return window.appState.create }

  function reset() {
    const c = st()
    c.step = 1
    c.phase = 'idle'
    c.parsed = null
    c.editTitle = ''
    c.editDays = 66
    c.editCategory = 'build'
    c.editDesc = ''
    c.planText = ''
    c.plan = []
    c.suggestions = []
    c.error = ''
    c.saving = false
    c.source = 'web'
  }

  const C = {
    open(preset) {
      reset()
      const c = st()
      c.show = true
      c.startMode = 'today'
      c.customDate = ''
      c.startDate = window.cpTodayStr()
      c.rawInput = ''
      if (preset) {
        if (preset.rawInput) c.rawInput = preset.rawInput
        if (preset.days) c.editDays = preset.days
        if (preset.category) c.editCategory = preset.category
        if (preset.source) c.source = preset.source
      }
    },

    close() {
      const c = st()
      if (c.phase === 'parsing' || c.phase === 'planning') window.api.cancel('/challenges/nl-create')
      c.show = false
    },

    setStartMode(mode) {
      const c = st()
      c.startMode = mode
      if (mode === 'today') c.startDate = window.cpTodayStr()
      else if (mode === 'tomorrow') c.startDate = window.cpAddDays(window.cpTodayStr(), 1)
      else if (mode === 'custom' && c.customDate) c.startDate = c.customDate
    },

    setCustomDate() {
      const c = st()
      if (c.customDate) c.startDate = c.customDate
    },

    setDays(n) { st().editDays = n },
    setCategory(k) { st().editCategory = k },

    back() {
      const c = st()
      if (c.phase === 'parsing' || c.phase === 'planning') window.api.cancel('/challenges/nl-create')
      c.step = 1
      c.phase = 'idle'
      c.error = ''
    },

    async startGenerate() {
      const c = st()
      const raw = (c.rawInput || '').trim()
      if (!raw || c.phase === 'parsing' || c.phase === 'planning') return
      if (c.startMode === 'custom' && c.customDate) c.startDate = c.customDate
      c.step = 2
      c.phase = 'parsing'
      c.error = ''
      c.planText = ''
      c.plan = []
      c.suggestions = []
      await window.api.streamPost('/challenges/nl-create', { raw_input: raw, start_date: c.startDate }, {
        onEvent: (event, data) => {
          if (!data) return
          if (data.step === 'parsing') c.phase = 'parsing'
          else if (data.step === 'parsed') {
            c.parsed = data.parsed || {}
            c.editTitle = c.parsed.title || raw.slice(0, 20)
            c.editCategory = c.parsed.category || c.editCategory || 'build'
            c.editDays = c.parsed.duration_days || c.editDays || 66
            c.editDesc = c.parsed.description || ''
            c.phase = 'planning'
          } else if (data.step === 'token') {
            c.phase = 'planning'
            c.planText += data.token || ''
          } else if (data.step === 'preview') {
            if (data.parsed) {
              c.parsed = data.parsed
              c.editTitle = c.editTitle || data.parsed.title || ''
              c.editCategory = data.parsed.category || c.editCategory
              c.editDays = data.parsed.duration_days || c.editDays
              c.editDesc = c.editDesc || data.parsed.description || ''
            }
            c.plan = data.plan || []
            c.suggestions = data.suggestions || []
            c.phase = 'preview'
          } else if (data.step === 'error') {
            c.error = data.message || '生成失败，请换个描述试试'
            c.phase = 'idle'
          }
        },
        onError: msg => {
          c.error = msg || '网络异常，生成中断'
          if (c.phase !== 'preview') c.phase = 'idle'
        },
        timeout: 120000,
      })
      if (c.phase === 'planning') c.phase = c.plan.length ? 'preview' : 'idle'
      if (c.phase === 'idle' && !c.error && !c.plan.length) c.error = '生成中断，请重试'
    },

    async confirmCreate() {
      const c = st()
      if (c.saving || c.phase !== 'preview') return
      if (!c.editTitle.trim()) { c.error = '请填写挑战标题'; return }
      c.saving = true
      c.error = ''
      try {
        const res = await window.api.post('/challenges/confirm', {
          title: c.editTitle.trim(),
          category: c.editCategory,
          duration_days: c.editDays,
          start_date: c.startDate,
          description: c.editDesc || '',
          plan: c.plan,
          source: c.source || 'web',
        })
        const ch = res.data || res
        c.show = false
        window.cpToast('挑战已开启，从今天开始！')
        await window.cpLoadChallenges()
        if (ch && ch.id) window.appState.current = window.appState.challenges.find(x => x.id === ch.id) || window.appState.current
        const home = window.cpViews.home
        if (home && window.appState.view === 'home') { home.loadedFor = null; home.onShow(); home.rerender() }
      } catch (e) {
        c.error = window.cpErrMsg(e, '创建失败，请重试')
      } finally {
        c.saving = false
      }
    },
  }
  return C
})()

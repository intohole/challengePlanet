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
    c.sceneTemplate = ''
    c.genDay = 0
    c.genTotal = 0
    c.genTitle = ''
    c.expandPlan = false
    c.adjustHint = ''
    c.adjusting = false
    c.goalRule = ''
    c.ladderEn = false
    c.ladderStart = 0
    c.ladderGoal = 0
    c.ladderInterval = 3
    c.ladderStep = 1
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
        if (preset.scene) c.sceneTemplate = preset.scene
      }
    },

    selectScene(sceneId) {
      const c = st()
      c.sceneTemplate = c.sceneTemplate === sceneId ? '' : sceneId
    },

    scenePlaceholder() {
      const c = st()
      if (c.sceneTemplate) {
        const scene = window.cpSceneMap[c.sceneTemplate]
        if (scene && scene.samples && scene.samples.length) return '例如：' + scene.samples[0]
      }
      return '如：42天戒烟、每天读书30分钟、21天学会Python...'
    },

    sceneNote() {
      const c = st()
      if (!c.sceneTemplate) return null
      const scene = window.cpSceneMap[c.sceneTemplate]
      if (!scene) return null
      return { name: scene.name, icon: scene.icon, desc: scene.desc || '', samples: scene.samples || [] }
    },

    sceneExamples() {
      const note = this.sceneNote()
      if (note && note.samples && note.samples.length) return note.samples
      return ['每天坚持一件事，21天养成习惯', '戒掉一个坏习惯，越到后面越轻松', '每天进步一点点，66天见证变化']
    },

    fillSample(s) { st().rawInput = s },

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

    syncLadder(p) {
      const c = st()
      if (!p || typeof p !== 'object') return
      const dir = String(p.direction || '')
      c.goalRule = String(p.goal_rule || 'fixed')
      c.ladderEn = c.goalRule === 'ladder' && !!p.ladder_start
      if (c.ladderEn) {
        c.ladderStart = Number(p.ladder_start) || 0
        c.ladderGoal = Number(p.ladder_goal) || 1
        c.ladderInterval = Math.max(1, Number(p.ladder_interval) || 1)
        c.ladderStep = Number(p.ladder_step) || 1
        if (dir === 'decrease' && !c.ladderGoal) c.ladderGoal = 0
      }
    },

    ladderDir() {
      const sc = window.cpSceneMap[st().sceneTemplate]
      return String(st().parsed && st().parsed.direction || (sc && sc.task_type === 'quit' ? 'decrease' : 'increase'))
    },

    ladderUnit() {
      const c = st()
      const sc = c.sceneTemplate && window.cpSceneMap[c.sceneTemplate]
      return String(c.parsed && c.parsed.unit || (sc && sc.unit) || '次')
    },

    ladderNodes() {
      const c = st()
      if (!c.ladderEn || c.ladderGoal <= 0) return []
      const days = Math.max(7, c.editDays || 66)
      const interval = Math.max(1, c.ladderInterval || 1)
      const step = c.ladderStep || 1
      const isDesc = this.ladderDir() === 'decrease'
      const nodes = []
      for (let d = 1; d <= days; d += interval) {
        const elapsed = Math.floor((d - 1) / interval)
        let v = isDesc
          ? Math.max(c.ladderGoal, c.ladderStart - elapsed * step)
          : Math.min(c.ladderGoal, c.ladderStart + elapsed * step)
        v = Math.round(v * 100) / 100
        nodes.push({ day: d, value: v })
        if (!isDesc && v >= c.ladderGoal) break
        if (isDesc && v <= c.ladderGoal) break
      }
      return nodes
    },

    playMode() {
      const c = st()
      const p = c.parsed || {}
      const sc = c.sceneTemplate && window.cpSceneMap[c.sceneTemplate]
      const tt = this.deriveTaskType(p, sc)
      const typeLabel = { binary: '每日打卡', counter: '计数打卡', timer: '计时打卡', text: '记录打卡', step: '分步打卡' }[tt] || '每日打卡'
      const target = Number(p.target_value) || 0
      const unit = String(p.unit || (sc && sc.unit) || '')
      const goalText = target > 0 && unit ? '每日 ' + target + ' ' + unit : '完成即打卡'
      const dir = String(p.direction || (sc && sc.task_type === 'quit' ? 'decrease' : 'increase'))
      const dirText = c.ladderEn ? (dir === 'decrease' ? '目标逐日递减' : '目标逐日递增') : (dir === 'decrease' ? '越做越少' : '越做越好')
      return { typeLabel, goalText, dirText, days: c.editDays || c.genTotal || 0 }
    },

    diffSvg() {
      const c = st()
      const plan = c.plan || []
      const days = plan.length || c.editDays || 0
      if (days < 3) return ''
      const step = Math.max(1, Math.ceil(days / 24))
      const pts = []
      for (let d = 1; d <= days; d += step) {
        const item = plan.find(x => x.day === d) || plan[plan.length - 1] || {}
        const diff = Math.min(5, Math.max(1, Number(item.difficulty) || 1))
        pts.push(Math.round((d / days) * 100) + ',' + Math.round(((6 - diff) / 5) * 100))
      }
      const last = plan[plan.length - 1] || {}
      const ld = Math.min(5, Math.max(1, Number(last.difficulty) || 1))
      pts.push('100,' + Math.round(((6 - ld) / 5) * 100))
      const poly = pts.join(' ')
      return '<svg viewBox="0 0 100 100" preserveAspectRatio="none" class="cp-curve-svg">' +
        '<line x1="20" y1="0" x2="20" y2="100" class="cp-curve-phase"/><line x1="80" y1="0" x2="80" y2="100" class="cp-curve-phase"/>' +
        '<polygon points="' + poly + ' 100,100 0,100" class="cp-curve-fill"/>' +
        '<polyline points="' + poly + '" class="cp-curve-line"/></svg>'
    },

    visiblePlan() {
      const c = st()
      const plan = c.plan || []
      if (c.expandPlan) return plan
      const days = c.editDays || (plan.length ? plan[plan.length - 1].day : 0)
      if (!days || days < 14) return plan
      const head = plan.filter(d => d.day <= 7)
      const mids = plan.filter(d => d.day > 7 && d.day < days && d.day % 7 === 0)
      let picked = mids
      if (mids.length > 6) {
        const gap = Math.ceil(mids.length / 6)
        picked = mids.filter((_, i) => i % gap === 0)
      }
      const last = plan.find(d => d.day === days)
      const seen = {}
      const out = []
      head.concat(picked, last ? [last] : []).forEach(d => {
        if (d && !seen[d.day]) { seen[d.day] = 1; out.push(d) }
      })
      return out.sort((a, b) => a.day - b.day)
    },

    togglePlan() { st().expandPlan = !st().expandPlan },

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
      await window.api.streamPost('/challenges/nl-create', { raw_input: raw, start_date: c.startDate, scene_template: c.sceneTemplate || '', adjust_hint: (c.adjustHint || '').trim() }, {
        onEvent: (event, data) => {
          if (!data) return
          if (data.type === 'parsing') c.phase = 'parsing'
          else if (data.type === 'parsed') {
            c.parsed = data.parsed || {}
            c.editTitle = c.parsed.title || raw.slice(0, 20)
            c.editCategory = c.parsed.category || c.editCategory || 'build'
            c.editDays = c.parsed.duration_days || c.editDays || 66
            c.editDesc = data.parsed.description || ''
            c.genTotal = data.parsed.duration_days || c.editDays || 0
            this.syncLadder(data.parsed)
            c.phase = 'planning'
          } else if (data.type === 'token') {
            c.phase = 'planning'
            c.planText += data.token || ''
            const titles = c.planText.match(/"title"\s*:\s*"([^"]+)"/g)
            if (titles && titles.length) {
              const m = titles[titles.length - 1].match(/"title"\s*:\s*"([^"]+)"/)
              if (m && m[1] && m[1] !== c.genTitle) c.genTitle = m[1]
            }
          } else if (data.type === 'day') {
            c.genDay = data.day || 0
            c.genTotal = data.total || c.genTotal
            c.phase = 'planning'
          } else if (data.type === 'preview') {
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
          } else if (data.type === 'error') {
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

    async applyAdjust() {
      const c = st()
      if (!(c.adjustHint || '').trim() || c.phase === 'parsing' || c.phase === 'planning') return
      c.adjusting = true
      c.genDay = 0
      c.genTotal = c.editDays || c.genTotal || 0
      await this.startGenerate()
      c.adjusting = false
    },

    async confirmCreate() {
      const c = st()
      if (c.saving || c.phase !== 'preview') return
      if (!c.editTitle.trim()) { c.error = '请填写挑战标题'; return }
      c.saving = true
      c.error = ''
      try {
        const scene = window.cpSceneMap[c.sceneTemplate]
        const p = c.parsed || {}
        const taskType = this.deriveTaskType(p, scene)
        const res = await window.api.post('/challenges/confirm', {
          title: c.editTitle.trim(),
          category: c.editCategory,
          duration_days: c.editDays,
          start_date: c.startDate,
          description: c.editDesc || '',
          plan: c.plan,
          source: c.source || 'web',
          task_type: taskType,
          scene_template: c.sceneTemplate || '',
          target_value: Number(p.target_value) || 1,
          unit: String(p.unit || (scene && scene.unit) || '次'),
          direction: String(p.direction || (scene && scene.task_type === 'quit' ? 'decrease' : 'increase')),
          goal_type: String(p.goal_type || 'hard'),
          decompose_mode: String(p.decompose_mode || 'none'),
          slot_hours: Number(p.slot_hours) || 1,
          slot_target_value: Number(p.slot_target_value) || 0,
          goal_rule: c.ladderEn ? 'ladder' : (String(p.goal_rule || 'fixed')),
          goal_mode: String(p.goal_mode || (c.ladderEn ? 'ceiling' : 'auto')),
          ladder_start: c.ladderStart || 0,
          ladder_goal: c.ladderEn ? (c.ladderGoal || 1) : 0,
          ladder_interval: c.ladderEn ? (c.ladderInterval || 1) : 1,
          ladder_step: c.ladderStep || 1,
        })
        const ch = res.data || res
        c.show = false
        const first = (c.plan && c.plan[0]) || {}
        window.cpToast('挑战已开启！第1天「' + (first.title || c.editTitle) + '」')
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

    deriveTaskType(p, scene) {
      if (p && p.task_type && ['binary', 'counter', 'timer', 'step', 'text', 'choice'].indexOf(p.task_type) >= 0) return p.task_type
      if (!p || typeof p !== 'object') return (scene && scene.task_type) || 'binary'
      if (p.decompose_mode === 'time_slot') return 'counter'
      const target = Number(p.target_value) || 0
      const unit = String(p.unit || '').trim()
      const countableUnits = ['杯','根','支','个','颗','圈','顿','遍','页','公里','km','分钟','小时','轮','张','篇','件','只','组']
      if (target > 1 || countableUnits.indexOf(unit) >= 0) return 'counter'
      return (scene && scene.task_type) || 'binary'
    },
  }
  return C
})()

;(function () {
  window.cpCreateDirect = {
    canDirect() {
      const c = window.appState.create
      if (!c.sceneTemplate) return false
      if (c.sceneTemplate === 'quit') return (c.ladderStart || 0) > 0
      return !!c.sceneTemplate
    },

    buildPlan(scene) {
      const c = window.appState.create
      const raw = (c.rawInput && c.rawInput.trim()) || ''
      const isQuit = scene && scene.id === 'quit'
      const title = raw ? String(raw).slice(0, 30) : (scene ? scene.name + '挑战' : '我的挑战')
      const dayMatch = raw.match(/(\d+)\s*天/)
      const days = Math.min(90, Math.max(7, dayMatch ? Number(dayMatch[1]) : (c.editDays || 30)))
      const tt = isQuit ? 'counter' : (scene && scene.task_type ? scene.task_type : ((c.parsed && c.parsed.task_type) || 'binary'))
      const unit = isQuit ? '根' : String(scene && scene.unit ? scene.unit : (c.parsed && c.parsed.unit) || '次')
      const target = isQuit
        ? (c.ladderStart || scene.default_target || 1)
        : Number(scene && scene.default_target !== undefined ? scene.default_target : (c.parsed && c.parsed.target_value) || 1)
      const steps = isQuit
        ? ['想抽时，先点一下记录这一根', '对照今日上限控制节奏', '记录每一天的进步']
        : (scene && scene.steps ? scene.steps : [])
      const plan = []
      for (let day = 1; day <= days; day++) {
        plan.push({
          day: day,
          title: title,
          description: scene && scene.desc ? scene.desc + '，第 ' + day + ' 天，稳住节奏，今天就做起来。' : '第 ' + day + ' 天，' + title + '，完成即可打卡。',
          tip: '每天完成一次，' + days + ' 天后再回看自己的变化。',
          task_type: tt,
          target_value: target,
          unit: unit,
          difficulty: Math.min(5, 1 + Math.floor((day - 1) / (days / 5))),
          steps: steps,
        })
      }
      return { title, days, tt, unit, target, plan }
    },

    inferCategory(tt, scene) {
      if (scene && scene.id) {
        const map = { quit: 'quit', running: 'fitness', fitness: 'fitness', study: 'learn', reading: 'learn', meditation: 'mind', morning: 'build', writing: 'build', gratitude: 'mind', water: 'build', diet: 'fitness', english: 'learn', poem: 'learn', pomodoro: 'learn' }
        if (map[scene.id]) return map[scene.id]
      }
      return { counter: 'fitness', timer: 'mind', text: 'other', word: 'learn', recite: 'learn' }[tt] || 'build'
    },

    async confirmDirect() {
      const c = window.appState.create
      if (c.saving || !this.canDirect()) return
      c.saving = true
      c.error = ''
      try {
        const scene = c.sceneTemplate ? window.cpSceneMap[c.sceneTemplate] : null
        const isQuit = scene && scene.id === 'quit'
        const built = this.buildPlan(scene)
        const body = {
          title: built.title,
          category: this.inferCategory(built.tt, scene),
          duration_days: built.days,
          start_date: c.startDate || window.cpTodayStr(),
          description: scene ? scene.desc : '每天坚持，打卡记录每一次',
          plan: built.plan,
          source: c.source || 'web',
          task_type: built.tt,
          scene_template: c.sceneTemplate || '',
          target_value: built.target,
          unit: built.unit,
          direction: String(isQuit ? 'decrease' : 'increase'),
          goal_type: String(isQuit ? 'soft' : 'hard'), decompose_mode: 'none', slot_hours: 1, slot_target_value: 0,
          goal_rule: String(isQuit ? 'ladder' : 'fixed'), goal_mode: String(isQuit ? 'ceiling' : 'auto'),
          ladder_start: isQuit ? (c.ladderStart || 0) : 0,
          ladder_goal: isQuit ? (c.ladderGoal || 0) : 0,
          ladder_interval: isQuit ? (c.ladderInterval || 1) : 1,
          ladder_step: isQuit ? (c.ladderStep || 1) : 1,
          gender: c.gender || '', age: Number(c.age) || 0, height_cm: Number(c.heightCm) || 0,
          weight_kg: Number(c.weightKg) || 0, goal_weight: Number(c.goalWeight) || 0,
          activity_level: Number(c.activityLevel) || 2,
        }
        const ch = await window.cpApi.post('/challenges/confirm', body)
        c.show = false
        window.cpToast('挑战已开启！「' + built.title + '」')
        await window.cpLoadChallenges()
        if (ch && ch.id) window.appState.current = window.appState.challenges.find(x => x.id === ch.id) || window.appState.current
        const view = window.cpViews && window.cpViews[window.appState.view]
        if (view) {
          if (view.loadedFor !== undefined) view.loadedFor = null
          if (typeof view.onShow === 'function') view.onShow()
          if (typeof view.rerender === 'function') view.rerender()
        }
      } catch (e) {
        c.error = window.cpErrMsg(e, '创建失败，请重试')
      } finally {
        c.saving = false
      }
    },
  }
  Object.assign(window.cpCreate, window.cpCreateDirect)
})()
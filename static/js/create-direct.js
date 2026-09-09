;(function () {
  window.cpCreateDirect = {
    canDirect() {
      const c = window.appState.create
      return !!(c.rawInput && c.rawInput.trim()) || !!c.sceneTemplate
    },

    buildPlan(scene) {
      const c = window.appState.create
      const raw = (c.rawInput && c.rawInput.trim()) || ''
      const title = raw ? String(raw).slice(0, 30) : (scene ? scene.name + '挑战' : '我的挑战')
      const dayMatch = raw.match(/(\d+)\s*天/)
      const days = Math.min(90, Math.max(7, dayMatch ? Number(dayMatch[1]) : (c.editDays || 30)))
      const tt = scene && scene.task_type ? scene.task_type : ((c.parsed && c.parsed.task_type) || 'binary')
      const unit = String(scene && scene.unit ? scene.unit : (c.parsed && c.parsed.unit) || '次')
      const target = Number(scene && scene.default_target !== undefined ? scene.default_target : (c.parsed && c.parsed.target_value) || 1)
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
          steps: scene && scene.steps ? scene.steps : [],
        })
      }
      return { title, days, tt, unit, target, plan }
    },

    inferCategory(tt, scene) {
      if (scene && scene.id) {
        const map = { quit: 'quit', running: 'fitness', fitness: 'fitness', study: 'learn', reading: 'learn', meditation: 'mind', morning: 'build', writing: 'build', gratitude: 'mind', water: 'build', diet: 'fitness' }
        if (map[scene.id]) return map[scene.id]
      }
      return { counter: 'fitness', timer: 'mind', text: 'other' }[tt] || 'build'
    },

    async confirm() {
      const c = window.appState.create
      if (c.saving || !this.canDirect()) return
      c.saving = true
      c.error = ''
      try {
        const scene = c.sceneTemplate ? window.cpSceneMap[c.sceneTemplate] : null
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
          direction: String(scene && scene.task_type === 'quit' ? 'decrease' : 'increase'),
          goal_type: 'hard', decompose_mode: 'none', slot_hours: 1, slot_target_value: 0,
          goal_rule: 'fixed', goal_mode: 'auto',
          ladder_start: 0, ladder_goal: 0, ladder_interval: 1, ladder_step: 1,
          gender: c.gender || '', age: Number(c.age) || 0, height_cm: Number(c.heightCm) || 0,
          weight_kg: Number(c.weightKg) || 0, goal_weight: Number(c.goalWeight) || 0,
          activity_level: Number(c.activityLevel) || 2,
        }
        const res = await window.api.post('/challenges/confirm', body)
        const ch = res.data || res
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
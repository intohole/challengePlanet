;(function () {
  Object.assign(window.cpCreate, {
    isPeriodScene() {
      const c = window.appState.create
      const sc = c.sceneTemplate && window.cpSceneMap[c.sceneTemplate]
      return !!sc && ['fitness', 'running', 'reading', 'study', 'meditation'].indexOf(sc.id) >= 0
    },

    isSportScene() {
      const c = window.appState.create
      const sc = c.sceneTemplate && window.cpSceneMap[c.sceneTemplate]
      return !!sc && ['fitness', 'running'].indexOf(sc.id) >= 0
    },

    sportOptions() {
      return [
        { met: 9.8, label: '跑步' }, { met: 7.5, label: '骑行' }, { met: 11.8, label: '跳绳' },
        { met: 8.0, label: '游泳' }, { met: 5.0, label: '力量训练' }, { met: 6.0, label: '综合健身' },
        { met: 4.3, label: '快走' }, { met: 3.0, label: '瑜伽' },
      ]
    },

    selectSport(met, label) {
      const c = window.appState.create
      c.sportMet = c.sportMet === met ? 0 : met
      c.sportLabel = c.sportMet ? label : ''
      c.periodUnit = c.sportMet ? '千卡' : '分钟'
    },

    syncLadder(p) {
      const c = window.appState.create
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
      const sc = window.cpSceneMap[window.appState.create.sceneTemplate]
      return String(window.appState.create.parsed && window.appState.create.parsed.direction || (sc && sc.task_type === 'quit' ? 'decrease' : 'increase'))
    },

    ladderUnit() {
      const c = window.appState.create
      const sc = c.sceneTemplate && window.cpSceneMap[c.sceneTemplate]
      return String(c.parsed && c.parsed.unit || (sc && sc.unit) || '次')
    },

    ladderNodes() {
      const c = window.appState.create
      if (!c.ladderEn || c.ladderStart <= 0) return []
      const days = Math.max(7, c.editDays || 66)
      const interval = Math.max(1, c.ladderInterval || 1)
      const step = Math.max(0.5, c.ladderStep || 1)
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

    ladderInterval() {
      return Math.max(1, window.appState.create.ladderInterval || 1)
    },
  })
})()
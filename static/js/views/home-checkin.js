;(function () {
  const V = window.cpViews.home

  V.doMainCheckin = async function () {
    const s = window.appState
    const ch = s.current
    const d = this.data
    const t = d.today
    if (!ch || d.checking || (t && t.settled)) return
    const tt = (t && t.task_type) || ch.task_type || 'binary'
    const target = (t && t.task_target) || ch.target_value || 1
    const isDecrease = ch.direction === 'decrease' || String(t && t.direction) === 'decrease'
    if (tt === 'counter' || tt === 'timer') { window.cpToast('直接点 +N 记账，达标由系统自动判定'); return }
    let payload = { value: 1.0, reflection: '' }
    if (isDecrease) {
      payload.value = 0
    } else if (tt === 'counter' || tt === 'timer') {
      payload.value = Math.max(0, target - ((t && t.today_total) || 0))
    } else if (tt === 'step') {
      const steps = (t && t.task_steps) || []
      if (!steps.length) { window.cpToast('请先在创建时配置分步清单'); return }
      payload.value = steps.length, payload.reflection = steps.join('；')
    } else if (tt === 'text') {
      const text = (d.textValue || '').trim()
      if (!text) { window.cpToast('先写下今日记录'); return }
      payload.value = 1
      payload.reflection = text
    }
    d.checking = true
    this.rerender()
    try {
      payload.mood = d.moodTag || ''
      const r = await window.cpApi.checkin(ch.id, payload)
      window.cpCelebrate('今日达标 +' + (r.points_earned || 0) + ' 分')
      this._panel = ''
      d.textValue = ''
      d.moodTag = ''
      await this._finishCheckin(r, ch, d, t && t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.togglePanel = function (key) {
    const d = this.data
    this._panel = this._panel === key ? '' : key
    this.rerender()
  }

  V.openWord = function () { this._panel = 'word'; this.rerender() }

  V.openText = function () { this._panel = 'text'; this.rerender() }

  V.openStep = function () { this._panel = 'steps'; this.rerender() }

  V.doCheckin = async function (checkinType) {
    const s = window.appState
    const ch = s.current
    const d = this.data
    if (!ch || d.checking || (d.today && d.today.checked_in)) return
    d.checking = true
    this.rerender()
    try {
      const r = await window.cpApi.checkin(ch.id, { value: checkinType === 'mini' ? 0.5 : 1.0, mood: d.moodTag || '' })
      d.moodTag = ''
      window.cpCelebrate((checkinType === 'mini' ? '微打卡 · 节奏守住 +' : '打卡成功 +') + (r.points_earned || 0) + ' 分')
      await this._finishCheckin(r, ch, d, d.today && d.today.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.doMini = function () { this.doCheckin('mini') }

  V.doUndoLast = async function () {
    const ch = window.appState.current
    const d = this.data
    const t = d.today
    const lst = t && t.today_checkins
    if (!ch || !lst || !lst.length || d.checking) return
    const last = lst[lst.length - 1]
    d.checking = true
    this.rerender()
    try {
      await window.cpApi.deleteCheckin(ch.id, last.id)
      window.cpToast('已撤销一笔')
      this._clearNudgeStamp(ch.id, t && t.date)
      await this.load()
      await window.cpLoadChallenges()
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '撤销失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.doFastTap = async function (value) {
    const ch = window.appState.current
    const d = this.data
    const t = d.today
    if (!ch || !t) return false
    const parsed = Number(value)
    const v = Number.isFinite(parsed) && parsed >= 0 ? parsed : 1
    t.today_total = (Number(t.today_total) || 0) + v
    this.rerender()
    try {
      const r = await window.cpApi.checkin(ch.id, { value: v, context_tag: d.contextTag || '', mood: d.moodTag || '' })
      d.contextTag = ''
      d.moodTag = ''
      t.today_total = Number(r.today_total) || t.today_total
      const total = r.today_total || 0
      const target = (t.today_target || ch.target_value || 1)
      if (ch.direction === 'decrease') {
        const tot = r.today_total || total
        const tgt = r.today_target || target
        if (v === 0) window.cpCelebrate('今天 0 ' + (ch.unit || '') + ' · 完美的一天 +' + (r.points_earned || 0) + ' 分')
        else if (tot > tgt) window.cpCelebrate(t.goal_rule === 'ladder' ? '已记录 +' + v + ' · 已超今日上限，明天梯度更低' : '已记录 +' + v + ' · 已超今日上限，今天辛苦了')
        else if (tot >= tgt) window.cpCelebrate('已记录 +' + v + ' · 已达今日上限 ' + tgt + (ch.unit || '') + '，今日守住！')
        else window.cpCelebrate('已记录 +' + v + ' ' + (ch.unit || '') + ' · 还可 ' + Math.max(0, tgt - tot) + (ch.unit || ''))
      } else {
        window.cpCelebrate(total >= target ? '已记 ' + total + ' · 今日目标已达成' : '已记 ' + total + ' / 目标 ' + target + ' · 还差 ' + Math.max(0, target - total))
      }
      d.lastFeedback = r.ai_feedback || d.lastFeedback
      d.chest = r.chest_points || 0
      d.shields = r.shields || 0
      this._nudgeNotify(r, ch, t.date)
      this._debouncedRefresh()
      if (r.checkin && r.checkin.id) this._streamFeedback(ch.id, r.checkin.id)
      return true
    } catch (e) {
      t.today_total = Math.max(0, (Number(t.today_total) || 0) - v)
      window.cpToast(window.cpErrMsg(e, '记录失败，请重试'))
      this._debouncedRefresh()
      return false
    }
  }

  V._debouncedRefresh = function () {
    clearTimeout(this._fastTimer)
    this._fastTimer = setTimeout(async () => {
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
      const ch = window.appState.current
      if (ch) this._ensureFeedback(ch.id)
    }, 450)
  }

  V._ctxRow = function () {
    const d = this.data
    const ch = window.appState.current
    const isDecrease = !!(ch && ch.direction === 'decrease')
    let h = '<div class="cp-ctx-row"><span class="cp-ctx-label"><i class="fas fa-location-dot"></i> ' + (isDecrease ? '诱因' : '情境') + '</span><div class="cp-pick-btns">'
    const tags = isDecrease
      ? [{ k: '', l: '不选' }, { k: 'stress', l: '😰 压力' }, { k: 'social', l: '👥 社交' }, { k: 'drink', l: '🍺 酒后' }, { k: 'meal', l: '🍚 饭后' }, { k: 'bored', l: '😞 无聊' }, { k: 'habit', l: '🔄 习惯性' }]
      : [{ k: '', l: '不选' }, { k: 'home', l: '🏠 家' }, { k: 'work', l: '💼 工作' }, { k: 'social', l: '👥 社交' }, { k: 'stress', l: '😰 压力' }]
    tags.forEach(tg => {
      const sel = (d.contextTag || '') === tg.k ? ' active' : ''
      h += '<button class="cp-pick-btn cp-ctx-chip' + sel + '" onclick="cpViews.home.setContext(\'' + tg.k + '\')">' + tg.l + '</button>'
    })
    return h + '</div></div>'
  }

  V.setContext = function (tag) {
    this.data.contextTag = tag || ''
    this.rerender()
  }

  V._moodRow = function () {
    const d = this.data
    let h = '<div class="cp-ctx-row"><span class="cp-ctx-label"><i class="fas fa-face-smile"></i> 心情</span><div class="cp-pick-btns">'
    const tags = [{ k: '', l: '不选' }, { k: 'good', l: '😊 不错' }, { k: 'normal', l: '😐 一般' }, { k: 'bad', l: '😔 吃力' }]
    tags.forEach(tg => {
      const sel = (d.moodTag || '') === tg.k ? ' active' : ''
      h += '<button class="cp-pick-btn cp-ctx-chip' + sel + '" onclick="cpViews.home.setMood(\'' + tg.k + '\')">' + tg.l + '</button>'
    })
    return h + '</div></div>'
  }

  V.setMood = function (mood) {
    this.data.moodTag = mood || ''
    this.rerender()
  }

  V.setText = function (val) {
    this.data.textValue = val || ''
  }

  V.toggleStep = function (stepEncoded) {
    const d = this.data
    const step = decodeURIComponent(stepEncoded)
    const idx = d.taskSteps.indexOf(step)
    if (idx >= 0) d.taskSteps.splice(idx, 1)
    else d.taskSteps.push(step)
    this.rerender()
  }

  V.doMultiCheckin = async function () {
    const s = window.appState
    const ch = s.current
    const d = this.data
    const t = d.today
    if (!ch || !t || d.checking || t.settled) return
    const steps = (t.task_steps) || []
    if (!steps.length) return
    if (!d.taskSteps.length) { window.cpToast('先勾选完成的分步再打卡'); return }
    const payload = { value: d.taskSteps.length, reflection: d.taskSteps.join('；'), mood: d.moodTag || '' }
    d.checking = true
    this.rerender()
    try {
      const r = await window.cpApi.checkin(ch.id, payload)
      window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
      d.taskSteps = []
      d.moodTag = ''
      await this._finishCheckin(r, ch, d, t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.doNuxSubmit = async function (payload) {
    const ch = window.appState.current
    const d = this.data
    const t = d.today
    if (!ch || !t || d.checking) return
    const tt = t.task_type || ch.task_type || 'binary'
    const data = { value: payload.value || 0, reflection: payload.reflection || '', context_tag: payload.context_tag || '', mood: payload.mood || d.moodTag || '' }
    if (tt === 'counter' && data.value <= 0) { window.cpToast('先输入数量'); return }
    d.checking = true
    this.rerender()
    try {
      const r = await window.cpApi.checkin(ch.id, data)
      window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
      d.moodTag = ''
      await this._finishCheckin(r, ch, d, t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V._finishCheckin = async function (r, ch, d, dateStr) {
    d.lastFeedback = r.ai_feedback || d.lastFeedback
    d.chest = r.chest_points || 0
    d.declaration = r.declaration || ''
    d.shields = r.shields || 0
    if (d.declaration && dateStr) {
      try { localStorage.setItem('cp_decl_' + ch.id + '_' + dateStr, d.declaration) } catch (e) {}
    }
    this._nudgeNotify(r, ch, dateStr)
    await this.load()
    await window.cpLoadChallenges()
    if (r.checkin && r.checkin.id && !r.ai_feedback) this._streamFeedback(ch.id, r.checkin.id)
    else this._ensureFeedback(ch.id)
  }
})()

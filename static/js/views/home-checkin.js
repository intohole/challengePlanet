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
    let payload = { value: 1.0, reflection: '' }
    if (isDecrease) {
      payload.value = 0
    } else if (tt === 'counter' || tt === 'timer') {
      payload.value = Math.max(0, target - ((t && t.today_total) || 0))
    } else if (tt === 'step') {
      const steps = (t && t.task_steps) || []
      payload.value = steps.length
      payload.reflection = steps.join('；')
    } else if (tt === 'text' && d.textValue && d.textValue.trim()) {
      payload.value = 1
      payload.reflection = d.textValue.trim()
    }
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', payload)
      const r = res.data || res
      window.cpCelebrate('今日达标 +' + (r.points_earned || 0) + ' 分')
      this._panel = ''
      d.textValue = ''
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

  V.doCheckin = async function (checkinType) {
    const s = window.appState
    const ch = s.current
    const d = this.data
    if (!ch || d.checking || (d.today && d.today.checked_in)) return
    d.checking = true
    this.rerender()
    try {
      const payload = { value: checkinType === 'mini' ? 0.5 : 1.0 }
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', payload)
      const r = res.data || res
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
      await window.api.delete('/challenges/' + ch.id + '/checkins/' + last.id)
      window.cpToast('已撤销一笔')
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
    if (!ch || !t || d.checking) return
    const v = Number(value) || 1
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', { value: v })
      const r = res.data || res
      const total = r.today_total || 0
      const target = (t.today_target || ch.target_value || 1)
      if (t.goal_rule === 'ladder' && ch.direction === 'decrease') {
        const tot = (r.today_total !== undefined ? r.today_total : total)
        const tgt = (r.today_target !== undefined ? r.today_target : target)
        if (tot > tgt) window.cpCelebrate('已记录 +' + v + ' · 已超今日上限，今天辛苦了，明天梯度更低')
        else if (tot >= tgt) window.cpCelebrate('已记录 +' + v + ' · 已达今日上限 ' + tgt + (ch.unit || '') + '，梯度守住！')
        else window.cpCelebrate('已记录 +' + v + ' ' + (ch.unit || '') + ' · 还可 ' + Math.max(0, tgt - tot) + (ch.unit || ''))
      } else {
        window.cpCelebrate('已记录 +' + v + ' ' + (ch.unit || '') + ' · 今日 ' + total + '/' + target)
      }
      await this._finishCheckin(r, ch, d, t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '记录失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V.adjustCount = function (delta) {
    const d = this.data
    d.taskValue = Math.max(0, d.taskValue + delta)
    this.rerender()
  }

  V.setCount = function (val) {
    this.data.taskValue = Math.max(0, val)
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
    if (!ch || !t || d.checking || t.checked_in) return
    const steps = (t.task_steps) || []
    if (steps.length) {
      if (!d.taskSteps.length) { window.cpToast('先勾选完成的分步再打卡'); return }
      d.taskValue = d.taskSteps.length
      const payload = { value: d.taskSteps.length, reflection: d.taskSteps.join('；') }
      d.checking = true
      this.rerender()
      try {
        const res = await window.api.post('/challenges/' + ch.id + '/checkin', payload)
        const r = res.data || res
        window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
        d.taskSteps = []
        await this._finishCheckin(r, ch, d, t.date)
      } catch (e) {
        window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
      } finally {
        d.checking = false
        this.rerender()
      }
      return
    }
    const tt = t.task_type || ch.task_type || 'binary'
    let payload = { value: 1.0, reflection: '' }
    if (tt === 'counter' || tt === 'timer') {
      if (d.taskValue <= 0) { window.cpToast('先输入数量'); return }
      payload.value = d.taskValue
    } else if (tt === 'text') {
      if (!d.textValue.trim()) { window.cpToast('先写点什么'); return }
      payload.value = d.textValue.length
      payload.reflection = d.textValue
    }
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', payload)
      const r = res.data || res
      window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
      d.taskValue = 0
      d.textValue = ''
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
    const data = { value: payload.value || 0, reflection: payload.reflection || '', context_tag: '', sub_goal_id: null }
    if (tt === 'counter' && data.value <= 0) { window.cpToast('先输入数量'); return }
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', data)
      const r = res.data || res
      window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
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
    await this.load()
    await window.cpLoadChallenges()
    if (!r.ai_feedback && dateStr && window.cpPollTodayAi) window.cpPollTodayAi(ch.id, dateStr, 3)
  }

  V._checkinArea = function (tt, t, ch) {
    const d = this.data
    const dis = d.checking ? 'disabled' : ''
    const done = !!t.settled
    let html = '<div class="cp-checkin-box">' + this._mainCTA(tt, t, ch, dis, done)
    const extras = this._extras(tt, t, ch, dis, done)
    if (extras) html += extras
    html += '</div>'
    return html
  }

  V._mainCTA = function (tt, t, ch, dis, done) {
    const d = this.data
    const unit = window.cpEsc(t.task_unit || ch.unit || '')
    const target = (t.task_target && t.task_target > 0) ? t.task_target : (ch.target_value || 1)
    const isDecrease = ch.direction === 'decrease' || String(t.direction) === 'decrease'
    if (done) {
      return '<button class="cp-cta-done" disabled><i class="fas fa-circle-check"></i><span>今日已完成</span></button>'
    }
    let title = '今日完成'
    let sub = ''
    if (isDecrease) {
      title = '守住今日'
      sub = '不超 ' + target + ' ' + unit + ' 即达标'
    } else if (tt === 'counter' || tt === 'timer') {
      title = '完成今日目标'
      sub = '记为今日 ' + target + ' ' + unit
    } else if (tt === 'step') {
      title = '今日达标'
      sub = '分步都完成即达标'
    } else if (tt === 'word') {
      title = '今日背词完成'
      sub = '达成 ' + target + ' ' + unit
    } else if (tt === 'recite') {
      title = '今日背诵完成'
    } else if (tt === 'text') {
      title = '完成今日记录'
      sub = target > 0 ? '目标 ' + target + ' ' + unit : ''
    }
    return '<button class="cp-cta-main" ' + dis + ' onclick="cpViews.home.doMainCheckin()"><i class="fas fa-fire"></i><span>' + (d.checking ? '记录中…' : title) + '</span>' + (sub ? '<em>' + sub + '</em>' : '') + '</button>'
  }

  V._extras = function (tt, t, ch, dis, done) {
    const d = this.data
    const isDecrease = ch.direction === 'decrease' || String(t.direction) === 'decrease'
    const isPm = (ch && ch.scene_template === 'pomodoro') || (ch && ch.task_type === 'timer' && ch.scene_template === 'pomodoro')
    const mini = done ? '' : '<button class="cp-extra-chip ghost" ' + dis + ' onclick="cpViews.home.doMini()">今天太累？微打卡</button>'
    if (isPm) {
      return '<button class="cp-extra-chip' + (this._panel === 'pm' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'pm\')"><i class="fas fa-clock"></i>番茄钟</button>' + this._panelBody(tt, t, ch, dis)
    }
    if (isDecrease || tt === 'counter' || tt === 'timer') {
      const has = (t.today_checkins || []).length > 0
      return '<div class="cp-extra-row"><button class="cp-extra-chip' + (this._panel === 'quick' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'quick\')"><i class="fas fa-pen"></i>' + (isDecrease ? '记一笔' : '记实际值') + '</button>' + (has ? '<button class="cp-extra-chip' + (this._panel === 'undo' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'undo\')"><i class="fas fa-rotate-left"></i>撤销上一笔</button>' : '') + mini + '</div>' + this._panelBody(tt, t, ch, dis)
    }
    if (tt === 'step') {
      return '<button class="cp-extra-chip' + (this._panel === 'steps' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'steps\')"><i class="fas fa-list-check"></i>分步清单</button>' + this._panelBody(tt, t, ch, dis)
    }
    if (tt === 'text') {
      if (done) return '<div class="cp-extra-row"></div>'
      return '<div class="cp-extra-row"><button class="cp-extra-chip' + (this._panel === 'text' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'text\')"><i class="fas fa-pen-nib"></i>写几句</button>' + mini + '</div>' + this._panelBody(tt, t, ch, dis)
    }
    if (tt === 'word') {
      return '<div class="cp-extra-row"><button class="cp-extra-chip' + (this._panel === 'word' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'word\')"><i class="fas fa-clipboard-list"></i>刷词卡</button></div>' + this._panelBody(tt, t, ch, dis)
    }
    if (tt === 'recite') {
      return '<div class="cp-extra-row"><button class="cp-extra-chip' + (this._panel === 'poem' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'poem\')"><i class="fas fa-feather-pointed"></i>看今日诗</button></div>' + this._panelBody(tt, t, ch, dis)
    }
    return '<div class="cp-extra-row">' + mini + '</div>'
  }

  V._panelBody = function (tt, t, ch, dis) {
    const key = this._panel
    if (!key) return ''
    if (key === 'quick') return this._quickPanel(tt, t, ch, dis)
    if (key === 'steps') {
      if (!(t.task_steps && t.task_steps.length)) return ''
      return this._stepPanel(t, dis)
    }
    if (key === 'pm') {
      if (!((ch && ch.scene_template === 'pomodoro') || (ch && ch.task_type === 'timer' && ch.scene_template === 'pomodoro'))) return ''
      return window.cpExtraPanelRender ? window.cpExtraPanelRender('pm', tt, t, ch, dis) : ''
    }
    if (key === 'text') return this._textPanel(t, dis)
    if (key === 'word') return this._wordUI(t, dis)
    if (key === 'poem') return this._reciteUI(t, dis)
    if (key === 'undo') return this._undoPanel(t, ch, dis)
    return ''
  }

  V._quickPanel = function (tt, t, ch, dis) {
    const d = this.data
    const isTimer = tt === 'timer'
    const unit = window.cpEsc(t.unit || ch.unit || '')
    const presets = isTimer ? [5, 10, 15, 20, 30] : [1, 2, 3, 5]
    const total = (t.today_total || 0)
    const target = (t.task_target || ch.target_value || 1)
    let html = '<div class="cp-extra-panel"><div class="cp-extra-head"><span class="cp-extra-pv">今日 ' + total + '/' + target + ' ' + unit + '</span></div><div class="cp-extra-btns">'
    presets.forEach(v => {
      const label = isTimer ? '+' + v + '分' : '+' + v
      html += '<button class="cp-tap-chip" ' + dis + ' onclick="cpViews.home.doFastTap(' + v + ')"><i class="fas fa-plus"></i>' + label + '</button>'
    })
    html += '<button class="cp-tap-chip ghost" ' + dis + ' onclick="cpViews.home.openQuickForm()"><i class="fas fa-sliders"></i>自定义</button>'
    html += '</div></div>'
    return html
  }

  V._stepPanel = function (t, dis) {
    const d = this.data
    const steps = t.task_steps || []
    let h = '<div class="cp-extra-panel"><div class="cp-step-list">'
    steps.forEach(st => {
      const done = d.taskSteps.includes(st)
      h += '<div class="cp-step-item' + (done ? ' done' : '') + '" onclick="cpViews.home.toggleStep(\'' + encodeURIComponent(st) + '\')"><span class="cp-step-check">' + (done ? '✓' : '○') + '</span><span class="cp-step-text">' + window.cpEsc(st) + '</span></div>'
    })
    h += '</div><button class="cp-btn-checkin"' + (d.taskSteps.length === 0 ? ' disabled' : '') + ' ' + dis + ' onclick="cpViews.home.doMultiCheckin()"><i class="fas fa-list-check"></i> 打卡完成 (' + d.taskSteps.length + '/' + steps.length + ')</button></div>'
    return h
  }

  V._textPanel = function (t, dis) {
    const d = this.data
    const target = t.task_target || 0
    const unit = window.cpEsc(t.task_unit || '字')
    const len = (d.textValue || '').length
    let h = '<div class="cp-extra-panel"><div class="cp-text-area">'
    h += '<textarea class="cp-text-input" ' + dis + ' placeholder="写几句此刻的想法，以后回看会感动自己..." oninput="cpViews.home.setText(this.value)" style="resize:none;font-size:15px;line-height:1.6;min-height:96px">' + window.cpEsc(d.textValue || '') + '</textarea>'
    h += '<div class="cp-text-counter"><span class="cp-text-count' + (target > 0 && len >= target ? ' done' : '') + '">' + len + '</span>' + (target > 0 ? ' / ' + target + ' ' + unit : ' 字') + '</div>'
    h += '</div><button class="cp-btn-checkin" ' + dis + ' onclick="cpViews.home.doMainCheckin()"><i class="fas fa-circle-check"></i> 写入并完成今日</button></div>'
    return h
  }

  V._undoPanel = function (t, ch, dis) {
    const lst = (t.today_checkins || []).slice().reverse()
    if (!lst.length) return ''
    let h = '<div class="cp-extra-panel">'
    lst.slice(0, 3).forEach(c => {
      h += '<div class="cp-undo-item"><span class="cp-undo-time">' + (c.timestamp || '').slice(11, 16) + '</span><span class="cp-undo-val">' + c.value + ' ' + window.cpEsc(c.unit || ch.unit || '') + '</span><button class="cp-undo-del" ' + dis + ' onclick="cpViews.home.doUndoLast()"><i class="fas fa-trash-can"></i></button></div>'
    })
    h += '</div>'
    return h
  }
})()
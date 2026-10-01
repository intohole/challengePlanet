;(function () {
  const V = window.cpViews.home

  V._checkinArea = function (tt, t, ch) {
    const d = this.data
    const dis = d.checking ? 'disabled' : ''
    const done = !!t.settled
    let html = '<div class="cp-checkin-box">' + this._mainCTA(tt, t, ch, dis, done)
    if (tt === 'timer' && ch.scene_template !== 'pomodoro' && window.cpStopwatchRender) {
      html += window.cpStopwatchRender(t, ch, dis, done)
    }
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
    const isCount = tt === 'counter' || tt === 'timer'
    if (isCount) return isDecrease || !done ? this._tallyCta(tt, t, ch, dis) : '<button class="cp-cta-done" disabled><i class="fas fa-circle-check"></i><span>今日已完成</span></button>'
    if (done) {
      return '<button class="cp-cta-done" disabled><i class="fas fa-circle-check"></i><span>今日已完成</span></button>'
    }
    if (tt === 'word') {
      return '<button class="cp-cta-main" ' + dis + ' onclick="cpViews.home.openWord()"><i class="fas fa-book"></i><span>今日背词</span><em>刷完当日词卡即自动达成</em></button>'
    }
    if (tt === 'text') {
      return '<button class="cp-cta-main" ' + dis + ' onclick="cpViews.home.openText()"><i class="fas fa-pen-nib"></i><span>今日记录</span><em>写下几句即自动完成</em></button>'
    }
    if (tt === 'step' && t.task_steps && t.task_steps.length) {
      return '<button class="cp-cta-main" ' + dis + ' onclick="cpViews.home.openStep()"><i class="fas fa-list-check"></i><span>今日分步</span><em>勾选完成项后提交即自动判定</em></button>'
    }
    if (tt === 'step') {
      return '<button class="cp-cta-main" disabled><i class="fas fa-list-check"></i><span>分步清单未配置</span><em>请先配置分步清单</em></button>'
    }
    let title = '今日完成'
    let sub = ''
    if (isDecrease) {
      title = '守住今日'
      sub = '不超 ' + target + ' ' + unit + ' 即达标'
    } else if (tt === 'recite') {
      title = '今日背诵完成'
    }
    return '<button class="cp-cta-main" ' + dis + ' onclick="cpViews.home.doMainCheckin()"><i class="fas fa-fire"></i><span>' + (d.checking ? '记录中…' : title) + '</span>' + (sub ? '<em>' + sub + '</em>' : '') + '</button>'
  }

  V._extras = function (tt, t, ch, dis, done) {
    const d = this.data
    const isDecrease = ch.direction === 'decrease' || String(t.direction) === 'decrease'
    const isCount = tt === 'counter' || tt === 'timer'
    if (isCount && !isDecrease && done) return '<div class="cp-extra-row"><button class="cp-extra-chip' + (this._panel === 'quick' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'quick\')"><i class="fas fa-pen"></i>记实际值</button></div>' + this._panelBody(tt, t, ch, dis)
    if (isCount) return ''
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
      return '<div class="cp-extra-row"><button class="cp-extra-chip' + (this._panel === 'text' ? ' active' : '') + '" ' + dis + ' onclick="cpViews.home.togglePanel(\'text\')"><i class="fas fa-pen-nib"></i>写几句</button></div>' + this._panelBody(tt, t, ch, dis)
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
    html += '</div>' + this._ctxRow() + this._moodRow() + '</div>'
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
      h += '<div class="cp-undo-item"><span class="cp-undo-time">' + (c.timestamp || '').slice(11, 16) + '</span><span class="cp-undo-val">' + c.value + ' ' + window.cpEsc(c.unit || ch.unit || '') + '</span><button class="cp-undo-del" onclick="cpViews.home.removeTodayRecord(' + c.id + ')"><i class="fas fa-trash-can"></i></button></div>'
    })
    h += '</div>'
    return h
  }
})()

;(function () {
  const V = window.cpViews.home

  window.cpExtraPanelRender = function (key, tt, t, ch, dis) {
    if (key !== 'pm') return ''
    return '<div class="cp-extra-panel">' + V._pomodoroUI(t, ch, dis) + '</div>'
  }

  V._pomodoroUI = function (t, ch, dis) {
    const d = this.data
    const isWork = d.pmPhase === 'work'
    const workMin = Math.round(t.task_target || (ch && ch.target_value) || 25)
    let html = '<div class="cp-checkin-box">'
    html += '<div class="cp-pm-wrap">'
    html += '<div class="cp-pm-ring' + (d.pmRunning ? ' running' : '') + '"><div class="cp-pm-time" id="cp-pm-time">' + this._pmFmt(d.pmLeft) + '</div><div class="cp-pm-phase">' + (isWork ? (d.pmRunning ? '🍅 专注中' : '🍅 专注计时') : '☕ 休息中') + '</div></div>'
    html += '<div class="cp-pm-controls">'
    html += '<button class="cp-pm-btn primary" ' + dis + ' onclick="cpViews.home.pmToggle()">' + (d.pmRunning ? '⏸ 暂停' : '▶ ' + (d.pmLeft < (isWork ? workMin * 60 : 300) ? '继续' : '开始专注')) + '</button>'
    html += '<button class="cp-pm-btn ghost" ' + dis + ' onclick="cpViews.home.pmReset()">↺ 重置</button></div>'
    html += (isWork ? '<p class="cp-pm-hint">专注完成自动记录一个番茄（' + workMin + ' 分钟）</p>' : '<p class="cp-pm-hint">休息完毕自动进入下一个专注</p>')
    html += '</div></div>'
    return html
  }

  V.pmToggle = function () {
    const d = this.data
    if (!window.appState.current) return
    d.pmRunning = !d.pmRunning
    if (d.pmRunning) this._pmStart()
    else clearInterval(V._pmIv)
    this.rerender()
  }

  V.pmReset = function () {
    const d = this.data
    const ch = window.appState.current
    clearInterval(V._pmIv)
    d.pmRunning = false
    d.pmPhase = 'work'
    d.pmLeft = Math.round((ch && (ch.target_value || 25)) * 60)
    this.rerender()
  }

  V._pmStart = function () {
    const d = this.data
    const ch = window.appState.current
    clearInterval(V._pmIv)
    V._pmIv = setInterval(() => {
      d.pmLeft--
      if (d.pmLeft <= 0) {
        if (d.pmPhase === 'work') {
          d.pmPhase = 'rest'
          d.pmLeft = 300
          clearInterval(V._pmIv)
          d.pmRunning = false
          V.doFastTap.call(this, Math.round((ch && (ch.target_value || 25)) * 60) / 60)
          window.cpToast('🍅 专注完成！休息 5 分钟')
        } else {
          d.pmPhase = 'work'
          d.pmLeft = Math.round((ch && (ch.target_value || 25)) * 60)
        }
        this.rerender()
        return
      }
      const el = document.getElementById('cp-pm-time')
      if (el && el.tagName === 'DIV') el.textContent = V._pmFmt(d.pmLeft)
    }, 1000)
  }

  V._pmFmt = function (sec) {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0')
  }
})()

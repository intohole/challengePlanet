;(function () {
  const V = window.cpViews.home

  window.cpStopwatchRender = function (t, ch, dis, done) {
    if (done) return ''
    const d = V.data
    let html = '<div class="cp-checkin-box cp-stopwatch">'
    html += '<div class="cp-sw-time" id="cp-sw-time">' + V._pmFmt(d.stElapsed) + '</div>'
    html += '<div class="cp-sw-controls">'
    html += '<button class="cp-sw-btn primary" ' + dis + ' onclick="cpViews.home.stopwatchToggle()">' + (d.stRunning ? '⏹ 结束并记录' : '▶ 开始计时') + '</button>'
    html += '<button class="cp-sw-btn ghost" ' + dis + ' onclick="cpViews.home.stopwatchReset()">↺ 重置</button></div>'
    html += '<p class="cp-sw-hint">专注结束点「结束并记录」，时长自动入账，达标由系统判定</p>'
    html += '</div>'
    return html
  }

  V.stopwatchToggle = async function () {
    const d = this.data
    if (d.stRunning) {
      clearInterval(V._stIv)
      d.stRunning = false
      this.rerender()
      const minutes = Math.max(0.1, Math.round(d.stElapsed / 60 * 10) / 10)
      if (minutes > 0.05) {
        const ok = await V.doFastTap.call(this, minutes)
        if (ok) {
          window.cpToast('已记录 ' + minutes + ' 分钟')
          d.stElapsed = 0
        } else {
          d.stRunning = true
          window.cpToast('记录失败，计时继续，可再点结束重试')
          V._stIv = setInterval(() => {
            d.stElapsed++
            const el = document.getElementById('cp-sw-time')
            if (el) el.textContent = V._pmFmt(d.stElapsed)
          }, 1000)
        }
      } else {
        d.stElapsed = 0
      }
      this.rerender()
      return
    }
    d.stRunning = true
    clearInterval(V._stIv)
    V._stIv = setInterval(() => {
      d.stElapsed++
      const el = document.getElementById('cp-sw-time')
      if (el) el.textContent = V._pmFmt(d.stElapsed)
    }, 1000)
    this.rerender()
  }

  V.stopwatchReset = function () {
    const d = this.data
    clearInterval(V._stIv)
    d.stRunning = false
    d.stElapsed = 0
    this.rerender()
  }

  V.clearLearnTimers = function () {
    if (V._stIv) { clearInterval(V._stIv); V._stIv = null }
    if (V._pmIv) { clearInterval(V._pmIv); V._pmIv = null }
  }

  window.cpClearLearnTimers = function () { V.clearLearnTimers() }
})()

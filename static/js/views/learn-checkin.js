;(function () {
  const V = window.cpViews.home
  V._jsonCache = {}
  V._pmIv = null

  V._loadJSON = async function (url) {
    if (V._jsonCache[url]) return V._jsonCache[url]
    const res = await fetch(url)
    const data = await res.json()
    V._jsonCache[url] = data
    return data
  }

  V._wordUI = function (t, dis) {
    const d = this.data
    const dayKey = (t && t.day_number) || 1
    if ((!d.wordCards.length || d.wordCardsDay !== dayKey) && !d.wordLoading) {
      d.wordCardsDay = dayKey
      d.wordLoading = true
      this._loadWordCards(t).then(cards => {
        d.wordCards = cards || []
        d.wordIdx = 0
        d.wordSeen = 0
        d.wordKnown = 0
        d.wordBlur = 0
        d.wordForgot = 0
        d.wordRevealed = false
        d.wordLoading = false
        this.rerender()
      })
      return '<div class="cp-checkin-box"><div class="cp-learn-loading">🔤 正在加载今日词卡...</div></div>'
    }
    const total = d.wordCards.length
    const cur = d.wordCards[d.wordIdx]
    if (!cur) {
      const doneLine = '<div class="cp-word-done"><i class="fas fa-circle-check"></i> 今日 ' + d.wordSeen + ' 个单词已学完 <b>😀 ' + d.wordKnown + '</b> <b>🤔 ' + d.wordBlur + '</b> <b>😵 ' + d.wordForgot + '</b></div>'
      if (t && t.checked_in) return '<div class="cp-checkin-box">' + doneLine + '<p class="cp-word-hint">✅ 今日背词已自动完成</p></div>'
      return '<div class="cp-checkin-box">' + doneLine + '<button class="cp-btn-checkin" ' + dis + ' onclick="cpViews.home.retryWordComplete()"><i class="fas fa-flag-checkered"></i> 记录未生效，点此重试</button></div>'
    }
    let html = '<div class="cp-checkin-box">'
    html += '<div class="cp-word-progress"><span>今日 ' + total + ' 词</span><span>' + (d.wordIdx + 1) + '/' + total + '</span></div>'
    html += '<div class="cp-word-card' + (d.wordRevealed ? ' revealed' : '') + '" onclick="cpViews.home.wordReveal()">'
    html += '<div class="cp-word-main">' + window.cpEsc(cur.w) + '</div>'
    if (d.wordRevealed) {
      html += '<div class="cp-word-meaning">' + window.cpEsc(cur.m) + '</div>'
      if (cur.s) html += '<div class="cp-word-sample">📖 ' + window.cpEsc(cur.s) + '</div>'
    }
    html += '</div>'
    if (!d.wordRevealed) {
      html += '<p class="cp-word-hint">点击卡片查看释义</p>'
    } else {
      html += '<div class="cp-word-feedback">'
      html += '<button class="cp-word-fb known" ' + dis + ' onclick="cpViews.home.wordGrade(\'known\')">😀 认识</button>'
      html += '<button class="cp-word-fb blur" ' + dis + ' onclick="cpViews.home.wordGrade(\'blur\')">🤔 模糊</button>'
      html += '<button class="cp-word-fb forgot" ' + dis + ' onclick="cpViews.home.wordGrade(\'forgot\')">😵 忘记</button>'
      html += '</div>'
    }
    html += '</div>'
    return html
  }

  V.wordReveal = function () {
    this.data.wordRevealed = true
    this.rerender()
  }

  V.wordGrade = function (g) {
    const d = this.data
    d.wordSeen++
    if (g === 'known') d.wordKnown++
    else if (g === 'blur') d.wordBlur++
    else d.wordForgot++
    const last = d.wordIdx >= d.wordCards.length - 1
    if (last) d.wordIdx = d.wordCards.length
    else {
      d.wordIdx++
      d.wordRevealed = false
    }
    this.rerender()
    if (last) this._autoCompleteWord()
  }

  V.retryWordComplete = function () { this._autoCompleteWord() }

  V._autoCompleteWord = async function () {
    const d = this.data
    const ch = window.appState.current
    const t = d.today
    if (!ch || d.checking || (t && t.checked_in)) return
    d.checking = true
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/checkin', { value: d.wordCards.length })
      const r = res.data || res
      window.cpToast('今日 ' + d.wordCards.length + ' 词已学完，背词打卡自动完成')
      await this._finishCheckin(r, ch, d, t && t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '背词记录失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V._loadWordCards = async function (t) {
    const ch = window.appState.current
    const count = Math.max(5, Math.round(t.task_target || (ch && ch.target_value) || 20))
    const list = await this._loadJSON('/static/data/vocab.json')
    if (!list || !list.length) return []
    const key = 'vocab.shuffled'
    let pool = V._jsonCache[key]
    if (!pool) {
      pool = list.slice()
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        const tmp = pool[i]
        pool[i] = pool[j]
        pool[j] = tmp
      }
      V._jsonCache[key] = pool
    }
    const start = ((t.day_number || 1) - 1) * count % pool.length
    const cards = []
    for (let i = 0; i < count; i++) cards.push(pool[(start + i) % pool.length])
    return cards
  }

  V._reciteUI = function (t, dis) {
    const d = this.data
    if (!d.poem && !d.poemLoading) {
      d.poemLoading = true
      this._loadPoem(t).then(p => {
        d.poem = p || null
        d.poemLoading = false
        this.rerender()
      })
      return '<div class="cp-checkin-box"><div class="cp-learn-loading">📜 正在准备今日诗篇...</div></div>'
    }
    const p = d.poem
    if (!p) return '<div class="cp-checkin-box"><div class="cp-learn-loading">📜 正在准备今日诗篇...</div></div>'
    let html = '<div class="cp-checkin-box cp-poem-box">'
    html += '<div class="cp-poem-title">' + window.cpEsc(p.title) + '</div>'
    html += '<div class="cp-poem-author">' + window.cpEsc(p.dynasty) + ' · ' + window.cpEsc(p.author) + '</div>'
    html += '<div class="cp-poem-content">' + p.content.map(l => '<div class="cp-poem-line">' + window.cpEsc(l) + '</div>').join('') + '</div>'
    if (d.poemShow) html += '<div class="cp-poem-meaning">💡 ' + window.cpEsc(p.meaning) + '</div>'
    html += '<button class="cp-poem-toggle" onclick="cpViews.home.poemToggle()">' + (d.poemShow ? '收起译文' : '看译文') + '</button>'
    html += '<button class="cp-btn-checkin" ' + dis + ' onclick="cpViews.home.doCheckin(\'full\')"><i class="fas fa-feather-pointed"></i> 我已能背诵全诗</button>'
    html += '</div>'
    return html
  }

  V.poemToggle = function () {
    this.data.poemShow = !this.data.poemShow
    this.rerender()
  }

  V._loadPoem = async function (t) {
    const list = await this._loadJSON('/static/data/poems.json')
    if (!list || !list.length) return null
    return list[((t.day_number || 1) - 1) % list.length]
  }

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
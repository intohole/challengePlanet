;(function () {
  const V = window.cpViews.home
  V._jsonCache = {}
  V._stIv = null
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
    const ch = window.appState.current
    const dayKey = (t && t.day_number) || 1
    if ((!d.wordCards.length || d.wordCardsDay !== dayKey) && !d.wordLoading) {
      d.wordCardsDay = dayKey
      const sessKey = 'cp_word_sess_' + ch.id + '_' + dayKey
      const saved = V._readSession(sessKey)
      if (saved && saved.cards && saved.cards.length) {
        d.wordCards = saved.cards
        d.wordIdx = saved.idx || 0
        d.wordSeen = saved.seen || 0
        d.wordKnown = saved.known || 0
        d.wordBlur = saved.blur || 0
        d.wordForgot = saved.forgot || 0
        d.wordNewTotal = saved.newTotal || saved.cards.length
        d.wordReviewTotal = saved.reviewTotal || 0
        d.wordReviewToday = saved.reviewToday || []
        d.wordSessionKey = sessKey
        d.wordRevealed = false
      } else {
        d.wordLoading = true
        V._buildWordDeck(t).then(deck => {
          d.wordLoading = false
          if (!deck || !deck.cards.length) { this.rerender(); return }
          d.wordCards = deck.cards
          d.wordIdx = 0
          d.wordSeen = 0
          d.wordKnown = 0
          d.wordBlur = 0
          d.wordForgot = 0
          d.wordNewTotal = deck.newTotal
          d.wordReviewTotal = deck.reviewCount
          d.wordReviewToday = []
          d.wordSessionKey = sessKey
          d.wordRevealed = false
          this.rerender()
        })
        return '<div class="cp-checkin-box"><div class="cp-learn-loading">🔤 正在准备今日词卡...</div></div>'
      }
    }
    const total = d.wordCards.length
    const cur = d.wordCards[d.wordIdx]
    if (!cur) {
      const needReview = (d.wordBlur || 0) + (d.wordForgot || 0)
      const doneLine = '<div class="cp-word-done"><i class="fas fa-circle-check"></i> 今日 ' + (d.wordNewTotal || total) + ' 新词已学完' + (d.wordReviewTotal ? ' + ' + d.wordReviewTotal + ' 复习' : '') + ' <b>😀 ' + (d.wordKnown || 0) + '</b> <b>🤔 ' + (d.wordBlur || 0) + '</b> <b>😵 ' + (d.wordForgot || 0) + '</b>' + (needReview > 0 ? '<p class="cp-word-hint">📌 模糊和忘记的 ' + needReview + ' 个词已加入明天复习</p>' : '') + '</div>'
      if (t && t.checked_in) return '<div class="cp-checkin-box">' + doneLine + '<p class="cp-word-hint">✅ 今日背词已自动完成</p></div>'
      return '<div class="cp-checkin-box">' + doneLine + '<button class="cp-btn-checkin" ' + dis + ' onclick="cpViews.home.retryWordComplete()"><i class="fas fa-flag-checkered"></i> 记录未生效，点此重试</button></div>'
    }
    let html = '<div class="cp-checkin-box">'
    html += '<div class="cp-word-progress"><span>今日 ' + (d.wordNewTotal || total) + ' 新词' + (d.wordReviewTotal ? ' + ' + d.wordReviewTotal + ' 复习' : '') + '</span><span>' + (d.wordIdx + 1) + '/' + total + '</span></div>'
    html += '<div class="cp-word-card' + (d.wordRevealed ? ' revealed' : '') + '" onclick="cpViews.home.wordReveal()">'
    if (cur.r) html += '<span class="cp-word-review-tag">🔁 复习</span>'
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

  V.wordReveal = function () { this.data.wordRevealed = true; this.rerender() }

  V.wordGrade = function (g) {
    const d = this.data
    d.wordSeen++
    if (g === 'known') d.wordKnown++
    else {
      if (g === 'blur') d.wordBlur++
      else d.wordForgot++
      const cur = d.wordCards[d.wordIdx]
      if (cur && cur.w) {
        if (!Array.isArray(d.wordReviewToday)) d.wordReviewToday = []
        d.wordReviewToday.push({ w: cur.w, m: cur.m || '', s: cur.s || '' })
      }
    }
    const last = d.wordIdx >= d.wordCards.length - 1
    if (last) d.wordIdx = d.wordCards.length
    else {
      d.wordIdx++
      d.wordRevealed = false
    }
    if (d.wordSessionKey) this._saveSession(d.wordSessionKey)
    this.rerender()
    if (last) this._autoCompleteWord()
  }

  V._saveSession = function (key) {
    const d = this.data
    try {
      localStorage.setItem(key, JSON.stringify({
        cards: d.wordCards, idx: d.wordIdx, seen: d.wordSeen, known: d.wordKnown, blur: d.wordBlur, forgot: d.wordForgot, newTotal: d.wordNewTotal, reviewTotal: d.wordReviewTotal, reviewToday: d.wordReviewToday || [],
      }))
    } catch (e) {}
  }

  V._readSession = function (key) {
    try {
      const raw = localStorage.getItem(key)
      return raw ? JSON.parse(raw) : null
    } catch (e) { return null }
  }

  V._reviewDeck = function (chId, dayKey) {
    if (!chId) return []
    let map = {}
    try {
      const raw = localStorage.getItem('cp_word_review_' + chId)
      map = raw ? JSON.parse(raw) : {}
    } catch (e) { map = {} }
    const items = []
    const seen = new Set()
    for (let d = dayKey - 1; d >= dayKey - 3 && d >= 1; d--) {
      const arr = map[String(d)]
      if (!Array.isArray(arr)) continue
      for (const it of arr) {
        if (!it || !it.w || seen.has(it.w)) continue
        seen.add(it.w)
        items.push(it)
      }
    }
    return items
  }

  V._storeReview = function (chId, dayKey, items) {
    if (!chId || !items || !items.length) return
    let map = {}
    try {
      const raw = localStorage.getItem('cp_word_review_' + chId)
      map = raw ? JSON.parse(raw) : {}
    } catch (e) { map = {} }
    const merged = {}
    const existing = Array.isArray(map[String(dayKey)]) ? map[String(dayKey)] : []
    existing.concat(items).forEach(it => { if (it && it.w) merged[it.w] = it })
    map[String(dayKey)] = Object.values(merged)
    for (const k of Object.keys(map)) {
      if (Number(k) < dayKey - 3) delete map[k]
    }
    try { localStorage.setItem('cp_word_review_' + chId, JSON.stringify(map)) } catch (e) {}
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
      const newTotal = d.wordNewTotal || Math.max(5, Math.round(t.task_target || (ch && ch.target_value) || 20)) || d.wordCards.length
      const r = await window.cpApi.checkin(ch.id, { value: newTotal })
      const needReview = (d.wordBlur || 0) + (d.wordForgot || 0)
      window.cpToast('今日 ' + newTotal + ' 新词刷完' + (d.wordReviewTotal ? ' + ' + d.wordReviewTotal + ' 复习' : '') + (needReview ? ' · 明天复习 ' + needReview : ''))
      if (d.wordReviewToday && d.wordReviewToday.length) {
        this._storeReview(ch.id, (t && t.day_number) || 1, d.wordReviewToday)
      }
      if (d.wordSessionKey) {
        try { localStorage.removeItem(d.wordSessionKey) } catch (e) {}
        d.wordSessionKey = ''
      }
      await this._finishCheckin(r, ch, d, t && t.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '背词记录失败，请重试'))
    } finally {
      d.checking = false
      this.rerender()
    }
  }

  V._buildWordDeck = async function (t) {
    const ch = window.appState.current
    const target = Math.max(5, Math.round(t.task_target || (ch && ch.target_value) || 20))
    const list = await this._loadJSON('/static/data/vocab.json')
    if (!list || !list.length) return { cards: [], newTotal: 0, reviewCount: 0 }
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
    const dayKey = (t.day_number || 1)
    const start = ((dayKey - 1) * target) % pool.length
    const newCards = []
    for (let i = 0; i < target; i++) newCards.push(pool[(start + i) % pool.length])
    const newSet = new Set(newCards.map(c => c.w))
    const reviews = this._reviewDeck(ch.id, dayKey)
      .filter(r => !newSet.has(r.w))
      .slice(0, 5)
      .map(r => ({ w: r.w, m: r.m, s: r.s, r: 1 }))
    return { cards: reviews.concat(newCards), newTotal: target, reviewCount: reviews.length }
  }
})()

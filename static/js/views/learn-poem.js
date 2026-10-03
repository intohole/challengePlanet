;(function () {
  const V = window.cpViews.home

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

  V.poemToggle = function () { this.data.poemShow = !this.data.poemShow; this.rerender() }

  V._loadPoem = async function (t) {
    const list = await this._loadJSON('/static/data/poems.json')
    if (!list || !list.length) return null
    return list[((t.day_number || 1) - 1) % list.length]
  }
})()

;(function () {
  const V = window.cpViews.home
  const SHIFT_CHOICES = [1, 2, 3, 7]

  V._slipCard = function (t, ch) {
    const s = t.slip
    if (!s || !s.yesterday_over || s.today_checked || !s.can_shift) return ''
    const key = 'cp_slip_dismiss_' + ch.id + '_' + window.cpTodayStr()
    try { if (sessionStorage.getItem(key)) return '' } catch (e) {}
    const unit = window.cpEsc(ch.unit || t.unit || '')
    const over = window.cpFmtInt(s.over_amount)
    const avoided = window.cpFmtInt(s.avoided_total)
    const cap = window.cpFmtInt(s.yesterday_cap)
    return '<div class="glass-card cp-slip-card" data-testid="slip-card">'
      + '<div class="cp-slip-icon"><i class="fas fa-mug-hot" aria-hidden="true"></i></div>'
      + '<div class="cp-slip-body">'
      + '<p class="cp-slip-title">昨天超了 ' + over + ' ' + unit + '</p>'
      + '<p class="cp-slip-sub">已少抽的 <b>' + avoided + '</b> ' + unit + '都还在——今天上限 ' + cap + ' ' + unit + '。坡太陡可以换挡。</p>'
      + '<div class="cp-slip-actions">'
      + '<button class="cp-btn-primary cp-slip-shift-btn" onclick="cpViews.home.openShift(' + ch.id + ')"><i class="fas fa-stairs" aria-hidden="true"></i> 阶梯换挡</button>'
      + '<button class="cp-slip-dismiss" onclick="cpViews.home.dismissSlip(' + ch.id + ')">今天照常守</button>'
      + '</div></div></div>'
  }

  V.dismissSlip = function (chId) {
    try { sessionStorage.setItem('cp_slip_dismiss_' + chId + '_' + window.cpTodayStr(), '1') } catch (e) {}
    this.rerender()
  }

  V.openShift = async function (chId) {
    const s = window.appState
    s.ladderShift = { show: true, chId: chId, k: 0, preview: null, saving: false, err: '' }
    await this.pickShift(2)
  }

  V.closeShift = function () {
    window.appState.ladderShift = null
  }

  V.pickShift = async function (k) {
    const s = window.appState
    if (!s.ladderShift) return
    s.ladderShift.k = k
    s.ladderShift.err = ''
    try {
      const res = await window.cpApi.post('/challenges/' + s.ladderShift.chId + '/ladder-adjust', { shift_days: k, preview: true })
      if (s.ladderShift) s.ladderShift.preview = res
    } catch (e) {
      if (s.ladderShift) s.ladderShift.err = window.cpErrMsg ? window.cpErrMsg(e, '预览失败，稍后再试') : '预览失败，稍后再试'
    }
  }

  V.confirmShift = async function () {
    const s = window.appState
    if (!s.ladderShift || !s.ladderShift.k) return
    s.ladderShift.saving = true
    s.ladderShift.err = ''
    try {
      const res = await window.cpApi.post('/challenges/' + s.ladderShift.chId + '/ladder-adjust', { shift_days: s.ladderShift.k })
      try { sessionStorage.setItem('cp_slip_dismiss_' + s.ladderShift.chId + '_' + window.cpTodayStr(), '1') } catch (e) {}
      window.cpCelebrate('已换挡 +' + res.shift_days + ' 天' + (res.graduation_date ? '，毕业日 ' + res.graduation_date : ''))
      s.ladderShift = null
      this.loadedFor = null
      await this.load()
    } catch (e) {
      if (s.ladderShift) {
        s.ladderShift.saving = false
        s.ladderShift.err = window.cpErrMsg ? window.cpErrMsg(e, '换挡失败，稍后再试') : '换挡失败，稍后再试'
      }
    }
  }

  V.openShiftFromDeepLink = async function (chId) {
    const key = 'cp_slip_deeplink_' + chId + '_' + window.cpTodayStr()
    try { if (sessionStorage.getItem(key)) return } catch (e) {}
    try { sessionStorage.setItem(key, '1') } catch (e) {}
    await this.openShift(chId)
  }

  V._shiftPreviewRows = function (p) {
    if (!p) return ''
    const rows = []
    if (p.today_cap !== undefined && this.data.today) {
      const oldCap = Number(this.data.today.today_cap) || 0
      const newCap = Number(p.today_cap) || 0
      if (newCap !== oldCap) {
        rows.push('<div class="cp-shift-row"><span>今天上限</span><b>' + window.cpFmtInt(oldCap) + ' → ' + window.cpFmtInt(newCap) + '</b></div>')
      }
    }
    const grad = p.graduation_date ? String(p.graduation_date) : ''
    if (grad) {
      const j = (this.data.today && this.data.today.journey) || {}
      const oldGrad = j.graduation && j.graduation.graduation_date ? j.graduation.graduation_date : ''
      if (grad !== oldGrad) {
        rows.push('<div class="cp-shift-row"><span>毕业日</span><b>' + window.cpEsc(oldGrad || '—') + ' → ' + window.cpEsc(grad) + '</b></div>')
      } else {
        rows.push('<div class="cp-shift-row"><span>毕业日</span><b>' + window.cpEsc(grad) + '</b></div>')
      }
    }
    return rows.join('')
  }

  V.shiftChoices = SHIFT_CHOICES
})()

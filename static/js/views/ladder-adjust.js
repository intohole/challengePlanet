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
    const cap = window.cpFmtInt(t.today_cap || t.today_target || 0)
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

  V._absenceCard = function (t, ch) {
    const a = t.absence
    if (!a || !a.can_shift || a.today_checked) return ''
    const key = 'cp_absence_dismiss_' + ch.id + '_' + window.cpTodayStr()
    try { if (sessionStorage.getItem(key)) return '' } catch (e) {}
    const unit = window.cpEsc(ch.unit || t.unit || '')
    const days = window.cpFmtInt(a.absent_days)
    const avoided = window.cpFmtInt(a.avoided_total)
    const cap = window.cpFmtInt(t.today_cap || t.today_target || 0)
    const dis = this.data.checking ? 'disabled' : ''
    const shiftBtn = a.suggest_adjust
      ? '<button class="cp-absence-shift-btn" ' + dis + ' onclick="cpViews.home.openShift(' + ch.id + ',\'absence\')"><i class="fas fa-stairs" aria-hidden="true"></i> 阶梯后移一点</button>'
      : ''
    const kept = avoided > 0 ? '已少抽的 <b>' + avoided + '</b> ' + unit + ' 都还在。' : ''
    const grad = t.journey && t.journey.graduation && t.journey.graduation.state === 'graduated'
    if (grad) {
      return '<div class="glass-card cp-absence-card" data-testid="absence-card">'
        + '<div class="cp-absence-icon"><i class="fas fa-graduation-cap" aria-hidden="true"></i></div>'
        + '<div class="cp-absence-body">'
        + '<p class="cp-absence-title">' + days + ' 天没见了，毕业证书在等你</p>'
        + '<p class="cp-absence-sub">阶梯已经走完，' + kept + '证书一直留着，随时回来领。</p>'
        + '<div class="cp-absence-actions">'
        + '<button class="cp-btn-primary cp-absence-log-btn" data-testid="absence-grad-btn" onclick="window.cpOpenShare(\'grad\')"><i class="fas fa-graduation-cap" aria-hidden="true"></i> 领取毕业证书</button>'
        + '<button class="cp-absence-shift-btn" ' + dis + ' onclick="cpViews.home.logAbsenceReturn(' + ch.id + ')"><i class="fas fa-pen" aria-hidden="true"></i> 今天记一笔</button>'
        + shiftBtn
        + '<button class="cp-absence-dismiss" onclick="cpViews.home.dismissAbsence(' + ch.id + ')">先看看</button>'
        + '</div></div></div>'
    }
    return '<div class="glass-card cp-absence-card" data-testid="absence-card">'
      + '<div class="cp-absence-icon"><i class="fas fa-door-open" aria-hidden="true"></i></div>'
      + '<div class="cp-absence-body">'
      + '<p class="cp-absence-title">' + days + ' 天没见了，门一直开着</p>'
      + '<p class="cp-absence-sub">今天上限 <b>' + cap + ' ' + unit + '</b>，记一笔就算守住。' + kept + '</p>'
      + '<div class="cp-absence-actions">'
      + '<button class="cp-btn-primary cp-absence-log-btn" ' + dis + ' onclick="cpViews.home.logAbsenceReturn(' + ch.id + ')"><i class="fas fa-pen" aria-hidden="true"></i> 今天记一笔</button>'
      + shiftBtn
      + '<button class="cp-absence-dismiss" onclick="cpViews.home.dismissAbsence(' + ch.id + ')">先看看</button>'
      + '</div></div></div>'
  }

  V.logAbsenceReturn = async function (chId) {
    const ch = window.appState.current
    if (!ch || Number(ch.id) !== Number(chId)) return
    await this.doFastTap(1)
    if (this.data.today && this.data.today.checked_in) this.dismissAbsence(chId)
  }

  V.dismissAbsence = function (chId) {
    try { sessionStorage.setItem('cp_absence_dismiss_' + chId + '_' + window.cpTodayStr(), '1') } catch (e) {}
    this.rerender()
  }

  V.openShift = async function (chId, ctx) {
    const s = window.appState
    const t = this.data.today
    const ab = (t && t.absence) || this.data.returnBlock || null
    const ctxData = ab ? { absent_days: ab.absent_days, last_value: ab.last_value, last_record_date: ab.last_record_date } : null
    s.ladderShift = { show: true, chId: chId, k: 0, preview: null, saving: false, err: '', ctx: ctx || '', ctxData: ctxData }
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
      try {
        sessionStorage.setItem('cp_slip_dismiss_' + s.ladderShift.chId + '_' + window.cpTodayStr(), '1')
        sessionStorage.removeItem('cp_rb_' + s.ladderShift.chId + '_' + window.cpTodayStr())
      } catch (e) {}
      this.data.returnBlock = null
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

  V.shiftLede = function () {
    const s = window.appState
    if (s.ladderShift && s.ladderShift.ctx === 'absence' && s.ladderShift.ctxData && Number(s.ladderShift.ctxData.absent_days) >= 2) {
      const days = window.cpFmtInt(s.ladderShift.ctxData.absent_days)
      return '离开 ' + days + ' 天回来了。如果坡太陡，把整条阶梯往后移几天——走过的每一天都算数。'
    }
    return '把整条阶梯往后移几天，走过的每一天都算数。'
  }

  V._shiftPreviewRows = function (p) {
    if (!p) return ''
    const rows = []
    const s = window.appState
    if (s.ladderShift && s.ladderShift.ctx === 'absence' && s.ladderShift.ctxData) {
      const cd = s.ladderShift.ctxData
      const lastVal = Number(cd.last_value) || 0
      if (lastVal > 0) {
        rows.push('<div class="cp-shift-row cp-shift-last"><span>上次记录 ' + window.cpEsc(String(cd.last_record_date || '')) + '</span><b>' + window.cpFmtInt(lastVal) + ' ' + window.cpEsc((this.data.today && this.data.today.unit) || '') + '</b></div>')
      }
    }
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

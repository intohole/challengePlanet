;(function () {
  const V = window.cpViews.home

  V._nudgeNotify = function (r, ch, dateStr) {
    const level = Number(r.nudge_level) || 0
    const msg = r.coach_nudge || ''
    if (!level || !msg || !dateStr) return
    const key = 'cp_nudge_' + ch.id + '_' + dateStr
    let prev = 0
    try { prev = Number(localStorage.getItem(key)) || 0 } catch (e) {}
    if (level <= prev) return
    try { localStorage.setItem(key, String(level)) } catch (e) {}
    setTimeout(() => window.cpToast(msg, 3600), 1200)
  }

  V._clearNudgeStamp = function (chId, dateStr) {
    if (!chId || !dateStr) return
    try { localStorage.removeItem('cp_nudge_' + chId + '_' + dateStr) } catch (e) {}
  }

  V.CTX_LABELS = { home: '家', work: '工作', social: '社交', stress: '压力', drink: '酒后', meal: '饭后', bored: '无聊', habit: '习惯性' }
  V.CTX_EMOJI = { home: '🏠', work: '💼', social: '👥', stress: '😰', drink: '🍺', meal: '🍚', bored: '😞', habit: '🔄' }
  V.QUIT_CTX = ['stress', 'social', 'drink', 'meal', 'bored', 'habit']
  V.BASE_CTX = ['home', 'work', 'social', 'stress']
  V._ctxKeys = function () {
    const ch = window.appState.current
    return ch && ch.direction === 'decrease' ? this.QUIT_CTX : this.BASE_CTX
  }
  V.MOOD_EMOJI = { good: '😊', normal: '😐', bad: '😔' }

  V.patchContext = async function (checkinId, tag) {
    const ch = window.appState.current
    if (!ch) return
    try {
      await window.cpApi.patchCheckinMeta(ch.id, checkinId, { context_tag: tag })
      const t = this.data.today
      const c = ((t && t.today_checkins) || []).find(x => x.id === checkinId)
      if (c) c.context_tag = tag
      window.cpToast('已记下情境 ' + (this.CTX_EMOJI[tag] || ''))
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '补充情境失败')) }
  }

  V.patchMood = async function (checkinId, mood) {
    const ch = window.appState.current
    if (!ch) return
    try {
      await window.cpApi.patchCheckinMeta(ch.id, checkinId, { mood: mood })
      const t = this.data.today
      const c = ((t && t.today_checkins) || []).find(x => x.id === checkinId)
      if (c) c.mood = mood
      window.cpToast('已记下心情 ' + (this.MOOD_EMOJI[mood] || ''))
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '补充心情失败')) }
  }

  V._todayTimeline = function (s) {
    const ch = s.current
    const d = this.data
    const t = d.today
    if (!t) return ''
    const checkins = t.today_checkins || []
    if (!checkins.length) return ''
    let html = '<div class="glass-card cp-timeline"><div class="cp-section-title"><i class="fas fa-list-check" style="color:var(--primary-light)"></i> 今日记录（' + checkins.length + '次）</div>'
    html += '<div class="cp-timeline-list">'
    checkins.slice().reverse().forEach((c, i) => {
      const time = (c.timestamp || '').slice(11, 16)
      const isSoftExceeded = c.target_value > 0 && c.value > c.target_value && (c.goal_type === 'soft')
      const isHardExceeded = c.target_value > 0 && c.value > c.target_value && (c.goal_type === 'hard')
      let valueColor = 'var(--emerald)'
      if (isSoftExceeded) valueColor = 'var(--amber)'
      if (isHardExceeded) valueColor = 'var(--red)'
      html += '<div class="cp-timeline-item' + (i === 0 ? ' latest' : '') + '">'
      html += '<div class="cp-timeline-time">' + time + '</div>'
      html += '<div class="cp-timeline-dot" style="background:' + valueColor + '"></div>'
      html += '<div class="cp-timeline-body">'
      html += '<div class="cp-timeline-valrow"><div class="cp-timeline-val" style="color:' + valueColor + '">' + c.value + ' ' + window.cpEsc(c.unit || ch.unit || '') + '</div>'
      html += '<button class="cp-timeline-del" onclick="cpViews.home.removeTodayRecord(' + c.id + ')"><i class="fas fa-trash-can"></i> 撤销</button></div>'
      if (c.context_tag) html += '<div class="cp-ctx-badge">' + (this.CTX_EMOJI[c.context_tag] || '') + ' ' + (this.CTX_LABELS[c.context_tag] || c.context_tag) + '</div>'
      else if (i === 0) html += this._ctxPatchRow(c.id)
      if (c.mood) html += '<div class="cp-timeline-mood">' + ({ good: '😊', normal: '😐', bad: '😔' }[c.mood] || '') + '</div>'
      else if (i === 0) html += this._moodPatchRow(c.id)
      if (c.reflection) html += '<div class="cp-timeline-reflection">' + window.cpEsc(c.reflection) + '</div>'
      html += '</div></div>'
    })
    html += '</div></div>'
    return html
  }

  V._ctxPatchRow = function (checkinId) {
    const isDecrease = (() => { const ch = window.appState.current; return !!(ch && ch.direction === 'decrease') })()
    let h = '<div class="cp-ctx-patch"><span class="cp-ctx-q">' + (isDecrease ? '当时什么场景？' : '刚在哪？') + '</span>'
    ;this._ctxKeys().forEach(k => {
      h += '<button class="cp-pick-btn cp-ctx-chip" onclick="cpViews.home.patchContext(' + checkinId + ',\'' + k + '\')">' + this.CTX_EMOJI[k] + ' ' + this.CTX_LABELS[k] + '</button>'
    })
    return h + '</div>'
  }

  V._moodPatchRow = function (checkinId) {
    const ch = window.appState.current
    const t = this.data.today
    const over = !!(ch && ch.direction === 'decrease' && t && Number(t.today_total) > (Number(t.today_cap) || Number(t.today_target) || 0))
    const pairs = over
      ? [['bad', '😔 这次不太爽'], ['normal', '😐 一般'], ['good', '😊 不错']]
      : [['good', '😊 不错'], ['normal', '😐 一般'], ['bad', '😔 吃力']]
    let h = '<div class="cp-ctx-patch"><span class="cp-ctx-q">' + (over ? '这个时段对你特别难——这次感觉如何？' : '这次感觉如何？') + '</span>'
    ;pairs.forEach(kv => {
      h += '<button class="cp-pick-btn cp-ctx-chip' + (over && kv[0] === 'bad' ? ' suggest' : '') + '" onclick="cpViews.home.patchMood(' + checkinId + ',\'' + kv[0] + '\')">' + kv[1] + '</button>'
    })
    return h + '</div>'
  }

  V._tallyCta = function (tt, t, ch, dis) {
    const unit = window.cpEsc(t.unit || ch.unit || '')
    const cap = Number(t.today_cap) || Number(t.today_target) || Number(t.task_target) || Number(ch.target_value) || 1
    const total = Number(t.today_total) || 0
    const over = total > cap
    const isTimer = tt === 'timer'
    const isDecrease = ch.direction === 'decrease' || String(t.direction) === 'decrease'
    const presets = isTimer ? [5, 10, 20, 30, 45] : [1, 2, 3, 5]
    const state = isDecrease
      ? (over ? '已超今日上限 ' + cap + unit + '，放慢一点，明天继续' : (total > 0 ? '已记 ' + total + ' / 上限 ' + cap + ' ' + unit + '，还可 ' + Math.max(0, cap - total) : '今日还未记录 · 上限 ' + cap + ' ' + unit))
      : (total > 0 ? '已记 ' + total + ' / 目标 ' + cap + ' ' + unit + '，还差 ' + Math.max(0, cap - total) : '今日还未记录 · 目标 ' + cap + ' ' + unit)
    const ctaLabel = ch.scene_template === 'quit' ? '记一根' : '记一笔'
    let html = '<div class="cp-cap-cta"><button class="cp-cta-main cp-cap-main" ' + dis + ' onclick="cpViews.home.doFastTap(1)"><i class="fas fa-plus"></i><span>' + ctaLabel + '</span><em>' + state + '</em></button>'
    html += '<div class="cp-extra-btns">'
    if (isDecrease && total === 0 && !(t.today_checkins || []).length) {
      html += '<button class="cp-tap-chip zero" ' + dis + ' onclick="cpViews.home.doFastTap(0)"><i class="fas fa-seedling"></i>今天 0 根</button>'
    }
    presets.forEach(v => {
      const label = isTimer ? '+' + v + '分' : '+' + v
      html += '<button class="cp-tap-chip" ' + dis + ' onclick="cpViews.home.doFastTap(' + v + ')"><i class="fas fa-plus"></i>' + label + '</button>'
    })
    if ((t.today_checkins || []).length) html += '<button class="cp-tap-chip ghost" ' + dis + ' onclick="cpViews.home.doUndoLast()"><i class="fas fa-rotate-left"></i>撤销上一笔</button>'
    html += '</div>' + this._ctxRow() + this._moodRow() + '</div>'
    return html
  }

  V.removeTodayRecord = async function (checkinId) {
    const ch = window.appState.current
    if (!ch) return
    if (!(await window.nuxConfirm('撤销这条打卡记录？撤销后不可恢复。'))) return
    try {
      await window.cpApi.deleteCheckin(ch.id, checkinId)
      window.cpToast('已撤销该条打卡')
      this._clearNudgeStamp(ch.id, this.data.today && this.data.today.date)
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '撤销失败')) }
  }

  V._adaptiveCard = function (a) {
    let html = '<div class="cp-adapt-card"><div class="cp-adapt-head"><i class="fas fa-sliders"></i> 教练为你调整了计划</div><p class="cp-adapt-reason">' + window.cpEsc(a.reason || '') + '</p>'
    if (a.task && a.task.title) {
      html += '<div class="cp-adapt-task"><span class="cp-adapt-day">第 ' + (a.target_day || a.task.day || '?') + ' 天新任务</span><b>' + window.cpEsc(a.task.title) + '</b>'
      if (a.task.description) html += '<p>' + window.cpEsc(a.task.description) + '</p>'
      if (a.task.tip) html += '<p>💡 ' + window.cpEsc(a.task.tip) + '</p>'
      html += '</div>'
    }
    html += '<div class="cp-sub-actions" style="margin-top:10px"><button class="cp-btn-ghost" onclick="cpViews.home.respondAdaptive(false)">保持原计划</button><button class="cp-btn-primary" onclick="cpViews.home.respondAdaptive(true)"><i class="fas fa-check"></i> 采纳调整</button></div></div>'
    return html
  }

  V._diagEntry = function (missedCount) {
    return '<div class="cp-adapt-card" style="border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.07)"><div class="cp-adapt-head" style="color:var(--red)"><i class="fas fa-stethoscope"></i> 断签了？AI 帮你找原因</div><p class="cp-adapt-reason">已有 ' + missedCount + ' 天缺失。断签不是失败，找不到原因才是。AI 分析打卡记录，为你定制重启方案。</p><div class="cp-sub-actions" style="margin-top:0"><button class="cp-btn-ghost" onclick="cpOpenShare(\'flop\')"><i class="fas fa-share-nodes"></i> 翻车复盘海报</button><button class="cp-btn-primary" onclick="cpViews.home.doDiagnose()"><i class="fas fa-wand-magic-sparkles"></i> 一键诊断重启</button></div></div>'
  }

  V.respondAdaptive = async function (accept) {
    const ch = window.appState.current
    const a = this.data.adaptive
    if (!ch || !a) return
    try {
      await window.api.post('/challenges/' + ch.id + '/adaptive/' + a.id + '/respond', { accept: !!accept })
      window.cpToast(accept ? '已采纳新任务，即刻生效' : '好的，保持原计划')
      this.data.adaptive = null
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '操作失败')) }
  }

  V.doDiagnose = async function () {
    const ch = window.appState.current
    if (!ch) return
    const dg = window.appState.diagnosis
    dg.show = true
    dg.loading = true
    dg.report = null
    dg.applying = false
    try {
      dg.report = await window.cpApi.post('/challenges/' + ch.id + '/diagnose', {})
    } catch (e) {
      dg.show = false
      window.cpToast(window.cpErrMsg(e, '诊断失败，请稍后再试'))
    } finally { dg.loading = false }
  }

  V.applyDiagnosis = async function (action) {
    const ch = window.appState.current
    const dg = window.appState.diagnosis
    if (!ch || dg.applying) return
    dg.applying = true
    try {
      const r = await window.cpApi.post('/challenges/' + ch.id + '/diagnose/apply', { action: action || 'keep' })
      window.cpToast(r.message || '已应用方案')
      dg.show = false
      await this.load()
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '应用失败')) }
    finally { dg.applying = false }
  }
})()
;(function () {
  const V = window.cpViews.home

  V._dietTargetPanel = function (t, ch) {
    const d = this.data
    const dt = d.dietTarget
    if (!dt || !dt.target_kcal) return ''
    const total = Number(t.today_total) || 0
    const goal = Number(dt.target_kcal) || 0
    const deficit = Number(dt.deficit_kcal) || 0
    let html = '<div class="cp-diet-target"><div class="cp-diet-target-head"><span class="cp-diet-target-title"><i class="fas fa-bullseye"></i> 每日卡路里</span>'
    if (deficit > 0) html += '<span class="cp-diet-target-deficit">减 ' + deficit + ' 千卡/天</span>'
    html += '</div>'
    html += '<div class="cp-diet-target-stats"><div class="cp-diet-target-stat"><b>' + goal + '</b><span>目标摄入</span></div>'
    html += '<div class="cp-diet-target-stat"><b>' + total + '</b><span>已摄入</span></div></div>'
    const pct = goal > 0 ? Math.min(100, Math.round(total / goal * 100)) : 0
    html += '<div class="cp-task-progress"><div class="cp-task-progress-bar"><div class="cp-task-progress-fill" style="width:' + pct + '%;background:var(--primary)"></div></div></div>'
    html += '<div class="cp-diet-meta">BMR ' + (dt.bmr_kcal || 0) + ' · 消耗 ' + (dt.tdee_kcal || 0) + ' 千卡/天</div></div>'
    return html
  }

  V._dietArea = function (t, ch) {
    const d = this.data
    const dis = d.dietChecking ? 'disabled' : ''
    let html = '<div class="glass-card cp-diet-area">'
    html += '<div class="cp-section-title"><i class="fas fa-utensils" style="color:var(--primary-light)"></i> 记录今天吃了什么</div>'
    html += '<div class="cp-diet-input-row"><textarea class="cp-text-input cp-diet-input" ' + dis + ' placeholder="一句话描述，如：早餐一个鸡蛋加牛奶，午餐盒饭，晚餐一碗面，还喝了杯奶茶" oninput="cpViews.home.setDietDesc(this.value)" style="resize:none;font-size:15px;line-height:1.6;min-height:80px">' + window.cpEsc(d.dietDesc || '') + '</textarea>'
    html += '<button class="cp-btn-primary cp-diet-est-btn" ' + dis + ' onclick="cpViews.home.doDietEstimate()"><i class="fas fa-calculator"></i> ' + (d.dietChecking ? '估算中…' : 'AI 估算') + '</button></div>'
    if (d.declaration && !t.checked_in) html += '<button class="cp-diet-copy" ' + dis + ' onclick="cpViews.home.copyDiet()"><i class="fas fa-copy"></i> 照着昨天记一份</button>'
    if (d.dietResult) html += this._dietResult(t, ch, dis)
    if (t.checked_in) {
      html += '<button class="cp-btn-checkin done" style="margin-top:10px"><i class="fas fa-circle-check"></i> 今日饮食已记录</button>'
    }
    html += '</div>'
    html += '<div class="glass-card cp-diet-area">'
    html += '<div class="cp-section-title"><i class="fas fa-weight-scale" style="color:var(--primary-light)"></i> 记录体重</div>'
    html += this._weightBox(ch)
    if (d.weightTrend && d.weightTrend.records && d.weightTrend.records.length) html += this._weightTrend()
    html += '</div>'
    if (t.checked_in && d.lastFeedback) return html
    return html
  }

  V._dietResult = function (t, ch, dis) {
    const res = this.data.dietResult
    const total = Number(res.total_kcal) || 0
    const goal = Number(res.target_kcal) || Number(this.data.dietTarget && this.data.dietTarget.target_kcal) || 0
    const assess = res.assessment || {}
    const status = assess.status || 'unknown'
    const iconMap = { ok: 'fa-circle-check', under: 'fa-circle-minus', over: 'fa-circle-exclamation' }
    const colorMap = { ok: 'var(--emerald)', under: 'var(--amber)', over: 'var(--red)' }
    let h = '<div class="cp-diet-result">'
    h += '<div class="cp-diet-result-head"><span class="cp-diet-result-title"><i class="fas ' + (iconMap[status] || 'fa-circle-question') + '" style="color:' + (colorMap[status] || 'var(--amber)') + '"></i> 今日摄入约 ' + total + ' 千卡</span><span class="cp-diet-conf">' + Math.round((res.confidence || 0) * 100) + '% 置信</span></div>'
    if (goal > 0) h += '<div class="cp-diet-assess"><b style="color:' + (colorMap[status] || 'var(--amber)') + '">' + (assess.label || '估算') + '</b> · <span>目标 ' + goal + ' 千卡 · ' + window.cpEsc(res.deficit_kcal || 0) + ' 缺口</span></div>'
    if (res.items && res.items.length) {
      h += '<div class="cp-diet-items">'
      res.items.forEach(it => { if (it && it.name) h += '<span class="cp-diet-item">' + window.cpEsc(it.name) + ' <i>' + window.cpEsc(it.kcal) + '</i></span>' })
      h += '</div>'
    }
    h += '<div class="cp-sub-actions"><button class="cp-btn-ghost" ' + dis + ' onclick="cpViews.home.clearDiet()"><i class="fas fa-xmark"></i> 重新描述</button><button class="cp-btn-primary" ' + dis + ' onclick="cpViews.home.doDietCheckin()"><i class="fas fa-check"></i> ' + (this.data.dietChecking ? '提交中…' : '以此打卡') + '</button></div>'
    h += '</div>'
    return h
  }

  V._weightBox = function (ch) {
    const d = this.data
    const dis = d.dietChecking ? 'disabled' : ''
    return '<div class="cp-weight-row"><input type="number" min="20" max="400" step="0.1" class="cp-field cp-weight-input" placeholder="今天体重 (kg)" value="' + window.cpEsc(d.weightInput || '') + '" oninput="cpViews.home.setWeight(this.value)"><button class="cp-btn-primary cp-weight-btn" ' + dis + ' onclick="cpViews.home.doWeightRecord()"><i class="fas fa-check"></i> 记录</button></div>'
  }

  V._weightTrend = function () {
    const d = this.data
    const recs = d.weightTrend.records || []
    const maxW = Math.max.apply(null, recs.map(r => r.weight_kg)) || 0
    const minW = Math.min.apply(null, recs.map(r => r.weight_kg)) || 0
    const span = (maxW - minW) || 1
    const pts = recs.map((r, i) => {
      const x = recs.length === 1 ? 50 : Math.round(i / (recs.length - 1) * 100)
      const y = Math.round(100 - (r.weight_kg - minW) / span * 80 - 10)
      return x + ',' + y
    })
    const poly = pts.join(' ')
    let h = '<div class="cp-weight-trend"><div class="cp-section-title" style="margin-top:12px"><i class="fas fa-chart-line" style="color:var(--primary-light)"></i> 体重趋势（7日均值）</div>'
    h += '<svg viewBox="0 0 100 100" preserveAspectRatio="none" class="cp-weight-svg"><polyline points="' + poly + '" class="cp-weight-line"/><polygon points="' + poly + ' 100,100 0,100" class="cp-weight-fill"/></svg>'
    h += '<div class="cp-weight-stats">'
    if (d.weightTrend.latest) h += '<div class="cp-weight-stat"><b>' + d.weightTrend.latest.weight_kg + '</b><span>今日</span></div>'
    if (d.weightTrend.latest && (d.weightTrend.latest.avg7 || 0) > 0) h += '<div class="cp-weight-stat"><b>' + d.weightTrend.latest.avg7 + '</b><span>7日均值</span></div>'
    if (d.weightTrend.latest && (d.weightTrend.latest.delta || 0) !== 0) h += '<div class="cp-weight-stat"><b>' + (d.weightTrend.latest.delta > 0 ? '+' : '') + d.weightTrend.latest.delta + '</b><span>较首日</span></div>'
    h += '</div></div>'
    return h
  }

  V.setDietDesc = function (val) { this.data.dietDesc = val || '' }
  V.setWeight = function (val) { this.data.weightInput = val || '' }
  V.clearDiet = function () { this.data.dietDesc = ''; this.data.dietResult = null; this.rerender() }

  V.copyDiet = async function () {
    const ch = window.appState.current
    const d = this.data
    if (!ch) return
    const cl = d.checkins || []
    const yesterday = cl[cl.length - 1]
    if (!yesterday || !yesterday.reflection) { window.cpToast('昨天还没有记录，先描述今天的饮食吧'); return }
    d.dietDesc = yesterday.reflection
    this.rerender()
    await this.doDietEstimate()
  }

  V.doDietEstimate = async function () {
    const ch = window.appState.current
    const d = this.data
    if (!ch || d.dietChecking) return
    if (!(d.dietDesc || '').trim()) { window.cpToast('先描述一下今天吃了什么'); return }
    d.dietChecking = true
    d.dietResult = null
    this.rerender()
    try {
      const res = await window.api.post('/challenges/' + ch.id + '/diet/estimate', { description: d.dietDesc.trim() })
      const r = res.data || res
      if (!r.total_kcal) { window.cpToast('没识别到食物，请描述得更具体些'); return }
      d.dietResult = r
      this.rerender()
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '估算失败，请重试'))
    } finally { d.dietChecking = false; this.rerender() }
  }

  V.doDietCheckin = async function () {
    const ch = window.appState.current
    const d = this.data
    if (!ch || d.dietChecking) return
    const res = d.dietResult
    if (!res || !res.total_kcal) { window.cpToast('先让 AI 估算今天的摄入'); return }
    d.dietChecking = true
    this.rerender()
    try {
      const r2 = await window.api.post('/challenges/' + ch.id + '/checkin', { value: Number(res.total_kcal) || 0, unit: '千卡', reflection: d.dietDesc.trim(), mood: this._dietMood(res) })
      const rr = r2.data || r2
      window.cpCelebrate('饮食已打卡 +' + (rr.points_earned || 0) + ' 分')
      d.dietResult = null
      d.dietDesc = ''
      await this._finishCheckin(rr, ch, d, d.today && d.today.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '提交失败，请重试'))
    } finally { d.dietChecking = false; this.rerender() }
  }

  V._dietMood = function (res) {
    const st = (res.assessment || {}).status
    if (st === 'over') return 'bad'
    if (st === 'under') return 'good'
    return 'normal'
  }

  V.doWeightRecord = async function () {
    const ch = window.appState.current
    const d = this.data
    if (!ch || d.dietChecking) return
    const w = Number(d.weightInput)
    if (!w || w <= 20 || w > 400) { window.cpToast('请输入 20-400 之间的体重'); return }
    d.dietChecking = true
    this.rerender()
    try {
      await window.api.post('/challenges/' + ch.id + '/weight', { weight_kg: w })
      window.cpToast('已记录今日体重 ' + w + ' kg')
      const safe = p => p.then(r => ((r && r.data) || r)).catch(() => null)
      d.weightTrend = await safe(window.api.get('/challenges/' + ch.id + '/weight/trend'))
      this.rerender()
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '记录失败，请重试'))
    } finally { d.dietChecking = false; this.rerender() }
  }
})()
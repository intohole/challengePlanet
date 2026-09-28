;(function () {
  const V = window.cpViews.home

  V._dietTargetPanel = function (t, ch) {
    const d = this.data
    const dt = d.dietTarget
    if (!dt || !dt.target_kcal) return ''
    const total = Number(t.today_total) || 0
    const goal = Number(dt.target_kcal) || 0
    const deficit = Number(dt.deficit_kcal) || 0
    const burn = this._todayBurn(t)
    const left = goal - total + burn
    let html = '<div class="cp-diet-target"><div class="cp-diet-target-head"><span class="cp-diet-target-title"><i class="fas fa-bullseye"></i> 每日卡路里</span>'
    if (deficit > 0) html += '<span class="cp-diet-target-deficit">减 ' + deficit + ' 千卡/天</span>'
    html += '</div>'
    html += '<div class="cp-diet-target-stats"><div class="cp-diet-target-stat"><b>' + goal + '</b><span>目标摄入</span></div>'
    html += '<div class="cp-diet-target-stat"><b>' + window.cpFmtInt(total) + '</b><span>已摄入</span></div>'
    html += '<div class="cp-diet-target-stat ' + (left < 0 ? 'over' : '') + '"><b>' + window.cpFmtInt(Math.abs(left)) + '</b><span>' + (left < 0 ? '已超出' : '还可吃') + '</span></div></div>'
    const pct = goal > 0 ? Math.min(100, Math.round((total - burn) / goal * 100)) : 0
    html += '<div class="cp-task-progress"><div class="cp-task-progress-bar"><div class="cp-task-progress-fill" style="width:' + pct + '%;background:' + (left < 0 ? 'var(--amber)' : 'var(--primary)') + '"></div></div></div>'
    html += '<div class="cp-diet-meta">BMR ' + (dt.bmr_kcal || 0) + ' · 消耗 ' + (dt.tdee_kcal || 0) + ' 千卡/天'
    if (burn > 0) html += ' · <span style="color:var(--emerald);font-weight:600">运动 -' + window.cpFmtInt(burn) + ' 千卡</span>'
    html += '</div></div>'
    return html
  }

  V._todayBurn = function (t) {
    return ((t && t.today_checkins) || [])
      .filter(c => !(Number(c.value) || 0) && (Number(c.calories) || 0) > 0)
      .reduce((s, c) => s + (Number(c.calories) || 0), 0)
  }

  V._dietArea = function (t, ch) {
    const d = this.data
    const dis = d.dietChecking ? 'disabled' : ''
    let html = '<div class="glass-card cp-diet-area">'
    html += '<div class="cp-section-title"><i class="fas fa-utensils" style="color:var(--primary-light)"></i> 记录这一餐</div>'
    html += '<div id="cp-nux-diet-cam"></div>'
    setTimeout(() => { V._mountDietCam() }, 50)
    html += '<div class="cp-diet-or">或直接描述这一餐</div>'
    html += '<div class="cp-diet-input-row"><textarea class="cp-text-input cp-diet-input" ' + dis + ' placeholder="如：米饭一碗、红烧肉三块、清炒青菜一份、可乐一罐" oninput="cpViews.home.setDietDesc(this.value)" style="resize:none;font-size:15px;line-height:1.6;min-height:72px">' + window.cpEsc(d.dietDesc || '') + '</textarea>'
    html += '<button class="cp-btn-primary cp-diet-est-btn" ' + dis + ' onclick="cpViews.home.doDietEstimate()"><i class="fas fa-calculator"></i> ' + (d.dietChecking ? '估算中…' : 'AI 估算') + '</button></div>'
    if (d.dietResult) html += this._dietResult(t, ch, dis)
    html += '</div>'
    html += this._dietMeals(t, ch, dis)
    html += this._sportArea(t, ch, dis)
    html += '<div class="glass-card cp-diet-area">'
    html += '<div class="cp-section-title"><i class="fas fa-weight-scale" style="color:var(--primary-light)"></i> 记录体重</div>'
    if (!(d.weightTrend && d.weightTrend.records && d.weightTrend.records.length)) html += '<div class="cp-weight-hint">选填 · 每天记一次更清晰，不测不影响打卡</div>'
    html += this._weightBox(ch)
    if (d.weightTrend && d.weightTrend.records && d.weightTrend.records.length) html += this._weightTrend(ch)
    html += '</div>'
    if (t.checked_in && d.lastFeedback) return html
    return html
  }

  V._dietResult = function (t, ch, dis) {
    const res = this.data.dietResult
    const meal = Number(res.total_kcal) || 0
    const goal = Number(res.target_kcal) || Number(this.data.dietTarget && this.data.dietTarget.target_kcal) || 0
    const cum = (Number(res.today_intake) || 0) + meal
    const assess = res.assessment || {}
    const status = assess.status || 'unknown'
    const iconMap = { ok: 'fa-circle-check', under: 'fa-circle-minus', over: 'fa-circle-exclamation' }
    const colorMap = { ok: 'var(--emerald)', under: 'var(--amber)', over: 'var(--red)' }
    let h = '<div class="cp-diet-result">'
    h += '<div class="cp-diet-result-head"><span class="cp-diet-result-title"><i class="fas ' + (iconMap[status] || 'fa-circle-question') + '" style="color:' + (colorMap[status] || 'var(--amber)') + '"></i> 这一餐约 ' + window.cpFmtInt(meal) + ' 千卡</span><span class="cp-diet-conf">' + Math.round((res.confidence || 0) * 100) + '% 置信</span></div>'
    if (goal > 0) h += '<div class="cp-diet-assess"><b style="color:' + (colorMap[status] || 'var(--amber)') + '">' + (assess.label || '估算') + '</b> · <span>今日累计 ' + window.cpFmtInt(cum) + ' / 目标 ' + goal + ' 千卡 · ' + (cum >= goal ? '超出 ' : '还可吃 ') + window.cpFmtInt(Math.abs(goal - cum)) + ' 千卡</span></div>'
    if (res.items && res.items.length) {
      h += '<div class="cp-diet-items">'
      res.items.forEach(it => { if (it && it.name) h += '<span class="cp-diet-item">' + window.cpEsc(it.name) + ' <i>' + window.cpEsc(it.kcal) + '</i></span>' })
      h += '</div>'
    }
    h += '<div class="cp-sub-actions"><button class="cp-btn-ghost" ' + dis + ' onclick="cpViews.home.clearDiet()"><i class="fas fa-xmark"></i> 重新拍/重描述</button><button class="cp-btn-primary" ' + dis + ' onclick="cpViews.home.doDietCheckin()"><i class="fas fa-check"></i> ' + (this.data.dietChecking ? '提交中…' : '记下这一餐') + '</button></div>'
    h += '</div>'
    return h
  }

  V._dietMeals = function (t, ch, dis) {
    const list = (t.today_checkins || []).slice().reverse().filter(c => (Number(c.value) || 0) > 0)
    if (!list.length) return ''
    let h = '<div class="glass-card cp-diet-area"><div class="cp-section-title"><i class="fas fa-clock-rotate-left" style="color:var(--primary-light)"></i> 今日饮食记录</div>'
    h += '<div class="cp-diet-meals">'
    list.forEach(c => {
      h += '<div class="cp-diet-meal"><span class="cp-diet-meal-time">' + String(c.timestamp || '').slice(11, 16) + '</span><span class="cp-diet-meal-txt">' + window.cpEsc(String(c.reflection || '') || '饮食记录') + '</span><span class="cp-diet-meal-kcal">' + window.cpFmtInt(c.value) + ' 千卡</span><button class="cp-diet-meal-del" ' + dis + ' onclick="cpViews.home.deleteDietMeal(' + c.id + ')"><i class="fas fa-trash-can"></i></button></div>'
    })
    h += '</div></div>'
    return h
  }

  V._sportArea = function (t, ch, dis) {
    const d = this.data
    const w = Number(ch && ch.weight_kg) || 0
    if (w <= 0) return ''
    const labelMap = { walking: '快走', running: '跑步', cycling: '骑行', jump_rope: '跳绳', swimming: '游泳', strength: '力量训练', fitness: '综合健身', yoga: '瑜伽' }
    const metMap = { walking: 4.3, running: 9.8, cycling: 7.5, jump_rope: 11.8, swimming: 8.0, strength: 5.0, fitness: 6.0, yoga: 3.0 }
    let h = '<div class="glass-card cp-diet-area">'
    h += '<div class="cp-section-title"><i class="fas fa-person-running" style="color:var(--primary-light)"></i> 记录运动</div>'
    h += '<div class="cp-weight-hint">选填 · 运动消耗可抵扣今日可吃额度</div>'
    h += '<div class="cp-sport-row"><select class="cp-field cp-sport-select" ' + dis + ' onchange="cpViews.home.setSportType(this.value)"><option value="">选择运动</option>'
    Object.keys(labelMap).forEach(k => { h += '<option value="' + k + '"' + (d.sportType === k ? ' selected' : '') + '>' + labelMap[k] + '</option>' })
    h += '</select><input type="number" min="1" max="600" class="cp-field cp-sport-min" ' + dis + ' placeholder="分钟" value="' + window.cpEsc(d.sportMinutes || '') + '" oninput="cpViews.home.setSportMinutes(this.value)" onchange="cpViews.home.setSportMinutes(this.value)"></div>'
    const mins = Number(d.sportMinutes) || 0
    const kcal = d.sportType && mins > 0 ? Math.round(metMap[d.sportType] * w * mins / 60) : 0
    if (kcal > 0) h += '<div class="cp-sport-est">约消耗 <b>' + kcal + '</b> 千卡</div>'
    h += '<button class="cp-btn-primary cp-sport-btn" ' + dis + ' onclick="cpViews.home.doSportCheckin()"><i class="fas fa-check"></i> ' + (d.dietChecking ? '提交中…' : '记下这次运动') + '</button>'
    const sports = ((t && t.today_checkins) || []).filter(c => !(Number(c.value) || 0) && (Number(c.calories) || 0) > 0).reverse()
    if (sports.length) {
      h += '<div class="cp-diet-meals" style="margin-top:10px">'
      sports.forEach(c => {
        h += '<div class="cp-diet-meal"><span class="cp-diet-meal-time">' + String(c.timestamp || '').slice(11, 16) + '</span><span class="cp-diet-meal-txt">' + window.cpEsc(String(c.reflection || '') || '运动记录') + '</span><span class="cp-diet-meal-kcal sport">-' + window.cpFmtInt(c.calories) + ' 千卡</span><button class="cp-diet-meal-del" ' + dis + ' onclick="cpViews.home.deleteDietMeal(' + c.id + ')"><i class="fas fa-trash-can"></i></button></div>'
      })
      h += '</div>'
    }
    h += '</div>'
    return h
  }

  V._weightBox = function (ch) {
    const d = this.data
    const dis = d.dietChecking ? 'disabled' : ''
    return '<div class="cp-weight-row"><input type="number" min="20" max="400" step="0.1" class="cp-field cp-weight-input" placeholder="今天体重 (kg)" value="' + window.cpEsc(d.weightInput || '') + '" oninput="cpViews.home.setWeight(this.value)"><button class="cp-btn-primary cp-weight-btn" ' + dis + ' onclick="cpViews.home.doWeightRecord()"><i class="fas fa-check"></i> 记录</button></div>'
  }

  V._weightTrend = function (ch) {
    const d = this.data
    const recs = d.weightTrend.records || []
    const baseW = Number(ch && ch.weight_kg) || 0
    const goalW = Number(ch && ch.goal_weight) || 0
    const maxW = Math.max.apply(null, recs.map(r => r.weight_kg))
    const minW = Math.min.apply(null, recs.map(r => r.weight_kg))
    const allMax = Math.max(maxW, baseW, goalW)
    const allMin = Math.min(minW, baseW || maxW, goalW || minW)
    const span = (allMax - allMin) || 1
    const yAt = w => Math.round((allMax - w) / span * 80 + 10)
    const pts = recs.map((r, i) => {
      const x = recs.length === 1 ? 50 : Math.round(i / (recs.length - 1) * 100)
      return x + ',' + yAt(r.weight_kg)
    })
    const poly = pts.join(' ')
    let h = '<div class="cp-weight-trend"><div class="cp-section-title" style="margin-top:12px"><i class="fas fa-chart-line" style="color:var(--primary-light)"></i> 体重趋势（7日均值）</div>'
    h += '<svg viewBox="0 0 100 100" preserveAspectRatio="none" class="cp-weight-svg">'
    h += '<g class="cp-weight-guide">'
    if (goalW > 0) h += '<line x1="0" y1="' + yAt(goalW) + '" x2="100" y2="' + yAt(goalW) + '" class="cp-weight-goalline"/>'
    if (baseW > 0 && goalW > 0) h += '<line x1="0" y1="' + yAt(baseW) + '" x2="100" y2="' + yAt(goalW) + '" class="cp-weight-planline"/>'
    h += '</g>'
    h += '<polyline points="' + poly + '" class="cp-weight-line"/><polygon points="' + poly + ' 100,100 0,100" class="cp-weight-fill"/></svg>'
    h += '<div class="cp-weight-legend">' + (baseW > 0 && goalW > 0 ? '<span><i class="cp-lg-dot plan"></i>计划</span>' : '') + (goalW > 0 ? '<span><i class="cp-lg-dot goal"></i>目标 ' + goalW + 'kg</span>' : '') + '<span><i class="cp-lg-dot actual"></i>实测</span></div>'
    h += '<div class="cp-weight-stats">'
    if (d.weightTrend.latest) h += '<div class="cp-weight-stat"><b>' + d.weightTrend.latest.weight_kg + '</b><span>今日</span></div>'
    if (d.weightTrend.latest && (d.weightTrend.latest.avg7 || 0) > 0) h += '<div class="cp-weight-stat"><b>' + d.weightTrend.latest.avg7 + '</b><span>7日均值</span></div>'
    if (d.weightTrend.latest && (d.weightTrend.latest.delta || 0) !== 0) h += '<div class="cp-weight-stat"><b>' + (d.weightTrend.latest.delta > 0 ? '+' : '') + d.weightTrend.latest.delta + '</b><span>较首日</span></div>'
    h += '</div></div>'
    return h
  }

  V.setDietDesc = function (val) { this.data.dietDesc = val || '' }
  V.setWeight = function (val) { this.data.weightInput = val || '' }
  V.setSportType = function (val) { this.data.sportType = val || ''; this.rerender() }
  V.setSportMinutes = function (val) { this.data.sportMinutes = val || '' }
  V.clearDiet = function () { this.data.dietDesc = ''; this.data.dietImage = ''; this.data.dietResult = null; this.rerender() }

  V._mountDietCam = function () {
    const el = document.getElementById('cp-nux-diet-cam')
    if (!el || !window.NuxCameraRecognize) return
    if (V._dietCamApp) { try { V._dietCamApp.unmount() } catch (e) {} V._dietCamApp = null }
    const d = V.data
    const handleRecognize = async function (blob) {
      const ch = window.appState.current
      if (!ch) throw new Error('挑战未加载，请刷新重试')
      const dataUrl = await NexusUtils.compressImage(blob, { maxDim: 1280, quality: 0.82, output: 'dataurl' })
      const res = await window.api.post('/challenges/' + ch.id + '/diet/estimate', { image: dataUrl }, { timeout: 90000 })
      const r = res && res.data !== undefined ? res.data : res
      if (!r || !r.total_kcal) throw new Error('没识别到食物，换个角度重拍或直接描述')
      return r
    }
    V._dietCamApp = Vue.createApp({
      components: { NuxCameraRecognize: window.NuxCameraRecognize },
      setup() {
        const cam = Vue.ref(null)
        const onStart = () => { d.dietChecking = true }
        const onSuccess = (payload) => {
          if (cam.value) { try { cam.value.reset() } catch (e) {} }
          d.dietChecking = false
          d.dietResult = payload
          V.rerender()
        }
        const onError = () => { d.dietChecking = false }
        const onCancel = () => { d.dietChecking = false }
        return { cam, handleRecognize, onStart, onSuccess, onError, onCancel }
      },
      template: '<nux-camera-recognize ref="cam" :handler="handleRecognize" hint="拍照或选一张餐食照片，AI 自动识别热量，约需 10-25 秒" recognize-text="识别热量" :max-edge="1280" @start="onStart" @success="onSuccess" @error="onError" @cancel="onCancel"></nux-camera-recognize>'
    })
    try { V._dietCamApp.mount(el) } catch (e) { V._dietCamApp = null }
  }

  V.doDietEstimate = function () {
    return this._runDietEstimate('')
  }

  V._runDietEstimate = async function (image) {
    const ch = window.appState.current
    const d = this.data
    if (!ch || d.dietChecking) return
    const desc = (d.dietDesc || '').trim()
    if (!image && !desc) { window.cpToast('先拍一张照片，或描述这一餐吃了什么'); return }
    d.dietChecking = true
    d.dietResult = null
    this.rerender()
    try {
      const r = await window.cpApi.post('/challenges/' + ch.id + '/diet/estimate', image ? { image: image } : { description: desc }, image ? { timeout: 90000 } : {})
      if (!r.total_kcal) { window.cpToast('没识别到食物，换个角度重拍或直接描述'); return }
      d.dietResult = r
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '估算失败，请重试'))
    } finally {
      d.dietChecking = false
      this.rerender()
    }
  }

  V.doDietCheckin = async function () {
    const ch = window.appState.current
    const d = this.data
    const res = d.dietResult
    if (!ch || d.dietChecking || !res || !res.total_kcal) { window.cpToast('先拍一张照片或描述这一餐'); return }
    const kcal = Math.round(Number(res.total_kcal) || 0)
    const names = (res.items || []).map(it => it && it.name).filter(Boolean)
    const reflection = (d.dietDesc || '').trim() || names.join('、') || '饮食记录'
    d.dietChecking = true
    this.rerender()
    try {
      const rr = await window.cpApi.checkin(ch.id, { value: kcal, reflection: reflection, mood: this._dietMood(res) })
      window.cpCelebrate('已记下这一餐 ' + kcal + ' 千卡 +' + (rr.points_earned || 0) + ' 分')
      d.dietResult = null
      d.dietDesc = ''
      d.dietImage = ''
      await this._finishCheckin(rr, ch, d, d.today && d.today.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '提交失败，请重试'))
    } finally {
      d.dietChecking = false
      this.rerender()
    }
  }

  V.doSportCheckin = async function () {
    const ch = window.appState.current
    const d = this.data
    if (!ch || d.dietChecking) return
    const minutes = Number(d.sportMinutes) || 0
    if (!d.sportType) { window.cpToast('先选择运动类型'); return }
    if (minutes <= 0 || minutes > 600) { window.cpToast('请填写 1-600 分钟的运动时长'); return }
    d.dietChecking = true
    this.rerender()
    try {
      const rr = await window.cpApi.checkin(ch.id, { value: 0, sport_type: d.sportType, sport_minutes: minutes })
      window.cpCelebrate('已记录运动 +' + (rr.points_earned || 0) + ' 分')
      d.sportType = ''
      d.sportMinutes = ''
      await this._finishCheckin(rr, ch, d, d.today && d.today.date)
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '提交失败，请重试'))
    } finally {
      d.dietChecking = false
      this.rerender()
    }
  }

  V.deleteDietMeal = async function (checkinId) {
    const ch = window.appState.current
    const d = this.data
    if (!ch || d.dietChecking) return
    d.dietChecking = true
    this.rerender()
    try {
      await window.cpApi.deleteCheckin(ch.id, checkinId)
      window.cpToast('已撤销这一笔')
      await this.load()
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '撤销失败，请重试'))
    } finally {
      d.dietChecking = false
      this.rerender()
    }
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
    } finally {
      d.dietChecking = false
      this.rerender()
    }
  }
})()
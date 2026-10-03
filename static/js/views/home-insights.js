;(function () {
  const V = window.cpViews.home

  V.openReport = function () {
    const s = window.appState
    if (!s.current) return
    s.reportView = { show: true, tab: 'overview', loading: true, overview: null, hourly: null, context: null, mood: null, trend: null, heatmap: null, completion: null }
    this._loadReportData()
  }

  V.closeReport = function () { window.appState.reportView = null }

  V.switchReportTab = function (tab) {
    const rv = window.appState.reportView
    if (!rv) return
    rv.tab = tab
    const ch = window.appState.current
    if (!ch) return
    const id = ch.id
    const safe = p => p.catch(() => null)
    if (tab === 'hourly' && !rv.hourly) {
      Promise.all([
        safe(window.cpApi.get('/challenges/' + id + '/report/hourly?days=7')),
        safe(window.cpApi.get('/challenges/' + id + '/report/context?days=30')),
        safe(window.cpApi.get('/challenges/' + id + '/report/mood?days=30')),
      ]).then(([d, ctx, md]) => { rv.hourly = d || null; rv.context = ctx || null; rv.mood = md || null; this.rerender() })
    } else if (tab === 'trend' && !rv.trend) {
      safe(window.cpApi.get('/challenges/' + id + '/report/trend?days=30')).then(d => { rv.trend = d || null; this.rerender() })
    } else if (tab === 'heatmap' && !rv.heatmap) {
      safe(window.cpApi.get('/challenges/' + id + '/report/heatmap')).then(d => { rv.heatmap = d || null; this.rerender() })
    } else if (tab === 'completion' && !rv.completion) {
      safe(window.cpApi.get('/challenges/' + id + '/report/completion?period=month')).then(d => { rv.completion = d || null; this.rerender() })
    }
  }

  V._loadReportData = async function () {
    const rv = window.appState.reportView
    const ch = window.appState.current
    if (!rv || !ch) return
    const id = ch.id
    const safe = p => p.catch(() => null)
    const [overview, hourly, context, mood] = await Promise.all([
      safe(window.cpApi.get('/challenges/' + id + '/report/overview')),
      safe(window.cpApi.get('/challenges/' + id + '/report/hourly?days=7')),
      safe(window.cpApi.get('/challenges/' + id + '/report/context?days=30')),
      safe(window.cpApi.get('/challenges/' + id + '/report/mood?days=30')),
    ])
    rv.overview = overview || null
    rv.hourly = hourly || null
    rv.context = context || null
    rv.mood = mood || null
    rv.loading = false
    this.rerender()
  }

  V._reportModal = function () {
    const rv = window.appState.reportView
    if (!rv || !rv.show) return ''
    const ch = window.appState.current
    if (!ch) return ''
    let html = '<div class="cp-report-tabs">'
    html += '<button class="cp-report-tab' + (rv.tab === 'overview' ? ' active' : '') + '" onclick="cpViews.home.switchReportTab(\'overview\')"><i class="fas fa-gauge"></i> 总览</button>'
    html += '<button class="cp-report-tab' + (rv.tab === 'hourly' ? ' active' : '') + '" onclick="cpViews.home.switchReportTab(\'hourly\')"><i class="fas fa-clock"></i> 时段分布</button>'
    html += '<button class="cp-report-tab' + (rv.tab === 'trend' ? ' active' : '') + '" onclick="cpViews.home.switchReportTab(\'trend\')"><i class="fas fa-chart-line"></i> 趋势</button>'
    html += '<button class="cp-report-tab' + (rv.tab === 'heatmap' ? ' active' : '') + '" onclick="cpViews.home.switchReportTab(\'heatmap\')"><i class="fas fa-fire"></i> 热力图</button>'
    html += '<button class="cp-report-tab' + (rv.tab === 'completion' ? ' active' : '') + '" onclick="cpViews.home.switchReportTab(\'completion\')"><i class="fas fa-check-circle"></i> 完成率</button>'
    html += '</div>'
    html += '<div class="cp-report-content">'
    if (rv.loading) {
      html += '<div class="cp-share-loading"><div class="cp-gen-spinner"></div>正在加载报表...</div>'
    } else if (rv.tab === 'overview') {
      html += this._renderOverview(rv.overview, ch)
    } else if (rv.tab === 'hourly') {
      html += this._renderHourly(rv, ch)
    } else if (rv.tab === 'trend') {
      html += this._renderTrend(rv.trend, ch)
    } else if (rv.tab === 'heatmap') {
      html += this._renderHeatmap(rv.heatmap, ch)
    } else if (rv.tab === 'completion') {
      html += this._renderCompletion(rv.completion, ch)
    }
    html += '</div>'
    return html
  }

  V._renderOverview = function (o, ch) {
    if (!o) return '<div class="cp-mini-empty">暂无数据</div>'
    let h = '<div class="cp-overview-grid">'
    h += this._ovCard('今日记录', o.today_total, ch.unit, 'var(--emerald)')
    h += this._ovCard('今日目标', o.today_target, ch.unit, 'var(--amber)')
    h += this._ovCard('动态基线', o.dynamic_baseline, ch.unit, 'var(--primary-light)')
    h += this._ovCard('连续天数', o.streak, '天', 'var(--primary)')
    h += this._ovCard('总记录数', o.total_checkins, '次', 'var(--emerald)')
    h += this._ovCard('活跃天数', o.active_days, '天', 'var(--primary-light)')
    h += this._ovCard('7天均值', o.last_7d_avg, ch.unit, 'var(--amber)')
    h += this._ovCard('30天均值', o.last_30d_avg, ch.unit, 'var(--primary)')
    h += '</div>'
    if (o.peak_hour >= 0) {
      h += '<div class="cp-overview-peak"><i class="fas fa-flag"></i> 高峰时段：' + o.peak_hour + ':00 - ' + (o.peak_hour + 1) + ':00</div>'
    }
    if (o.insight) h += '<div class="cp-overview-insight nx-md"><i class="fas fa-lightbulb"></i> ' + window.cpMd(o.insight) + '</div>'
    if (o.journey) h += this._journeySection(o.journey)
    return h
  }

  V._journeySection = function (j) {
    const cp = window.cpViews.home
    let h = '<div class="cp-journey cp-journey-embedded">'
    if (j.mode === 'reduction') {
      h += '<div class="cp-journey-head"><span class="cp-journey-title"><i class="fas fa-route"></i> 减量旅程</span>' + (Number(j.ladder_total_stages) > 1 ? '<span class="cp-journey-stage">阶梯 ' + j.ladder_stage + '/' + j.ladder_total_stages + ' 档</span>' : '') + '</div>'
      h += '<div class="cp-journey-hero"><b>' + window.cpFmtInt(j.cigarettes_avoided) + '</b><span>' + window.cpEsc(j.unit || '') + '已少抽</span><em>-' + j.reduction_pct + '%</em></div>'
      h += '<div class="cp-journey-sub">省下约 <b>¥' + window.cpFmtInt(j.money_saved) + '</b></div>'
      if (j.money_note) h += '<div class="cp-journey-note">' + window.cpEsc(j.money_note) + '</div>'
    } else {
      h += '<div class="cp-journey-head"><span class="cp-journey-title"><i class="fas fa-route"></i> 戒断旅程</span></div>'
      h += '<div class="cp-journey-hero"><b>' + (j.quit_days || 0) + '</b><span>天戒断旅程</span></div>'
    }
    const reached = (j.milestones || []).filter(m => m.reached)
    if (reached.length) h += '<div class="cp-journey-ms">' + reached.map(m => '<span class="cp-journey-ms-chip">🏅 ' + window.cpEsc(m.label) + '</span>').join('') + '</div>'
    const health = j.health || {}
    const ms = health.milestones || []
    if (ms.length) {
      const done = ms.filter(m => m.reached).length
      h += '<div class="cp-journey-health-open"><div class="cp-journey-health-title"><i class="fas fa-heart-pulse"></i> 身体恢复线 ' + done + '/' + ms.length + '</div>'
      ms.forEach(m => {
        h += '<div class="cp-journey-health-item' + (m.reached ? ' reached' : '') + '"><i class="fas ' + (m.reached ? 'fa-circle-check' : 'fa-circle') + '"></i><div><b>' + window.cpEsc(m.title) + '</b><span>' + window.cpEsc(m.detail) + '</span><em>' + (m.reached ? '已达成' : window.cpEsc(m.reach_date)) + '</em></div></div>'
      })
      h += '<div class="cp-journey-src">' + window.cpEsc(health.source_note || '') + '</div></div>'
    }
    return h + '</div>'
  }

  V._ovCard = function (label, val, unit, color) {
    return '<div class="cp-ov-card"><div class="cp-ov-label">' + label + '</div><div class="cp-ov-val" style="color:' + color + '">' + val + '</div><div class="cp-ov-unit">' + window.cpEsc(unit || '') + '</div></div>'
  }

  V._renderHourly = function (rv, ch) {
    const r = rv && rv.hourly
    if (!r || !r.items || !r.items.length) return '<div class="cp-mini-empty">暂无时段数据，先记录几次打卡看看吧</div>'
    const items = r.items
    const max = Math.max.apply(null, items.map(i => i.total_value || 0)) || 1
    let h = '<div class="cp-rose-chart">'
    items.forEach(it => {
      const v = it.total_value || 0
      const ratio = v / max
      const isPeak = it.hour === r.peak_hour
      const cls = isPeak ? 'peak' : (v > 0 ? 'active' : '')
      h += '<div class="cp-rose-col" title="' + it.hour + ':00 ' + v + '">'
      h += '<div class="cp-rose-bar ' + cls + '" style="height:' + (ratio * 100) + '%">'
      if (v > 0) h += '<span class="cp-rose-val">' + (v < 10 ? v : Math.round(v)) + '</span>'
      h += '</div></div>'
    })
    h += '</div>'
    h += '<div class="cp-rose-axis"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div>'
    h += this._hourlyRhythm(items, r.peak_hour)
    if (r.peak_hour >= 0) {
      const dir = r.direction === 'decrease' ? '高风险时段' : '高效时段'
      h += '<div class="cp-chart-insight"><i class="fas fa-flag"></i> ' + dir + '：' + r.peak_hour + ':00 - ' + (r.peak_hour + 1) + ':00</div>'
    }
    if (r.insight) h += '<div class="cp-chart-insight nx-md"><i class="fas fa-lightbulb"></i> ' + window.cpMd(r.insight) + '</div>'
    h += this._renderContextBlock(rv && rv.context, ch)
    h += this._renderMoodBlock(rv && rv.mood)
    return h
  }

  V._renderMoodBlock = function (md) {
    if (!md) return ''
    if (!md.items || !md.items.length) {
      return '<div class="cp-ctx-empty"><i class="fas fa-face-smile"></i> 记录时顺手选一下心情（😊/😐/😔），积累几条就能看到状态起伏和坚持效果的关系</div>'
    }
    const emoji = { good: '😊', normal: '😐', bad: '😔' }
    const max = Math.max.apply(null, md.items.map(i => i.checkin_count || 0)) || 1
    let h = '<div class="cp-ctx-block"><div class="cp-ctx-title"><i class="fas fa-face-smile" style="color:var(--amber)"></i> 心情分布 · 近' + (md.date_range || '30d').replace('d', '天') + '</div>'
    md.items.forEach(it => {
      const ratio = (it.checkin_count || 0) / max
      h += '<div class="cp-ctx-bar-row"><span class="cp-ctx-bar-label">' + (emoji[it.mood] || '') + ' ' + window.cpEsc(it.label || it.mood) + '</span>'
      h += '<div class="cp-ctx-bar"><div class="cp-ctx-bar-fill" style="width:' + Math.max(4, ratio * 100) + '%"></div></div>'
      h += '<span class="cp-ctx-bar-val">' + it.checkin_count + ' 次 · ' + it.share_pct + '%</span></div>'
    })
    if (md.insight) h += '<div class="cp-chart-insight nx-md"><i class="fas fa-lightbulb"></i> ' + window.cpMd(md.insight) + '</div>'
    return h + '</div>'
  }

  V._renderContextBlock = function (ctx, ch) {
    if (!ctx) return ''
    if (!ctx.items || !ctx.items.length) {
      return '<div class="cp-ctx-empty"><i class="fas fa-location-dot"></i> 记一笔时选一下情境（或记录后在时间线补选），坚持一两周就能看到你在什么场景、什么时间最容易破戒</div>'
    }
    const max = Math.max.apply(null, ctx.items.map(i => i.total_value || 0)) || 1
    let h = '<div class="cp-ctx-block"><div class="cp-ctx-title"><i class="fas fa-location-dot" style="color:var(--primary-light)"></i> 情境分布 · 近' + (ctx.date_range || '30d').replace('d', '天') + '</div>'
    ctx.items.forEach(it => {
      const ratio = (it.total_value || 0) / max
      h += '<div class="cp-ctx-bar-row"><span class="cp-ctx-bar-label">' + window.cpEsc(it.label || it.context_tag) + '</span>'
      h += '<div class="cp-ctx-bar"><div class="cp-ctx-bar-fill" style="width:' + Math.max(4, ratio * 100) + '%"></div></div>'
      h += '<span class="cp-ctx-bar-val">' + it.total_value + ' ' + window.cpEsc(ctx.unit || '') + ' · ' + it.share_pct + '%</span></div>'
    })
    if (ctx.insight) h += '<div class="cp-chart-insight nx-md"><i class="fas fa-lightbulb"></i> ' + window.cpMd(ctx.insight) + '</div>'
    return h + '</div>'
  }

  V._hourlyRhythm = function (items, peak) {
    const vals = items.map(i => i.total_value || 0)
    const sum = vals.reduce((a, b) => a + b, 0)
    if (sum <= 0) return ''
    const avg = sum / vals.length
    const high = [], low = []
    let run = [], runIsHigh = null
    for (let h = 0; h < 24; h++) {
      const isHigh = vals[h] > avg * 0.5
      if (runIsHigh === null) { runIsHigh = isHigh; run = [h] }
      else if (runIsHigh === isHigh) run.push(h)
      else { (runIsHigh ? high : low).push(run.slice()); run = [h]; runIsHigh = isHigh }
    }
    ;(runIsHigh ? high : low).push(run)
    const fmt = r => r.length <= 1 ? r[0] + ':00' : r[0] + ':00–' + (r[r.length - 1] + 1) + ':00'
    const hRuns = high.filter(r => r.some(h => vals[h] > avg)).sort((a, b) => b.length - a.length).slice(0, 2)
    const lRuns = low.filter(r => r.length >= 3).sort((a, b) => b.length - a.length)
    const peakHour = peak >= 0 ? peak : null
    const lFilt = peakHour != null ? lRuns.filter(r => !r.some(h => h === peakHour)) : lRuns
    const lowBand = (lFilt.length ? lFilt : lRuns)[0]
    let txt = ''
    if (hRuns.length) txt += '作息节奏：活跃集中在 ' + hRuns.map(fmt).join('、')
    if (lowBand) txt += (txt ? '；' : '作息节奏：') + fmt(lowBand) + ' 是相对低谷，避开这时安排高难度任务更易坚持'
    if (!txt) return ''
    return '<div class="cp-rhythm"><i class="fas fa-chart-pie"></i> ' + txt + '</div>'
  }

  V._renderTrend = function (r, ch) {
    if (!r || !r.points || !r.points.length) return '<div class="cp-mini-empty">暂无趋势数据</div>'
    const pts = r.points
    const vals = pts.map(p => p.value || 0)
    const max = Math.max.apply(null, vals) || 1
    const min = Math.min.apply(null, vals) || 0
    const range = max - min || 1
    const w = 320, h = 160, pad = 20
    const stepX = (w - pad * 2) / Math.max(pts.length - 1, 1)
    let pathD = '', areaD = ''
    pts.forEach((p, i) => {
      const x = pad + i * stepX
      const y = h - pad - ((p.value - min) / range) * (h - pad * 2)
      if (i === 0) { pathD += 'M' + x.toFixed(1) + ',' + y.toFixed(1); areaD += 'M' + x.toFixed(1) + ',' + y.toFixed(1) }
      else { pathD += ' L' + x.toFixed(1) + ',' + y.toFixed(1); areaD += ' L' + x.toFixed(1) + ',' + y.toFixed(1) }
    })
    areaD += ' L' + (pad + (pts.length - 1) * stepX).toFixed(1) + ',' + (h - pad) + ' L' + pad + ',' + (h - pad) + ' Z'
    const todayIdx = pts.findIndex(p => p.date === window.cpTodayStr())
    const todayX = todayIdx >= 0 ? (pad + todayIdx * stepX).toFixed(1) : 0
    let hhtml = '<div class="cp-svg-trend">'
    hhtml += '<svg width="100%" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '" style="max-width:100%">'
    hhtml += '<defs><linearGradient id="trend-grad" x1="0" y1="0" x2="0" y2="1">'
    hhtml += '<stop offset="0%" stop-color="rgba(129,140,248,.35)"/>'
    hhtml += '<stop offset="100%" stop-color="rgba(129,140,248,0)"/>'
    hhtml += '</linearGradient></defs>'
    hhtml += '<path d="' + areaD + '" fill="url(#trend-grad)" opacity="0.8"/>'
    hhtml += '<path d="' + pathD + '" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    if (todayIdx >= 0) {
      hhtml += '<circle cx="' + todayX + '" cy="' + (h - pad - ((pts[todayIdx].value - min) / range) * (h - pad * 2)).toFixed(1) + '" r="4" fill="var(--emerald)" stroke="rgba(15,23,42,.6)" stroke-width="2"/>'
    }
    hhtml += '<line x1="' + pad + '" y1="' + (h - pad) + '" x2="' + (w - pad) + '" y2="' + (h - pad) + '" stroke="rgba(148,163,184,.15)" stroke-width="1"/>'
    hhtml += '</svg>'
    hhtml += '</div>'
    hhtml += '<div class="cp-trend-legend">'
    hhtml += '<span><i class="fas fa-circle" style="color:var(--emerald)"></i> 今日</span>'
    hhtml += '<span>均值 ' + (r.avg_value || 0).toFixed(1) + ' ' + window.cpEsc(ch.unit) + '</span>'
    const tdMap = { improving: '进步中 ↑', worsening: '需关注 ↓', stable: '稳定 →' }
    hhtml += '<span>趋势 ' + (tdMap[r.trend_direction] || '稳定 →') + '</span></div>'
    if (r.insight) hhtml += '<div class="cp-chart-insight nx-md"><i class="fas fa-lightbulb"></i> ' + window.cpMd(r.insight) + '</div>'
    return hhtml
  }

  V._renderHeatmap = function (r, ch) {
    if (!r || !r.cells || !r.cells.length) return '<div class="cp-mini-empty">暂无热力图数据</div>'
    setTimeout(() => { V._mountHeatmap(r) }, 50)
    let h = '<div id="cp-nux-heat"></div>'
    h += '<div class="cp-heatmap-stats"><span>活跃 ' + r.active_days + '天</span><span>达标 ' + r.on_track_days + '天</span><span>共 ' + r.total_days + '天</span></div>'
    return h
  }

  V._mountHeatmap = function (r) {
    const el = document.getElementById('cp-nux-heat')
    if (!el || !window.NuxCalendar) return
    if (window.cpNuxHeatApp) { try { window.cpNuxHeatApp.unmount() } catch (e) {} }
    window.cpNuxHeatApp = Vue.createApp({
      components: { NuxCalendar: window.NuxCalendar },
      data() { return { cells: r.cells || [] } },
      template: '<nux-calendar mode="heatmap" :cells="cells"></nux-calendar>'
    })
    try { window.cpNuxHeatApp.mount(el) } catch (e) {}
  }

  V._renderCompletion = function (r, ch) {
    if (!r) return '<div class="cp-mini-empty">暂无数据</div>'
    const rate = r.completion_rate || 0
    const circumference = 2 * Math.PI * 36
    const offset = circumference * (1 - rate / 100)
    let h = '<div class="cp-completion">'
    h += '<div class="cp-completion-ring">'
    h += '<svg width="100" height="100" viewBox="0 0 100 100">'
    h += '<circle cx="50" cy="50" r="36" fill="none" stroke="rgba(148,163,184,.1)" stroke-width="8"/>'
    h += '<circle cx="50" cy="50" r="36" fill="none" stroke="var(--emerald)" stroke-width="8" stroke-linecap="round" stroke-dasharray="' + circumference + '" stroke-dashoffset="' + offset + '" transform="rotate(-90 50 50)"/>'
    h += '</svg>'
    h += '<div class="cp-completion-pct"><b>' + rate.toFixed(0) + '</b>%</div>'
    h += '</div>'
    h += '<div class="cp-completion-stats">'
    h += '<div class="cp-cs-item"><div class="cp-cs-val" style="color:var(--emerald)">' + r.on_track_days + '</div><div class="cp-cs-label">达标</div></div>'
    h += '<div class="cp-cs-item"><div class="cp-cs-val" style="color:var(--amber)">' + r.soft_exceed_days + '</div><div class="cp-cs-label">软超出</div></div>'
    h += '<div class="cp-cs-item"><div class="cp-cs-val" style="color:var(--red)">' + r.hard_exceed_days + '</div><div class="cp-cs-label">硬超出</div></div>'
    h += '<div class="cp-cs-item"><div class="cp-cs-val">' + r.total_days + '</div><div class="cp-cs-label">总天数</div></div>'
    h += '</div></div>'
    if (r.insight) h += '<div class="cp-chart-insight nx-md"><i class="fas fa-lightbulb"></i> ' + window.cpMd(r.insight) + '</div>'
    return h
  }

  V.openShareConfig = function () {
    const ch = window.appState.current
    if (!ch || !ch.share_token) return
    const url = window.location.origin + window.cpPrefix + '/?shared=' + ch.share_token
    const text = '我在星轨挑战参加「' + ch.title + '」挑战！\n' + (ch.completed_days || 0) + '/' + ch.total_days + '天已完成，来一起打卡吧！\n' + url
    window.cpCopy(text)
  }
})()
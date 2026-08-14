;(function () {
  const V = window.cpViews.home

  V.openReport = function () {
    const s = window.appState
    if (!s.current) return
    s.reportView = { show: true, tab: 'overview', loading: true, overview: null, hourly: null, trend: null, heatmap: null, completion: null }
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
      safe(window.api.get('/challenges/' + id + '/report/hourly?days=7')).then(r => { rv.hourly = (r && (r.data || r)) || null; this.rerender() })
    } else if (tab === 'trend' && !rv.trend) {
      safe(window.api.get('/challenges/' + id + '/report/trend?days=30')).then(r => { rv.trend = (r && (r.data || r)) || null; this.rerender() })
    } else if (tab === 'heatmap' && !rv.heatmap) {
      safe(window.api.get('/challenges/' + id + '/report/heatmap')).then(r => { rv.heatmap = (r && (r.data || r)) || null; this.rerender() })
    } else if (tab === 'completion' && !rv.completion) {
      safe(window.api.get('/challenges/' + id + '/report/completion?period=month')).then(r => { rv.completion = (r && (r.data || r)) || null; this.rerender() })
    }
  }

  V._loadReportData = async function () {
    const rv = window.appState.reportView
    const ch = window.appState.current
    if (!rv || !ch) return
    const id = ch.id
    const safe = p => p.catch(() => null)
    const [overview, hourly] = await Promise.all([
      safe(window.api.get('/challenges/' + id + '/report/overview')),
      safe(window.api.get('/challenges/' + id + '/report/hourly?days=7')),
    ])
    rv.overview = (overview && (overview.data || overview)) || null
    rv.hourly = (hourly && (hourly.data || hourly)) || null
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
      html += this._renderHourly(rv.hourly, ch)
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
    if (o.insight) h += '<div class="cp-overview-insight"><i class="fas fa-lightbulb"></i> ' + window.cpEsc(o.insight) + '</div>'
    return h
  }

  V._ovCard = function (label, val, unit, color) {
    return '<div class="cp-ov-card"><div class="cp-ov-label">' + label + '</div><div class="cp-ov-val" style="color:' + color + '">' + val + '</div><div class="cp-ov-unit">' + window.cpEsc(unit || '') + '</div></div>'
  }

  V._renderHourly = function (r, ch) {
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
    if (r.peak_hour >= 0) {
      const dir = r.direction === 'decrease' ? '高风险时段' : '高效时段'
      h += '<div class="cp-chart-insight"><i class="fas fa-flag"></i> ' + dir + '：' + r.peak_hour + ':00 - ' + (r.peak_hour + 1) + ':00</div>'
    }
    if (r.insight) h += '<div class="cp-chart-insight"><i class="fas fa-lightbulb"></i> ' + window.cpEsc(r.insight) + '</div>'
    return h
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
    if (r.insight) hhtml += '<div class="cp-chart-insight"><i class="fas fa-lightbulb"></i> ' + window.cpEsc(r.insight) + '</div>'
    return hhtml
  }

  V._renderHeatmap = function (r, ch) {
    if (!r || !r.cells || !r.cells.length) return '<div class="cp-mini-empty">暂无热力图数据</div>'
    const cells = r.cells
    const weeks = []
    let curWeek = []
    const first = new Date(cells[0].date + 'T00:00:00')
    const firstDay = first.getDay()
    for (let i = 0; i < firstDay; i++) curWeek.push(null)
    cells.forEach(c => {
      curWeek.push(c)
      if (curWeek.length === 7) { weeks.push(curWeek); curWeek = [] }
    })
    if (curWeek.length) weeks.push(curWeek)
    const monthLabels = []
    let lastMonth = -1
    weeks.forEach((w, i) => {
      for (let j = 0; j < 7; j++) {
        const c = w[j]
        if (c) {
          const m = parseInt(c.date.slice(5, 7), 10)
          if (m !== lastMonth) { monthLabels.push({ idx: i, label: m + '月' }); lastMonth = m }
        }
      }
    })
    let h = '<div class="cp-heatmap">'
    h += '<div class="cp-heatmap-months">'
    monthLabels.forEach(ml => { h += '<span class="cp-heatmap-month" style="left:' + (ml.idx * 14) + 'px">' + ml.label + '</span>' })
    h += '</div>'
    h += '<div class="cp-heatmap-grid">'
    weeks.forEach(w => {
      h += '<div class="cp-heatmap-week">'
      w.forEach(c => {
        if (!c) { h += '<div class="cp-heat-cell empty"></div>'; return }
        h += '<div class="cp-heat-cell level-' + c.level + '" title="' + c.date + ' ' + c.value + ' ' + window.cpEsc(ch.unit) + '"></div>'
      })
      h += '</div>'
    })
    h += '</div></div>'
    h += '<div class="cp-heatmap-stats"><span>活跃 ' + r.active_days + '天</span><span>达标 ' + r.on_track_days + '天</span><span>共 ' + r.total_days + '天</span></div>'
    return h
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
    if (r.insight) h += '<div class="cp-chart-insight"><i class="fas fa-lightbulb"></i> ' + window.cpEsc(r.insight) + '</div>'
    return h
  }
})()
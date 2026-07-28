;(function () {
  const V = window.cpViews.home

  V._reportSection = function (s) {
    const ch = s.current
    const d = this.data
    if (!ch) return ''
    const isDecompose = ch.decompose_mode === 'time_slot' || ch.task_type === 'counter' || ch.task_type === 'timer'
    let html = '<div class="glass-card cp-report-section"><div class="cp-report-head"><div class="cp-section-title"><i class="fas fa-chart-pie" style="color:var(--primary-light)"></i> 数据报表</div>'
    html += '<button class="cp-btn-ghost cp-report-expand" onclick="cpViews.home.openReport()"><i class="fas fa-expand"></i> 完整报表</button></div>'
    html += '<div class="cp-report-quickgrid">'
    html += this._quickStat('今日', (d.today && d.today.today_total) || 0, '/', (d.today && d.today.today_target) || ch.target_value, ch.unit, 'var(--emerald)')
    const baseline = (d.today && d.today.dynamic_baseline) || 0
    html += this._quickStat('软目标', baseline.toFixed(1), '', '', ch.unit, 'var(--amber)')
    const streak = ch.streak || 0
    html += this._quickStat('连续', streak, '', '', '天', 'var(--primary-light)')
    html += this._quickStat('累计', ch.completed_days || 0, '/', ch.total_days || 0, '天', 'var(--primary)')
    html += '</div>'
    if (isDecompose) {
      html += '<div class="cp-report-mini-chart" id="cp-mini-hourly-' + ch.id + '"></div>'
    }
    html += '</div>'
    return html
  }

  V._quickStat = function (label, val, sep, val2, unit, color) {
    let v = '<div class="cp-quick-stat"><div class="cp-quick-stat-label">' + label + '</div>'
    v += '<div class="cp-quick-stat-val" style="color:' + color + '"><b>' + val + '</b>'
    if (sep) v += '<span class="cp-quick-stat-sep">' + sep + '</span><span class="cp-quick-stat-val2">' + val2 + '</span>'
    v += '</div><div class="cp-quick-stat-unit">' + window.cpEsc(unit || '') + '</div></div>'
    return v
  }

  V._renderMiniHourly = function () {
    const ch = window.appState.current
    if (!ch) return
    const box = document.getElementById('cp-mini-hourly-' + ch.id)
    if (!box) return
    window.api.get('/challenges/' + ch.id + '/report/hourly?days=7').then(res => {
      const r = (res && (res.data || res)) || {}
      const items = r.items || []
      if (!items.length) { box.innerHTML = '<div class="cp-mini-empty">暂无时段数据</div>'; return }
      const max = Math.max.apply(null, items.map(i => i.total_value || 0)) || 1
      let html = '<div class="cp-mini-bars">'
      items.forEach(it => {
        const h = it.hour
        const v = it.total_value || 0
        const ratio = v / max
        const isPeak = h === r.peak_hour
        const cls = isPeak ? ' peak' : (v > 0 ? ' active' : '')
        html += '<div class="cp-mini-bar' + cls + '" title="' + h + ':00 ' + v + '"><div class="cp-mini-bar-fill" style="height:' + (ratio * 100) + '%"></div></div>'
      })
      html += '</div>'
      html += '<div class="cp-mini-axis"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div>'
      if (r.insight) html += '<div class="cp-mini-insight"><i class="fas fa-lightbulb"></i> ' + window.cpEsc(r.insight) + '</div>'
      box.innerHTML = html
    }).catch(() => { box.innerHTML = '<div class="cp-mini-empty">加载失败</div>' })
  }

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
    const min = 0
    let h = '<div class="cp-trend-chart">'
    pts.forEach(p => {
      const v = p.value || 0
      const ratio = (v - min) / (max - min || 1)
      const isToday = p.date === window.cpTodayStr()
      const cls = isToday ? 'today' : ''
      h += '<div class="cp-trend-col ' + cls + '" title="' + p.date + ' ' + v + '">'
      h += '<div class="cp-trend-bar" style="height:' + (ratio * 100) + '%"></div>'
      h += '</div>'
    })
    h += '</div>'
    h += '<div class="cp-trend-legend">'
    h += '<span><i class="fas fa-circle" style="color:var(--emerald)"></i> 今日</span>'
    h += '<span>均值 ' + r.avg_value + ' ' + window.cpEsc(ch.unit) + '</span>'
    const tdMap = { improving: '进步中', worsening: r.direction === 'decrease' ? '需关注' : '需关注', stable: '稳定' }
    h += '<span>趋势 ' + (tdMap[r.trend_direction] || '稳定') + '</span></div>'
    if (r.insight) h += '<div class="cp-chart-insight"><i class="fas fa-lightbulb"></i> ' + window.cpEsc(r.insight) + '</div>'
    return h
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
    h += '<circle cx="50" cy="50" r="36" fill="none" stroke="rgba(0,0,0,0.06)" stroke-width="8"/>'
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

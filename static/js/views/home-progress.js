;(function () {
  const V = window.cpViews.home

  V._tabProgress = function (s) {
    const ch = s.current
    const d = this.data
    const tt = (d.today && d.today.task_type) || ch.task_type || 'binary'
    const isMultiMode = !!(d.today && d.today.repeatable) || ch.decompose_mode === 'time_slot' || ch.task_type === 'counter' || ch.task_type === 'timer' || tt === 'counter' || tt === 'timer'
    let html = '<div class="glass-card cp-hero cp-progress-card">'
    html += '<div class="cp-hero-progress"><div class="cp-hero-progress-bar"><div class="cp-hero-progress-fill" style="width:' + (ch.total_days ? Math.round((ch.completed_days || 0) / ch.total_days * 100) : 0) + '%"></div></div><span class="cp-hero-progress-text">' + (ch.total_days ? Math.round((ch.completed_days || 0) / ch.total_days * 100) : 0) + '% 完成</span></div>'
    html += '<div class="cp-galaxy-wrap"><div id="galaxy-box"></div></div></div>'
    html += '<div class="glass-card cp-progress-stats">' + this._reportContent(s) + '</div>'
    if (isMultiMode) html += '<div class="glass-card cp-today-viz"><div class="cp-section-title"><i class="fas fa-chart-column" style="color:var(--primary-light)"></i> 近 7 天节奏</div><div id="cp-mini-hourly-' + ch.id + '"></div></div>'
    return html
  }

  V._tabInsight = function (s) {
    const d = this.data
    let html = ''
    if (d.adaptive) html += this._adaptiveCard(d.adaptive)
    if (d.mercy && (d.mercy.missed_dates || []).length) html += this._diagEntry(d.mercy.missed_dates.length)
    if (d.weekly && d.weekly.content) {
      html += '<div class="glass-card" style="padding:14px"><div class="cp-section-title" style="margin-bottom:8px"><i class="fas fa-lightbulb" style="color:var(--amber)"></i> 本周洞察</div><div class="cp-weekly-md nx-md" id="' + this._pushMd(d.weekly.content) + '"></div><div class="cp-weekly-meta">本周进度 ' + (d.weekly.week_checkins || 0) + '/' + (d.weekly.week_days || 7) + ' 天</div></div>'
    }
    if (d.guidance) html += this._guidanceCard(d.guidance)
    return html
  }

  V._reportContent = function (s) {
    const ch = s.current
    const d = this.data
    if (!ch) return ''
    let html = '<div class="cp-report-head"><div class="cp-section-title" style="margin-bottom:0"><i class="fas fa-chart-pie" style="color:var(--primary-light)"></i> 数据报表</div>'
    html += '<button class="cp-btn-ghost cp-report-expand" onclick="cpViews.home.openReport()"><i class="fas fa-expand"></i> 完整报表</button></div>'
    html += '<div class="cp-report-quickgrid">'
    html += this._quickStat('今日', (d.today && d.today.today_total) || 0, '/', (d.today && d.today.today_target) || ch.target_value, ch.unit, 'var(--emerald)')
    const baseline = (d.today && d.today.dynamic_baseline) || 0
    html += this._quickStat('软目标', baseline.toFixed(1), '', '', ch.unit, 'var(--amber)')
    html += this._quickStat('连续', ch.streak || 0, '', '', '天', 'var(--primary-light)')
    html += this._quickStat('累计', ch.completed_days || 0, '/', ch.total_days || 0, '天', 'var(--primary)')
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
})()

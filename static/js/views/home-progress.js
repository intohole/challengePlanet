;(function () {
  const V = window.cpViews.home

  V._tabProgress = function (s) {
    const ch = s.current
    const d = this.data
    const pct = window.NexusUseProgress ? window.NexusUseProgress.computeStats({ done: ch.completed_days || 0, total: ch.total_days || 0 }).percent : (ch.total_days ? Math.round((ch.completed_days || 0) / ch.total_days * 100) : 0)
    let html = '<div class="glass-card cp-hero cp-progress-card">'
    html += '<div class="cp-hero-progress"><div class="cp-hero-progress-bar"><div class="cp-hero-progress-fill" style="width:' + pct + '%"></div></div><span class="cp-hero-progress-text">' + pct + '% 完成</span></div>'
    html += '<div class="cp-galaxy-wrap"><div id="galaxy-box"></div></div></div>'
    html += '<div id="cp-nux-checkin"></div>'
    html += '<div class="glass-card cp-progress-stats">' + this._reportContent(s) + '</div>'
    html += this._heatmapCard(s)
    return html
  }

  V._heatmapCard = function (s) {
    const ch = s.current
    const d = this.data
    const list = d.checkins || []
    if (!list.length) return ''
    const days = 7
    const dayArr = []
    const now = new Date()
    for (let i = days - 1; i >= 0; i--) {
      const dt = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
      const mm = String(dt.getMonth() + 1).padStart(2, '0')
      const dd = String(dt.getDate()).padStart(2, '0')
      dayArr.push({ key: mm + '-' + dd, ymd: dt.getFullYear() + '-' + mm + '-' + dd, counts: new Array(24).fill(0) })
    }
    const byDay = {}
    dayArr.forEach(day => { byDay[day.ymd] = day })
    let total = 0
    list.forEach(c => {
      const ts = String(c.timestamp || '')
      const day = byDay[ts.slice(0, 10)]
      const hh = parseInt(ts.slice(11, 13), 10)
      if (day && hh >= 0 && hh < 24) {
        day.counts[hh]++
        total++
      }
    })
    if (!total) return ''
    let peakDay = '', peakHour = -1, peakVal = 1
    dayArr.forEach(day => day.counts.forEach((v, h) => {
      if (v >= peakVal) { peakVal = v; peakHour = h; peakDay = day.ymd }
    }))
    const hourLabel = String(peakHour).padStart(2, '0') + ':00'
    const isDecrease = ch.direction === 'decrease'
    const titleClean = ch.title.replace(/(戒烟|戒掉|戒糖|戒断|戒)\s*/g, '')
    const insight = isDecrease
      ? '你在 ' + hourLabel + ' 前后记录最密，这可能是你最容易想「' + titleClean + '」的时段，提前安排一杯水或散步'
      : '你在 ' + hourLabel + ' 前后最活跃，把重要动作放在这个时段，效率最高'
    let html = '<div class="glass-card cp-heatmap-card"><div class="cp-section-title"><i class="fas fa-fire" style="color:var(--amber)"></i> 近 7 天打卡热度</div>'
    html += '<div class="cp-heatmap">'
    html += '<div class="cp-heatmap-row head"><span class="cp-heat-ym"></span>'
    dayArr.forEach(day => { html += '<span class="cp-heat-d">' + day.key.slice(3) + '</span>' })
    html += '</div>'
    for (let h = 0; h < 24; h++) {
      const yl = h % 3 === 0 ? String(h).padStart(2, '0') : ''
      html += '<div class="cp-heatmap-row"><span class="cp-heat-ym">' + yl + '</span>'
      dayArr.forEach(day => {
        const v = day.counts[h]
        const lv = v === 0 ? 0 : (v >= 4 ? 4 : v >= 3 ? 3 : v >= 2 ? 2 : 1)
        html += '<span class="cp-heat-cell lv' + lv + '" title="' + day.ymd + ' ' + String(h).padStart(2, '0') + ':00 · ' + v + '次"' + (v > 0 ? (' data-v="' + v + '"') : '') + '>' + (v > 0 && h === peakHour && day.ymd === peakDay ? '·' : '') + '</span>'
      })
      html += '</div>'
    }
    html += '</div>'
    html += '<div class="cp-heatmap-legend"><span class="cp-heat-lb">少</span><span class="cp-heat-cell lv1"></span><span class="cp-heat-cell lv2"></span><span class="cp-heat-cell lv3"></span><span class="cp-heat-cell lv4"></span><span class="cp-heat-lb">多</span></div>'
    html += '<div class="cp-heatmap-insight"><i class="fas fa-lightbulb"></i> ' + window.cpEsc(insight) + '</div>'
    return html
  }

  V._tabInsight = function (s) {
    this.ensureInsight()
    const d = this.data
    let html = ''
    if (d.guidance) html += this._phaseSnap(d.guidance)
    html += this._weeklyCard()
    if (d.adaptive) html += this._adaptiveCard(d.adaptive)
    if (d.mercy && (d.mercy.missed_dates || []).length) html += this._diagEntry(d.mercy.missed_dates.length)
    return html
  }

  V._weeklyCard = function () {
    const d = this.data
    if (d.insightRunning) {
      return '<div class="glass-card" style="padding:14px"><div class="cp-section-title" style="margin-bottom:8px"><i class="fas fa-lightbulb" style="color:var(--amber)"></i> 本周洞察</div><div class="cp-weekly-stream nx-md"><span class="cp-typing-dots"><i></i><i></i><i></i></span>' + window.cpEsc(d.insightText || '') + '</div><div class="cp-weekly-meta">根据你的打卡记录实时生成中…</div></div>'
    }
    if (d.weekly && d.weekly.content) {
      return '<div class="glass-card" style="padding:14px"><div class="cp-section-title" style="margin-bottom:8px"><i class="fas fa-lightbulb" style="color:var(--amber)"></i> 本周洞察<button class="cp-btn-ghost" style="float:right;padding:3px 8px;font-size:12px;margin-left:8px" onclick="cpViews.home.refreshInsight()"><i class="fas fa-rotate"></i> 重新生成</button></div><div class="cp-weekly-md nx-md" id="' + this._pushMd(d.weekly.content) + '"></div><div class="cp-weekly-meta">洞察基于你的打卡记录生成，可随时重新生成</div></div>'
    }
    return '<div class="glass-card" style="padding:14px"><div class="cp-section-title" style="margin-bottom:8px"><i class="fas fa-lightbulb" style="color:var(--amber)"></i> 本周洞察</div><div class="cp-weekly-stream nx-md"><span class="cp-typing-dots"><i></i><i></i><i></i></span>正在分析你的打卡记录…</div></div>'
  }

  V.ensureInsight = function () {
    const d = this.data
    const ch = window.appState.current
    if (!ch || d.insightRunning || d.weekly) return
    this._streamInsight(false)
  }

  V.refreshInsight = function () {
    const ch = window.appState.current
    if (!ch || this.data.insightRunning) return
    this._streamInsight(true)
  }

  V._streamInsight = async function (force) {
    const ch = window.appState.current
    const d = this.data
    if (!ch || d.insightRunning) return
    d.insightRunning = true
    d.insightText = ''
    d.weekly = null
    this.rerender()
    const handleError = msg => {
      d.insightRunning = false
      d.insightText = ''
      this.rerender()
      window.cpToast(window.cpErrMsg(msg, '洞察生成失败，请重试'))
    }
    try {
      await window.api.streamPost('/challenges/' + ch.id + '/insight/stream', { force: !!force }, {
        onEvent: (ev, data) => {
          if (!data) return
          if (data.type === 'token') {
            d.insightText = (d.insightText || '') + (data.token || '')
            this.rerender()
          } else if (data.type === 'done') {
            d.weekly = { content: String(data.content || d.insightText || '').trim() }
            d.insightRunning = false
            d.insightText = ''
            this.rerender()
          }
        },
        onError: msg => handleError(msg),
        timeout: 60000,
      })
    } catch (e) {
      handleError(e)
    }
  }

  V._phaseSnap = function (g) {
    const m = g.next_milestone
    const done = g.completed_days || 0
    let html = '<div class="glass-card cp-phase-snap">'
    html += '<div class="cp-phase-snap-head"><span class="cp-phase-badge-n" style="color:' + (g.phase_color || '#8B5CF6') + '">' + (g.phase_icon || '🌱') + ' ' + window.cpEsc(g.phase_name || '') + (g.phase_range ? '<em>· ' + window.cpEsc(g.phase_range) + '</em>' : '') + '</span><b>' + (done ? '已打卡 ' + done + ' 天' : '还没开始打卡') + '</b></div>'
    if (m && done === 0) {
      html += '<div class="cp-phase-snap-milestone"><span>🎯 完成第 1 次打卡，点亮第一个里程碑</span><div class="cp-phase-snap-bar"><div class="cp-phase-snap-fill" style="width:0%"></div></div></div>'
    } else if (m && m.days_to_go > 0) {
      html += '<div class="cp-phase-snap-milestone"><span>🎯 距 ' + m.day + ' 天里程碑还差 ' + m.days_to_go + ' 天</span><div class="cp-phase-snap-bar"><div class="cp-phase-snap-fill" style="width:' + Math.min(100, Math.round((done / m.day) * 100)) + '%"></div></div></div>'
    }
    const tip = (m && m.tip) || g.phase_tip || ''
    if (tip) html += '<p class="cp-phase-snap-tip">' + window.cpEsc(tip) + '</p>'
    const c = g.companion
    if (c && (c.level === 'high' || c.level === 'medium')) {
      const msg = c.message || c.micro_action || '今天重新打卡，节奏就能恢复'
      html += '<div class="cp-phase-snap-risk' + (c.level === 'high' ? ' hot' : '') + '"><i class="fas ' + (c.level === 'high' ? 'fa-heart-crack' : 'fa-hand-holding-heart') + '"></i><span>' + window.cpEsc(msg) + '</span></div>'
    }
    html += '</div>'
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
    html += this._quickStat('动态基线', baseline.toFixed(1), '', '', ch.unit, 'var(--amber)')
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
})()

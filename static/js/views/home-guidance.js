;(function () {
  const V = window.cpViews.home

  V._guidanceCard = function (g) {
    if (!g) return ''
    let h = '<div class="glass-card cp-guidance-card">'
    h += '<div class="cp-guidance-head">'
    h += '<div class="cp-phase-badge" style="background:' + (g.phase_color || '#D97706') + '20;color:' + (g.phase_color || '#D97706') + ';border-color:' + (g.phase_color || '#D97706') + '40">'
    h += '<span class="cp-phase-icon">' + (g.phase_icon || '🌱') + '</span>'
    h += '<div class="cp-phase-info"><div class="cp-phase-name">' + window.cpEsc(g.phase_name || '适应期') + '</div><div class="cp-phase-range">' + window.cpEsc(g.phase_range || '第1-7天') + '</div></div>'
    h += '</div>'
    if (g.percentile > 0) {
      h += '<div class="cp-percentile"><span class="cp-percentile-num">' + g.percentile + '%</span><span class="cp-percentile-label">超越用户</span></div>'
    }
    h += '</div>'
    if (g.encouragement) {
      h += '<p class="cp-guidance-encourage">' + window.cpEsc(g.encouragement) + '</p>'
    }
    if (g.phase_desc) {
      h += '<p class="cp-guidance-desc">' + window.cpEsc(g.phase_desc) + '</p>'
    }
    if (g.phase_tip) {
      h += '<div class="cp-guidance-tip"><i class="fas fa-lightbulb"></i><span>' + window.cpEsc(g.phase_tip) + '</span></div>'
    }
    const b = g.benchmark
    if (b) {
      h += '<div class="cp-benchmark">'
      h += '<div class="cp-benchmark-title"><i class="fas fa-chart-line"></i> 行业参考数据</div>'
      h += '<div class="cp-benchmark-grid">'
      h += '<div class="cp-benchmark-item"><div class="cp-benchmark-val">' + (b.avg_streak || 0) + '</div><div class="cp-benchmark-label">平均连续天数</div></div>'
      h += '<div class="cp-benchmark-item"><div class="cp-benchmark-val">' + (b.avg_completion_rate || 0) + '%</div><div class="cp-benchmark-label">平均完成率</div></div>'
      h += '<div class="cp-benchmark-item"><div class="cp-benchmark-val">第' + (b.drop_off_day || 0) + '天</div><div class="cp-benchmark-label">放弃高峰</div></div>'
      h += '</div>'
      if (b.scene_tip) h += '<p class="cp-benchmark-tip">' + window.cpEsc(b.scene_tip) + '</p>'
      h += '</div>'
    }
    const m = g.next_milestone
    if (m && m.days_to_go > 0) {
      h += '<div class="cp-milestone">'
      h += '<div class="cp-milestone-bar"><div class="cp-milestone-fill" style="width:' + Math.min(100, (g.completed_days / m.day) * 100) + '%"></div></div>'
      h += '<div class="cp-milestone-info"><span class="cp-milestone-target">🎯 第' + m.day + '天里程碑</span><span class="cp-milestone-remain">还差 ' + m.days_to_go + ' 天</span></div>'
      h += '<p class="cp-milestone-tip">' + window.cpEsc(m.tip) + '</p>'
      h += '</div>'
    }
    if (g.is_at_risk) {
      h += '<div class="cp-risk-warn"><i class="fas fa-triangle-exclamation"></i><span>连续中断了！今天重新打卡即可恢复节奏，中断不可怕，重启才重要。</span></div>'
    }
    h += this._companionBubble(g.companion)
    h += '</div>'
    return h
  }

  V._companionBubble = function (c) {
    if (!c || c.level === 'low') return ''
    const hour = new Date().getHours()
    const greet = hour < 5 ? '夜深了' : (hour < 12 ? '上午好' : (hour < 18 ? '下午好' : '晚上好'))
    const levelTxt = { high: '今天有点危险', medium: '今天需要留意' }[c.level] || '今天的提醒'
    const icon = c.level === 'high' ? 'fa-heart-crack' : 'fa-hand-holding-heart'
    let h = '<div class="cp-companion ' + (c.level === 'high' ? 'cp-companion-hot' : '') + '">'
    h += '<div class="cp-companion-head"><div class="cp-companion-avatar"><i class="fas ' + icon + '"></i></div>'
    h += '<div class="cp-companion-meta"><div class="cp-companion-name">' + greet + '，我是你的习惯伙伴</div><div class="cp-companion-tag">' + levelTxt + '</div></div>'
    h += '</div>'
    if ((c.reasons || []).length) {
      h += '<div class="cp-companion-reasons">' + (c.reasons.map(function (r) { return '<span>' + window.cpEsc(r) + '</span>' }).join('')) + '</div>'
    }
    if (c.message) h += '<p class="cp-companion-msg">' + window.cpEsc(c.message) + '</p>'
    if (c.micro_action) {
      h += '<div class="cp-companion-action"><i class="fas fa-bolt"></i><span>' + window.cpEsc(c.micro_action) + '</span></div>'
    }
    h += '</div>'
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

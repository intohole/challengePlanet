window.cpViews = window.cpViews || {}
window.cpViews.me = (function () {
  const V = {
    el: null,
    data: { points: null },

    render(el) {
      this.el = el
      const s = window.appState
      const d = this.data
      const totalCheckins = s.challenges.reduce((sum, c) => sum + (c.completed_days || 0), 0)
      const bestStreak = s.challenges.reduce((m, c) => Math.max(m, c.streak || 0), 0)
      let html = '<div class="cp-greet"><div><h1>我的</h1><p>管理挑战与账号</p></div></div><div class="cp-view">'
      html += '<div class="glass-card cp-me-card"><div class="cp-me-avatar">' + window.cpEsc((s.nickname || '挑').slice(0, 1)) + '</div><div><div class="cp-me-name">' + window.cpEsc(s.nickname) + '</div><div class="cp-me-pts">总积分 <b>' + ((d.points && d.points.total) || 0) + '</b> · 本周 <b>' + ((d.points && d.points.week_points) || 0) + '</b></div></div></div>'
      html += '<div class="glass-card" style="padding:16px"><div class="cp-section-title"><i class="fas fa-flag-checkered" style="color:var(--primary-light)"></i> 我的挑战</div>'
      if (!s.booted) {
        html += '<div class="cp-skel-line w80"></div><div class="cp-skel-line w60"></div>'
      } else if (!s.challenges.length) {
        html += '<p style="font-size:13px;color:var(--text-muted);margin-bottom:12px">还没有挑战，从现在开始吧</p>'
      } else {
        s.challenges.forEach(c => {
          const pct = c.total_days ? Math.min(100, Math.round((c.completed_days || 0) / c.total_days * 100)) : 0
          const cur = s.current && s.current.id === c.id
          const done = c.status === 'completed'
          html += '<button class="cp-ch-row' + (cur ? ' current' : '') + '" style="margin-bottom:8px" onclick="cpSelectChallenge(\'' + c.id + '\')"><span class="cp-ch-row-icon">' + (c.icon || window.cpTemplates[0].icon) + '</span><span class="cp-ch-row-info"><span class="cp-ch-row-title">' + window.cpEsc(c.title) + '<span class="cp-ch-status' + (done ? ' done' : '') + '">' + (done ? '已完成' : (c.status === 'active' ? '进行中' : c.status || '')) + '</span></span><span class="cp-progress-bar"><span class="cp-progress-fill" style="width:' + pct + '%"></span></span><span class="cp-ch-row-meta">' + (c.completed_days || 0) + '/' + c.total_days + ' 天 · 连续 ' + (c.streak || 0) + ' 天</span></span>' + (cur ? '<i class="fas fa-circle-check" style="color:var(--primary-light)"></i>' : '') + '</button>'
        })
      }
      html += '<button class="cp-btn-ghost" style="width:100%" onclick="cpCreate.open()"><i class="fas fa-plus"></i> 新建挑战</button></div>'
      html += '<div class="glass-card cp-me-stats"><div class="cp-stat"><div class="cp-stat-num" style="color:var(--primary-light)">' + totalCheckins + '</div><div class="cp-stat-label">总打卡次数</div></div><div class="cp-stat"><div class="cp-stat-num" style="color:var(--emerald)">' + bestStreak + '</div><div class="cp-stat-label">最长连续</div></div><div class="cp-stat"><div class="cp-stat-num" style="color:var(--amber)">' + s.challenges.length + '</div><div class="cp-stat-label">挑战总数</div></div></div>'
      html += '<button class="cp-btn-ghost danger" onclick="cpViews.me.logout()"><i class="fas fa-right-from-bracket"></i> 退出登录</button>'
      html += '</div>'
      el.innerHTML = html
    },

    onShow() {
      window.cpLoadChallenges().then(() => this.rerender()).catch(() => {})
      window.api.get('/points/summary').then(r => { this.data.points = r.data || r; this.rerender() }).catch(() => { this.data.points = null })
    },

    rerender() { if (this.el) this.render(this.el) },

    logout() {
      if (!window.confirm('确定退出登录吗？')) return
      ;['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(k => localStorage.removeItem(k))
      window.location.href = window.cpPrefix + '/login'
    },
  }
  return V
})()

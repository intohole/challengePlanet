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
      html += '<div class="glass-card cp-pad16"><div class="cp-section-title"><i class="fas fa-flag-checkered cp-ic-primary"></i> 我的挑战</div>'
      if (!s.booted) {
        html += '<div class="cp-skel-line w80"></div><div class="cp-skel-line w60"></div>'
      } else if (!s.challenges.length) {
        html += '<p class="cp-empty-tip">还没有挑战，从现在开始吧</p>'
      } else {
        s.challenges.forEach(c => {
          const pct = c.total_days ? Math.min(100, Math.round((c.completed_days || 0) / c.total_days * 100)) : 0
          const cur = s.current && s.current.id === c.id
          const done = c.status === 'completed'
          const statusLabel = done ? '已完成' : (c.status === 'active' ? '进行中' : '已结束')
          html += '<button class="cp-ch-row' + (cur ? ' current' : '') + '" onclick="cpSelectChallenge(\'' + c.id + '\')"><span class="cp-ch-row-icon">' + (c.icon || window.cpTemplates[0].icon) + '</span><span class="cp-ch-row-info"><span class="cp-ch-row-title">' + window.cpEsc(c.title) + '<span class="cp-ch-status' + (done ? ' done' : '') + '">' + statusLabel + '</span></span><span class="cp-progress-bar"><span class="cp-progress-fill" style="width:' + pct + '%"></span></span><span class="cp-ch-row-meta">' + (c.completed_days || 0) + '/' + c.total_days + ' 天 · 连续 ' + (c.streak || 0) + ' 天</span></span>' + (cur ? '<span class="cp-ic-primary"><i class="fas fa-circle-check"></i></span>' : '') + '<span class="cp-ch-row-end" title="' + ((c.completed_days || 0) > 0 ? '放弃挑战' : '删除挑战') + '" onclick="event.stopPropagation();cpViews.me.endChallenge(' + c.id + ')"><i class="fas fa-' + ((c.completed_days || 0) > 0 ? 'flag' : 'trash') + '"></i></span></button>'
        })
      }
      html += '<button class="cp-btn-ghost cp-block" onclick="cpCreate.open()"><i class="fas fa-plus"></i> 新建挑战</button></div>'
      html += '<div class="glass-card cp-me-stats"><div class="cp-stat"><div class="cp-stat-num cp-ic-primary">' + totalCheckins + '</div><div class="cp-stat-label">总打卡次数</div></div><div class="cp-stat"><div class="cp-stat-num cp-ic-emerald">' + bestStreak + '</div><div class="cp-stat-label">最长连续</div></div><div class="cp-stat"><div class="cp-stat-num cp-ic-amber">' + s.challenges.length + '</div><div class="cp-stat-label">挑战总数</div></div></div>'
      html += '<button class="cp-btn-ghost danger" onclick="cpViews.me.logout()"><i class="fas fa-right-from-bracket"></i> 退出登录</button>'
      html += '</div>'
      el.innerHTML = html
    },

    onShow() {
      window.cpLoadChallenges().then(() => this.rerender()).catch(() => {})
      window.api.get('/points/summary').then(r => { this.data.points = r.data || r; this.rerender() }).catch(() => { this.data.points = null })
    },

    rerender() { if (this.el) this.render(this.el) },

    endChallenge(id) {
      const s = window.appState
      const c = s.challenges.find(x => x.id === id)
      if (!c || c.status !== 'active') return
      const hasRecord = (c.completed_days || 0) > 0
      const msg = hasRecord
        ? '放弃该挑战？已有 ' + (c.completed_days || 0) + ' 天打卡战绩会保留，挑战将不再出现在首页。'
        : '删除该挑战？还没有打卡记录，删除后不可恢复。'
      if (!window.confirm(msg)) return
      window.api.delete('/challenges/' + id)
        .then(() => {
          window.cpToast(hasRecord ? '已放弃挑战，战绩保留' : '已删除挑战')
          return window.cpLoadChallenges()
        })
        .then(() => this.rerender())
        .catch(e => window.cpToast(window.cpErrMsg(e, '操作失败')))
    },

    logout() {
      if (!window.confirm('确定退出登录吗？')) return
      ;['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(k => localStorage.removeItem(k))
      window.location.href = window.cpPrefix + '/login'
    },
  }
  return V
})()
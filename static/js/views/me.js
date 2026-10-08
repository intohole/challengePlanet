window.cpViews = window.cpViews || {}
  window.cpViews.me = (function () {
    const V = {
      el: null,
      data: { points: null, prefs: null, saving: false },

      titleClean(t) {
        return window.cpTitleClean(t)
      },

    render(el) {
      this.el = el
      const s = window.appState
      const d = this.data
      const sum = d.summary
      const archives = d.archives || []
      const totalCheckins = sum ? sum.checkin_days : s.challenges.reduce((sum2, c) => sum2 + (c.completed_days || 0), 0)
      const bestStreak = sum ? sum.best_streak : s.challenges.reduce((m, c) => Math.max(m, c.streak || 0), 0)
      let html = '<div class="cp-greet"><div><h1>我的</h1><p>管理挑战与账号</p></div></div><div class="cp-view">'
      html += '<div class="glass-card cp-me-card"><div class="cp-me-avatar">' + window.cpEsc((s.nickname || '挑').slice(0, 1)) + '</div><div><div class="cp-me-name">' + window.cpEsc(s.nickname) + '</div><div class="cp-me-pts">总积分 <b>' + ((d.points && d.points.total) || 0) + '</b> · 本周 <b>' + ((d.points && d.points.week_points) || 0) + '</b></div></div></div>'
      html += '<div class="glass-card cp-pad16"><div class="cp-section-title"><i class="fas fa-flag-checkered cp-ic-primary"></i> 我的挑战' + (s.booted && s.challenges.length ? ' <span class="cp-ch-count">' + s.challenges.length + '</span>' : '') + '</div>'
      if (!s.booted) {
        html += '<div class="cp-skel-line w80"></div><div class="cp-skel-line w60"></div>'
      } else if (!s.challenges.length) {
        html += '<p class="cp-empty-tip">还没有挑战，从现在开始吧</p>'
      } else {
        s.challenges.forEach(c => {
          const pct = c.total_days ? Math.min(100, Math.round((c.completed_days || 0) / c.total_days * 100)) : 0
          const cur = s.current && s.current.id === c.id
          const done = c.status === 'completed' || c.status === 'graduated'
          const statusLabel = c.status === 'graduated' ? '🎓 已毕业' : (done ? '已完成' : (c.status === 'active' ? '进行中' : '已结束'))
          const stTxt = (c.streak || 0) > 0 ? '连续 ' + c.streak + ' 天' : ((c.completed_days || 0) > 0 ? '上次连续 ' + (c.last_streak || 0) + ' 天' : '连续 0 天')
          html += '<button class="cp-ch-row' + (cur ? ' current' : '') + '" onclick="cpSelectChallenge(\'' + c.id + '\')"><span class="cp-ch-row-icon">' + (c.icon || window.cpTemplates[0].icon) + '</span><span class="cp-ch-row-info"><span class="cp-ch-row-title">' + window.cpEsc(this.titleClean(c.title)) + '<span class="cp-ch-status' + (done ? ' done' : '') + '">' + statusLabel + '</span></span><span class="cp-progress-bar"><span class="cp-progress-fill" style="width:' + pct + '%"></span></span><span class="cp-ch-row-meta">' + (c.completed_days || 0) + '/' + c.total_days + ' 天 · ' + stTxt + '</span></span>' + (cur ? '<span class="cp-ic-primary"><i class="fas fa-circle-check"></i></span>' : '') + '<span class="cp-ch-row-end" title="删除挑战" onclick="event.stopPropagation();cpViews.me.endChallenge(' + c.id + ')"><i class="fas fa-trash"></i></span></button>'
        })
      }
      html += '<button class="cp-btn-ghost cp-block" onclick="cpCreate.open()"><i class="fas fa-plus"></i> 新建挑战</button></div>'
      html += '<div class="glass-card cp-me-stats"><div class="cp-stat"><div class="cp-stat-num cp-ic-primary">' + totalCheckins + '</div><div class="cp-stat-label">总打卡天数</div></div><div class="cp-stat"><div class="cp-stat-num cp-ic-emerald">' + bestStreak + '</div><div class="cp-stat-label">最长连续</div></div>' + (sum && sum.avoided_total > 0
        ? '<div class="cp-stat"><div class="cp-stat-num cp-ic-amber">' + sum.avoided_total + '</div><div class="cp-stat-label">累计少抽</div></div>'
        : '<div class="cp-stat"><div class="cp-stat-num cp-ic-amber">' + s.challenges.length + '</div><div class="cp-stat-label">挑战总数</div></div>') + '</div>'
      if (archives.length) {
        html += '<div class="glass-card cp-pad16"><div class="cp-section-title"><i class="fas fa-box-archive cp-ic-amber"></i> 走过的旅程</div>'
        archives.forEach(a => {
          const grad = a.graduation_state === 'graduated'
          const avoidTxt = a.avoided_total > 0 ? ' · 少抽 ' + a.avoided_total + ' ' + window.cpEsc(a.unit || '根') : ''
          html += '<div class="cp-archive-row"><span class="cp-archive-icon">' + (a.icon || '🎯') + '</span><span class="cp-archive-info"><span class="cp-archive-title">' + window.cpEsc(this.titleClean(a.title)) + (grad ? ' <i class="fas fa-graduation-cap cp-ic-primary" title="已毕业" aria-label="已毕业"></i>' : '') + '</span><span class="cp-archive-meta">' + window.cpEsc(a.start_date) + ' ~ ' + window.cpEsc(a.end_date) + ' · ' + a.completed_days + ' 天打卡' + avoidTxt + '</span></span></div>'
        })
        html += '</div>'
      }
      html += this._prefsCard()
      html += '<button class="cp-btn-ghost danger" onclick="cpViews.me.logout()"><i class="fas fa-right-from-bracket"></i> 退出登录</button>'
      html += '</div>'
      el.innerHTML = html
    },

    _prefsCard() {
      const p = this.data.prefs
      if (!p) return ''
      const hours = []
      for (let h = 6; h <= 23; h++) hours.push(h)
      let opts = ''
      hours.forEach(h => {
        opts += '<option value="' + h + '"' + (p.remind_hour === h ? ' selected' : '') + '>' + h + ' 点</option>'
      })
      const toggle = '<button class="cp-pref-toggle' + (p.enabled ? ' on' : '') + '" onclick="cpViews.me.toggleRemind()" role="switch" aria-checked="' + p.enabled + '" aria-label="打卡提醒开关"><span class="cp-pref-knob"></span></button>'
      return '<div class="glass-card cp-pad16"><div class="cp-section-title"><i class="fas fa-bell cp-ic-amber"></i> 打卡提醒</div><div class="cp-pref-row">' + toggle + '<div class="cp-pref-desc">' + (p.enabled ? '每天 <select class="cp-pref-hour" onchange="cpViews.me.setRemindHour(this.value)">' + opts + '</select> 提醒未完成的挑战' : '提醒已关闭，断档时也不会收到通知') + '</div></div></div>'
    },

    async toggleRemind() {
      const p = this.data.prefs
      if (!p || this.data.saving) return
      p.enabled = !p.enabled
      this.rerender()
      await this._savePrefs()
    },

    async setRemindHour(v) {
      const p = this.data.prefs
      if (!p) return
      const hour = parseInt(v, 10)
      if (hour === p.remind_hour) return
      p.remind_hour = hour
      await this._savePrefs()
    },

    async _savePrefs() {
      const p = this.data.prefs
      if (!p || this.data.saving) return
      this.data.saving = true
      try {
        const r = await window.cpApi.put('/challenges/reminder/prefs', { remind_hour: p.remind_hour, enabled: p.enabled })
        this.data.prefs = r
        window.cpToast(p.enabled ? '已开启，每天 ' + p.remind_hour + ' 点提醒' : '已关闭提醒')
      } catch (e) { window.cpToast(window.cpErrMsg(e, '保存失败')) }
      finally { this.data.saving = false; this.rerender() }
    },

    onShow() {
      window.cpLoadChallenges().then(() => this.rerender()).catch(() => {})
      window.cpApi.get('/points/summary').then(d => { this.data.points = d; this.rerender() }).catch(() => { this.data.points = null })
      window.cpApi.get('/challenges/reminder/prefs').then(d => { this.data.prefs = d; this.rerender() }).catch(() => { this.data.prefs = null })
      window.cpApi.archiveSummary().then(d => { this.data.summary = d; this.rerender() }).catch(() => { this.data.summary = null })
      window.cpApi.archives().then(d => { this.data.archives = Array.isArray(d) ? d : []; this.rerender() }).catch(() => { this.data.archives = [] })
    },

    rerender() { if (this.el) this.render(this.el) },

    async endChallenge(id) {
      window.cpEndJourney(id)
    },

    async logout() {
      if (!(await window.nuxConfirm('确定退出登录吗？'))) return
      ;['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(k => localStorage.removeItem(k))
      window.location.href = window.cpPrefix + '/login'
    },
  }
  return V
})()
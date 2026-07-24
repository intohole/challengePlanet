window.cpViews = window.cpViews || {}
window.cpViews.home = (function () {
  const moodMap = { good: '😊 状态不错', normal: '😐 一般般', bad: '😔 有点难' }

  const V = {
    el: null,
    loadedFor: null,
    data: { today: null, checkins: [], mercy: null, weekly: null, points: null, loading: false, error: '', checking: false, lastFeedback: '', chest: 0, declaration: '', shields: 0, adaptive: null },
    _ignite: null,

    render(el) {
      this.el = el
      const s = window.appState
      const h = new Date().getHours()
      const greet = h < 6 ? '夜深了' : h < 12 ? '早上好' : h < 14 ? '中午好' : h < 18 ? '下午好' : '晚上好'
      let html = '<div class="cp-brand-banner"><span class="cp-brand-icon">🌍</span><div class="cp-brand-text"><div class="cp-brand-name">挑战星球</div><div class="cp-brand-slogan">AI 打卡教练 · 陪你每一天</div></div>'
      if (s.booted && s.challenges.length) {
        html += s.pendingCount > 0
          ? '<span class="cp-pending-badge"><i class="fas fa-bolt"></i>待打卡 ' + s.pendingCount + '</span>'
          : '<span class="cp-pending-badge zero"><i class="fas fa-check"></i>已全完成</span>'
      }
      html += '</div>'
      html += '<div class="cp-greet"><div><h1>' + greet + '，' + window.cpEsc(s.nickname) + '</h1><p>' + window.cpTodayStr() + '</p></div></div>'
      html += '<div class="cp-view">'
      if (!s.booted) {
        html += this._skeleton()
      } else if (!s.challenges.length) {
        html += this._empty()
      } else if (s.current) {
        html += this._main(s)
      }
      html += '</div>'
      el.innerHTML = html
      const gx = el.querySelector('#galaxy-box')
      if (gx && s.current) {
        const cat = window.cpCat(s.current.category)
        window.renderGalaxy(gx, { total: s.current.total_days, completed: s.current.completed_days || 0, streak: s.current.streak || 0, color: cat.color, icon: s.current.icon || '' })
      }
    },

    onShow() { this.load() },

    rerender() { if (this.el) this.render(this.el) },

    async load() {
      const s = window.appState
      const ch = s.current
      if (!ch) { this.loadedFor = null; return }
      if (this.loadedFor !== ch.id) {
        this.loadedFor = ch.id
        this.data = { today: null, checkins: [], mercy: null, weekly: null, points: null, loading: true, error: '', checking: false, lastFeedback: '', chest: 0, declaration: '', shields: 0, adaptive: null }
        this.rerender()
      }
      const safe = p => p.catch(() => null)
      const [today, checkins, mercy, weekly, points, adaptive] = await Promise.all([
        window.api.get('/challenges/' + ch.id + '/today').then(r => r.data || r).catch(e => { this._todayErr = e; return null }),
        safe(window.api.get('/challenges/' + ch.id + '/checkins')),
        safe(window.api.get('/challenges/' + ch.id + '/mercy')),
        safe(window.api.get('/challenges/' + ch.id + '/weekly-report')),
        safe(window.api.get('/points/summary')),
        safe(window.api.get('/challenges/' + ch.id + '/adaptive/pending')),
      ])
      const d = this.data
      d.today = today
      const cl = checkins && (checkins.data || checkins)
      d.checkins = Array.isArray(cl) ? cl : ((cl && cl.items) || [])
      d.mercy = mercy && (mercy.data || mercy)
      d.weekly = weekly && (weekly.data || weekly)
      d.points = points && (points.data || points)
      const ad = adaptive && (adaptive.data || adaptive)
      d.adaptive = (ad && ad.suggestion) || null
      if (!d.declaration && today && today.checked_in) {
        try { d.declaration = localStorage.getItem('cp_decl_' + ch.id + '_' + today.date) || '' } catch (e) {}
      }
      const notStarted = ch.start_date && ch.start_date > window.cpTodayStr()
      if (!today && this._todayErr && !notStarted && ch.status === 'active') d.error = window.cpErrMsg(this._todayErr, '今日任务加载失败')
      else d.error = ''
      this._todayErr = null
      if (!d.lastFeedback && today && today.checkin_data && today.checkin_data.ai_feedback) d.lastFeedback = today.checkin_data.ai_feedback
      d.loading = false
      this.rerender()
    },

    _skeleton() {
      return '<div class="glass-card cp-skeleton-card"><div class="cp-skel-row"><div class="cp-skel-circle"></div><div class="cp-skel-lines"><div class="cp-skel-line w60"></div><div class="cp-skel-line w40"></div><div class="cp-skel-line w80"></div></div></div><div class="cp-skel-line w80"></div><div class="cp-skel-line w60"></div></div>'
    },

    _empty() {
      let html = '<div class="glass-card cp-empty"><div class="cp-empty-icon">🌍</div><h2>开启你的第一个挑战</h2><p>选择一个模板，或描述目标让 AI 为你规划每一天</p><div class="cp-templates">'
      window.cpTemplates.forEach((t, i) => {
        html += '<button class="cp-template-card" onclick="cpViews.home.useTemplate(' + i + ')"><span class="cp-template-icon">' + t.icon + '</span><span class="cp-template-title">' + window.cpEsc(t.title) + '</span><span class="cp-template-desc">' + window.cpEsc(t.desc) + '</span><span class="cp-template-days">' + t.days + '天</span></button>'
      })
      html += '</div><button class="cp-btn-primary" onclick="cpCreate.open()"><i class="fas fa-wand-magic-sparkles"></i> 自定义挑战</button></div>'
      return html
    },

    _main(s) {
      const ch = s.current
      const d = this.data
      let html = ''
      if (s.challenges.length > 1) {
        html += '<div class="cp-ch-scroll">'
        s.challenges.forEach(c => {
          const cc = window.cpCat(c.category)
          html += '<div class="cp-ch-chip' + (c.id === ch.id ? ' active' : '') + '" onclick="cpSelectChallenge(\'' + c.id + '\')"><i class="fas ' + cc.icon + '" style="color:' + cc.color + '"></i><span>' + window.cpEsc(c.title) + '</span><span class="cp-chip-badge">' + (c.completed_days || 0) + '/' + c.total_days + '</span></div>'
        })
        html += '</div>'
      }
      html += '<div class="glass-card cp-hero"><div class="cp-hero-title">' + (ch.icon ? ch.icon + ' ' : '') + window.cpEsc(ch.title) + '</div><div class="cp-hero-date">' + (ch.start_date || '?') + ' → ' + (ch.end_date || '?') + '</div>'
      const pct = ch.total_days ? Math.round((ch.completed_days || 0) / ch.total_days * 100) : 0
      html += '<div class="cp-hero-progress"><div class="cp-hero-progress-bar"><div class="cp-hero-progress-fill" style="width:' + pct + '%"></div></div><span class="cp-hero-progress-text">' + pct + '%</span></div>'
      html += '<div class="cp-galaxy-wrap"><div id="galaxy-box"></div></div></div>'
      if (d.loading && !d.today) return html + this._skeleton()
      const shieldCount = (d.mercy && d.mercy.shields) || d.shields || 0
      if (shieldCount > 0) html += '<div style="text-align:center"><span class="cp-shield-tag">🛡️ 连续护盾 ×' + shieldCount + ' · 断签自动保护</span></div>'
      if (d.mercy && d.mercy.shield_activated) html += '<div class="cp-repair-card" style="border-color:rgba(129,140,248,.4);background:rgba(129,140,248,.08)"><p>🛡️ 护盾已自动生效！昨天的断签被保护，连续记录未中断。继续保持！</p></div>'
      if (d.error) html += '<div class="cp-error-box"><i class="fas fa-circle-exclamation"></i><span>' + window.cpEsc(d.error) + '</span><button class="cp-btn-ghost" onclick="cpViews.home.load()">重试</button></div>'
      if (d.adaptive) html += this._adaptiveCard(d.adaptive)
      html += this._taskArea(s)
      if (d.mercy && d.mercy.repair_available) {
        html += '<div class="cp-repair-card"><p>💛 昨天不小心断签了，别灰心！48小时内完成今天任务即可修复连续记录。</p><button class="cp-btn-primary" onclick="cpViews.home.doRepair()"><i class="fas fa-band-aid"></i> 立即修复 streak</button></div>'
      }
      if (d.mercy && (d.mercy.missed_dates || []).length) html += this._diagEntry(d.mercy.missed_dates.length)
      html += this._calendar(s)
      if (d.weekly && d.weekly.content) {
        html += '<div class="glass-card cp-weekly-box"><div class="cp-section-title"><i class="fas fa-lightbulb" style="color:var(--amber)"></i> 本周洞察</div><div class="cp-weekly-text">' + window.cpEsc(d.weekly.content) + '</div><div class="cp-weekly-meta">本周进度 ' + (d.weekly.week_checkins || 0) + '/' + (d.weekly.week_days || 7) + ' 天</div></div>'
      }
      html += '<div class="glass-card cp-stats-row">'
      html += '<div class="cp-stat"><div class="cp-stat-icon">🔥</div><div class="cp-stat-num" style="color:var(--emerald)">' + (ch.streak || 0) + '</div><div class="cp-stat-label">连续打卡</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-icon">✅</div><div class="cp-stat-num" style="color:var(--primary-light)">' + (ch.completed_days || 0) + '</div><div class="cp-stat-label">累计打卡</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-icon">📅</div><div class="cp-stat-num" style="color:var(--amber)">' + (ch.total_days || 0) + '</div><div class="cp-stat-label">总天数</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-icon">⭐</div><div class="cp-stat-num" style="color:var(--primary)">' + ((d.points && d.points.total) || 0) + '</div><div class="cp-stat-label">总积分</div></div></div>'
      return html
    },

    _taskArea(s) {
      const ch = s.current
      const d = this.data
      const t = d.today
      let html = ''
      if (!t) {
        if (ch.status !== 'active') return '<div class="glass-card cp-task-card"><p class="cp-task-title">🎉 挑战已' + (ch.status === 'completed' ? '完成，太棒了！' : '结束') + '</p><p class="cp-task-desc">可在「我的」页创建新挑战，继续保持节奏。</p></div>'
        if (ch.start_date && ch.start_date > window.cpTodayStr()) return '<div class="glass-card cp-task-card"><p class="cp-task-title">挑战尚未开始</p><p class="cp-task-desc">将于 ' + ch.start_date + ' 正式开始，先去准备一下吧。</p></div>'
        return ''
      }
      html += '<div class="glass-card cp-task-card"><div class="cp-task-head"><span class="cp-task-day"><i class="fas fa-flag"></i>第 ' + (t.day_number || 1) + ' 天 · ' + (t.date || '') + '</span><span class="cp-task-pct">' + (t.progress_pct || 0) + '%</span></div><p class="cp-task-title">' + window.cpEsc(t.task_title || '完成今日打卡') + '</p>'
      if (t.task_description) html += '<p class="cp-task-desc">' + window.cpEsc(t.task_description) + '</p>'
      if (t.task_tip) html += '<p class="cp-task-tip"><i class="fas fa-lightbulb"></i><span>' + window.cpEsc(t.task_tip) + '</span></p>'
      html += '</div>'
      if (!t.checked_in) {
        html += '<div class="cp-ignite-wrap">'
        html += '<button class="cp-ignite-btn" ' + (d.checking ? 'disabled' : '') + ' onpointerdown="cpViews.home.igniteDown(event)" onpointerup="cpViews.home.igniteUp()" onpointerleave="cpViews.home.igniteUp()" onpointercancel="cpViews.home.igniteUp()" oncontextmenu="return false"><i class="fas fa-fire"></i><span>' + (d.checking ? '点燃中' : '长按点火') + '</span></button>'
        html += '<span class="cp-ignite-hint">按住 1 秒点燃今日，松手取消</span>'
        html += '<button class="cp-mini-link" ' + (d.checking ? 'disabled' : '') + ' onclick="cpViews.home.doMini()"><i class="fas fa-feather"></i> 今天太累？5分钟微打卡守住节奏</button>'
        html += '</div>'
      } else {
        if (d.declaration) html += '<div class="cp-declare">🔥 ' + window.cpEsc(d.declaration) + '</div>'
        html += '<button class="cp-btn-checkin done"><i class="fas fa-circle-check"></i> 今日已完成</button>'
        const plan = ch.ai_plan || []
        const next = plan[t.day_number]
        if (next && next.title) html += '<div class="cp-tomorrow"><i class="fas fa-sun"></i> 明日预告：' + window.cpEsc(next.title) + '</div>'
        if (d.lastFeedback) {
          html += '<div class="cp-ai-card"><div class="cp-ai-head"><i class="fas fa-robot"></i> AI 教练反馈</div><p>' + window.cpEsc(d.lastFeedback) + '</p>'
          if (d.chest) html += '<span class="cp-chest-tag">🎁 惊喜宝箱 +' + d.chest + ' 分</span>'
          html += '</div>'
        } else if (d.chest) {
          html += '<div class="cp-ai-card"><span class="cp-chest-tag">🎁 惊喜宝箱 +' + d.chest + ' 分</span></div>'
        }
        html += '<div class="cp-sub-actions"><button class="cp-btn-ghost" onclick="cpViews.home.openReflection()"><i class="fas fa-pen"></i> ' + ((t.checkin_data && t.checkin_data.reflection) ? '查看/改心得' : '写心得') + '</button><button class="cp-btn-ghost" onclick="cpOpenShare()"><i class="fas fa-share-nodes"></i> 分享海报</button></div>'
      }
      return html
    },

    useTemplate(i) {
      const t = window.cpTemplates[i]
      window.cpCreate.open({ rawInput: t.title + '，' + t.desc, days: t.days, category: t.category })
    },

    moodLabel(m) { return moodMap[m] || m },
  }
  return V
})()

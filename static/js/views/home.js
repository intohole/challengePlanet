window.cpViews = window.cpViews || {}
window.cpViews.home = (function () {
  const moodMap = { good: '😊 状态不错', normal: '😐 一般般', bad: '😔 有点难' }

  const V = {
    el: null,
    loadedFor: null,
    data: { today: null, checkins: [], mercy: null, weekly: null, points: null, guidance: null, loading: false, error: '', checking: false, lastFeedback: '', chest: 0, declaration: '', shields: 0, adaptive: null, taskValue: 0, taskSteps: [], textValue: '', quickValue: 1, quickSubGoalId: null, quickMood: '', quickReflection: '', showQuickForm: false, justRepaired: false, activeTab: 'today' },
    _ignite: null,

    render(el) {
      this.el = el
      this._mdJobs = []
      const s = window.appState
      const h = new Date().getHours()
      const greet = h < 6 ? '夜深了' : h < 12 ? '早上好' : h < 14 ? '中午好' : h < 18 ? '下午好' : '晚上好'
      let html = '<div class="cp-brand-banner cp-nebula-card"><span class="cp-brand-icon">🌍</span><div class="cp-brand-text"><div class="cp-brand-name">星轨挑战</div><div class="cp-brand-slogan">AI 打卡教练 · 陪你每一天</div></div>'
      if (s.booted && s.challenges.length) {
        html += s.pendingCount > 0
          ? '<span class="cp-pending-badge"><i class="fas fa-bolt"></i>待打卡 ' + s.pendingCount + '</span>'
          : '<span class="cp-pending-badge zero"><i class="fas fa-check"></i>已全完成</span>'
      }
      html += '</div>'
      html += '<div class="cp-greet"><div><h1>' + greet + '，' + window.cpEsc(s.nickname) + '</h1><p>' + window.cpTodayStr() + '</p></div>'
      if (s.booted && s.challenges.length) {
        const totalDone = s.challenges.reduce((a, c) => a + (c.completed_days || 0), 0)
        const totalDays = s.challenges.reduce((a, c) => a + (c.total_days || 0), 0)
        if (totalDays > 0) html += '<div class="cp-greet-stats"><span class="cp-greet-stat"><b>' + s.challenges.length + '</b>个挑战</span><span class="cp-greet-sep">·</span><span class="cp-greet-stat"><b>' + totalDone + '</b>/' + totalDays + '天</span></div>'
      }
      html += '</div>'
      html += '<div class="cp-view">'
      if (!s.booted) {
        html += this._skeleton()
      } else if (!s.challenges.length) {
        html += this._empty()
      } else if (s.current) {
        html += this._main(s)
      }
      html += '</div>'
      if (window.cpNuxTeardown) window.cpNuxTeardown()
      el.innerHTML = html
      const gx = el.querySelector('#galaxy-box')
      if (gx && s.current) {
        const cat = window.cpCat(s.current.category)
        window.renderGalaxy(gx, { total: s.current.total_days, completed: s.current.completed_days || 0, streak: s.current.streak || 0, color: cat.color, icon: s.current.icon || '' })
      }
      this._renderMiniHourly()
      this._flushMarkdown()
      const nz = el.querySelector('#cp-nux-checkin')
      if (nz && window.cpNuxMount) window.cpNuxMount(nz)
    },

    _pushMd(text) {
      this._mdSeq = (this._mdSeq || 0) + 1
      const id = 'cp-md-' + this._mdSeq
      this._mdJobs.push({ id: id, text: text })
      return id
    },

    _flushMarkdown() {
      const jobs = this._mdJobs || []
      this._mdJobs = []
      jobs.forEach(job => {
        const el = document.getElementById(job.id)
        if (!el) return
        if (!window.NexusMarkdown) { el.textContent = job.text || ''; return }
        window.NexusMarkdown.renderToAsync(el, job.text || '').catch(() => { el.textContent = job.text || '' })
      })
    },

    onShow() { this.load() },

    rerender() { if (this.el) this.render(this.el) },

    async load() {
      const s = window.appState
      const ch = s.current
      if (!ch) { this.loadedFor = null; return }
      if (this.loadedFor !== ch.id) {
        this.loadedFor = ch.id
        this.data = { today: null, checkins: [], mercy: null, weekly: null, points: null, guidance: null, loading: true, error: '', checking: false, lastFeedback: '', chest: 0, declaration: '', shields: 0, adaptive: null, taskValue: 0, taskSteps: [], textValue: '', quickValue: 1, quickSubGoalId: null, quickMood: '', quickReflection: '', showQuickForm: false, justRepaired: false, activeTab: this.data.activeTab || 'today' }
        this.rerender()
      }
      const safe = p => p.catch(() => null)
      const [today, checkins, mercy, weekly, points, adaptive, guidance] = await Promise.all([
        window.api.get('/challenges/' + ch.id + '/today').then(r => r.data || r).catch(e => { this._todayErr = e; return null }),
        safe(window.api.get('/challenges/' + ch.id + '/checkins')),
        safe(window.api.get('/challenges/' + ch.id + '/mercy')),
        safe(window.api.get('/challenges/' + ch.id + '/weekly-report')),
        safe(window.api.get('/points/summary')),
        safe(window.api.get('/challenges/' + ch.id + '/adaptive/pending')),
        safe(window.api.get('/challenges/' + ch.id + '/guidance')),
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
      const gd = guidance && (guidance.data || guidance)
      d.guidance = gd || null
      if (!d.declaration && today && today.checked_in) {
        try { d.declaration = localStorage.getItem('cp_decl_' + ch.id + '_' + today.date) || '' } catch (e) {}
      }
      const apiDecl = today && today.checkin_data && today.checkin_data.declaration
      if (apiDecl) {
        d.declaration = apiDecl
        try { localStorage.setItem('cp_decl_' + ch.id + '_' + today.date, apiDecl) } catch (e) {}
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

    switchTab(tab) {
      const d = this.data
      if (d.activeTab === tab) return
      d.activeTab = tab
      this.rerender()
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

      html += '<div class="glass-card cp-hero cp-ch-titlebar"><div class="cp-ch-title-main"><div class="cp-hero-title">' + (ch.icon ? ch.icon + ' ' : '') + window.cpEsc(ch.title) + '</div>' + (ch.total_days ? '<span class="cp-ch-title-meta"><i class="fas fa-flag-checkered"></i> ' + (ch.completed_days || 0) + '/' + ch.total_days + ' 天</span>' : '') + '</div><div class="cp-hero-actions">' + (ch.share_token ? '<button class="cp-hero-share-btn" onclick="cpViews.home.openShareConfig()"><i class="fas fa-link"></i></button>' : '') + '<button class="cp-hero-share-btn cp-hero-companion-btn" onclick="cpCompanion.open()"><i class="fas fa-robot"></i></button></div></div>'

      html += '<div class="cp-tabs"><button class="cp-tab' + (d.activeTab === 'today' ? ' active' : '') + '" onclick="cpViews.home.switchTab(\'today\')"><i class="fas fa-fire"></i><span>今日</span></button><button class="cp-tab' + (d.activeTab === 'progress' ? ' active' : '') + '" onclick="cpViews.home.switchTab(\'progress\')"><i class="fas fa-chart-line"></i><span>进度</span></button><button class="cp-tab' + (d.activeTab === 'insight' ? ' active' : '') + '" onclick="cpViews.home.switchTab(\'insight\')"><i class="fas fa-lightbulb"></i><span>洞察</span></button></div>'

      if (d.loading && !d.today) return html + this._skeleton()
      if (d.error) html += '<div class="cp-error-box"><i class="fas fa-circle-exclamation"></i><span>' + window.cpEsc(d.error) + '</span><button class="cp-btn-ghost" onclick="cpViews.home.load()">重试</button></div>'
      if (d.activeTab === 'progress') html += this._tabProgress(s)
      else if (d.activeTab === 'insight') html += this._tabInsight(s)
      else html += this._tabToday(s)
      html += '<button class="cp-fab" onclick="cpCreate.open()"><i class="fas fa-plus"></i></button>'
      return html
    },

    _tabToday(s) {
      const d = this.data
      let html = ''
      if (d.guidance && d.guidance.is_at_risk) {
        html += '<div class="cp-risk-banner"><i class="fas fa-triangle-exclamation"></i><span>中断了！今天重新打卡，节奏就能恢复</span><button class="cp-risk-btn" onclick="cpViews.home.load()">立即打卡</button></div>'
      }
      html += this._taskArea(s)
      html += this._todayTimeline(s)
      return html
    },

    useTemplate(i) {
      const t = window.cpTemplates[i]
      window.cpCreate.open({ rawInput: t.title + '，' + t.desc, days: t.days, category: t.category, scene: t.scene })
    },

    moodLabel(m) { return moodMap[m] || m },
  }

  V._cacheDeclaration = function (chId, dateStr, text) {
    try { localStorage.setItem('cp_decl_' + chId + '_' + dateStr, text) } catch (e) {}
  }

  V._pollTodayAi = async function (chId, dateStr, maxTry) {
    for (let i = 0; i < maxTry; i++) {
      await new Promise(r => setTimeout(r, 3500))
      const t = await window.api.get('/challenges/' + chId + '/today').then(x => x.data || x).catch(() => null)
      const cd = t && t.checkin_data
      if (!t) break
      const d = this.data
      if (cd && cd.declaration) {
        d.declaration = cd.declaration
        this._cacheDeclaration(chId, dateStr, cd.declaration)
      }
      if (cd && cd.ai_feedback) {
        d.lastFeedback = cd.ai_feedback
        this.rerender()
        return
      }
      this.rerender()
    }
  }

  window.cpPollTodayAi = V._pollTodayAi.bind(V)
  return V
})()
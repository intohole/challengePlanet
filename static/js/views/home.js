window.cpViews = window.cpViews || {}
window.cpViews.home = (function () {
  const moodMap = { good: '😊 状态不错', normal: '😐 一般般', bad: '😔 有点难' }

  const V = {
    el: null,
    loadedFor: null,
    data: { today: null, checkins: [], mercy: null, weekly: null, points: null, loading: false, error: '', checking: false, lastFeedback: '', chest: 0 },

    render(el) {
      this.el = el
      const s = window.appState
      const h = new Date().getHours()
      const greet = h < 6 ? '夜深了' : h < 12 ? '早上好' : h < 14 ? '中午好' : h < 18 ? '下午好' : '晚上好'
      let html = '<div class="cp-greet"><div><h1>' + greet + '，' + window.cpEsc(s.nickname) + '</h1><p>' + window.cpTodayStr() + '</p></div>'
      if (s.booted && s.challenges.length) {
        html += s.pendingCount > 0
          ? '<span class="cp-pending-badge"><i class="fas fa-bolt"></i>今日待打卡 ' + s.pendingCount + ' 项</span>'
          : '<span class="cp-pending-badge zero"><i class="fas fa-check"></i>今日已全部完成</span>'
      }
      html += '</div><div class="cp-view">'
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
        this.data = { today: null, checkins: [], mercy: null, weekly: null, points: null, loading: true, error: '', checking: false, lastFeedback: '', chest: 0 }
        this.rerender()
      }
      const safe = p => p.catch(() => null)
      const [today, checkins, mercy, weekly, points] = await Promise.all([
        window.api.get('/challenges/' + ch.id + '/today').then(r => r.data || r).catch(e => { this._todayErr = e; return null }),
        safe(window.api.get('/challenges/' + ch.id + '/checkins')),
        safe(window.api.get('/challenges/' + ch.id + '/mercy')),
        safe(window.api.get('/challenges/' + ch.id + '/weekly-report')),
        safe(window.api.get('/points/summary')),
      ])
      const d = this.data
      d.today = today
      const cl = checkins && (checkins.data || checkins)
      d.checkins = Array.isArray(cl) ? cl : ((cl && cl.items) || [])
      d.mercy = mercy && (mercy.data || mercy)
      d.weekly = weekly && (weekly.data || weekly)
      d.points = points && (points.data || points)
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
      html += '<div class="glass-card cp-hero"><div class="cp-hero-title">' + (ch.icon ? ch.icon + ' ' : '') + window.cpEsc(ch.title) + '</div><div class="cp-hero-date">' + (ch.start_date || '?') + ' → ' + (ch.end_date || '?') + '</div><div class="cp-galaxy-wrap"><div id="galaxy-box"></div></div></div>'
      if (d.loading && !d.today) return html + this._skeleton()
      if (d.error) html += '<div class="cp-error-box"><i class="fas fa-circle-exclamation"></i><span>' + window.cpEsc(d.error) + '</span><button class="cp-btn-ghost" onclick="cpViews.home.load()">重试</button></div>'
      html += this._taskArea(s)
      if (d.mercy && d.mercy.repair_available) {
        html += '<div class="cp-repair-card"><p>💛 昨天不小心断签了，别灰心！48小时内完成今天任务即可修复连续记录。</p><button class="cp-btn-primary" onclick="cpViews.home.doRepair()"><i class="fas fa-band-aid"></i> 立即修复 streak</button></div>'
      }
      html += this._calendar(s)
      if (d.weekly && d.weekly.content) {
        html += '<div class="glass-card cp-weekly-box"><div class="cp-section-title"><i class="fas fa-lightbulb" style="color:var(--amber)"></i> 本周洞察</div><div class="cp-weekly-text">' + window.cpEsc(d.weekly.content) + '</div><div class="cp-weekly-meta">本周进度 ' + (d.weekly.week_checkins || 0) + '/' + (d.weekly.week_days || 7) + ' 天</div></div>'
      }
      html += '<div class="glass-card cp-stats-row">'
      html += '<div class="cp-stat"><div class="cp-stat-num" style="color:var(--emerald)">' + (ch.streak || 0) + '</div><div class="cp-stat-label">连续打卡</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-num" style="color:var(--primary-light)">' + (ch.completed_days || 0) + '</div><div class="cp-stat-label">累计打卡</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-num" style="color:var(--amber)">' + (ch.total_days || 0) + '</div><div class="cp-stat-label">总天数</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-num" style="color:var(--primary)">' + ((d.points && d.points.total) || 0) + '</div><div class="cp-stat-label">总积分</div></div></div>'
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
      html += '<div class="glass-card cp-task-card"><div class="cp-task-head"><span>第 ' + (t.day_number || 1) + ' 天 · ' + (t.date || '') + '</span><span>' + (t.progress_pct || 0) + '%</span></div><p class="cp-task-title">' + window.cpEsc(t.task_title || '完成今日打卡') + '</p>'
      if (t.task_description) html += '<p class="cp-task-desc">' + window.cpEsc(t.task_description) + '</p>'
      if (t.task_tip) html += '<p class="cp-task-tip"><i class="fas fa-lightbulb"></i><span>' + window.cpEsc(t.task_tip) + '</span></p>'
      html += '</div>'
      if (!t.checked_in) {
        html += '<button class="cp-btn-checkin" ' + (d.checking ? 'disabled' : '') + ' onclick="cpViews.home.doCheckin()"><i class="fas fa-check"></i> ' + (d.checking ? '打卡中...' : '一键打卡') + '</button>'
      } else {
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

    _calendar(s) {
      const ch = s.current
      const d = this.data
      if (!ch.start_date) return ''
      const today = window.cpTodayStr()
      const statusMap = {}
      d.checkins.forEach(c => { statusMap[c.date] = c })
      const total = ch.total_days || 1
      const end = ch.end_date || window.cpAddDays(ch.start_date, total - 1)
      let html = '<div class="glass-card cp-calendar-box"><div class="cp-section-title"><i class="fas fa-calendar-check" style="color:var(--emerald)"></i> 打卡日历</div><div class="cp-calendar-grid">'
      for (let i = 0; i < total; i++) {
        const ds = window.cpAddDays(ch.start_date, i)
        if (ds > end) break
        const rec = statusMap[ds]
        const st = rec ? (rec.status || 'checked') : ''
        let cls = '', mark = '<span class="st">·</span>'
        if (st === 'checked' || st === 'completed') { cls = ' checked'; mark = '<span class="st">✓</span>' }
        else if (st === 'frozen') { cls = ' frozen'; mark = '<span class="st">❄</span>' }
        else if (st === 'mended') { cls = ' mended'; mark = '<span class="st">✚</span>' }
        else if (ds < today) { cls = ' missed'; mark = '<span class="st">·</span>' }
        else if (ds > today) cls = ' future'
        if (ds === today) cls += ' today'
        const clickable = rec ? ' onclick="cpViews.home.openDayDetail(\'' + ds + '\')"' : ''
        html += '<div class="cp-cal-cell' + cls + '"' + clickable + '>' + mark + '<span>' + (i + 1) + '</span></div>'
      }
      html += '</div><div class="cp-cal-legend"><span>✓ 已打卡</span><span>❄ 冻结</span><span>✚ 补签</span><span>· 缺失</span></div>'
      if (d.mercy) {
        const missed = d.mercy.missed_dates || []
        html += '<div class="cp-mercy-row">'
        if (missed.length) html += '<button class="cp-btn-ghost" onclick="cpViews.home.openMend()"><i class="fas fa-plus"></i> 补签（本月剩 ' + (d.mercy.mend_left_this_month || 0) + ' 次）</button>'
        html += '<button class="cp-btn-ghost" onclick="cpViews.home.openFreeze()"><i class="fas fa-snowflake"></i> 冻结（本周剩 ' + (d.mercy.freeze_left_this_week || 0) + ' 次）</button></div>'
      }
      html += '</div>'
      return html
    },

    useTemplate(i) {
      const t = window.cpTemplates[i]
      window.cpCreate.open({ rawInput: t.title + '，' + t.desc, days: t.days, category: t.category })
    },

    async doCheckin() {
      const s = window.appState
      const ch = s.current
      const d = this.data
      if (!ch || d.checking || (d.today && d.today.checked_in)) return
      d.checking = true
      this.rerender()
      try {
        const res = await window.api.post('/challenges/' + ch.id + '/checkin', {})
        const r = res.data || res
        window.cpCelebrate('打卡成功 +' + (r.points_earned || 0) + ' 分')
        d.lastFeedback = r.ai_feedback || d.lastFeedback
        d.chest = r.chest_points || 0
        await this.load()
        await window.cpLoadChallenges()
      } catch (e) {
        window.cpToast(window.cpErrMsg(e, '打卡失败，请重试'))
      } finally {
        d.checking = false
        this.rerender()
      }
    },

    async doRepair() {
      const ch = window.appState.current
      if (!ch) return
      try {
        const res = await window.api.post('/challenges/' + ch.id + '/repair', {})
        const r = res.data || res
        window.cpToast(r.message || '已修复！偶尔断签没关系，重要的是继续前进')
        await this.load()
        await window.cpLoadChallenges()
        this.rerender()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '修复失败')) }
    },

    openDayDetail(ds) {
      const ch = window.appState.current
      const rec = this.data.checkins.find(c => c.date === ds)
      if (!rec) return
      const plan = (ch.ai_plan || [])[(rec.day_number || 1) - 1] || {}
      window.appState.dayDetail = {
        date: ds,
        day: rec.day_number || 1,
        status: rec.status || 'checked',
        taskTitle: plan.title || '',
        mood: rec.mood || '',
        reflection: rec.reflection || '',
        aiFeedback: rec.ai_feedback || '',
      }
    },
    closeDayDetail() { window.appState.dayDetail = null },

    openMend() {
      const m = this.data.mercy
      if (!m) return
      window.appState.mend = { show: true, dates: m.missed_dates || [], left: m.mend_left_this_month || 0, busy: false }
    },
    async doMend(ds) {
      const ch = window.appState.current
      const md = window.appState.mend
      if (!ch || md.busy) return
      md.busy = true
      try {
        await window.api.post('/challenges/' + ch.id + '/mend', { date: ds })
        window.cpToast('补签成功！又补上了一块拼图')
        md.show = false
        await this.load()
        await window.cpLoadChallenges()
        this.rerender()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '补签失败')) }
      finally { md.busy = false }
    },

    openFreeze() {
      const ch = window.appState.current
      const m = this.data.mercy
      if (!ch) return
      const today = window.cpTodayStr()
      const end = ch.end_date || window.cpAddDays(today, 7)
      const dates = []
      for (let i = 1; i <= 7; i++) {
        const ds = window.cpAddDays(today, i)
        if (ds > end) break
        dates.push(ds)
      }
      window.appState.freeze = { show: true, dates, left: (m && m.freeze_left_this_week) || 0, busy: false }
    },
    async doFreeze(ds) {
      const ch = window.appState.current
      const fz = window.appState.freeze
      if (!ch || fz.busy) return
      fz.busy = true
      try {
        await window.api.post('/challenges/' + ch.id + '/freeze', { date: ds })
        window.cpToast('已冻结 ' + ds + '，该日不计断签')
        fz.show = false
        await this.load()
        this.rerender()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '冻结失败')) }
      finally { fz.busy = false }
    },

    openReflection() {
      const t = this.data.today
      const cd = (t && t.checkin_data) || {}
      window.appState.reflection = { show: true, mood: cd.mood || 'good', content: cd.reflection || '', busy: false }
    },
    async saveReflection() {
      const ch = window.appState.current
      const rf = window.appState.reflection
      if (!ch || rf.busy) return
      rf.busy = true
      try {
        const res = await window.api.patch('/challenges/' + ch.id + '/checkin/today', { mood: rf.mood, reflection: rf.content })
        const r = res.data || res
        if (r.ai_feedback) this.data.lastFeedback = r.ai_feedback
        window.cpToast('心得已保存')
        rf.show = false
        await this.load()
        this.rerender()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '保存失败')) }
      finally { rf.busy = false }
    },

    moodLabel(m) { return moodMap[m] || m },
  }
  return V
})()

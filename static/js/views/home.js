window.cpViews = window.cpViews || {}
window.cpViews.home = (function () {
  const moodMap = { good: '😊 状态不错', normal: '😐 一般般', bad: '😔 有点难' }

  const V = {
    el: null,
    loadedFor: null,
    data: { today: null, checkins: [], mercy: null, weekly: null, points: null, guidance: null, loading: false, error: '', checking: false, lastFeedback: '', chest: 0, declaration: '', shields: 0, adaptive: null, taskValue: 0, taskSteps: [], textValue: '', quickValue: 1, quickSubGoalId: null, quickMood: '', quickReflection: '', showQuickForm: false, justRepaired: false, collapsedSections: {} },
    _ignite: null,

    render(el) {
      this.el = el
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
      el.innerHTML = html
      const gx = el.querySelector('#galaxy-box')
      if (gx && s.current) {
        const cat = window.cpCat(s.current.category)
        window.renderGalaxy(gx, { total: s.current.total_days, completed: s.current.completed_days || 0, streak: s.current.streak || 0, color: cat.color, icon: s.current.icon || '' })
      }
      this._renderMiniHourly()
    },

    onShow() { this.load() },

    rerender() { if (this.el) this.render(this.el) },

    async load() {
      const s = window.appState
      const ch = s.current
      if (!ch) { this.loadedFor = null; return }
      if (this.loadedFor !== ch.id) {
        this.loadedFor = ch.id
        this.data = { today: null, checkins: [], mercy: null, weekly: null, points: null, guidance: null, loading: true, error: '', checking: false, lastFeedback: '', chest: 0, declaration: '', shields: 0, adaptive: null, taskValue: 0, taskSteps: [], textValue: '', quickValue: 1, quickSubGoalId: null, quickMood: '', quickReflection: '', showQuickForm: false, justRepaired: false, collapsedSections: {} }
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

    _collapsible(id, title, icon, iconColor, content, defaultOpen) {
      const isOpen = this.data.collapsedSections[id] !== undefined ? this.data.collapsedSections[id] : (defaultOpen !== false)
      return '<div class="glass-card" style="padding:14px">' +
        '<div class="cp-collapsible-head" onclick="cpViews.home.toggleSection(\'' + id + '\')">' +
        '<div class="cp-section-title" style="margin-bottom:0"><i class="fas ' + icon + '" style="color:' + iconColor + '"></i> ' + title + '</div>' +
        '<i class="fas fa-chevron-' + (isOpen ? 'up' : 'down') + '" style="color:var(--text-muted);font-size:12px;transition:transform .2s"></i></div>' +
        (isOpen ? '<div class="cp-collapsible-body" style="margin-top:12px">' + content + '</div>' : '') + '</div>'
    },

    toggleSection(id) {
      const d = this.data.collapsedSections
      d[id] = !d[id]
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

      if (d.guidance && d.guidance.is_at_risk) {
        html += '<div class="cp-risk-banner"><i class="fas fa-triangle-exclamation"></i><span>中断了！今天重新打卡，节奏就能恢复</span><button class="cp-risk-btn" onclick="cpViews.home.load()">立即打卡</button></div>'
      }

      html += '<div class="glass-card cp-hero cp-nebula-card"><div class="cp-hero-top"><div class="cp-hero-title">' + (ch.icon ? ch.icon + ' ' : '') + window.cpEsc(ch.title) + '</div>' + (ch.share_token ? '<button class="cp-hero-share-btn" onclick="cpViews.home.openShareConfig()"><i class="fas fa-link"></i></button>' : '') + '</div><div class="cp-hero-date">' + (ch.start_date || '?') + ' → ' + (ch.end_date || '?') + '</div>'
      const scene = window.cpSceneMap[ch.scene_template]
      if (scene) html += '<div class="cp-hero-scene"><span class="cp-hero-scene-icon">' + scene.icon + '</span><span class="cp-hero-scene-name">' + window.cpEsc(scene.name) + '</span><span class="cp-hero-scene-type">' + ({ counter: '计数打卡', timer: '计时打卡', text: '文字记录', step: '分步打卡', binary: '每日打卡' }[scene.task_type] || '打卡') + '</span></div>'
      html += '<div class="cp-hero-progress"><div class="cp-hero-progress-bar"><div class="cp-hero-progress-fill" style="width:' + (ch.total_days ? Math.round((ch.completed_days || 0) / ch.total_days * 100) : 0) + '%"></div></div><span class="cp-hero-progress-text">' + (ch.total_days ? Math.round((ch.completed_days || 0) / ch.total_days * 100) : 0) + '%</span></div>'
      html += '<div class="cp-galaxy-wrap"><div id="galaxy-box"></div></div></div>'

      if (d.loading && !d.today) return html + this._skeleton()

      const shieldCount = (d.mercy && d.mercy.shields) || d.shields || 0
      if (shieldCount > 0) html += '<div style="text-align:center"><span class="cp-shield-tag cp-shield-active">🛡️ 连续护盾 ×' + shieldCount + ' · 断签自动保护</span></div>'
      if (d.mercy && d.mercy.shield_activated) html += '<div class="cp-repair-card cp-shield-active" style="border-color:rgba(129,140,248,.4);background:rgba(129,140,248,.08)"><p>🛡️ 护盾已自动生效！昨天的断签被保护，连续记录未中断。继续保持！</p></div>'
      if (d.error) html += '<div class="cp-error-box"><i class="fas fa-circle-exclamation"></i><span>' + window.cpEsc(d.error) + '</span><button class="cp-btn-ghost" onclick="cpViews.home.load()">重试</button></div>'
      if (d.adaptive) html += this._adaptiveCard(d.adaptive)
      if (d.guidance) html += this._guidanceCard(d.guidance)
      html += this._taskArea(s)

      if (d.justRepaired) {
        html += '<div class="cp-repair-card cp-shield-mend-card" style="text-align:center"><div class="cp-shield-mend-icon">🛡️</div><p>盾牌已重组！连续记录恢复，继续加油。</p></div>'
      } else if (d.mercy && d.mercy.repair_available) {
        html += '<div class="cp-repair-card" style="text-align:center"><div class="cp-shield-break-icon">🛡️</div><p>💛 昨天不小心断签了，别灰心！48小时内完成今天任务即可修复连续记录。</p><button class="cp-btn-primary" onclick="cpViews.home.doRepair()"><i class="fas fa-band-aid"></i> 立即修复 streak</button></div>'
      }
      if (d.mercy && (d.mercy.missed_dates || []).length) html += this._diagEntry(d.mercy.missed_dates.length)

      html += this._todayTimeline(s)
      html += this._collapsible('reports', '数据报表', 'fa-chart-pie', 'var(--primary-light)', this._reportContent(s))
      html += this._collapsible('calendar', '打卡日历', 'fa-calendar-check', 'var(--emerald)', this._calendarContent(s))

      if (d.weekly && d.weekly.content) {
        html += this._collapsible('weekly', '本周洞察', 'fa-lightbulb', 'var(--amber)', '<div class="cp-weekly-text">' + window.cpEsc(d.weekly.content) + '</div><div class="cp-weekly-meta">本周进度 ' + (d.weekly.week_checkins || 0) + '/' + (d.weekly.week_days || 7) + ' 天</div>')
      }

      html += '<div class="glass-card" style="padding:16px">'
      html += '<div class="cp-stats-row">'
      const streakVal = ch.streak || 0
      const prevStreak = ch.prev_streak || 0
      const streakTrend = streakVal > prevStreak ? '↑' : (streakVal < prevStreak ? '↓' : '')
      const streakTrendColor = streakVal >= prevStreak ? 'var(--emerald)' : 'var(--red)'
      html += '<div class="cp-stat"><div class="cp-stat-icon">🔥</div><div class="cp-stat-num" style="color:var(--emerald)">' + streakVal + '</div><div class="cp-stat-label">连续打卡' + (streakTrend ? ' <span style="color:' + streakTrendColor + '">' + streakTrend + '</span>' : '') + '</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-icon">✅</div><div class="cp-stat-num" style="color:var(--primary-light)">' + (ch.completed_days || 0) + '</div><div class="cp-stat-label">累计打卡</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-icon">📅</div><div class="cp-stat-num" style="color:var(--amber)">' + (ch.total_days || 0) + '</div><div class="cp-stat-label">总天数</div></div>'
      html += '<div class="cp-stat"><div class="cp-stat-icon">⭐</div><div class="cp-stat-num" style="color:var(--primary)">' + ((d.points && d.points.total) || 0) + '</div><div class="cp-stat-label">总积分</div></div></div></div>'
      html += '<button class="cp-fab" onclick="cpCreate.open()"><i class="fas fa-plus"></i></button>'
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
      const tt = t.task_type || ch.task_type || 'binary'
      const ttLabel = { counter: '计数', timer: '计时', step: '分步', choice: '选择', text: '记录', binary: '打卡' }[tt] || '打卡'
      const isMultiMode = ch.decompose_mode === 'time_slot' || tt === 'counter' || tt === 'timer'
      html += '<div class="glass-card cp-task-card"><div class="cp-task-head"><span class="cp-task-day"><i class="fas fa-flag"></i>第 ' + (t.day_number || 1) + ' 天 · ' + (t.date || '') + '</span><div class="cp-task-head-right"><span class="cp-task-type-badge">' + ttLabel + '</span><span class="cp-task-pct">' + (t.progress_pct || 0) + '%</span></div></div><p class="cp-task-title">' + window.cpEsc(t.task_title || '完成今日打卡') + '</p>'
      if (t.task_description) html += '<p class="cp-task-desc">' + window.cpEsc(t.task_description) + '</p>'
      const baseline = t.dynamic_baseline || 0
      const isDecrease = ch.direction === 'decrease'
      if (baseline > 0) {
        const mainText = isDecrease ? '比昨天少 <b>' + baseline.toFixed(1) + '</b> 就行' : '比昨天多 <b>' + baseline.toFixed(1) + '</b> 就行'
        const refText = (t.task_target && t.task_target > 0) ? '<span class="cp-task-target-ref">目标 ' + t.task_target + ' ' + window.cpEsc(t.task_unit || '') + '（参考）</span>' : ''
        html += '<div class="cp-task-target"><i class="fas fa-bullseye"></i> ' + mainText + ' ' + window.cpEsc(t.task_unit || '') + refText + '</div>'
      } else if (t.task_target && t.task_target > 0) {
        html += '<div class="cp-task-target"><i class="fas fa-bullseye"></i> 今日目标 <b>' + t.task_target + '</b> ' + window.cpEsc(t.task_unit || '') + '</div>'
      }
      if (isMultiMode && t.today_total !== undefined) {
        const staticTarget = t.today_target || 1
        let pct, barColor
        if (baseline > 0) {
          if (isDecrease) {
            const reached = t.today_total <= baseline
            if (reached) { pct = 100; barColor = 'var(--emerald)' }
            else {
              const overRatio = baseline > 0 ? Math.min(1, (t.today_total - baseline) / baseline) : 0
              pct = Math.round(80 + overRatio * 20)
              barColor = overRatio < 0.2 ? 'var(--amber)' : 'var(--red)'
            }
          } else {
            const ratio = baseline > 0 ? t.today_total / baseline : 0
            pct = Math.round(Math.min(100, ratio * 100))
            if (ratio >= 1) barColor = 'var(--emerald)'
            else if (ratio >= 0.8) barColor = 'var(--amber)'
            else barColor = 'var(--primary)'
          }
        } else {
          pct = staticTarget > 0 ? Math.min(100, Math.round(t.today_total / staticTarget * 100)) : 0
          const overTarget = isDecrease ? t.today_total > staticTarget : t.today_total < staticTarget
          barColor = overTarget ? 'var(--red)' : 'var(--emerald)'
        }
        html += '<div class="cp-task-progress"><div class="cp-task-progress-bar"><div class="cp-task-progress-fill" style="width:' + pct + '%;background:' + barColor + '"></div></div>'
        html += '<div class="cp-task-progress-info"><span style="color:' + barColor + '">' + t.today_total + '</span><span class="cp-task-progress-sep">/</span><span>' + staticTarget + ' ' + window.cpEsc(t.unit || ch.unit || '') + '</span>'
        if (baseline > 0) html += '<span class="cp-task-progress-baseline">基准 ' + baseline.toFixed(1) + '</span>'
        html += '</div></div>'
      }
      if (t.sub_goals && t.sub_goals.length) html += this._subGoalProgress(t.sub_goals, ch)
      if (t.task_tip) html += '<p class="cp-task-tip"><i class="fas fa-lightbulb"></i><span>' + window.cpEsc(t.task_tip) + '</span></p>'
      if (t.task_steps && t.task_steps.length) html += '<div class="cp-task-steps-preview">' + t.task_steps.map(st => '<span class="cp-step-preview-tag">' + window.cpEsc(st) + '</span>').join('') + '</div>'
      html += '</div>'
      if (isMultiMode) {
        html += this._multiCheckinArea(tt, t, ch)
      } else if (!t.checked_in) {
        html += this._checkinArea(tt, t)
      } else {
        if (tt === 'text' && t.checkin_data && t.checkin_data.reflection) {
          html += '<div class="glass-card cp-text-display"><div class="cp-text-display-head"><i class="fas fa-quote-left"></i> 今日记录</div><p class="cp-text-display-body">' + window.cpEsc(t.checkin_data.reflection) + '</p></div>'
        }
        if (d.declaration) html += '<div class="cp-declare">🔥 ' + window.cpEsc(d.declaration) + '</div>'
        html += '<button class="cp-btn-checkin done"><i class="fas fa-circle-check"></i> 今日已完成</button>'
        const plan = ch.ai_plan || []
        const next = plan[t.day_number]
        if (next && next.title) {
          html += '<div class="cp-tomorrow-enhanced"><div class="cp-tomorrow-icon">🌅</div><div class="cp-tomorrow-body"><div class="cp-tomorrow-label">明日预告</div><div class="cp-tomorrow-title">' + window.cpEsc(next.title) + '</div>' + (next.description ? '<div class="cp-tomorrow-desc">' + window.cpEsc(next.description) + '</div>' : '') + '</div></div>'
        }
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

    _reportContent(s) {
      const ch = s.current
      const d = this.data
      if (!ch) return ''
      const isDecompose = ch.decompose_mode === 'time_slot' || ch.task_type === 'counter' || ch.task_type === 'timer'
      let html = '<div class="cp-report-head"><div class="cp-section-title" style="margin-bottom:0"><i class="fas fa-chart-pie" style="color:var(--primary-light)"></i> 数据报表</div>'
      html += '<button class="cp-btn-ghost cp-report-expand" onclick="cpViews.home.openReport()"><i class="fas fa-expand"></i> 完整报表</button></div>'
      html += '<div class="cp-report-quickgrid">'
      html += this._quickStat('今日', (d.today && d.today.today_total) || 0, '/', (d.today && d.today.today_target) || ch.target_value, ch.unit, 'var(--emerald)')
      const baseline = (d.today && d.today.dynamic_baseline) || 0
      html += this._quickStat('软目标', baseline.toFixed(1), '', '', ch.unit, 'var(--amber)')
      html += this._quickStat('连续', ch.streak || 0, '', '', '天', 'var(--primary-light)')
      html += this._quickStat('累计', ch.completed_days || 0, '/', ch.total_days || 0, '天', 'var(--primary)')
      html += '</div>'
      if (isDecompose) {
        html += '<div class="cp-report-mini-chart" id="cp-mini-hourly-' + ch.id + '"></div>'
      }
      return html
    },

    _quickStat(label, val, sep, val2, unit, color) {
      let v = '<div class="cp-quick-stat"><div class="cp-quick-stat-label">' + label + '</div>'
      v += '<div class="cp-quick-stat-val" style="color:' + color + '"><b>' + val + '</b>'
      if (sep) v += '<span class="cp-quick-stat-sep">' + sep + '</span><span class="cp-quick-stat-val2">' + val2 + '</span>'
      v += '</div><div class="cp-quick-stat-unit">' + window.cpEsc(unit || '') + '</div></div>'
      return v
    },

    _renderMiniHourly() {
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
    },

    _calendarContent(s) {
      const ch = s.current
      const d = this.data
      if (!ch.start_date) return ''
      const today = window.cpTodayStr()
      const statusMap = {}
      d.checkins.forEach(c => { statusMap[c.date] = c })
      const total = ch.total_days || 1
      const end = ch.end_date || window.cpAddDays(ch.start_date, total - 1)
      let html = '<div class="cp-calendar-grid">'
      for (let i = 0; i < total; i++) {
        const ds = window.cpAddDays(ch.start_date, i)
        if (ds > end) break
        const rec = statusMap[ds]
        const st = rec ? (rec.status || 'checked') : ''
        const phasePct = i / total
        const phaseColor = phasePct < 0.25 ? 'rgba(52,211,153,' : (phasePct < 0.6 ? 'rgba(245,158,11,' : 'rgba(167,139,250,')
        let cls = '', mark = '<span class="st">·</span>'
        if (st === 'checked' || st === 'completed') {
          cls = ' checked'
          mark = '<span class="st">✓</span>'
        }
        else if (st === 'frozen') { cls = ' frozen'; mark = '<span class="st">❄</span>' }
        else if (st === 'mended') { cls = ' mended'; mark = '<span class="st">✚</span>' }
        else if (ds < today) { cls = ' missed'; mark = '<span class="st">·</span>' }
        else if (ds > today) cls = ' future'
        if (ds === today) cls += ' today'
        const clickable = rec ? ' onclick="cpViews.home.openDayDetail(\'' + ds + '\')"' : ''
        html += '<div class="cp-cal-cell' + cls + '"' + clickable + ' style="' + (ds < today && !rec ? 'background:' + phaseColor + '0.08)' : '') + '">' + mark + '<span>' + (i + 1) + '</span></div>'
      }
      html += '</div><div class="cp-cal-legend"><span>✓ 已打卡</span><span>❄ 冻结</span><span>✚ 补签</span><span>· 缺失</span></div>'
      if (d.mercy) {
        const missed = d.mercy.missed_dates || []
        html += '<div class="cp-mercy-row">'
        if (missed.length) html += '<button class="cp-btn-ghost" onclick="cpViews.home.openMend()"><i class="fas fa-plus"></i> 补签（本月剩 ' + (d.mercy.mend_left_this_month || 0) + ' 次）</button>'
        html += '<button class="cp-btn-ghost" onclick="cpViews.home.openFreeze()"><i class="fas fa-snowflake"></i> 冻结（本周剩 ' + (d.mercy.freeze_left_this_week || 0) + ' 次）</button></div>'
      }
      return html
    },

    useTemplate(i) {
      const t = window.cpTemplates[i]
      window.cpCreate.open({ rawInput: t.title + '，' + t.desc, days: t.days, category: t.category, scene: t.scene })
    },

    moodLabel(m) { return moodMap[m] || m },
  }
  return V
})()
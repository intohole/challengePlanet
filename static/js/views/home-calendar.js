;(function () {
  const V = window.cpViews.home

  V._calendar = function (s) {
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
      if (st === 'checked' || st === 'completed') {
        const mini = rec.checkin_type === 'mini'
        cls = mini ? ' mini' : ' checked'
        mark = '<span class="st">✓</span>'
      }
      else if (st === 'frozen') { cls = ' frozen'; mark = '<span class="st">❄</span>' }
      else if (st === 'mended') { cls = ' mended'; mark = '<span class="st">✚</span>' }
      else if (ds < today) { cls = ' missed'; mark = '<span class="st">·</span>' }
      else if (ds > today) cls = ' future'
      if (ds === today) cls += ' today'
      const clickable = rec ? ' onclick="cpViews.home.openDayDetail(\'' + ds + '\')"' : ''
      html += '<div class="cp-cal-cell' + cls + '"' + clickable + '>' + mark + '<span>' + (i + 1) + '</span></div>'
    }
    html += '</div><div class="cp-cal-legend"><span>✓ 已打卡</span><span style="color:#c084fc">✓ 微打卡</span><span>❄ 冻结</span><span>✚ 补签</span><span>· 缺失</span></div>'
    if (d.mercy) {
      const missed = d.mercy.missed_dates || []
      html += '<div class="cp-mercy-row">'
      if (missed.length) html += '<button class="cp-btn-ghost" onclick="cpViews.home.openMend()"><i class="fas fa-plus"></i> 补签（本月剩 ' + (d.mercy.mend_left_this_month || 0) + ' 次）</button>'
      html += '<button class="cp-btn-ghost" onclick="cpViews.home.openFreeze()"><i class="fas fa-snowflake"></i> 冻结（本周剩 ' + (d.mercy.freeze_left_this_week || 0) + ' 次）</button></div>'
    }
    html += '</div>'
    return html
  }

  V._adaptiveCard = function (a) {
    let html = '<div class="cp-adapt-card"><div class="cp-adapt-head"><i class="fas fa-sliders"></i> 教练为你调整了计划</div><p class="cp-adapt-reason">' + window.cpEsc(a.reason || '') + '</p>'
    if (a.task && a.task.title) {
      html += '<div class="cp-adapt-task"><span class="cp-adapt-day">第 ' + (a.target_day || a.task.day || '?') + ' 天新任务</span><b>' + window.cpEsc(a.task.title) + '</b>'
      if (a.task.description) html += '<p>' + window.cpEsc(a.task.description) + '</p>'
      if (a.task.tip) html += '<p>💡 ' + window.cpEsc(a.task.tip) + '</p>'
      html += '</div>'
    }
    html += '<div class="cp-sub-actions" style="margin-top:10px"><button class="cp-btn-ghost" onclick="cpViews.home.respondAdaptive(false)">保持原计划</button><button class="cp-btn-primary" onclick="cpViews.home.respondAdaptive(true)"><i class="fas fa-check"></i> 采纳调整</button></div></div>'
    return html
  }

  V._diagEntry = function (missedCount) {
    return '<div class="cp-adapt-card" style="border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.07)"><div class="cp-adapt-head" style="color:var(--red)"><i class="fas fa-stethoscope"></i> 断签了？AI 帮你找原因</div><p class="cp-adapt-reason">已有 ' + missedCount + ' 天缺失。断签不是失败，找不到原因才是。AI 分析打卡记录，为你定制重启方案。</p><div class="cp-sub-actions" style="margin-top:0"><button class="cp-btn-ghost" onclick="cpOpenShare(\'flop\')"><i class="fas fa-share-nodes"></i> 翻车复盘海报</button><button class="cp-btn-primary" onclick="cpViews.home.doDiagnose()"><i class="fas fa-wand-magic-sparkles"></i> 一键诊断重启</button></div></div>'
  }
})()

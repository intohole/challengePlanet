;(function () {
  const V = window.cpViews.home

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
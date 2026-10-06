window.cpViews = window.cpViews || {}
window.cpViews.home = window.cpViews.home || {}
;(function () {
  const V = window.cpViews.home

  V._rescueCardHtml = function (c) {
    const cc = window.cpCat(c.category)
    const r = c.rescue
    const isQuit = c.category === 'quit'
    const soft = isQuit ? '<div class="cp-rescue-soft">一次没记录不等于前功尽弃，每一天都可以重新开始。</div>' : ''
    let actions = ''
    if (r.can_repair) actions += '<button class="cp-rescue-btn primary" onclick="cpViews.home.rescueRepair(' + c.id + ')"><i class="fas fa-wand-magic-sparkles"></i> 补回昨天</button>'
    if (r.missed_days >= 2) actions += '<button class="cp-rescue-btn primary" onclick="cpViews.home.rescueMend(' + c.id + ')"><i class="fas fa-calendar-check"></i> 补上 ' + (r.mend_date || '').slice(5) + '</button>'
    if (r.missed_days >= 4) actions += '<button class="cp-rescue-btn" onclick="cpViews.home.rescueDiagnose(' + c.id + ')"><i class="fas fa-stethoscope"></i> 看看怎么回事</button>'
    actions += '<button class="cp-rescue-btn ghost" onclick="cpViews.home.rerender()"><i class="fas fa-fire"></i> 今天先打卡</button>'
    return '<div class="cp-rescue-card"><div class="cp-rescue-head"><span class="cp-rescue-star"><i class="fas ' + cc.icon + '" style="color:' + cc.color + '"></i></span><div class="cp-rescue-title"><b>' + window.cpEsc(window.cpTitleClean(c.title)) + '</b><span>断了 ' + r.missed_days + ' 天，星轨还在</span></div><span class="cp-rescue-days">+' + (c.completed_days || 0) + ' 天已完成</span></div>' + soft + '<div class="cp-rescue-actions">' + actions + '</div></div>'
  }

  V._rescueCards = function (s) {
    const items = s.challenges.filter(c => c.status === 'active' && c.rescue && c.rescue.missed_days && c.id !== (s.current && s.current.id))
    if (!items.length) return ''
    let html = ''
    items.slice(0, 2).forEach(c => {
      html += this._rescueCardHtml(c)
    })
    return html
  }

  V.rescueRepair = async function (id) {
    const c = window.appState.challenges.find(x => x.id === id)
    if (!c) return
    try {
      const r = await window.cpApi.post('/challenges/' + id + '/repair', {})
      window.cpToast((r && r.message) || '已补回昨天，节奏恢复了')
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '补签失败')) }
  }

  V.rescueMend = async function (id) {
    const c = window.appState.challenges.find(x => x.id === id)
    const r = c && c.rescue
    if (!c || !r || !r.mend_date) return
    try {
      await window.cpApi.post('/challenges/' + id + '/mend', { date: r.mend_date })
      window.cpToast('已补上 ' + (r.mend_date || '').slice(5) + '，星轨重新亮了')
      await window.cpLoadChallenges()
      this.rerender()
    } catch (e) { window.cpToast(window.cpErrMsg(e, '补签失败，可能是本月免费次数用完了')) }
  }

  V.rescueDiagnose = function (id) {
    window.cpSelectChallenge(id)
    this.doDiagnose()
  }
})()

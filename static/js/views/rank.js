window.cpViews = window.cpViews || {}
window.cpViews.rank = (function () {
  const V = {
    el: null,
    data: { loading: true, scope: 'global', list: [], squads: [], squadId: null, error: '' },

    render(el) {
      this.el = el
      const d = this.data
      let html = '<div class="cp-greet"><div><h1>每周排行</h1><p>坚持打卡，冲击榜单</p></div></div><div class="cp-view">'
      html += '<div class="cp-scope-tabs"><button class="cp-pick-btn' + (d.scope === 'global' ? ' active' : '') + '" onclick="cpViews.rank.setScope(\'global\')">好友周榜</button>'
      if (d.squads.length) html += '<button class="cp-pick-btn' + (d.scope === 'squad' ? ' active' : '') + '" onclick="cpViews.rank.setScope(\'squad\')">小队榜</button>'
      html += '</div>'
      if (d.loading) html += '<div class="glass-card cp-skeleton-card"><div class="cp-skel-line w80"></div><div class="cp-skel-line w60"></div><div class="cp-skel-line w80"></div><div class="cp-skel-line w40"></div></div>'
      else if (d.error) html += '<div class="cp-error-box"><i class="fas fa-circle-exclamation"></i><span>' + window.cpEsc(d.error) + '</span><button class="cp-btn-ghost" onclick="cpViews.rank.load()">重试</button></div>'
      else if (!d.list.length) html += '<div class="glass-card cp-empty"><div class="cp-empty-icon">🏆</div><h2>本周榜单虚位以待</h2><p>完成一次打卡即可上榜，冲！</p></div>'
      else {
        d.list.forEach((r, i) => {
          const me = String(r.user_id) === String(window.appState.userId)
          const noCls = i === 0 ? ' m1' : i === 1 ? ' m2' : i === 2 ? ' m3' : ''
          html += '<div class="cp-rank-row' + (me ? ' self' : '') + '"><div class="cp-rank-no' + noCls + '">' + (i + 1) + '</div><div class="cp-rank-name">' + window.cpEsc(r.nickname || '挑战者') + (me ? '（我）' : '') + '</div><div class="cp-rank-pts">' + (r.points || 0) + ' 分</div></div>'
        })
      }
      html += '<div class="cp-rule-card"><i class="fas fa-circle-info" style="color:var(--amber)"></i> 榜单每周一重置。连续打卡积分逐日递增（第1天 +6 分 … 第7天起 +12 分），还有随机惊喜宝箱 🎁。</div>'
      html += '</div>'
      el.innerHTML = html
    },

    onShow() { this.load() },
    rerender() { if (this.el) this.render(this.el) },

    setScope(scope) {
      const d = this.data
      if (d.scope === scope) return
      d.scope = scope
      this.load()
    },

    async load() {
      const d = this.data
      d.loading = true
      d.error = ''
      this.rerender()
      try {
        if (!d.squads.length) {
          try {
            const sr = await window.api.get('/squads/my')
            const s = sr.data || sr
            d.squads = Array.isArray(s) ? s : (s.items || [])
            if (!d.squadId && d.squads.length) d.squadId = d.squads[0].id
          } catch (e) {}
        }
        const params = d.scope === 'squad' && d.squadId ? { scope: 'squad', squad_id: d.squadId } : { scope: 'global' }
        const res = await window.api.get('/leaderboard/weekly', params)
        const r = res.data || res
        d.list = Array.isArray(r) ? r : (r.items || [])
      } catch (e) { d.error = window.cpErrMsg(e, '榜单加载失败') }
      finally { d.loading = false; this.rerender() }
    },
  }
  return V
})()

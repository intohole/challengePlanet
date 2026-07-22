window.cpViews = window.cpViews || {}
window.cpViews.squad = (function () {
  const V = {
    el: null,
    data: { loading: true, squads: [], currentId: null, board: null, error: '', busy: false, nameInput: '', codeInput: '' },

    render(el) {
      this.el = el
      const d = this.data
      let html = '<div class="cp-greet"><div><h1>我的小队</h1><p>组队打卡，互相监督</p></div></div><div class="cp-view">'
      if (d.loading) html += this._skeleton()
      else if (d.error) html += '<div class="cp-error-box"><i class="fas fa-circle-exclamation"></i><span>' + window.cpEsc(d.error) + '</span><button class="cp-btn-ghost" onclick="cpViews.squad.load()">重试</button></div>'
      else if (!d.squads.length) html += this._empty()
      else html += this._main()
      html += '</div>'
      el.innerHTML = html
    },

    onShow() { this.load() },
    rerender() { if (this.el) this.render(this.el) },

    async load() {
      const d = this.data
      d.loading = true
      d.error = ''
      this.rerender()
      try {
        const res = await window.api.get('/squads/my')
        const r = res.data || res
        d.squads = Array.isArray(r) ? r : (r.items || [])
        d.currentId = d.squads.find(s => s.id === d.currentId) ? d.currentId : (d.squads[0] && d.squads[0].id)
        d.board = null
        if (d.currentId) await this.loadBoard()
      } catch (e) { d.error = window.cpErrMsg(e, '小队信息加载失败') }
      finally { d.loading = false; this.rerender() }
    },

    async loadBoard() {
      const d = this.data
      if (!d.currentId) return
      try {
        const res = await window.api.get('/squads/' + d.currentId + '/board')
        d.board = res.data || res
      } catch (e) { d.board = null }
    },

    _skeleton() {
      return '<div class="glass-card cp-skeleton-card"><div class="cp-skel-line w60"></div><div class="cp-skel-line w80"></div><div class="cp-skel-line w40"></div></div>'
    },

    _empty() {
      const d = this.data
      return '<div class="glass-card cp-empty"><div class="cp-empty-icon">👥</div><h2>还没有小队</h2><p>创建一个战队，或输入邀请码加入好友的小队</p></div>' +
        '<div class="glass-card" style="padding:16px"><div class="cp-form-row"><label class="cp-label">创建小队</label><div style="display:flex;gap:8px"><input class="cp-field" placeholder="给小队起个名字" value="' + window.cpEsc(d.nameInput) + '" oninput="cpViews.squad.data.nameInput=this.value" onkeyup="if(event.key===\'Enter\')cpViews.squad.createSquad()"><button class="cp-btn-primary" style="width:auto;padding:11px 18px" onclick="cpViews.squad.createSquad()">创建</button></div></div>' +
        '<div class="cp-form-row" style="margin-bottom:0"><label class="cp-label">加入小队</label><div style="display:flex;gap:8px"><input class="cp-field" placeholder="输入6位邀请码" value="' + window.cpEsc(d.codeInput) + '" oninput="cpViews.squad.data.codeInput=this.value" onkeyup="if(event.key===\'Enter\')cpViews.squad.joinSquad()"><button class="cp-btn-ghost" style="padding:11px 18px" onclick="cpViews.squad.joinSquad()">加入</button></div></div></div>'
    },

    _main() {
      const d = this.data
      const sq = d.squads.find(s => s.id === d.currentId) || d.squads[0]
      let html = ''
      if (d.squads.length > 1) {
        html += '<div class="cp-squad-tabs">'
        d.squads.forEach(s => {
          html += '<button class="cp-pick-btn' + (s.id === sq.id ? ' active' : '') + '" onclick="cpViews.squad.selectSquad(\'' + s.id + '\')">' + window.cpEsc(s.name) + '</button>'
        })
        html += '</div>'
      }
      html += '<button class="cp-invite" onclick="cpViews.squad.copyInvite()"><i class="fas fa-ticket" style="color:var(--primary-light)"></i><code>' + window.cpEsc(sq.invite_code || '------') + '</code><span style="font-size:12px;color:var(--text-muted)">点击复制邀请码</span></button>'
      html += '<div class="cp-rule-card"><i class="fas fa-users" style="color:var(--amber)"></i> 小队规则：全队都完成当日打卡，每人额外 +5 分。队友未打卡时可以提醒TA，每人每天限提醒1次。</div>'
      if (d.board && d.board.members) {
        html += '<div class="cp-member-grid">'
        d.board.members.forEach(m => {
          const me = String(m.user_id) === String(window.appState.userId)
          const nudged = this._nudged(sq.id, m.user_id)
          html += '<div class="cp-member"><div class="cp-avatar">' + window.cpEsc((m.nickname || '?').slice(0, 1)) + '</div><div class="cp-member-info"><div class="cp-member-name"><span class="cp-status-dot' + (m.checked_today ? ' on' : '') + '"></span>' + window.cpEsc(m.nickname || '队友') + (me ? '（我）' : '') + '</div><div class="cp-member-pts">本周 ' + (m.week_points || 0) + ' 分</div></div>'
          if (!m.checked_today && !me) html += '<button class="cp-btn-ghost cp-nudge-btn" ' + (nudged ? 'disabled' : '') + ' onclick="cpViews.squad.nudge(\'' + m.user_id + '\')">' + (nudged ? '已提醒' : '提醒TA') + '</button>'
          html += '</div>'
        })
        html += '</div>'
      } else {
        html += this._skeleton()
      }
      html += '<div style="display:flex;justify-content:center"><button class="cp-btn-ghost danger" onclick="cpViews.squad.leaveSquad()"><i class="fas fa-right-from-bracket"></i> 退出小队</button></div>'
      return html
    },

    _nudgeKey(squadId, uid) { return 'cp_nudge_' + squadId + '_' + uid + '_' + window.cpTodayStr() },
    _nudged(squadId, uid) { return !!localStorage.getItem(this._nudgeKey(squadId, uid)) },

    selectSquad(id) {
      this.data.currentId = id
      this.data.board = null
      this.rerender()
      this.loadBoard().then(() => this.rerender())
    },

    copyInvite() {
      const d = this.data
      const sq = d.squads.find(s => s.id === d.currentId)
      if (sq && sq.invite_code) window.cpCopy(sq.invite_code)
    },

    async createSquad() {
      const d = this.data
      const name = (d.nameInput || '').trim()
      if (!name || d.busy) return
      d.busy = true
      try {
        await window.api.post('/squads', { name })
        d.nameInput = ''
        window.cpToast('小队创建成功，把邀请码发给好友吧')
        await this.load()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '创建失败')) }
      finally { d.busy = false }
    },

    async joinSquad() {
      const d = this.data
      const code = (d.codeInput || '').trim()
      if (!code || d.busy) return
      d.busy = true
      try {
        await window.api.post('/squads/join', { invite_code: code })
        d.codeInput = ''
        window.cpToast('加入成功，一起打卡吧')
        await this.load()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '加入失败，请检查邀请码')) }
      finally { d.busy = false }
    },

    async leaveSquad() {
      const d = this.data
      const sq = d.squads.find(s => s.id === d.currentId)
      if (!sq || d.busy) return
      if (!window.confirm('确定退出「' + sq.name + '」吗？退出后本周积分将保留但无法再互相监督。')) return
      d.busy = true
      try {
        await window.api.delete('/squads/' + sq.id + '/leave')
        window.cpToast('已退出小队')
        d.currentId = null
        await this.load()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '退出失败')) }
      finally { d.busy = false }
    },

    async nudge(uid) {
      const d = this.data
      const sq = d.squads.find(s => s.id === d.currentId)
      if (!sq || this._nudged(sq.id, uid)) return
      try {
        await window.api.post('/squads/' + sq.id + '/nudge', { to_user_id: uid })
        localStorage.setItem(this._nudgeKey(sq.id, uid), '1')
        window.cpToast('已提醒，TA会收到打卡提醒')
        this.rerender()
      } catch (e) { window.cpToast(window.cpErrMsg(e, '提醒失败')) }
    },
  }
  return V
})()

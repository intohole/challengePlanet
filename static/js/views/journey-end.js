// 结束旅程（封存/彻底删除）+ 毕业最后一程动线
;(function () {
  const state = () => window.appState

  function rerenderCurrentView() {
    const view = window.cpViews[state().view]
    const el = document.getElementById('view-root')
    if (view && el) {
      view.loadedFor = null
      if (view.render) view.render(el)
      if (view.onShow) view.onShow()
    }
  }

  window.cpEndJourney = function (id) {
    const ch = state().challenges.find(c => c.id === Number(id))
    if (!ch) return
    state().endModal = { show: true, id: Number(id), title: window.cpTitleClean(ch.title) || '这段旅程', busy: false }
  }

  window.cpEndJourneyArchive = async function () {
    const m = state().endModal
    if (!m.id || m.busy) return
    m.busy = true
    try {
      await window.cpApi.deleteChallenge(m.id, 'archive')
      m.show = false
      window.cpToast('旅程已封存，战绩已计入累计')
      await window.cpLoadChallenges()
      rerenderCurrentView()
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '操作失败'))
    } finally {
      m.busy = false
    }
  }

  window.cpEndJourneyPurge = async function () {
    const m = state().endModal
    if (!m.id || m.busy) return
    if (!(await window.nuxConfirm('彻底删除后「' + m.title + '」的打卡记录将不可恢复，确定吗？'))) return
    m.busy = true
    try {
      await window.cpApi.deleteChallenge(m.id, 'purge')
      m.show = false
      window.cpToast('已彻底删除')
      await window.cpLoadChallenges()
      rerenderCurrentView()
    } catch (e) {
      window.cpToast(window.cpErrMsg(e, '操作失败'))
    } finally {
      m.busy = false
    }
  }

  window.cpNextLeg = function () {
    const c = state().current
    const cap = (c && Number(c.ladder_goal)) || 0
    const unit = (c && c.unit) || '次'
    window.cpCreate.open({
      rawInput: '我已经减量到每天约 ' + cap + ' ' + unit + '，现在准备彻底戒断：从今天开始一点都不再碰，坚持到底不再回头',
      category: (c && c.category) || 'quit',
      source: 'next_leg',
    })
  }
})()

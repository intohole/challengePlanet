window.cpCompanion = (function () {
  var conversationId = ''
  var currentChallengeId = null
  var chatRef = null

  function handleUnauthorized() {
    var store = window.NexusUtils.createDualStorage()
    ;['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(function (k) { store.removeItem(k) })
    window.location.href = window.cpPrefix + '/login'
  }

  var chatApi = new NexusApi({
    baseUrl: window.PATH_PREFIX || '',
    tokenKey: 'uc_access_token',
    dualStorage: true,
    onUnauthorized: handleUnauthorized
  })
  var unwrap = function (res) { return (res && res.data) || res }

  var conversationApi = {
    get: function (url, params) { return chatApi.get(url, params).then(unwrap) },
    post: function (url, data) { return chatApi.post(url, data).then(unwrap) },
    patch: function (url, data) { return chatApi.patch(url, data).then(unwrap) },
    delete: function (url) { return chatApi.delete(url).then(unwrap) }
  }

  function sessionFilter(res) {
    var arr = Array.isArray(res) ? res : (res && Array.isArray(res.data) ? res.data : (res && Array.isArray(res.items) ? res.items : []))
    var cid = currentChallengeId
    return arr.filter(function (c) { return c.meta && String(c.meta.challenge_id) === String(cid) })
  }

  function currentId() { return conversationId }

  function switchConversation(conv) {
    if (!conv || !conv.id) return
    conversationId = conv.id
    window.appState.companion.sessions = false
    loadHistory()
  }

  function onSessionCreated(conv) {
    if (!conv || !conv.id) return
    conversationId = conv.id
    window.appState.companion.sessions = false
    conversationApi.patch('/api/chat/conversations/' + conversationId, { meta: { challenge_id: currentChallengeId } })
      .then(loadHistory)
      .catch(function () {})
  }

  function runStream(content, callbacks) {
    var accumulated = ''
    var finished = false
    function finish(text) {
      if (!finished) {
        finished = true
        callbacks.onDone(text || accumulated)
      }
    }
    setQueue(0, 0)
    chatApi.streamPost('/api/chat/conversations/' + conversationId + '/messages/stream', { content: content }, {
      timeout: 120000,
      onEvent: function (eventName, data) {
        var type = (data && data.type) || ''
        if (type === 'queue') { setQueue(data.position || 0, data.estimated_wait || 0); return }
        if (type === 'queue_ready') { setQueue(0, 0); return }
        if (type === 'delta') { accumulated += data.content || ''; callbacks.onChunk(data.content || '', accumulated); return }
        if (type === 'meta') { applyMeta(data); return }
        if (type === 'thinking' || type === 'tool' || type === 'tool_executed' || type === 'references' || type === 'widget' || type === 'widget_update') {
          if (callbacks.routeRich) callbacks.routeRich(type, data)
          return
        }
        if (type === 'done') { setQueue(0, 0); finish(accumulated) }
      },
      onError: function (msg) {
        setQueue(0, 0)
        if (!finished) {
          finished = true
          if (accumulated) callbacks.onDone(accumulated)
          else callbacks.onError(new Error(msg || 'AI服务暂时不可用'))
        }
      }
    }).then(function () {
      setQueue(0, 0)
      finish(accumulated)
    })
  }

  var initChallengeId = null
  var initPromise = null
  function ensureConversation(challengeId) {
    if (conversationId && currentChallengeId === challengeId) return Promise.resolve()
    if (initPromise && initChallengeId === challengeId) return initPromise
    initChallengeId = challengeId
    currentChallengeId = challengeId
    initPromise = conversationApi.get('/api/chat/conversations', { page_size: 50 }).then(function (res) {
      var items = Array.isArray(res) ? res : ((res && res.items) || [])
      var hit = null
      for (var i = 0; i < items.length; i++) {
        if (items[i].meta && String(items[i].meta.challenge_id) === String(challengeId)) { hit = items[i]; break }
      }
      if (hit) { conversationId = hit.id; return }
      return conversationApi.post('/api/chat/conversations', { title: '挑战伴学' }).then(function (c) {
        conversationId = c.id
        return conversationApi.patch('/api/chat/conversations/' + conversationId, { meta: { challenge_id: challengeId } })
      })
    }).catch(function (e) {
      conversationId = ''
      currentChallengeId = null
      throw e
    }).finally(function () {
      initPromise = null
    })
    return initPromise
  }

  function loadHistory() {
    if (!conversationId) return Promise.resolve()
    return conversationApi.get('/api/chat/conversations/' + conversationId + '/messages', { page_size: 50 }).then(function (res) {
      var items = Array.isArray(res) ? res : ((res && res.items) || [])
      var msgs = items.map(function (m) { return { id: m.id, role: m.role, content: m.content } })
      Vue.nextTick(function () {
        if (chatRef && chatRef.value) chatRef.value.setMessages(msgs)
      })
    }).catch(function () {})
  }

  function applyMeta(m) {
    if (!m) return
    var fields = {}
    Object.keys(m).forEach(function (k) { if (k !== 'type') fields[k] = m[k] })
    window.appState.companionMeta = Object.assign({}, window.appState.companionMeta || {}, fields)
  }

  function setQueue(pos, wait) {
    var q = window.appState.companionQueue
    q.position = pos || 0
    q.wait = wait || 0
  }

  function getCurrentChallengeId() {
    var s = window.appState
    return (s && s.current && s.current.id) || null
  }

  function sendHandler(content, callbacks) {
    setQueue(0, 0)
    if (!conversationId) {
      ensureConversation(getCurrentChallengeId()).then(function () {
        if (conversationId) runStream(content, callbacks)
        else callbacks.onError(new Error('伴学会话初始化失败，请稍后再试'))
      }).catch(function () {
        callbacks.onError(new Error('伴学会话初始化失败，请稍后再试'))
      })
      return
    }
    runStream(content, callbacks)
  }

  function toggleSessions() {
    var s = window.appState
    s.companion.sessions = !s.companion.sessions
  }

  function open() {
    var s = window.appState
    var ch = s.current
    if (!ch) return
    conversationId = ''
    currentChallengeId = null
    chatRef = window.cpCompanionChatRef || null
    s.companion.show = true
    s.companion.sessions = false
    s.companionMeta = {}
    window.api.get('/challenges/' + ch.id + '/companion-status').then(function (meta) {
      applyMeta(meta.data || meta)
    }).catch(function () {})
    ensureConversation(ch.id).then(function () {
      loadHistory()
    }).catch(function () {
      window.cpToast('伴学会话初始化失败，请稍后再试')
    })
  }

  function close() {
    window.appState.companion.show = false
  }

  return { open: open, close: close, toggleSessions: toggleSessions, sendHandler: sendHandler, loadHistory: loadHistory, currentId: currentId, conversationApi: conversationApi, sessionFilter: sessionFilter, switchConversation: switchConversation, onSessionCreated: onSessionCreated }
})()

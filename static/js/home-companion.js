window.cpCompanion = (function () {
  var conversationId = ''
  var currentChallengeId = null
  var chatRef = null

  function token() {
    return localStorage.getItem('uc_access_token') || ''
  }

  function headers(extra) {
    var h = Object.assign({ 'Content-Type': 'application/json' }, extra || {})
    var t = token()
    if (t) h['Authorization'] = 'Bearer ' + t
    return h
  }

  function handleUnauthorized() {
    ;['uc_access_token', 'uc_refresh_token', 'cp_user_id', 'cp_nickname'].forEach(function (k) { localStorage.removeItem(k) })
    window.location.href = window.cpPrefix + '/login'
  }

  function check(resp) {
    if (resp.status === 401) { handleUnauthorized(); throw new Error('Unauthorized') }
    if (!resp.ok) {
      var err = new Error('HTTP ' + resp.status)
      err.status = resp.status
      throw err
    }
    return resp
  }

  function getJSON(url) {
    return fetch(window.cpPrefix + url, { headers: headers() }).then(check).then(function (r) { return r.json() }).then(function (d) { return d.data || d })
  }

  function sendJSON(method, url, data) {
    return fetch(window.cpPrefix + url, { method: method, headers: headers(), body: JSON.stringify(data || {}) }).then(check).then(function (r) { return r.json() }).then(function (d) { return d.data || d })
  }

  function bindParams(url, params) {
    if (!params) return url
    var qs = Object.keys(params).filter(function (k) { return params[k] !== null && params[k] !== undefined && params[k] !== '' })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]) }).join('&')
    return qs ? url + (url.indexOf('?') >= 0 ? '&' : '?') + qs : url
  }

  var conversationApi = {
    get: function (url, params) { return getJSON(bindParams(url, params)) },
    post: function (url, data) { return sendJSON('POST', url, data) },
    patch: function (url, data) { return sendJSON('PATCH', url, data) },
    delete: function (url) { return sendJSON('DELETE', url) }
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
    sendJSON('PATCH', '/api/chat/conversations/' + conversationId, { meta: { challenge_id: currentChallengeId } })
      .then(loadHistory)
      .catch(function () {})
  }

  function readSSE(response, onData, onDone, onError) {
    var reader = response.body.getReader()
    var decoder = new TextDecoder()
    var buffer = ''
    function process() {
      return reader.read().then(function (result) {
        if (result.done) { if (onDone) onDone(); return }
        buffer += decoder.decode(result.value, { stream: true })
        var lines = buffer.split('\n')
        buffer = lines.pop() || ''
        lines.forEach(function (line) {
          if (line.indexOf('data: ') === 0) {
            try { onData(JSON.parse(line.slice(6))) } catch (e) {}
          }
        })
        return process()
      }).catch(function (err) { if (onError) onError(err) })
    }
    return process()
  }

  var initChallengeId = null
  var initPromise = null
  function ensureConversation(challengeId) {
    if (conversationId && currentChallengeId === challengeId) return Promise.resolve()
    if (initPromise && initChallengeId === challengeId) return initPromise
    initChallengeId = challengeId
    currentChallengeId = challengeId
    initPromise = getJSON('/api/chat/conversations?page_size=50').then(function (res) {
      var items = (res && res.items) || []
      var hit = null
      for (var i = 0; i < items.length; i++) {
        if (items[i].meta && String(items[i].meta.challenge_id) === String(challengeId)) { hit = items[i]; break }
      }
      if (hit) { conversationId = hit.id; return }
      return sendJSON('POST', '/api/chat/conversations', { title: '挑战伴学' }).then(function (c) {
        conversationId = c.id
        return sendJSON('PATCH', '/api/chat/conversations/' + conversationId, { meta: { challenge_id: challengeId } })
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
    return getJSON('/api/chat/conversations/' + conversationId + '/messages?page_size=50').then(function (res) {
      var items = (res && res.items) || []
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

  function runStream(content, callbacks) {
    var accumulated = ''
    setQueue(0, 0)
    fetch(window.cpPrefix + '/api/chat/conversations/' + conversationId + '/messages/stream', {
      method: 'POST', headers: headers(), body: JSON.stringify({ content: content })
    }).then(check).then(function (response) {
      readSSE(response, function (data) {
        var type = data.type || ''
        if (type === 'queue') { setQueue(data.position || 0, data.estimated_wait || 0); return }
        if (type === 'queue_ready') { setQueue(0, 0); return }
        if (type === 'delta') { accumulated += data.content || ''; callbacks.onChunk(data.content || '', accumulated); return }
        if (type === 'meta') { applyMeta(data); return }
        if (type === 'thinking' || type === 'tool' || type === 'tool_executed' || type === 'references') {
          if (callbacks.routeRich) callbacks.routeRich(type, data)
          return
        }
        if (type === 'done') { setQueue(0, 0); callbacks.onDone(accumulated); return }
        if (type === 'error') { setQueue(0, 0); callbacks.onError(new Error(data.message || 'AI服务暂时不可用')) }
      }, function () {
        setQueue(0, 0)
        callbacks.onDone(accumulated)
      }, function (err) {
        setQueue(0, 0)
        if (accumulated) callbacks.onDone(accumulated)
        else callbacks.onError(err || new Error('AI服务暂时不可用'))
      })
    }).catch(function (err) {
      setQueue(0, 0)
      var msg = '网络出了点问题，稍后再试～'
      if (err && err.status === 503) msg = 'AI服务繁忙，请稍后再试～'
      callbacks.onError(new Error(msg))
    })
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
    getJSON('/api/v1/challenges/' + ch.id + '/companion-status').then(function (meta) {
      applyMeta(meta)
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

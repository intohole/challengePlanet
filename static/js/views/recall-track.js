;(function () {
  function track(stage, channel, challengeId, detail) {
    try {
      const key = 'cp_rk_' + stage + '_' + (challengeId || 0) + '_' + (channel || '') + '_' + window.cpTodayStr()
      if (sessionStorage.getItem(key)) return
      sessionStorage.setItem(key, '1')
      const token = window.localStorage.getItem('uc_access_token') || ''
      if (!token) return
      fetch(window.cpPrefix + '/api/v1/recall/track', {
        method: 'POST',
        keepalive: true,
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ challenge_id: challengeId || 0, channel: channel || '', stage: stage, detail: detail || '' }),
      }).catch(function () {})
    } catch (e) {}
  }
  window.cpRecallTrack = {
    arrived: function (challengeId, channel) { track('arrived', channel, challengeId) },
    seen: function (challengeId, channel) { track('seen', channel, challengeId) },
  }
})()

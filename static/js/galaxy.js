(function () {
  function shade(hex, f) {
    const n = parseInt(hex.slice(1), 16)
    const r = Math.min(255, Math.max(0, (n >> 16) + f))
    const g = Math.min(255, Math.max(0, ((n >> 8) & 255) + f))
    const b = Math.min(255, Math.max(0, (n & 255) + f))
    return 'rgb(' + r + ',' + g + ',' + b + ')'
  }

  window.renderGalaxy = function (container, opts) {
    const total = Math.max(1, opts.total || 1)
    const completed = Math.max(0, opts.completed || 0)
    const streak = opts.streak || 0
    const color = opts.color || '#635bff'
    const icon = opts.icon || ''
    const pct = Math.min(1, completed / total)
    const cx = 120, cy = 120, orbit = 92, planetR = 48
    let dots = ''
    for (let i = 0; i < total; i++) {
      const a = -Math.PI / 2 + (Math.PI * 2 * i) / total
      const x = (cx + orbit * Math.cos(a)).toFixed(1)
      const y = (cy + orbit * Math.sin(a)).toFixed(1)
      const isToday = i === completed && completed < total
      if (i < completed) {
        dots += '<circle cx="' + x + '" cy="' + y + '" r="4" fill="#34d399" opacity="0.95"/>'
      } else if (isToday) {
        dots += '<circle class="galaxy-today-dot" cx="' + x + '" cy="' + y + '" r="5" fill="none" stroke="#818cf8" stroke-width="2"/>'
      } else {
        dots += '<circle cx="' + x + '" cy="' + y + '" r="3" fill="rgba(148,163,255,.22)"/>'
      }
    }
    const dim = 0.45 + pct * 0.55
    container.innerHTML =
      '<svg width="240" height="240" viewBox="0 0 240 240" style="max-width:100%;height:auto">' +
      '<defs><radialGradient id="pg" cx="38%" cy="32%" r="75%">' +
      '<stop offset="0%" stop-color="' + shade(color, 70) + '"/>' +
      '<stop offset="55%" stop-color="' + color + '"/>' +
      '<stop offset="100%" stop-color="' + shade(color, -60) + '"/>' +
      '</radialGradient></defs>' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + orbit + '" fill="none" stroke="rgba(148,163,255,.14)" stroke-width="1.5" stroke-dasharray="3 5"/>' +
      dots +
      '<g class="galaxy-planet" style="--planet-glow:' + color + '">' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + planetR + '" fill="url(#pg)" opacity="' + dim.toFixed(2) + '"/>' +
      '<ellipse cx="' + cx + '" cy="' + cy + '" rx="' + (planetR + 14) + '" ry="' + Math.round(planetR / 3) + '" fill="none" stroke="rgba(238,241,250,.25)" stroke-width="2" transform="rotate(-18 ' + cx + ' ' + cy + ')"/>' +
      '</g>' +
      (icon ? '<text x="' + cx + '" y="' + (cy - 14) + '" text-anchor="middle" font-size="20">' + icon + '</text>' : '') +
      '<text x="' + cx + '" y="' + (cy + 14) + '" text-anchor="middle" font-size="30" font-weight="800" fill="#eef1fa">' + streak + '</text>' +
      '<text x="' + cx + '" y="' + (cy + 32) + '" text-anchor="middle" font-size="11" fill="#c3cbdd">连续打卡</text>' +
      '</svg>'
  }
})()

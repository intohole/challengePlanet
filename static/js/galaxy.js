(function () {
  function shade(hex, f) {
    const n = parseInt(hex.slice(1), 16)
    const r = Math.min(255, Math.max(0, (n >> 16) + f))
    const g = Math.min(255, Math.max(0, ((n >> 8) & 255) + f))
    const b = Math.min(255, Math.max(0, (n & 255) + f))
    return 'rgb(' + r + ',' + g + ',' + b + ')'
  }

  function getPhaseColor(dayIndex, totalDays) {
    const pct = dayIndex / totalDays
    if (pct < 0.25) return '#34D399'    // 适应期 — 绿色
    if (pct < 0.6) return '#F59E0B'     // 坚持期 — 琥珀色
    return '#A78BFA'                     // 冲刺期 — 紫色
  }

  window.renderGalaxy = function (container, opts) {
    const total = Math.max(1, opts.total || 1)
    const completed = Math.max(0, opts.completed || 0)
    const streak = opts.streak || 0
    const color = opts.color || '#818CF8'
    const icon = opts.icon || ''
    const pct = Math.min(1, completed / total)
    const cx = 120, cy = 120, orbit = 92, planetR = 48
    const isFull = completed >= total

    let dots = ''
    for (let i = 0; i < total; i++) {
      const a = -Math.PI / 2 + (Math.PI * 2 * i) / total
      const x = (cx + orbit * Math.cos(a)).toFixed(1)
      const y = (cy + orbit * Math.sin(a)).toFixed(1)
      const isToday = i === completed && completed < total
      if (i < completed) {
        const phaseColor = getPhaseColor(i, total)
        const sparkle = total > 7 && i % 3 === 0 ? ' class="galaxy-sparkle"' : ''
        dots += '<circle cx="' + x + '" cy="' + y + '" r="4.5" fill="' + phaseColor + '" opacity="0.95"' + sparkle + '/>'
        if (total > 14 && i % 7 === 0) {
          dots += '<circle cx="' + x + '" cy="' + y + '" r="7" fill="none" stroke="' + phaseColor + '" stroke-width="1" opacity="0.3"/>'
        }
      } else if (isToday) {
        dots += '<circle class="galaxy-today-dot" cx="' + x + '" cy="' + y + '" r="5" fill="none" stroke="#818cf8" stroke-width="2.5"/>'
        dots += '<circle class="galaxy-today-pulse" cx="' + x + '" cy="' + y + '" r="5" fill="none" stroke="rgba(129,140,248,.3)" stroke-width="4"/>'
      } else {
        dots += '<circle cx="' + x + '" cy="' + y + '" r="3" fill="rgba(148,163,184,.15)"/>'
      }
    }

    const dim = 0.45 + pct * 0.55
    const fireGlow = streak >= 7 ? ' animation:streak-fire 1.6s ease-in-out infinite;' : ''
    container.innerHTML =
      '<svg width="240" height="240" viewBox="0 0 240 240" style="max-width:100%;height:auto">' +
      '<defs>' +
      '<radialGradient id="pg" cx="38%" cy="32%" r="75%">' +
      '<stop offset="0%" stop-color="' + shade(color, 70) + '"/>' +
      '<stop offset="55%" stop-color="' + color + '"/>' +
      '<stop offset="100%" stop-color="' + shade(color, -60) + '"/>' +
      '</radialGradient>' +
      '<radialGradient id="ng" cx="50%" cy="50%" r="50%">' +
      '<stop offset="0%" stop-color="rgba(129,140,248,.08)"/>' +
      '<stop offset="100%" stop-color="transparent"/>' +
      '</radialGradient>' +
      '</defs>' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + (orbit + 20) + '" fill="url(#ng)"/>' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + orbit + '" fill="none" stroke="rgba(148,163,184,.1)" stroke-width="1.5" stroke-dasharray="3 5"/>' +
      '<g class="galaxy-orbit-group">' + dots + '</g>' +
      '<g class="galaxy-planet" style="--planet-glow:' + color + ';filter:drop-shadow(0 0 ' + (18 + pct * 12) + 'px ' + color + '80)">' +
      '<circle cx="' + cx + '" cy="' + cy + '" r="' + planetR + '" fill="url(#pg)" opacity="' + dim.toFixed(2) + '"/>' +
      '<ellipse cx="' + cx + '" cy="' + cy + '" rx="' + (planetR + 14) + '" ry="' + Math.round(planetR / 3) + '" fill="none" stroke="rgba(238,241,250,.2)" stroke-width="2" transform="rotate(-18 ' + cx + ' ' + cy + ')"/>' +
      '<circle cx="' + (cx - 12) + '" cy="' + (cy - 10) + '" r="8" fill="rgba(255,255,255,.08)"/>' +
      '<circle cx="' + (cx + 16) + '" cy="' + (cy + 8) + '" r="5" fill="rgba(255,255,255,.05)"/>' +
      '</g>' +
      (icon ? '<text x="' + cx + '" y="' + (cy - 14) + '" text-anchor="middle" font-size="20">' + icon + '</text>' : '') +
      '<text x="' + cx + '" y="' + (cy + 14) + '" text-anchor="middle" font-size="30" font-weight="800" fill="#eef1fa" style="' + fireGlow + '">' + streak + '</text>' +
      '<text x="' + cx + '" y="' + (cy + 32) + '" text-anchor="middle" font-size="11" fill="#64748B">连续打卡</text>' +
      '</svg>'
  }
})()
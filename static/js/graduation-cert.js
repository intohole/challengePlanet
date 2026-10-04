window.cpGradCert = (function () {
  const GOLD = '#fbbf24'
  const GOLD_SOFT = 'rgba(251,191,36,.16)'
  const INK = '#eef1fa'
  const MUTED = '#c3cbdd'

  function fitFont(ctx, text, maxWidth, size, weight) {
    ctx.font = (weight || 'bold') + ' ' + size + 'px sans-serif'
    while (size > 14 && ctx.measureText(text).width > maxWidth) {
      size -= 2
      ctx.font = (weight || 'bold') + ' ' + size + 'px sans-serif'
    }
    return size
  }

  async function generate(journey, ch) {
    if (!journey || !journey.graduation) throw new Error('no graduation')
    const g = journey.graduation
    const unit = journey.unit || ''
    const avoided = journey.cigarettes_avoided || 0
    const money = journey.money_saved || 0
    const pct = journey.reduction_pct || 0
    const guard = journey.guard_days || 0
    const msReached = (journey.milestones || []).filter(m => m.reached)
    const health = journey.health || {}
    const healthReached = (health.milestones || []).filter(m => m.reached)
    const goalDay = Number(journey.ladder_total_stages) > 0
      ? (Number(journey.ladder_total_stages) - 1) * Math.max(1, Number(ch.ladder_interval || 1)) + 1
      : (ch.completed_days || 0)

    try { if (document.fonts && document.fonts.ready) await document.fonts.ready } catch (e) {}

    const canvas = document.createElement('canvas')
    canvas.width = 750
    canvas.height = 1000
    const ctx = canvas.getContext('2d')

    const bg = ctx.createLinearGradient(0, 0, 0, 1000)
    bg.addColorStop(0, '#221503')
    bg.addColorStop(0.55, '#2e2007')
    bg.addColorStop(1, '#1f1504')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, 750, 1000)
    for (let i = 0; i < 110; i++) {
      ctx.fillStyle = 'rgba(251,191,36,' + (0.08 + Math.random() * 0.3).toFixed(2) + ')'
      ctx.beginPath()
      ctx.arc(Math.random() * 750, Math.random() * 1000, Math.random() * 1.6 + 0.4, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.strokeStyle = 'rgba(251,191,36,.4)'
    ctx.lineWidth = 3
    ctx.strokeRect(28, 28, 694, 944)
    ctx.strokeStyle = 'rgba(251,191,36,.18)'
    ctx.lineWidth = 1
    ctx.strokeRect(40, 40, 670, 920)

    ctx.textAlign = 'left'
    ctx.fillStyle = GOLD
    ctx.font = 'bold 22px sans-serif'
    ctx.fillText('星轨挑战', 64, 92)
    ctx.textAlign = 'center'
    ctx.fillStyle = MUTED
    ctx.font = '15px sans-serif'
    ctx.letterSpacing = '6px'
    ctx.fillText('减 量 毕 业 证 书', 375, 92)
    ctx.letterSpacing = '0px'

    ctx.font = '64px sans-serif'
    ctx.fillText('🎓', 375, 196)

    const title = '「' + (ch.title || '我的挑战') + '」'
    fitFont(ctx, title, 560, 34)
    ctx.fillStyle = INK
    ctx.fillText(title, 375, 262)

    ctx.fillStyle = MUTED
    ctx.font = '17px sans-serif'
    ctx.fillText('完成了从每天约 ' + Number(journey.baseline) + ' ' + unit + ' 到 ' + Number(g.final_cap) + ' ' + unit + ' 的全部阶梯', 375, 296)

    ctx.fillStyle = GOLD
    ctx.font = 'bold 88px sans-serif'
    ctx.fillText(String(avoided), 375, 408)
    ctx.fillStyle = INK
    ctx.font = 'bold 24px sans-serif'
    ctx.fillText('累计少抽 ' + unit, 375, 446)

    const cells = [
      ['阶梯旅程', goalDay + ' 天'],
      ['减量幅度', '-' + pct + '%'],
      ['省下约', '¥' + money],
      ['守线纪录', '连续 ' + guard + ' 天'],
    ]
    const cw = 290, chh = 92, gx = 60, gy = 490
    cells.forEach((c, i) => {
      const x = gx + (i % 2) * (cw + 50), y = gy + Math.floor(i / 2) * (chh + 18)
      ctx.fillStyle = GOLD_SOFT
      ctx.fillRect(x, y, cw, chh)
      ctx.fillStyle = MUTED
      ctx.font = '16px sans-serif'
      ctx.textAlign = 'left'
      ctx.fillText(c[0], x + 20, y + 34)
      ctx.fillStyle = INK
      ctx.font = 'bold 26px sans-serif'
      ctx.fillText(c[1], x + 20, y + 70)
    })

    ctx.textAlign = 'center'
    ctx.fillStyle = MUTED
    ctx.font = '16px sans-serif'
    const hLabel = healthReached.length
      ? '身体恢复线已点亮 ' + healthReached.length + '/6 站 · 下一站：' + ((health.milestones || []).find(m => !m.reached) || {}).title
      : '身体恢复线将从毕业日起逐站点亮'
    fitFont(ctx, hLabel, 600, 16, '')
    ctx.fillText(hLabel, 375, 726)
    const badges = msReached.length ? msReached.map(m => '🏅' + m.label) : ['🏅 首个里程碑就在前方']
    let line = ''
    const lines = []
    badges.forEach(b => {
      if ((line + '  ' + b).length > 30) { lines.push(line); line = b } else line = line ? line + '  ' + b : b
    })
    if (line) lines.push(line)
    ctx.fillStyle = GOLD
    ctx.font = '17px sans-serif'
    lines.slice(0, 2).forEach((ln, i) => ctx.fillText(ln, 375, 764 + i * 28))

    ctx.fillStyle = MUTED
    ctx.font = '15px sans-serif'
    ctx.fillText('毕业日期 ' + (g.graduation_date || '') + (g.keep_days_total > 1 ? ' · 保持期至 ' + (ch.end_date || '') : ''), 375, 846)
    ctx.fillStyle = 'rgba(195,203,221,.75)'
    ctx.font = 'italic 14px sans-serif'
    ctx.fillText('减量是通往戒断的一步，每一根没抽的烟都算数', 375, 878)

    ctx.textAlign = 'left'
    ctx.fillStyle = GOLD
    ctx.font = 'bold 17px sans-serif'
    ctx.fillText('星轨挑战 · AI打卡教练', 64, 936)
    return canvas.toDataURL('image/png')
  }

  return { generate }
})()

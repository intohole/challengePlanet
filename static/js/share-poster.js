window.cpSharePoster = (function () {
  const QUOTES = ['坚持不是咬牙硬撑，而是每天比昨天多爱自己一点。', '星球不亮，是因为你还没开始；一旦开始，银河为你闪耀。', '真正的高手，都赢在不为人知的每一天。', '别小看每天的一小步，时间会把它变成一大步。']

  function wrapText(ctx, text, maxWidth) {
    const lines = []
    let line = ''
    for (const ch of text) {
      if (ctx.measureText(line + ch).width > maxWidth && line) { lines.push(line); line = ch }
      else line += ch
    }
    if (line) lines.push(line)
    return lines
  }

  function drawQR(ctx, url, x, y, size) {
    return new Promise(resolve => {
      try {
        if (typeof QRCode === 'undefined') throw new Error('no qr')
        const box = document.createElement('div')
        box.style.cssText = 'position:fixed;left:-9999px;top:-9999px'
        document.body.appendChild(box)
        new QRCode(box, { text: url, width: size, height: size, colorDark: '#0b0d1a', colorLight: '#ffffff', correctLevel: QRCode.CorrectLevel.M })
        const qc = box.querySelector('canvas')
        if (qc) {
          ctx.fillStyle = '#ffffff'
          ctx.fillRect(x - 8, y - 8, size + 16, size + 16)
          ctx.drawImage(qc, x, y, size, size)
          document.body.removeChild(box)
          resolve(true)
          return
        }
        document.body.removeChild(box)
        throw new Error('no canvas')
      } catch (e) {
        ctx.strokeStyle = 'rgba(238,241,250,.3)'
        ctx.lineWidth = 2
        ctx.strokeRect(x, y, size, size)
        ctx.fillStyle = '#9aa5c0'
        ctx.font = '14px sans-serif'
        ctx.textAlign = 'center'
        wrapText(ctx, url, size).slice(0, 4).forEach((ln, i) => ctx.fillText(ln, x + size / 2, y + 30 + i * 20))
        resolve(false)
      }
    })
  }

  async function generate(ch) {
    let quote = ''
    try {
      const res = await window.api.get('/challenges/' + ch.id + '/share-data')
      const d = res.data || res
      quote = d.share_quote || ''
    } catch (e) {}
    if (!quote) quote = QUOTES[Math.floor(Math.random() * QUOTES.length)]

    let checkedDates = {}
    try {
      const res = await window.api.get('/challenges/' + ch.id + '/checkins')
      const d = res.data || res
      const list = Array.isArray(d) ? d : (d.items || [])
      list.forEach(c => { checkedDates[c.date] = c.status || 'checked' })
    } catch (e) {}

    const cat = window.cpCat(ch.category)
    const canvas = document.createElement('canvas')
    canvas.width = 750
    canvas.height = 1000
    const ctx = canvas.getContext('2d')

    const bg = ctx.createLinearGradient(0, 0, 0, 1000)
    bg.addColorStop(0, '#0b0d1a')
    bg.addColorStop(0.6, '#12142e')
    bg.addColorStop(1, '#1a1c3e')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, 750, 1000)
    for (let i = 0; i < 90; i++) {
      ctx.fillStyle = 'rgba(238,241,250,' + (0.15 + Math.random() * 0.5).toFixed(2) + ')'
      ctx.beginPath()
      ctx.arc(Math.random() * 750, Math.random() * 1000, Math.random() * 1.6 + 0.4, 0, Math.PI * 2)
      ctx.fill()
    }

    ctx.textAlign = 'left'
    ctx.fillStyle = '#818cf8'
    ctx.font = 'bold 22px sans-serif'
    ctx.fillText('🌍 挑战星球', 40, 64)

    const px = 375, py = 290, pr = 96
    const pg = ctx.createRadialGradient(px - 30, py - 34, 10, px, py, pr)
    pg.addColorStop(0, cat.color)
    pg.addColorStop(1, '#0b0d1a')
    ctx.save()
    ctx.shadowColor = cat.color
    ctx.shadowBlur = 60
    ctx.fillStyle = pg
    ctx.beginPath()
    ctx.arc(px, py, pr, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
    ctx.strokeStyle = 'rgba(238,241,250,.35)'
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.ellipse(px, py, pr + 26, pr / 3.2, -0.3, 0, Math.PI * 2)
    ctx.stroke()
    ctx.font = '44px sans-serif'
    ctx.textAlign = 'center'
    if (ch.icon) ctx.fillText(ch.icon, px, py + 16)

    ctx.fillStyle = '#eef1fa'
    ctx.font = 'bold 34px sans-serif'
    ctx.fillText(ch.title || '我的挑战', px, 470)
    ctx.fillStyle = '#fbbf24'
    ctx.font = 'bold 46px sans-serif'
    ctx.fillText('已连续打卡 ' + (ch.streak || 0) + ' 天', px, 540)

    const rx = 375, ry = 660, rr = 62
    const pct = ch.total_days ? Math.min(1, (ch.completed_days || 0) / ch.total_days) : 0
    ctx.strokeStyle = 'rgba(148,163,255,.15)'
    ctx.lineWidth = 12
    ctx.beginPath()
    ctx.arc(rx, ry, rr, 0, Math.PI * 2)
    ctx.stroke()
    ctx.strokeStyle = '#635bff'
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.arc(rx, ry, rr, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * pct)
    ctx.stroke()
    ctx.fillStyle = '#eef1fa'
    ctx.font = 'bold 34px sans-serif'
    ctx.fillText(Math.round(pct * 100) + '%', rx, ry + 8)
    ctx.fillStyle = '#9aa5c0'
    ctx.font = '16px sans-serif'
    ctx.fillText((ch.completed_days || 0) + '/' + ch.total_days + ' 天', rx, ry + 34)

    const today = new Date()
    const dotR = 13, gap = 74, startX = 375 - gap * 3
    for (let i = 6; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      const ds = window.cpDateStr(d)
      const x = startX + gap * (6 - i)
      const st = checkedDates[ds]
      ctx.fillStyle = st === 'checked' || st === 'completed' ? '#34d399' : st === 'frozen' ? '#818cf8' : st === 'mended' ? '#fbbf24' : 'rgba(148,163,255,.15)'
      ctx.beginPath()
      ctx.arc(x, 790, dotR, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#9aa5c0'
      ctx.font = '12px sans-serif'
      ctx.fillText('周' + '日一二三四五六'[d.getDay()], x, 822)
    }

    ctx.fillStyle = '#c3cbdd'
    ctx.font = 'italic 20px sans-serif'
    const qlines = wrapText(ctx, '“' + quote + '”', 620)
    qlines.slice(0, 2).forEach((ln, i) => ctx.fillText(ln, 375, 872 + i * 30))

    const shareUrl = window.location.origin + window.cpPrefix
    await drawQR(ctx, shareUrl, 596, 856, 104)
    ctx.fillStyle = '#9aa5c0'
    ctx.font = '15px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('扫码一起挑战', 648, 982)
    ctx.fillStyle = '#818cf8'
    ctx.font = 'bold 17px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText('挑战星球 · AI打卡教练', 40, 960)

    return canvas.toDataURL('image/png')
  }

  const FLOP_QUOTES = ['断签不可怕，可怕的是不再开始。我回来了。', '真正的失败只有一种，就是放弃。翻车不算。', '允许自己跌倒，但不允许自己躺平。', '习惯的敌人不是断签，是断签后的自责。我选择继续。']

  async function generateFlop(ch) {
    let checkedDates = {}
    try {
      const res = await window.api.get('/challenges/' + ch.id + '/checkins')
      const d = res.data || res
      const list = Array.isArray(d) ? d : (d.items || [])
      list.forEach(c => { checkedDates[c.date] = c.status || 'checked' })
    } catch (e) {}

    const todayStr = window.cpTodayStr()
    let missed = 0
    if (ch.start_date) {
      let ds = ch.start_date
      while (ds < todayStr) {
        if (!checkedDates[ds]) missed++
        ds = window.cpAddDays(ds, 1)
      }
    }
    const done = ch.completed_days || 0

    const canvas = document.createElement('canvas')
    canvas.width = 750
    canvas.height = 1000
    const ctx = canvas.getContext('2d')

    const bg = ctx.createLinearGradient(0, 0, 0, 1000)
    bg.addColorStop(0, '#1a0e0a')
    bg.addColorStop(0.6, '#241210')
    bg.addColorStop(1, '#2e1a12')
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, 750, 1000)
    for (let i = 0; i < 90; i++) {
      ctx.fillStyle = 'rgba(251,191,36,' + (0.1 + Math.random() * 0.35).toFixed(2) + ')'
      ctx.beginPath()
      ctx.arc(Math.random() * 750, Math.random() * 1000, Math.random() * 1.6 + 0.4, 0, Math.PI * 2)
      ctx.fill()
    }

    ctx.textAlign = 'left'
    ctx.fillStyle = '#fbbf24'
    ctx.font = 'bold 22px sans-serif'
    ctx.fillText('🌍 挑战星球 · 翻车复盘', 40, 64)

    const px = 375, py = 280, pr = 96
    const pg = ctx.createRadialGradient(px - 30, py - 34, 10, px, py, pr)
    pg.addColorStop(0, '#78716c')
    pg.addColorStop(1, '#1a0e0a')
    ctx.fillStyle = pg
    ctx.beginPath()
    ctx.arc(px, py, pr, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = '#fbbf24'
    ctx.lineWidth = 4
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(px - 40, py - pr + 8)
    ctx.lineTo(px - 12, py - 26)
    ctx.lineTo(px - 30, py + 4)
    ctx.lineTo(px + 6, py + 30)
    ctx.lineTo(px - 8, py + pr - 10)
    ctx.stroke()
    ctx.font = '38px sans-serif'
    ctx.textAlign = 'center'
    if (ch.icon) ctx.fillText(ch.icon, px + 40, py - 40)

    ctx.fillStyle = '#eef1fa'
    ctx.font = 'bold 30px sans-serif'
    ctx.fillText('「' + (ch.title || '我的挑战') + '」', px, 440)
    ctx.fillStyle = '#f87171'
    ctx.font = 'bold 52px sans-serif'
    ctx.fillText('断签 ' + missed + ' 天', px, 520)
    ctx.fillStyle = '#fbbf24'
    ctx.font = 'bold 40px sans-serif'
    ctx.fillText('但我回来了', px, 590)

    ctx.fillStyle = 'rgba(238,241,250,.1)'
    ctx.fillRect(95, 650, 560, 100)
    ctx.fillStyle = '#eef1fa'
    ctx.font = 'bold 26px sans-serif'
    ctx.fillText('已完成 ' + done + '/' + ch.total_days + ' 天 · 进度不清零', px, 690)
    ctx.fillStyle = '#c3cbdd'
    ctx.font = '18px sans-serif'
    ctx.fillText('研究证实：恢复速度比断签次数更重要', px, 724)

    const today = new Date()
    const dotR = 13, gap = 74, startX = 375 - gap * 3
    for (let i = 6; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      const ds = window.cpDateStr(d)
      const x = startX + gap * (6 - i)
      const st = checkedDates[ds]
      ctx.fillStyle = st === 'checked' || st === 'completed' ? '#34d399' : st === 'frozen' ? '#818cf8' : st === 'mended' ? '#fbbf24' : 'rgba(248,113,113,.4)'
      ctx.beginPath()
      ctx.arc(x, 800, dotR, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#c3cbdd'
      ctx.font = '12px sans-serif'
      ctx.fillText('周' + '日一二三四五六'[d.getDay()], x, 832)
    }

    ctx.fillStyle = '#fbbf24'
    ctx.font = 'italic 20px sans-serif'
    const quote = FLOP_QUOTES[Math.floor(Math.random() * FLOP_QUOTES.length)]
    wrapText(ctx, '“' + quote + '”', 620).slice(0, 2).forEach((ln, i) => ctx.fillText(ln, 375, 878 + i * 30))

    const shareUrl = window.location.origin + window.cpPrefix
    await drawQR(ctx, shareUrl, 596, 856, 104)
    ctx.fillStyle = '#c3cbdd'
    ctx.font = '15px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('扫码一起挑战', 648, 982)
    ctx.fillStyle = '#fbbf24'
    ctx.font = 'bold 17px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText('挑战星球 · 真实打卡，允许翻车', 40, 960)

    return canvas.toDataURL('image/png')
  }

  return { generate, generateFlop }
})()

const fs = require('fs')
const path = '/Users/intoblack/remoteWork/challengePlanet/static/js/views/learn-checkin.js'
const vocab = JSON.parse(fs.readFileSync('/Users/intoblack/remoteWork/challengePlanet/static/data/vocab.json', 'utf8'))

global.window = { __ls: {} }
const shim = {
  getItem: k => (k in window.__ls ? window.__ls[k] : null),
  setItem: (k, v) => { window.__ls[k] = String(v) },
  removeItem: k => { delete window.__ls[k] },
}
Object.defineProperty(global, 'localStorage', { value: shim, configurable: true })
Object.defineProperty(window, 'localStorage', { value: shim, configurable: true })
window.cpViews = { home: {} }
const V = window.cpViews.home
window.appState = { current: { id: 7, target_value: 20, unit: '词' } }
window.cpEsc = s => String(s)
window.cpToast = () => {}
window.cpErrMsg = () => 'err'
window.cpLoadChallenges = async () => {}
window.api = { post: async () => ({ data: { points_earned: 1 } }), get: async () => ({ data: null }) }

eval(fs.readFileSync(path, 'utf8'))

let fail = 0
function eq(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  if (ok) console.log('PASS', name)
  else { fail++; console.log('FAIL', name, 'got', JSON.stringify(got), 'want', JSON.stringify(want)) }
}
function ok(name, cond) { if (cond) console.log('PASS', name); else { fail++; console.log('FAIL', name) } }

V._storeReview(7, 2, [{ w: 'apple', m: '苹果' }, { w: 'banana', m: '香蕉' }])
V._storeReview(7, 3, [{ w: 'apple', m: '苹果新释义' }, { w: 'cherry', m: '樱桃' }])
const deck3 = V._reviewDeck(7, 4)
eq('复习池跨天收集(去重且新天优先)', deck3.map(i => i.w), ['apple', 'cherry', 'banana'])
ok('apple用了第3天的新释义', deck3[0].m === '苹果新释义')

V._storeReview(7, 10, [{ w: 'old', m: 'x' }])
V._storeReview(7, 12, [{ w: 'new', m: 'y' }])
eq('3天窗口内旧词仍可复习', V._reviewDeck(7, 13).map(i => i.w).filter(w => w === 'old'), ['old'])
V._storeReview(7, 16, [{ w: 'zz', m: 'z' }])
eq('存储时清理3天前', V._reviewDeck(7, 16).map(i => i.w).filter(w => w === 'old' || w === 'new'), [])

const cards = [ { w: 'a', m: '1' }, { w: 'b', m: '2' } ]
V.data = { wordCards: cards, wordIdx: 1, wordSeen: 1, wordKnown: 0, wordBlur: 1, wordForgot: 0, wordNewTotal: 1, wordReviewTotal: 1 }
V._saveSession('cp_word_sess_7_1')
const s = V._readSession('cp_word_sess_7_1')
eq('会话保存/读取 roundtrip idx', s.idx, 1)
eq('会话保存/读取 newTotal', s.newTotal, 1)

V._loadJSON = async () => vocab
V._buildWordDeck({ task_target: 20, day_number: 1 }).then(deck => {
  ok('卡组含复习+新词', deck.reviewCount >= 0 && deck.newTotal === 20 && deck.cards.length === 20 + deck.reviewCount)
  const noDup = new Set(deck.cards.map(c => c.w)).size === deck.cards.length
  ok('卡组无重复词', noDup)
  ok('复习词带 r 标记', deck.cards.slice(0, deck.reviewCount).every(c => c.r === 1))
  console.log(fail ? 'RESULT FAIL' : 'RESULT PASS')
  process.exit(fail ? 1 : 0)
}).catch(e => { console.log('ERR', e); process.exit(1) })
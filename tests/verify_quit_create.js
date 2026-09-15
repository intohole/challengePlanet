const fs = require('fs')
const path = '/Users/intoblack/remoteWork/challengePlanet/static/js/'

global.window = global.window || {}
const w = global.window

w.cpSceneMap = { quit: { id: 'quit', name: '戒断', icon: '🚭', color: '#ef4444', task_type: 'counter', unit: '根', desc: '每抽一根记一笔，目标是逐日递减到 0', default_target: 1, samples: ['戒烟：每天20根，每周减2根', '戒奶茶：从每天2杯减到0'], steps: ['想抽时，先点一下记录这一根', '对照今日上限控制节奏', '记录每一天的进步'] } }
w.cpTodayStr = () => '2026-09-15'
w.cpToast = m => console.log('[toast]', m)
w.cpErrMsg = () => 'err'
w.cpLoadChallenges = async () => null
w.cpViews = {}
let confirmBody = null
w.api = { post: async (url, body) => { confirmBody = body; return { data: { id: 99 } } }, get: async () => ({ data: null }) }

function load(f) { eval(fs.readFileSync(path + f, 'utf8')) }
load('create.js')
load('create-direct.js')
load('create-extra.js')

const C = w.cpCreate
function freshState() {
  return { step: 1, phase: 'idle', parsed: null, editTitle: '', editDays: 66, editCategory: 'quit', editDesc: '', rawInput: '', source: 'web', sceneTemplate: 'quit', ladderEn: false, ladderStart: 0, ladderGoal: 0, ladderInterval: 3, ladderStep: 1, startDate: '2026-09-15', startMode: 'today', gender: '男', age: 28, heightCm: 170, weightKg: 70, goalWeight: 60, activityLevel: 2, saving: false, error: '', plan: [], sportMet: 0, periodDays: 7, periodTarget: 0, periodUnit: '分钟', genTotal: 0 }
}
function setState(partial) { w.appState = { create: Object.assign(freshState(), partial) } }

let fail = 0
function eq(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  if (ok) console.log('PASS', name, '=>', JSON.stringify(got))
  else { fail++; console.log('FAIL', name, '=> got', JSON.stringify(got), 'want', JSON.stringify(want)) }
}
function ok(name, cond) {
  if (cond) console.log('PASS', name)
  else { fail++; console.log('FAIL', name) }
}

async function main() {
  // 1. 模板打开(useTemplate): applySceneLadder 应默认开启 quit 梯度
  setState({})
  C.open({ rawInput: '戒烟挑战，抽一根记一根', days: 42, category: 'quit', scene: 'quit' })
  eq('open订阅套件 sceneTemplate', w.appState.create.sceneTemplate, 'quit')
  ok('open后 ladderEn=true', w.appState.create.ladderEn === true)
  eq('quit默认 interval/step', [w.appState.create.ladderInterval, w.appState.create.ladderStep], [1, 1])

  // 2. canDirect: 未填当前每天 => 禁止直接创建
  setState({})
  C.open({ rawInput: '戒烟挑战', days: 42, category: 'quit', scene: 'quit' })
  w.appState.create.sceneTemplate = 'quit'
  ok('canDirect(未填当前每天)=false', w.cpCreateDirect.canDirect() === false)
  w.appState.create.ladderStart = 20
  ok('canDirect(填了20)=true', w.cpCreateDirect.canDirect() === true)

  // 3. buildPlan(quit): counter/根/目标=当前每天
  setState({ rawInput: '戒烟挑战', editDays: 7, ladderStart: 20, ladderGoal: 0 })
  w.appState.create.sceneTemplate = 'quit'
  const bp = w.cpCreateDirect.buildPlan(w.cpSceneMap.quit)
  ok('plan task_type=counter', bp.tt === 'counter')
  eq('plan unit=根', bp.unit, '根')
  eq('plan target=20', bp.target, 20)
  eq('plan 7天', bp.plan.length, 7)
  ok('plan 每天 target=20', bp.plan[0].target_value === 20)

  // 4. confirmDirect(quit): 直接创建 body 应输出 counter+decrease+ladder+soft+根
  setState({ rawInput: '戒烟挑战', editDays: 7, sceneTemplate: 'quit', ladderStart: 20, ladderGoal: 0, ladderInterval: 1, ladderStep: 1 })
  await w.cpCreateDirect.confirmDirect()
  eq('confirm.task_type', confirmBody.task_type, 'counter')
  eq('confirm.unit', confirmBody.unit, '根')
  eq('confirm.direction', confirmBody.direction, 'decrease')
  eq('confirm.goal_type', confirmBody.goal_type, 'soft')
  eq('confirm.goal_rule', confirmBody.goal_rule, 'ladder')
  eq('confirm.goal_mode', confirmBody.goal_mode, 'ceiling')
  eq('confirm.ladder_start', confirmBody.ladder_start, 20)
  eq('confirm.ladder_goal', confirmBody.ladder_goal, 0)
  eq('confirm.target_value', confirmBody.target_value, 20)
  eq('confirm.category', confirmBody.category, 'quit')

  // 5. confirmCreate(AI路径, parsed 无 ladder): quit 强制 counter/ladder/soft，未填当前每天拦截
  setState({ sceneTemplate: 'quit', editTitle: '戒烟挑战', editDays: 42, startDate: '2026-09-15', phase: 'preview', parsed: { category: 'quit', task_type: 'binary', target_value: 1, unit: '次', direction: 'increase', goal_rule: 'fixed' }, plan: [{ day: 1, title: '戒烟挑战', target_value: 1, unit: '次', task_type: 'binary' }] })
  await C.confirmCreate()
  ok('未填当前每天被拦截', w.appState.create.error.indexOf('当前每天') >= 0)
  confirmBody = null
  setState({ sceneTemplate: 'quit', editTitle: '戒烟挑战', editDays: 42, startDate: '2026-09-15', phase: 'preview', ladderStart: 20, ladderGoal: 0, ladderInterval: 1, ladderStep: 1, parsed: { category: 'quit', task_type: 'binary', target_value: 1, unit: '次', direction: 'increase', goal_rule: 'fixed' }, plan: [{ day: 1, title: '戒烟挑战', target_value: 1, unit: '次', task_type: 'binary' }] })
  await C.confirmCreate()
  eq('AIConfirm.task_type', confirmBody.task_type, 'counter')
  eq('AIConfirm.unit', confirmBody.unit, '根')
  eq('AIConfirm.direction', confirmBody.direction, 'decrease')
  eq('AIConfirm.goal_rule', confirmBody.goal_rule, 'ladder')
  eq('AIConfirm.goal_type', confirmBody.goal_type, 'soft')
  eq('AIConfirm.ladder_start', confirmBody.ladder_start, 20)
  eq('AIConfirm.ladder_goal', confirmBody.ladder_goal, 0)

  // 6. 其他场景不受影响(reading 模板直接创建仍 counter/increase/fixed)
  w.cpSceneMap.reading = { id: 'reading', name: '阅读', icon: '📖', color: '#10b981', task_type: 'counter', unit: '页', desc: '每天读一点，长期积累', default_target: 30, samples: ['每天阅读30页'], steps: ['挑选一本书', '静心阅读目标页数', '记录一句感悟'] }
  setState({ rawInput: '每天读书30分钟', editDays: 7, sceneTemplate: 'reading' })
  await w.cpCreateDirect.confirmDirect()
  eq('reading.task_type', confirmBody.task_type, 'counter')
  eq('reading.direction', confirmBody.direction, 'increase')
  eq('reading.goal_rule', confirmBody.goal_rule, 'fixed')
  eq('reading.ladder_start', confirmBody.ladder_start, 0)

  console.log(fail === 0 ? '\nALL PASS' : '\n' + fail + ' FAILURES')
  process.exit(fail === 0 ? 0 : 1)
}
main()
window.cpTemplates = [
  { title: '戒烟挑战', category: 'quit', days: 42, icon: '🚭', desc: '抽一根记一根，目标逐日递减到 0', scene: 'quit' },
  { title: '每天读书30分钟', category: 'learn', days: 66, icon: '📚', desc: '用66天养成终身阅读习惯', scene: 'reading' },
  { title: '坚持跑步', category: 'fitness', days: 21, icon: '🏃', desc: '从1公里到5公里，循序渐进', scene: 'running' },
  { title: '早睡早起', category: 'build', days: 21, icon: '🌙', desc: '21天重建作息节律', scene: 'morning' },
  { title: '每日冥想', category: 'mind', days: 21, icon: '🧘', desc: '每天10分钟正念练习', scene: 'meditation' },
  { title: '每日感恩', category: 'mind', days: 21, icon: '🙏', desc: '每天记录3件感恩的事', scene: 'gratitude' },
]

window.cpScenes = [
  { id: 'quit', name: '戒断', icon: '🚭', color: '#ef4444', task_type: 'counter', unit: '根', desc: '每抽一根记一笔，目标是逐日递减到 0', default_target: 1, samples: ['戒烟：每天20根，每周减2根', '戒奶茶：从每天2杯减到0'], steps: ['想抽时，先点一下记录这一根', '对照今日上限控制节奏', '记录每一天的进步'] },
  { id: 'fitness', name: '健身', icon: '💪', color: '#f59e0b', task_type: 'counter', unit: '个', desc: '力量与有氧，目标逐日加量', default_target: 30, samples: ['30天每天30个俯卧撑', '21天腹肌撕裂者计划'], steps: ['热身3分钟', '完成今日训练', '记录完成个数'] },
  { id: 'running', name: '跑步', icon: '🏃', color: '#f43f5e', task_type: 'counter', unit: '公里', desc: '从1公里逐步跑到5公里', default_target: 3, samples: ['42天从0到5公里跑步计划', '每天跑步3公里'], steps: ['换上跑鞋', '按计划跑完目标公里数', '拉伸放松'] },
  { id: 'study', name: '学习', icon: '📚', color: '#6366f1', task_type: 'counter', unit: '页', desc: '按页数稳步推进学习进度', default_target: 20, samples: ['30天每天读20页专业书', '考研复习66天计划'], steps: ['翻开教材/资料', '读完目标页数', '写下3个要点'] },
  { id: 'reading', name: '阅读', icon: '📖', color: '#10b981', task_type: 'counter', unit: '页', desc: '每天读一点，长期积累', default_target: 30, samples: ['每天阅读30页', '21天养成阅读习惯'], steps: ['挑选一本书', '静心阅读目标页数', '记录一句感悟'] },
  { id: 'meditation', name: '冥想', icon: '🧘', color: '#8b5cf6', task_type: 'timer', unit: '分钟', desc: '每天静心几分钟，稳定心境', default_target: 10, samples: ['每天冥想10分钟', '21天正念冥想入门'], steps: ['找个安静的地方', '闭眼专注呼吸', '完成目标时长'] },
  { id: 'morning', name: '早起', icon: '🌅', color: '#f97316', task_type: 'timer', unit: '点', desc: '规律起床，重建作息节律', default_target: 7, samples: ['30天早起6点起床', '坚持每天7点前起床'], steps: ['设定闹钟', '闹钟响后起床洗漱', '记录起床时间'] },
  { id: 'writing', name: '写作', icon: '✍️', color: '#8b5cf6', task_type: 'text', unit: '篇', desc: '记录思考，沉淀每日成长', default_target: 1, samples: ['30天每日写作打卡', '21天晨间日记'], steps: ['打开文档', '写下今日主题', '完成300字'] },
  { id: 'gratitude', name: '感恩', icon: '🙏', color: '#fbbf24', task_type: 'text', unit: '件', desc: '每天记3件感恩的小事', default_target: 3, samples: ['21天感恩日记', '每天记录3件感恩的事'], steps: ['回想今天的美好瞬间', '写下3件感恩的小事'] },
  { id: 'water', name: '饮水', icon: '💧', color: '#06b6d4', task_type: 'counter', unit: '杯', desc: '每天喝够8杯水，规律补水', default_target: 8, samples: ['30天每天喝够8杯水', '21天养成喝水习惯'], steps: ['准备一个水杯', '分时段喝完8杯水', '记录杯数'] },
  { id: 'diet', name: '减重', icon: '⚖️', color: '#0ea5e9', task_type: 'diet', unit: '千卡', desc: '控制每日摄入，科学减重', default_target: 300, samples: ['30天减重3公斤', '66天饮食控制科学减脂'], steps: ['记录三餐', '控制摄入在目标内', '记录体重变化'] },
  { id: 'english', name: '英语', icon: '🔤', color: '#3b82f6', task_type: 'word', unit: '词', desc: '每日背单词，内置四级高频词库', default_target: 20, samples: ['30天每天背20个英语单词', '14天掌握高频核心词'], steps: ['看释义', '记例句', '自测默写'] },
  { id: 'poem', name: '古诗', icon: '📜', color: '#b45309', task_type: 'recite', unit: '首', desc: '每日背一首唐诗，朗读到默写', default_target: 1, samples: ['30天背30首唐诗', '每天背一首古诗词'], steps: ['朗读全诗', '理解大意', '背诵全诗'] },
  { id: 'pomodoro', name: '番茄', icon: '🍅', color: '#ef4444', task_type: 'timer', unit: '分钟', desc: '番茄工作法，25分钟专注打卡', default_target: 25, samples: ['每天4个番茄钟专注', '25分钟专注学习'], steps: ['设定任务', '专注25分钟', '休息5分钟'] },
  { id: 'custom', name: '自定义', icon: '🎯', color: '#8b5cf6', task_type: 'binary', unit: '次', desc: '完全按你的想法来', default_target: 1, samples: ['30天不喝奶茶', '每天给家人打个电话'], steps: [] },
]
window.cpSceneMap = {}
window.cpScenes.forEach(s => { window.cpSceneMap[s.id] = s })

window.cpTaskTypeLabel = tt => ({ counter: '计数', timer: '计时', text: '记录', step: '分步', diet: '减重', binary: '打卡', word: '背词', recite: '背诵' })[tt] || '打卡'

window.cpCategoryMap = {
  build: { icon: 'fa-seedling', color: '#34d399', label: '习惯养成' },
  quit: { icon: 'fa-ban', color: '#f87171', label: '戒除' },
  learn: { icon: 'fa-book', color: '#818cf8', label: '学习' },
  fitness: { icon: 'fa-dumbbell', color: '#fbbf24', label: '运动' },
  mind: { icon: 'fa-brain', color: '#c084fc', label: '心灵' },
  other: { icon: 'fa-star', color: '#635bff', label: '其他' },
}
window.cpCat = cat => window.cpCategoryMap[cat] || window.cpCategoryMap.other


(function() {
    const ABOUT_CSS = `
.nux-about-wrap{min-height:100dvh;background:var(--nx-bg-base);color:var(--nx-text-body);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7}
.nux-about-topbar{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:12px;padding:12px 20px;background:var(--nx-glass-bg);backdrop-filter:blur(var(--nx-glass-blur));border-bottom:1px solid var(--nx-border)}
.nux-about-back{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:20px;background:var(--nx-bg-muted);color:var(--nx-text-secondary);font-size:14px;text-decoration:none;transition:all .2s}
.nux-about-back:hover{background:var(--app-accent);color:#fff}
.nux-about-topbar-name{font-weight:600;color:var(--nx-text-heading);font-size:15px}
.nux-about-hero{max-width:720px;margin:0 auto;padding:56px 24px 40px;text-align:center}
.nux-about-logo{width:80px;height:80px;margin:0 auto 20px;border-radius:22px;background:linear-gradient(135deg,var(--app-accent),var(--app-accent-hover));display:flex;align-items:center;justify-content:center;font-size:40px;color:#fff;box-shadow:0 12px 32px rgba(var(--app-accent-rgb),.3)}
.nux-about-hero h1{font-size:32px;font-weight:700;color:var(--nx-text-heading);margin:0 0 10px;letter-spacing:-.5px}
.nux-about-slogan{font-size:18px;color:var(--app-accent);font-weight:600;margin:0 0 12px}
.nux-about-desc{font-size:15px;color:var(--nx-text-secondary);max-width:560px;margin:0 auto}
.nux-about-section{max-width:720px;margin:0 auto;padding:32px 24px}
.nux-about-section-title{font-size:13px;font-weight:600;color:var(--app-accent);text-transform:uppercase;letter-spacing:1.5px;margin:0 0 8px}
.nux-about-section h2{font-size:22px;font-weight:700;color:var(--nx-text-heading);margin:0 0 20px}
.nux-about-story p{font-size:15px;color:var(--nx-text-body);margin:0 0 14px;line-height:1.85}
.nux-about-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.nux-about-card{padding:20px;background:var(--nx-bg-surface);border:1px solid var(--nx-border);border-radius:14px;transition:all .25s}
.nux-about-card:hover{border-color:var(--nx-border-accent);box-shadow:var(--nx-shadow-md);transform:translateY(-2px)}
.nux-about-card-icon{width:40px;height:40px;border-radius:10px;background:rgba(var(--app-accent-rgb),.1);display:flex;align-items:center;justify-content:center;font-size:18px;color:var(--app-accent);margin-bottom:12px}
.nux-about-card h3{font-size:15px;font-weight:600;color:var(--nx-text-heading);margin:0 0 6px}
.nux-about-card p{font-size:13px;color:var(--nx-text-secondary);margin:0}
.nux-about-promise .nux-about-card-icon{background:rgba(var(--nx-success-rgb),.1);color:var(--nx-success)}
.nux-about-eco{display:flex;flex-wrap:wrap;gap:10px}
.nux-about-eco-item{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:20px;background:var(--nx-bg-surface);border:1px solid var(--nx-border);font-size:13px;color:var(--nx-text-body);text-decoration:none;transition:all .2s}
.nux-about-eco-item:hover{border-color:var(--nx-border-accent);color:var(--nx-text-heading)}
.nux-about-eco-dot{width:8px;height:8px;border-radius:50%}
.nux-about-footer{max-width:720px;margin:0 auto;padding:32px 24px 56px;text-align:center;border-top:1px solid var(--nx-border);margin-top:24px}
.nux-about-footer p{font-size:13px;color:var(--nx-text-muted);margin:4px 0}
.nux-about-contact{display:inline-flex;align-items:center;gap:6px;margin-top:12px;padding:8px 18px;border-radius:20px;background:var(--app-accent);color:#fff;font-size:14px;text-decoration:none;transition:all .2s}
.nux-about-contact:hover{background:var(--app-accent-hover)}
@media(max-width:640px){
.nux-about-hero{padding:40px 20px 28px}
.nux-about-hero h1{font-size:26px}
.nux-about-slogan{font-size:16px}
.nux-about-section{padding:24px 20px}
.nux-about-grid{grid-template-columns:1fr}
}
`;

    const DEFAULT_ECOSYSTEM = [
        { name: '知路', desc: '志愿评估', color: '#059669' },
        { name: '天才学伴', desc: '学习成长', color: '#0891b2' },
        { name: '跃职', desc: 'AI简历', color: '#6366f1' },
        { name: '拾光', desc: '生活笔记', color: '#8b5cf6' },
        { name: 'VerseCraft', desc: '小说创作', color: '#228FBD' },
        { name: '宠小护', desc: '宠物健康', color: '#ec4899' },
        { name: '码趣星', desc: '少儿编程', color: '#f97316' },
        { name: '知识图谱', desc: '智能问答', color: '#d97706' },
        { name: '投察', desc: '股票分析', color: '#1d4ed8' },
        { name: '鱼跃', desc: '闲鱼助手', color: '#155e75' },
        { name: 'adSmart', desc: '广告投放', color: '#ef4444' },
        { name: '司南', desc: '人生推演', color: '#0d9488' },
        { name: '星轨挑战', desc: 'AI打卡', color: '#4f46e5' },
        { name: 'PromptGenius', desc: '提示词优化', color: '#0f172a' }
    ];

    function injectStyle() {
        if (document.getElementById('nux-about-style')) return;
        const style = document.createElement('style');
        style.id = 'nux-about-style';
        style.textContent = ABOUT_CSS;
        document.head.appendChild(style);
    }

    const NuxAboutPage = {
        name: 'NuxAboutPage',
        props: {
            appName: { type: String, default: '' },
            appIcon: { type: String, default: '' },
            slogan: { type: String, default: '' },
            description: { type: String, default: '' },
            story: { type: Array, default: () => [] },
            features: { type: Array, default: () => [] },
            promises: { type: Array, default: () => [] },
            ecosystem: { type: Array, default: () => DEFAULT_ECOSYSTEM },
            showEcosystem: { type: Boolean, default: true },
            version: { type: String, default: '' },
            backUrl: { type: String, default: '/' },
            contactText: { type: String, default: '反馈建议' }
        },
        setup(props) {
            function applyTheme(color) {
                if (color) {
                    document.documentElement.style.setProperty('--app-accent', color);
                    const rgb = hexToRgb(color);
                    if (rgb) document.documentElement.style.setProperty('--app-accent-rgb', rgb);
                }
            }
            function hexToRgb(hex) {
                const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
                return m ? `${parseInt(m[1],16)}, ${parseInt(m[2],16)}, ${parseInt(m[3],16)}` : null;
            }
            Vue.onMounted(() => { injectStyle(); });
            return { applyTheme };
        },
        template: `
            <div class="nux-about-wrap">
                <div class="nux-about-topbar">
                    <a :href="backUrl" class="nux-about-back"><i class="fas fa-arrow-left"></i> 返回</a>
                    <span class="nux-about-topbar-name">{{ appName }}</span>
                </div>
                <div class="nux-about-hero">
                    <div v-if="appIcon" class="nux-about-logo">{{ appIcon }}</div>
                    <h1 v-if="appName">{{ appName }}</h1>
                    <p v-if="slogan" class="nux-about-slogan">{{ slogan }}</p>
                    <p v-if="description" class="nux-about-desc">{{ description }}</p>
                </div>
                <div v-if="story.length" class="nux-about-section nux-about-story">
                    <p class="nux-about-section-title">我们的故事</p>
                    <h2>为什么做这个产品</h2>
                    <p v-for="(p, i) in story" :key="i">{{ p }}</p>
                </div>
                <div v-if="features.length" class="nux-about-section">
                    <p class="nux-about-section-title">核心能力</p>
                    <h2>这个产品能做什么</h2>
                    <div class="nux-about-grid">
                        <div v-for="(f, i) in features" :key="i" class="nux-about-card">
                            <div class="nux-about-card-icon"><i :class="f.icon"></i></div>
                            <h3>{{ f.title }}</h3>
                            <p>{{ f.desc }}</p>
                        </div>
                    </div>
                </div>
                <div v-if="promises.length" class="nux-about-section nux-about-promise">
                    <p class="nux-about-section-title">对用户的承诺</p>
                    <h2>我们坚持什么</h2>
                    <div class="nux-about-grid">
                        <div v-for="(p, i) in promises" :key="i" class="nux-about-card">
                            <div class="nux-about-card-icon"><i :class="p.icon"></i></div>
                            <h3>{{ p.title }}</h3>
                            <p>{{ p.desc }}</p>
                        </div>
                    </div>
                </div>
                <div v-if="showEcosystem && ecosystem.length" class="nux-about-section">
                    <p class="nux-about-section-title">应用生态</p>
                    <h2>不止这一个产品</h2>
                    <p style="color:var(--nx-text-secondary);font-size:14px;margin:0 0 16px">这是一个持续构建的AI应用矩阵，每个产品都专注解决一个真实问题。</p>
                    <div class="nux-about-eco">
                        <a v-for="(e, i) in ecosystem" :key="i" class="nux-about-eco-item" :href="e.url || '#'">
                            <span class="nux-about-eco-dot" :style="{background: e.color}"></span>
                            {{ e.name }}
                        </a>
                    </div>
                </div>
                <div class="nux-about-footer">
                    <p v-if="version">版本 {{ version }}</p>
                    <p>用心打磨，持续迭代</p>
                    <a href="mailto:feedback@example.com" class="nux-about-contact"><i class="fas fa-comment-dots"></i> {{ contactText }}</a>
                </div>
            </div>
        `
    };

    window.NuxAboutPage = NuxAboutPage;
})();

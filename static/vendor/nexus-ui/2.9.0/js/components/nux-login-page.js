(function() {
    const NuxLoginPage = {
        name: 'NuxLoginPage',
        props: {
            appName: { type: String, default: '' },
            appIcon: { type: String, default: '' },
            slogan: { type: String, default: '' },
            description: { type: String, default: '' },
            features: { type: Array, default: () => [] },
            themeColor: { type: String, default: '' },
            showRegister: { type: Boolean, default: true },
            showPhoneLogin: { type: Boolean, default: false },
            showEmailField: { type: Boolean, default: false },
            showInviteCode: { type: Boolean, default: false },
            loading: { type: Boolean, default: false },
            error: { type: String, default: '' }
        },
        emits: ['login', 'register'],
        setup(props, { emit }) {
            const mode = Vue.ref('login');
            const localError = Vue.ref('');
            const form = Vue.reactive({
                username: '',
                password: '',
                confirmPassword: '',
                email: '',
                phone: '',
                inviteCode: ''
            });

            const combinedError = Vue.computed(() => props.error || localError.value);

            function applyTheme() {
                if (props.themeColor) {
                    document.documentElement.style.setProperty('--app-accent', props.themeColor);
                }
            }

            function restoreTheme() {
                if (props.themeColor) {
                    document.documentElement.style.removeProperty('--app-accent');
                }
            }

            Vue.onMounted(applyTheme);
            Vue.onUnmounted(restoreTheme);

            function onLogin() {
                localError.value = '';
                emit('login', { username: form.username, password: form.password });
            }

            function onRegister() {
                localError.value = '';
                if (!form.username && !form.email && !form.phone) {
                    localError.value = '请填写用户名、邮箱或手机号';
                    return;
                }
                if (form.password.length < 8) {
                    localError.value = '密码至少8位';
                    return;
                }
                if (form.password !== form.confirmPassword) {
                    localError.value = '两次密码不一致';
                    return;
                }
                emit('register', {
                    username: form.username || null,
                    password: form.password,
                    email: form.email || null,
                    phone: form.phone || null,
                    inviteCode: form.inviteCode || null
                });
            }

            function switchMode(m) {
                localError.value = '';
                mode.value = m;
            }

            return { mode, form, combinedError, onLogin, onRegister, switchMode };
        },
        template: `
            <div class="nux-login-page">
                <div class="nux-login-form-side">
                    <div class="nux-login-card">
                        <div class="nux-login-tabs">
                            <button :class="['nux-login-tab', { active: mode === 'login' }]" @click="switchMode('login')">登录</button>
                            <button v-if="showRegister" :class="['nux-login-tab', { active: mode === 'register' }]" @click="switchMode('register')">注册</button>
                        </div>

                        <div v-if="combinedError" class="nux-login-error">{{ combinedError }}</div>

                        <form @submit.prevent="mode === 'login' ? onLogin() : onRegister()">
                            <div class="nux-form-group">
                                <label class="nux-form-label">用户名</label>
                                <input v-model="form.username" type="text" class="nux-input" placeholder="请输入用户名" autocomplete="username">
                            </div>

                            <div v-if="showEmailField && mode === 'register'" class="nux-form-group">
                                <label class="nux-form-label">邮箱</label>
                                <input v-model="form.email" type="email" class="nux-input" placeholder="请输入邮箱" autocomplete="email">
                            </div>

                            <div v-if="showPhoneLogin && mode === 'register'" class="nux-form-group">
                                <label class="nux-form-label">手机号</label>
                                <input v-model="form.phone" type="tel" class="nux-input" placeholder="请输入手机号" autocomplete="tel">
                            </div>

                            <div class="nux-form-group">
                                <label class="nux-form-label">密码</label>
                                <input v-model="form.password" type="password" class="nux-input" placeholder="请输入密码" autocomplete="current-password" required>
                            </div>

                            <div v-if="mode === 'register'" class="nux-form-group">
                                <label class="nux-form-label">确认密码</label>
                                <input v-model="form.confirmPassword" type="password" class="nux-input" placeholder="请再次输入密码" autocomplete="new-password" required>
                            </div>

                            <div v-if="showInviteCode && mode === 'register'" class="nux-form-group">
                                <label class="nux-form-label">邀请码</label>
                                <input v-model="form.inviteCode" type="text" class="nux-input" placeholder="邀请码（选填）">
                            </div>

                            <button type="submit" class="nux-login-submit" :disabled="loading">
                                <span v-if="loading" class="nx-spinner"></span>
                                {{ mode === 'login' ? '登 录' : '注 册' }}
                            </button>
                        </form>

                        <div class="nux-login-footer">
                            <slot name="footer"></slot>
                        </div>
                    </div>
                </div>
                <div class="nux-login-brand">
                    <div class="nux-login-brand-content">
                        <span v-if="appIcon" class="nux-login-icon">{{ appIcon }}</span>
                        <h1 v-if="appName" class="nux-login-app-name">{{ appName }}</h1>
                        <p v-if="slogan" class="nux-login-slogan">{{ slogan }}</p>
                        <p v-if="description" class="nux-login-desc">{{ description }}</p>
                        <div v-if="features && features.length" class="nux-login-features">
                            <div v-for="(f, i) in features" :key="i" class="nux-login-feature">
                                <span v-if="f.icon" class="nux-login-feature-icon">{{ f.icon }}</span>
                                <div class="nux-login-feature-text">
                                    <strong v-if="f.title">{{ f.title }}</strong>
                                    <span v-if="f.desc">{{ f.desc }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `
    };

    window.NuxLoginPage = NuxLoginPage;
})();

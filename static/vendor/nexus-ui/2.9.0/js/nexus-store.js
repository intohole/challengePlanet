(function() {
    const { reactive, computed, watch } = Vue;

    class NexusStore {
        constructor(initialState = {}, options = {}) {
            this._state = reactive({
                user: null,
                token: null,
                loading: false,
                ...initialState
            });
            this._persistKeys = options.persistKeys || ['token', 'user'];
            this._tokenKey = options.tokenKey || 'token';
            this._userKey = options.userKey || 'user';
            this._unwatchFns = [];
            this._isAuthenticated = computed(() => !!this._state.token && !!this._state.user);
            this._initPersistence();
        }

        get state() { return this._state; }

        get(key) { return this._state[key]; }
        set(key, value) { this._state[key] = value; }

        get isAuthenticated() { return this._isAuthenticated.value; }

        destroy() {
            if (this._unwatchFns) {
                this._unwatchFns.forEach(fn => { try { fn(); } catch (e) {} });
                this._unwatchFns = [];
            }
        }

        logout() {
            this._state.user = null;
            this._state.token = null;
            this._persistKeys.forEach(key => localStorage.removeItem(key));
        }

        _initPersistence() {
            this._persistKeys.forEach(key => {
                const saved = localStorage.getItem(key);
                if (saved) {
                    try { this._state[key] = key === 'user' ? JSON.parse(saved) : saved; }
                    catch (e) { console.error(`解析${key}失败:`, e); }
                }
                const unwatch = watch(() => this._state[key], (newVal) => {
                    if (newVal) {
                        localStorage.setItem(key, typeof newVal === 'object' ? JSON.stringify(newVal) : newVal);
                    } else {
                        localStorage.removeItem(key);
                    }
                }, { deep: true });
                this._unwatchFns.push(unwatch);
            });
        }
    }

    window.NexusStore = NexusStore;
})();

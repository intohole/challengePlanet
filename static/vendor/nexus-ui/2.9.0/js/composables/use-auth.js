(function() {
    const { computed } = Vue;

    const useAuth = (store) => {
        const isAuthenticated = computed(() => store.get('token') && store.get('user'));
        const currentUser = computed(() => store.get('user'));
        const isAdmin = computed(() => {
            const user = store.get('user');
            return user && (user.role === 'admin' || user.is_admin === true);
        });

        const hasRole = (role) => {
            const user = store.get('user');
            if (!user) return false;
            if (Array.isArray(user.roles)) return user.roles.includes(role);
            return user.role === role;
        };

        const requireAuth = (callback) => {
            if (!isAuthenticated.value) {
                if (window.showToast) window.showToast('请先登录', 'warning');
                return false;
            }
            if (callback) callback();
            return true;
        };

        return { isAuthenticated, currentUser, isAdmin, hasRole, requireAuth };
    };

    window.useAuth = useAuth;
})();

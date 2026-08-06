(function() {
    const { ref } = Vue;

    const toasts = ref([]);

    const NuxToast = {
        name: 'NuxToast',
        setup() {
            return { toasts };
        },
        template: `
            <div class="nux-toast-container" v-if="toasts.length">
                <transition-group name="nux-toast">
                    <div v-for="toast in toasts" :key="toast.id"
                         :class="['nux-toast-item', 'nux-toast-' + toast.type]">
                        <span class="nux-toast-icon">{{ toast.type === 'success' ? '✓' : toast.type === 'error' ? '✕' : toast.type === 'warning' ? '⚠' : 'ℹ' }}</span>
                        <span class="nux-toast-msg">{{ toast.message }}</span>
                    </div>
                </transition-group>
            </div>
        `
    };

    const showToast = (message, type = 'success', duration = 3000) => {
        const id = Date.now() + Math.random();
        toasts.value.push({ id, message, type });
        setTimeout(() => {
            toasts.value = toasts.value.filter(t => t.id !== id);
        }, duration);
    };

    window.NuxToast = NuxToast;
    window.showToast = showToast;
})();

(function() {
    const NuxErrorState = {
        name: 'NuxErrorState',
        props: {
            icon: { type: String, default: '⚠️' },
            title: { type: String, default: '加载失败' },
            message: { type: String, default: '' },
            retryText: { type: String, default: '重试' }
        },
        emits: ['retry'],
        template: `
            <div class="nx-empty nux-error-state">
                <div class="nx-empty-icon">{{ icon }}</div>
                <p class="nx-empty-text" style="font-size: var(--nx-text-base); font-weight: 500; color: var(--nx-text-heading);">{{ title }}</p>
                <p v-if="message" class="nx-empty-text">{{ message }}</p>
                <button v-if="retryText" class="nx-btn nx-btn-primary nx-btn-sm" style="margin-top: var(--nx-space-4);" @click="$emit('retry')">{{ retryText }}</button>
            </div>
        `
    };

    window.NuxErrorState = NuxErrorState;
})();

(function() {
    const NuxEmpty = {
        name: 'NuxEmpty',
        props: {
            icon: { type: String, default: '📭' },
            title: { type: String, default: '暂无数据' },
            description: { type: String, default: '' }
        },
        template: `
            <div class="nx-empty">
                <div class="nx-empty-icon">{{ icon }}</div>
                <p class="nx-empty-text" style="font-size: var(--nx-text-base); font-weight: 500; color: var(--nx-text-heading); margin-bottom: var(--nx-space-2);">{{ title }}</p>
                <p v-if="description" class="nx-empty-text">{{ description }}</p>
            </div>
        `
    };

    window.NuxEmpty = NuxEmpty;
})();

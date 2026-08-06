(function() {
    const NuxSkeleton = {
        name: 'NuxSkeleton',
        props: {
            loading: { type: Boolean, default: true },
            rows: { type: Number, default: 3 },
            avatar: { type: Boolean, default: false }
        },
        template: `
            <div v-if="loading" class="nux-skeleton">
                <div v-if="avatar" class="nux-skeleton-avatar"></div>
                <div class="nux-skeleton-content">
                    <div v-for="i in rows" :key="i" class="nux-skeleton-row" :style="{ width: i === rows ? '60%' : '100%' }"></div>
                </div>
            </div>
            <slot v-else></slot>
        `
    };
    window.NuxSkeleton = NuxSkeleton;
})();

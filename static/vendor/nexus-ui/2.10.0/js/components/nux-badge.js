(function() {
    const NuxBadge = {
        name: 'NuxBadge',
        props: {
            type: { type: String, default: 'default' },
            dot: { type: Boolean, default: false },
            count: { type: Number, default: 0 },
            max: { type: Number, default: 99 }
        },
        computed: {
            displayCount() {
                return this.count > this.max ? `${this.max}+` : this.count;
            }
        },
        template: `
            <span class="nux-badge">
                <slot></slot>
                <sup v-if="dot" :class="['nux-badge-dot', 'nux-badge-' + type]"></sup>
                <sup v-else-if="count > 0" :class="['nux-badge-count', 'nux-badge-' + type]">{{ displayCount }}</sup>
            </span>
        `
    };
    window.NuxBadge = NuxBadge;
})();

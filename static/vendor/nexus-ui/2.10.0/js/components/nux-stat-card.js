(function() {
    const NuxStatCard = {
        name: 'NuxStatCard',
        props: {
            icon: { type: String, default: '' },
            value: { type: [String, Number], default: '0' },
            label: { type: String, default: '' },
            subtext: { type: String, default: '' },
            trend: { type: Number, default: 0 },
            color: { type: String, default: '' }
        },
        computed: {
            trendClass() {
                return this.trend > 0 ? 'nux-stat-trend-up' : this.trend < 0 ? 'nux-stat-trend-down' : '';
            },
            trendText() {
                if (this.trend === 0) return '';
                return this.trend > 0 ? `+${this.trend}%` : `${this.trend}%`;
            }
        },
        template: `
            <div class="nx-card nux-stat-card" :style="color ? '--stat-color: ' + color : ''">
                <div class="nux-stat-icon" v-if="icon">{{ icon }}</div>
                <div class="nux-stat-body">
                    <div class="nux-stat-value">{{ value }}</div>
                    <div class="nux-stat-label" v-if="label">{{ label }}</div>
                    <div class="nux-stat-sub" v-if="subtext">{{ subtext }}</div>
                </div>
                <div v-if="trend !== 0" :class="['nux-stat-trend', trendClass]">{{ trendText }}</div>
            </div>
        `
    };

    window.NuxStatCard = NuxStatCard;
})();

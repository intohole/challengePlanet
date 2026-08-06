(function() {
    var NuxRadarChart = {
        name: 'NuxRadarChart',
        props: {
            labels: { type: Array, default: function() { return []; } },
            datasets: { type: Array, default: function() { return []; } },
            maxValue: { type: Number, default: 100 },
            size: { type: Number, default: 320 },
            showLabels: { type: Boolean, default: true },
            showLegend: { type: Boolean, default: true },
            gridLevels: { type: Number, default: 4 },
            gridColor: { type: String, default: '#e2e8f0' },
            axisColor: { type: String, default: '#cbd5e1' },
            textColor: { type: String, default: '#64748b' }
        },
        data: function() {
            return { ro: null };
        },
        watch: {
            labels: function() { this.$nextTick(this.draw); },
            datasets: function() { this.$nextTick(this.draw); },
            maxValue: function() { this.$nextTick(this.draw); }
        },
        mounted: function() {
            var self = this;
            this.$nextTick(this.draw);
            if (typeof ResizeObserver !== 'undefined') {
                this.ro = new ResizeObserver(function() { self.draw(); });
                this.ro.observe(this.$el);
            }
            window.addEventListener('resize', this.draw);
        },
        beforeUnmount: function() {
            if (this.ro) this.ro.disconnect();
            window.removeEventListener('resize', this.draw);
        },
        methods: {
            draw: function() {
                var canvas = this.$el.querySelector('canvas');
                if (!canvas || typeof window.NuxRadarDraw === 'undefined') return;
                window.NuxRadarDraw.draw(canvas, {
                    labels: this.labels,
                    datasets: this.datasets,
                    maxValue: this.maxValue,
                    size: this.size,
                    showLabels: this.showLabels,
                    showLegend: this.showLegend,
                    gridLevels: this.gridLevels,
                    gridColor: this.gridColor,
                    axisColor: this.axisColor,
                    textColor: this.textColor
                });
            }
        },
        template: '<div class="nux-radar-chart-wrap" style="text-align:center;"><canvas></canvas></div>'
    };

    window.NuxRadarChart = NuxRadarChart;
})();

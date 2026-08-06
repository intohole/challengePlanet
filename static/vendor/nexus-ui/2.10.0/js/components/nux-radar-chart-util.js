(function() {
    var DEFAULT_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

    function hexToRgba(hex, alpha) {
        var h = hex.replace('#', '');
        if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
        var r = parseInt(h.substr(0, 2), 16) || 0;
        var g = parseInt(h.substr(2, 2), 16) || 0;
        var b = parseInt(h.substr(4, 2), 16) || 0;
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function normalizeDatasets(datasets, labels, maxValue) {
        return (datasets || []).map(function(ds, i) {
            var vals = (ds.values || []).map(function(v) {
                return Math.max(0, Math.min(maxValue, Number(v) || 0));
            });
            while (vals.length < labels.length) vals.push(0);
            return {
                label: ds.label || ('数据集' + (i + 1)),
                values: vals.slice(0, labels.length),
                color: ds.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]
            };
        });
    }

    function draw(canvas, options) {
        if (!canvas) return;
        var opts = options || {};
        var labels = opts.labels || [];
        var maxValue = opts.maxValue || 100;
        var datasets = normalizeDatasets(opts.datasets, labels, maxValue);
        var cssSize = opts.size || Math.max(200, Math.min(canvas.parentElement ? canvas.parentElement.clientWidth : 320, 500));
        var showLabels = opts.showLabels !== false;
        var showLegend = opts.showLegend !== false;
        var gridLevels = opts.gridLevels || 4;
        var gridColor = opts.gridColor || '#e2e8f0';
        var axisColor = opts.axisColor || '#cbd5e1';
        var textColor = opts.textColor || '#64748b';

        var dpr = window.devicePixelRatio || 1;
        canvas.style.width = cssSize + 'px';
        canvas.style.height = cssSize + 'px';
        canvas.width = cssSize * dpr;
        canvas.height = cssSize * dpr;
        var ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssSize, cssSize);

        var cx = cssSize / 2;
        var cy = cssSize / 2;
        var labelMargin = showLabels ? 50 : 20;
        var radius = Math.max(20, cssSize / 2 - labelMargin);
        var n = labels.length;
        if (n < 3) {
            ctx.fillStyle = textColor;
            ctx.font = '13px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('至少需要3个维度', cx, cy);
            return;
        }
        var angleStep = (Math.PI * 2) / n;
        var startAngle = -Math.PI / 2;
        var level, i, angle, x, y, r, ratio;

        ctx.strokeStyle = gridColor;
        ctx.lineWidth = 1;
        for (level = 1; level <= gridLevels; level++) {
            r = (radius * level) / gridLevels;
            ctx.beginPath();
            for (i = 0; i < n; i++) {
                angle = startAngle + i * angleStep;
                x = cx + r * Math.cos(angle);
                y = cy + r * Math.sin(angle);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.stroke();
        }
        ctx.strokeStyle = axisColor;
        ctx.lineWidth = 1;
        for (i = 0; i < n; i++) {
            angle = startAngle + i * angleStep;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle));
            ctx.stroke();
        }
        if (showLabels) {
            ctx.fillStyle = textColor;
            ctx.font = '12px -apple-system, sans-serif';
            for (i = 0; i < n; i++) {
                angle = startAngle + i * angleStep;
                x = cx + (radius + 18) * Math.cos(angle);
                y = cy + (radius + 18) * Math.sin(angle);
                var cosA = Math.cos(angle);
                if (cosA > 0.3) ctx.textAlign = 'left';
                else if (cosA < -0.3) ctx.textAlign = 'right';
                else ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(String(labels[i] || ''), x, y);
            }
        }
        datasets.forEach(function(ds) {
            ctx.beginPath();
            ds.values.forEach(function(val, i) {
                ratio = val / maxValue;
                r = radius * Math.max(0, Math.min(1, ratio));
                angle = startAngle + i * angleStep;
                x = cx + r * Math.cos(angle);
                y = cy + r * Math.sin(angle);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.closePath();
            ctx.fillStyle = hexToRgba(ds.color, 0.15);
            ctx.fill();
            ctx.strokeStyle = ds.color;
            ctx.lineWidth = 2;
            ctx.stroke();
            ds.values.forEach(function(val, i) {
                ratio = val / maxValue;
                r = radius * Math.max(0, Math.min(1, ratio));
                angle = startAngle + i * angleStep;
                x = cx + r * Math.cos(angle);
                y = cy + r * Math.sin(angle);
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fillStyle = ds.color;
                ctx.fill();
            });
        });
        if (showLegend && datasets.length) {
            ctx.font = '12px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            datasets.forEach(function(ds, i) {
                y = 14 + i * 18;
                ctx.fillStyle = ds.color;
                ctx.fillRect(10, y - 6, 12, 12);
                ctx.fillStyle = textColor;
                ctx.fillText(ds.label, 28, y);
            });
        }
    }

    window.NuxRadarDraw = { draw: draw, hexToRgba: hexToRgba, normalizeDatasets: normalizeDatasets, DEFAULT_COLORS: DEFAULT_COLORS };
})();

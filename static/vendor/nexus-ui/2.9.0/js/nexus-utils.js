(function() {
    const utils = {
        formatDate(dateString, options = {}) {
            if (!dateString) return '';
            try {
                const date = new Date(dateString);
                if (isNaN(date.getTime())) return '';
                return date.toLocaleString('zh-CN', {
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit',
                    ...options
                });
            } catch (e) { return ''; }
        },

        formatDateShort(dateString) {
            return this.formatDate(dateString, { hour: undefined, minute: undefined });
        },

        formatCurrency(amount) {
            if (amount === undefined || amount === null || isNaN(amount)) return '¥0';
            return '¥' + Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
        },

        formatNumber(num, decimals = 2) {
            if (num === undefined || num === null || isNaN(num)) return '0';
            return Number(num).toLocaleString('zh-CN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
        },

        truncateText(text, maxLength = 100) {
            if (!text) return '';
            if (text.length <= maxLength) return text;
            return text.substring(0, maxLength) + '...';
        },

        debounce(func, wait) {
            let timeout;
            return function(...args) {
                clearTimeout(timeout);
                timeout = setTimeout(() => func.apply(this, args), wait);
            };
        },

        throttle(func, limit) {
            let inThrottle;
            return function(...args) {
                if (!inThrottle) {
                    func.apply(this, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        },

        generateId() {
            if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
                return crypto.randomUUID();
            }
            return Date.now().toString(36) + Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
        },

        deepClone(obj) {
            if (typeof structuredClone === 'function') {
                try { return structuredClone(obj); } catch (e) { }
            }
            return JSON.parse(JSON.stringify(obj));
        },

        downloadFile(content, filename, mimeType = 'text/plain') {
            const blob = new Blob([content], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        },

        formatPhone(phone) {
            if (!phone || phone.length < 7) return phone || '';
            return phone.substring(0, 3) + '****' + phone.substring(phone.length - 4);
        },

        formatMsg(content) {
            if (!content) return '';
            let html = String(content)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
            const codeBlocks = [];
            html = html.replace(/```([\s\S]*?)```/g, (m, code) => {
                codeBlocks.push(code.replace(/^\n/, ''));
                return `\x00CODEBLOCK${codeBlocks.length - 1}\x00`;
            });
            html = html.replace(/`([^`]+)`/g, (m, code) => `<code>${code}</code>`);
            html = html.replace(/\n/g, '<br>');
            codeBlocks.forEach((code, i) => {
                html = html.replace(`\x00CODEBLOCK${i}\x00`, `<pre><code>${code}</code></pre>`);
            });
            return html;
        },

        autoResize(el) {
            if (!el) return;
            el.style.height = 'auto';
            el.style.height = el.scrollHeight + 'px';
        },

        pick(obj, keys) {
            const result = {};
            keys.forEach(key => { if (key in obj) result[key] = obj[key]; });
            return result;
        },

        omit(obj, keys) {
            const result = { ...obj };
            keys.forEach(key => delete result[key]);
            return result;
        },

        setViewportHeight() {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--nx-vh', `${vh}px`);
        },

        escapeHtml(text) {
            if (text === null || text === undefined) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        formatRelativeTime(dateString) {
            if (!dateString) return '';
            const date = new Date(dateString);
            if (isNaN(date.getTime())) return '';
            const now = Date.now();
            const diff = now - date.getTime();
            const seconds = Math.floor(diff / 1000);
            const minutes = Math.floor(seconds / 60);
            const hours = Math.floor(minutes / 60);
            const days = Math.floor(hours / 24);
            if (seconds < 60) return '刚刚';
            if (minutes < 60) return `${minutes}分钟前`;
            if (hours < 24) return `${hours}小时前`;
            if (days < 30) return `${days}天前`;
            return this.formatDateShort(dateString);
        },

        formatDateTime(dateString, options = {}) {
            if (!dateString) return '';
            try {
                const date = new Date(dateString);
                if (isNaN(date.getTime())) return '';
                return date.toLocaleString('zh-CN', {
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit', second: '2-digit',
                    ...options
                });
            } catch (e) { return ''; }
        },

        formatPercent(value, decimals = 1) {
            if (value === undefined || value === null || isNaN(value)) return '0%';
            return (Number(value) * 100).toFixed(decimals) + '%';
        },

        formatChatTime(timeStr) {
            if (!timeStr) return '';
            const date = new Date(timeStr);
            if (isNaN(date.getTime())) return '';
            const now = new Date();
            const isToday = date.getFullYear() === now.getFullYear()
                && date.getMonth() === now.getMonth()
                && date.getDate() === now.getDate();
            const hh = String(date.getHours()).padStart(2, '0');
            const mm = String(date.getMinutes()).padStart(2, '0');
            if (isToday) return `${hh}:${mm}`;
            const M = String(date.getMonth() + 1).padStart(2, '0');
            const D = String(date.getDate()).padStart(2, '0');
            return `${M}/${D} ${hh}:${mm}`;
        },

        formatTime(dateString) {
            return this.formatRelativeTime(dateString);
        },

        getPathPrefix() {
            if (window.PATH_PREFIX) return window.PATH_PREFIX;
            const scripts = document.querySelectorAll('script[src]');
            for (const script of scripts) {
                const src = script.getAttribute('src');
                if (src && src.startsWith('/') && !src.startsWith('//')) {
                    const match = src.match(/^\/([^/]+)\//);
                    if (match && match[1] !== 'static' && match[1] !== 'api') {
                        window.PATH_PREFIX = '/' + match[1];
                        return window.PATH_PREFIX;
                    }
                }
            }
            window.PATH_PREFIX = '';
            return '';
        },

        copyToClipboard(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(text).then(() => true).catch(() => this._copyFallback(text));
            }
            return Promise.resolve(this._copyFallback(text));
        },

        _copyFallback(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            let ok = false;
            try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
            textarea.remove();
            return ok;
        }
    };

    utils.setViewportHeight();
    utils._resizeHandler = utils.debounce(utils.setViewportHeight, 100);
    window.addEventListener('resize', utils._resizeHandler);

    window.NexusUtils = utils;
})();

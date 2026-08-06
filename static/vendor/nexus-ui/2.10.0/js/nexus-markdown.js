(function () {
    'use strict';

    const VERSION = '1.0.0';

    const LIBS = {
        marked: 'https://cdn.jsdmirror.com/npm/marked@12.0.0/marked.min.js',
        dompurify: 'https://cdn.jsdmirror.com/npm/dompurify@3.0.6/dist/purify.min.js',
        highlight: 'https://cdn.bootcdn.net/ajax/libs/highlight.js/11.9.0/highlight.min.js',
        highlightCss: 'https://cdn.bootcdn.net/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css'
    };

    const DEFAULT_ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'code', 'pre', 'span',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'hr',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'a', 'img', 'div', 'del', 'sub', 'sup',
        'details', 'summary', 'figure', 'figcaption',
        'kbd', 'samp', 'var', 'mark', 'input'
    ];

    let libsLoaded = false;
    let libsLoading = null;

    function loadScript(src) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = () => reject(new Error(`load fail: ${src}`));
            document.head.appendChild(script);
        });
    }

    function loadStylesheet(href) {
        return new Promise((resolve) => {
            if (document.querySelector(`link[href="${href}"]`)) { resolve(); return; }
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            link.onload = resolve;
            link.onerror = resolve;
            document.head.appendChild(link);
        });
    }

    async function injectLibs() {
        if (libsLoaded) return true;
        if (libsLoading) return libsLoading;
        libsLoading = (async () => {
            await Promise.all([
                loadScript(LIBS.marked),
                loadScript(LIBS.dompurify),
                loadScript(LIBS.highlight),
                loadStylesheet(LIBS.highlightCss)
            ]).catch(err => console.warn('[NexusMarkdown] lib load fail:', err.message));
            if (window.marked) {
                marked.setOptions({ breaks: true, gfm: true });
            }
            libsLoaded = true;
            return true;
        })();
        return libsLoading;
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function render(text, options) {
        if (!text) return '';
        const opts = options || {};
        if (window.marked && window.DOMPurify) {
            try {
                const raw = marked.parse(text);
                return DOMPurify.sanitize(raw, {
                    ADD_ATTR: ['target', 'rel'],
                    ALLOWED_TAGS: opts.allowTags || DEFAULT_ALLOWED_TAGS
                });
            } catch (e) {
                console.warn('[NexusMarkdown] render fail:', e);
            }
        }
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    async function renderAsync(text, options) {
        await injectLibs();
        return render(text, options);
    }

    function postProcess(container) {
        if (!container) return;
        if (window.hljs) {
            container.querySelectorAll('pre code').forEach(block => {
                if (block.dataset.nxHighlighted) return;
                try {
                    hljs.highlightElement(block);
                    block.dataset.nxHighlighted = '1';
                } catch (e) {}
            });
        }
        container.querySelectorAll('a').forEach(a => {
            if (!a.target) a.target = '_blank';
            if (!a.rel) a.rel = 'noopener noreferrer';
        });
        container.querySelectorAll('pre').forEach(pre => {
            if (pre.querySelector('.nx-md-copy')) return;
            const code = pre.querySelector('code');
            if (!code) return;
            const lang = (code.className.match(/language-(\w+)/) || [])[1] || '';
            if (lang) {
                const tag = document.createElement('span');
                tag.className = 'nx-md-lang';
                tag.textContent = lang;
                pre.appendChild(tag);
            }
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'nx-md-copy';
            btn.textContent = '复制';
            btn.addEventListener('click', () => {
                const text = code.textContent || '';
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(text).then(() => {
                        btn.textContent = '已复制';
                        setTimeout(() => { btn.textContent = '复制'; }, 1500);
                    }).catch(() => {});
                }
            });
            pre.appendChild(btn);
        });
    }

    function renderTo(element, text, options) {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (!el) return;
        el.innerHTML = render(text, options);
        el.classList.add('nx-md');
        postProcess(el);
    }

    async function renderToAsync(element, text, options) {
        await injectLibs();
        renderTo(element, text, options);
    }

    const NexusMarkdown = {
        version: VERSION,
        injectLibs,
        render,
        renderAsync,
        renderTo,
        renderToAsync,
        escapeHtml,
        postProcess,
        DEFAULT_ALLOWED_TAGS
    };

    window.NexusMarkdown = NexusMarkdown;
})();

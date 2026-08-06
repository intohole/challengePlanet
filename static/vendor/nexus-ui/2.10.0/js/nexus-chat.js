(function () {
    'use strict';

    const CHAT_VERSION = '1.1.0';

    function delegateMarkdown(text) {
        if (window.NexusMarkdown && typeof window.NexusMarkdown.render === 'function') {
            return window.NexusMarkdown.render(text);
        }
        if (window.NexusMarkdown && typeof window.NexusMarkdown.escapeHtml === 'function') {
            return window.NexusMarkdown.escapeHtml(text).replace(/\n/g, '<br>');
        }
        return String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/\n/g, '<br>');
    }

    function delegateEscape(str) {
        if (window.NexusMarkdown && typeof window.NexusMarkdown.escapeHtml === 'function') {
            return window.NexusMarkdown.escapeHtml(str);
        }
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    async function delegateInject() {
        if (window.NexusMarkdown && typeof window.NexusMarkdown.injectLibs === 'function') {
            return window.NexusMarkdown.injectLibs();
        }
        return false;
    }

    class ChatController {
        constructor(options) {
            const opts = options || {};
            this.api = opts.api || (window.NexusApi ? new NexusApi() : null);
            this.url = opts.url || '';
            this.body = opts.body || {};
            this.timeout = opts.timeout || 120000;
            this.eventKey = opts.eventKey || 'delta';
            this.contentKey = opts.contentKey || 'content';
            this.doneKey = opts.doneKey || 'done';
            this.onChunk = opts.onChunk || (function () {});
            this.onDone = opts.onDone || (function () {});
            this.onError = opts.onError || (function () {});
            this.onEvent = opts.onEvent || null;
            this.controller = null;
            this.receivedChunks = '';
            this._currentEvent = null;
        }

        get isStreaming() { return this.controller !== null; }

        async start() {
            if (!this.api || !this.url) { this.onError('未配置API或URL'); return; }
            this.receivedChunks = '';
            this.controller = new AbortController();
            const requestId = `chat_${Date.now()}_${Math.random().toString(36).slice(2)}`;
            this.api._registerController(requestId, this.controller);
            const timeoutId = setTimeout(() => this.controller.abort(), this.timeout);
            try {
                const response = await fetch(`${this.api.baseUrl}${this.url}`, {
                    method: 'POST',
                    headers: this.api._buildHeaders({ 'Accept': 'text/event-stream' }),
                    body: JSON.stringify(this.body),
                    signal: this.controller.signal
                });
                if (!response.ok) {
                    let errData;
                    try { errData = await response.json(); } catch (e) { errData = {}; }
                    this.onError(this.api._extractError(errData) || `请求失败 ${response.status}`);
                    return;
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    let newlineIdx;
                    while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
                        const line = buffer.slice(0, newlineIdx).replace(/\r$/, '');
                        buffer = buffer.slice(newlineIdx + 1);
                        if (line.startsWith('event:')) {
                            this._currentEvent = line.slice(6).trim();
                        } else if (line.startsWith('data:')) {
                            const payload = line.slice(5).trim();
                            if (!payload) continue;
                            try { this._handleData(JSON.parse(payload)); }
                            catch (e) {}
                        } else if (line === '') {
                            this._currentEvent = null;
                        }
                    }
                }
                this.onDone(this.receivedChunks);
            } catch (error) {
                if (error.name === 'AbortError') {
                    this.onDone(this.receivedChunks);
                } else {
                    this.onError(error.message || '网络错误');
                }
            } finally {
                clearTimeout(timeoutId);
                this.api.abortControllers.delete(requestId);
                this.controller = null;
                this._currentEvent = null;
            }
        }

        _handleData(data) {
            const event = this._currentEvent || this.eventKey;
            if (this.onEvent) this.onEvent(event, data);
            if (event === 'error') {
                this.onError(data.message || data.error || 'AI处理出错');
                return;
            }
            if (event === this.eventKey || event === 'delta' || event === 'content' || event === 'message') {
                const content = data[this.contentKey] || data.content || data.delta || data.text || data.message;
                if (content) {
                    this.receivedChunks += content;
                    this.onChunk(content, this.receivedChunks);
                }
                if (data[this.doneKey] === true || data.done === true || data.finished === true) {
                    this.controller && this.controller.abort();
                }
            }
        }

        stop() {
            if (this.controller) {
                try { this.controller.abort(); } catch (e) {}
            }
        }
    }

    function createStreamingButton(opts) {
        const options = opts || {};
        const button = options.button;
        const onSend = options.onSend;
        const onStop = options.onStop;
        const streamingClass = options.streamingClass || 'nx-chat-streaming';
        if (!button) return null;
        const sendIcon = button.innerHTML;
        let streaming = false;
        function setStreaming(state) {
            streaming = state;
            button.classList.toggle(streamingClass, state);
            button.innerHTML = state
                ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>'
                : sendIcon;
            button.disabled = false;
            button.setAttribute('aria-label', state ? '停止生成' : '发送');
        }
        button.addEventListener('click', function () {
            if (streaming) { onStop && onStop(); }
            else { onSend && onSend(); }
        });
        return { setStreaming: setStreaming, getStreaming: function () { return streaming; } };
    }

    function renderError(message, onRetry, retryLabel) {
        const label = retryLabel || '重试';
        const errId = `nx-chat-err-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
        const retryBtn = onRetry
            ? `<button type="button" class="nx-chat-retry" data-err-id="${errId}">${delegateEscape(label)}</button>`
            : '';
        return `<div class="nx-chat-error" id="${errId}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>${delegateEscape(message)}</span>
            ${retryBtn}
        </div>`;
    }

    function bindRetry(container, onRetry) {
        if (!container) return;
        const btn = container.querySelector('.nx-chat-retry');
        if (btn) btn.addEventListener('click', onRetry);
    }

    function typingCursor() {
        return '<span class="nx-chat-typing-cursor" aria-hidden="true"></span>';
    }

    const NexusChat = {
        version: CHAT_VERSION,
        injectLibs: delegateInject,
        renderMarkdown: delegateMarkdown,
        escapeHtml: delegateEscape,
        ChatController: ChatController,
        createStreamingButton: createStreamingButton,
        renderError: renderError,
        bindRetry: bindRetry,
        typingCursor: typingCursor
    };

    window.NexusChat = NexusChat;
})();

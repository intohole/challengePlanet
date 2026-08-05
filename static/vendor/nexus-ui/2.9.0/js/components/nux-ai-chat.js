(function () {
    'use strict';

    const { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } = Vue;

    const DEFAULT_FEATURES = {
        stopButton: true,
        streamFallback: true,
        scrollToBottomButton: true,
        smartScroll: true,
        typingIndicator: true,
        messageCopy: true,
        aiTag: true,
        timestamp: false
    };

    const DEFAULT_INPUT = {
        enterToSend: true,
        shiftEnterNewline: true,
        autoResize: true,
        maxLength: 4000,
        rateLimit: 0,
        checkComposing: true,
        maxRows: 6
    };

    const DEFAULT_ROLES = {
        user: { avatar: '🧑', label: '我' },
        assistant: { avatar: '🤖', label: 'AI助手', aiTag: true }
    };

    function scrollToBottomEl(el, smooth) {
        if (!el) return;
        el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
    }

    function isNearBottom(el, threshold) {
        if (!el) return true;
        return el.scrollHeight - el.scrollTop - el.clientHeight < (threshold || 150);
    }

    const NuxAiChat = {
        name: 'NuxAiChat',
        props: {
            messages: { type: Array, default: () => [] },
            apiConfig: { type: Object, default: () => ({}) },
            sendHandler: { type: Function, default: null },
            features: { type: Object, default: () => ({}) },
            inputConfig: { type: Object, default: () => ({}) },
            welcome: { type: Object, default: () => ({}) },
            quickReplies: { type: Array, default: () => [] },
            roles: { type: Object, default: () => ({}) },
            placeholder: { type: String, default: '输入消息，Enter发送，Shift+Enter换行' },
            disabled: { type: Boolean, default: false },
            scrollThreshold: { type: Number, default: 150 },
            streaming: { type: Boolean, default: false }
        },
        emits: ['update:messages', 'send', 'chunk', 'done', 'error', 'stop', 'retry', 'clear', 'stream-start', 'stream-end'],
        setup(props, ctx) {
            const feat = Object.assign({}, DEFAULT_FEATURES, props.features);
            const inputCfg = Object.assign({}, DEFAULT_INPUT, props.inputConfig);
            const roleCfg = Object.assign({}, DEFAULT_ROLES, props.roles);

            const list = reactive(props.messages.slice());
            const input = ref('');
            const isStreaming = ref(false);
            const isError = ref(false);
            const errorMsg = ref('');
            const showScrollBtn = ref(false);
            const newMsgCount = ref(0);
            const isComposing = ref(false);
            const lastSendTime = ref(0);

            const scrollEl = ref(null);
            const inputEl = ref(null);
            const listEl = ref(null);
            let controller = null;
            let rafId = null;
            let pendingContent = '';

            const mergedMessages = computed(() => list);

            function emitMessages() {
                ctx.emit('update:messages', list.slice());
            }

            function autoResize() {
                const el = inputEl.value;
                if (!el || !inputCfg.autoResize) return;
                el.style.height = 'auto';
                const lineHeight = 24;
                const maxH = lineHeight * inputCfg.maxRows;
                el.style.height = Math.min(el.scrollHeight, maxH) + 'px';
            }

            function onScroll() {
                if (!feat.smartScroll) return;
                const near = isNearBottom(scrollEl.value, props.scrollThreshold);
                showScrollBtn.value = !near && list.length > 0;
                if (near) newMsgCount.value = 0;
            }

            function smartScroll(force) {
                if (rafId) cancelAnimationFrame(rafId);
                rafId = requestAnimationFrame(() => {
                    if (!scrollEl.value) return;
                    if (force || !feat.smartScroll || isNearBottom(scrollEl.value, props.scrollThreshold)) {
                        scrollToBottomEl(scrollEl.value, false);
                        showScrollBtn.value = false;
                        newMsgCount.value = 0;
                    } else {
                        newMsgCount.value++;
                    }
                });
            }

            function scrollToBottom() {
                scrollToBottomEl(scrollEl.value, true);
                showScrollBtn.value = false;
                newMsgCount.value = 0;
            }

            function renderMarkdown(text) {
                if (window.NexusMarkdown) return NexusMarkdown.render(text || '');
                return String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;').replace(/\n/g, '<br>');
            }

            function postProcessMd(el) {
                if (window.NexusMarkdown && el) NexusMarkdown.postProcess(el);
            }

            function buildAssistantMsg() {
                return reactive({
                    id: 'a_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
                    role: 'assistant',
                    content: '',
                    streaming: true,
                    error: false,
                    created_at: new Date().toISOString()
                });
            }

            async function defaultSendHandler(content, callbacks) {
                const cfg = props.apiConfig || {};
                if (!cfg.streamUrl) {
                    callbacks.onError(new Error('未配置 apiConfig.streamUrl'));
                    return;
                }
                const api = cfg.apiInstance || (window.NexusApi ? new NexusApi() : null);
                if (!api) {
                    callbacks.onError(new Error('NexusApi 未加载'));
                    return;
                }
                const ctrl = new (window.NexusChat ? NexusChat.ChatController : null)({
                    api: api,
                    url: cfg.streamUrl,
                    body: Object.assign({}, cfg.body || {}, { content: content }),
                    contentKey: cfg.contentKey || 'content',
                    eventKey: cfg.eventKey || 'delta',
                    doneKey: cfg.doneKey || 'done',
                    onChunk: (chunk, full) => callbacks.onChunk(chunk, full),
                    onDone: (full) => callbacks.onDone(full),
                    onError: (err) => callbacks.onError(err)
                });
                callbacks.registerStop(() => ctrl.stop());
                ctrl.start();
            }

            async function send(content) {
                const text = (content !== undefined ? content : input.value).trim();
                if (!text || isStreaming.value || props.disabled) return;

                if (inputCfg.rateLimit > 0) {
                    const now = Date.now();
                    if (now - lastSendTime.value < inputCfg.rateLimit) return;
                    lastSendTime.value = now;
                }

                if (content === undefined) input.value = '';
                autoResize();

                const userMsg = reactive({
                    id: 'u_' + Date.now(),
                    role: 'user',
                    content: text,
                    created_at: new Date().toISOString()
                });
                list.push(userMsg);

                const assistantMsg = buildAssistantMsg();
                list.push(assistantMsg);
                emitMessages();

                ctx.emit('send', text);
                smartScroll(true);

                isStreaming.value = true;
                isError.value = false;
                errorMsg.value = '';
                ctx.emit('stream-start');

                let stopped = false;
                let stopFn = null;

                const callbacks = {
                    onChunk: (chunk, full) => {
                        assistantMsg.content = full;
                        smartScroll(false);
                        ctx.emit('chunk', chunk, full, assistantMsg);
                    },
                    onDone: (full) => {
                        if (full && !assistantMsg.content) assistantMsg.content = full;
                        assistantMsg.streaming = false;
                        finishStream(true, assistantMsg);
                    },
                    onError: (err) => {
                        if (stopped) {
                            assistantMsg.streaming = false;
                            finishStream(true, assistantMsg);
                            return;
                        }
                        if (feat.streamFallback && props.apiConfig.fallbackUrl) {
                            fallbackSync(text, assistantMsg);
                        } else {
                            assistantMsg.streaming = false;
                            assistantMsg.error = true;
                            isError.value = true;
                            errorMsg.value = err && err.message ? err.message : 'AI服务暂时不可用';
                            finishStream(false, assistantMsg, errorMsg.value);
                        }
                    },
                    registerStop: (fn) => { stopFn = fn; }
                };

                try {
                    const handler = props.sendHandler || defaultSendHandler;
                    await handler(text, callbacks);
                } catch (e) {
                    if (!stopped) {
                        assistantMsg.streaming = false;
                        assistantMsg.error = true;
                        isError.value = true;
                        errorMsg.value = e.message || '请求异常';
                        finishStream(false, assistantMsg, errorMsg.value);
                    }
                }

                function finishStream(ok, msg, err) {
                    isStreaming.value = false;
                    ctx.emit('stream-end', ok);
                    if (!ok) ctx.emit('error', err || '未知错误', msg);
                    else ctx.emit('done', msg.content, msg);
                    emitMessages();
                    nextTick(() => {
                        if (msg.content && listEl.value) {
                            const els = listEl.value.querySelectorAll('.nx-ai-chat-msg');
                            const last = els[els.length - 1];
                            if (last) postProcessMd(last.querySelector('.nx-ai-chat-bubble'));
                        }
                    });
                }
            }

            async function fallbackSync(content, assistantMsg) {
                try {
                    const cfg = props.apiConfig;
                    const api = cfg.apiInstance || (window.NexusApi ? new NexusApi() : null);
                    if (!api) throw new Error('NexusApi 未加载');
                    const res = await api.post(cfg.fallbackUrl, Object.assign({}, cfg.body || {}, { content: content }));
                    assistantMsg.content = res.data.content || res.data.answer || res.data.reply || '（无内容）';
                    assistantMsg.streaming = false;
                    isStreaming.value = false;
                    ctx.emit('stream-end', true);
                    ctx.emit('done', assistantMsg.content, assistantMsg);
                    emitMessages();
                    nextTick(() => {
                        if (listEl.value) {
                            const els = listEl.value.querySelectorAll('.nx-ai-chat-msg');
                            const last = els[els.length - 1];
                            if (last) postProcessMd(last.querySelector('.nx-ai-chat-bubble'));
                        }
                    });
                } catch (e) {
                    assistantMsg.streaming = false;
                    assistantMsg.error = true;
                    isError.value = true;
                    errorMsg.value = e.message || '降级同步也失败';
                    isStreaming.value = false;
                    ctx.emit('stream-end', false);
                    ctx.emit('error', errorMsg.value, assistantMsg);
                    emitMessages();
                }
            }

            function stop() {
                if (!isStreaming.value) return;
                if (controller) try { controller.stop(); } catch (e) {}
                if (window.NexusApi) {
                    try { NexusApi.abortAll && NexusApi.abortAll(); } catch (e) {}
                }
                isStreaming.value = false;
                ctx.emit('stop');
                ctx.emit('stream-end', true);
                const last = list[list.length - 1];
                if (last && last.streaming) {
                    last.streaming = false;
                    if (!last.content) last.content = '（已停止生成）';
                }
                emitMessages();
            }

            function retry(msg) {
                const target = msg || (list.length >= 2 ? list[list.length - 2] : null);
                if (!target) return;
                if (list.length > 0) list.pop();
                if (isError.value) {
                    isError.value = false;
                    errorMsg.value = '';
                }
                ctx.emit('retry', target);
                send(target.content);
            }

            function clear() {
                stop();
                list.splice(0, list.length);
                isError.value = false;
                errorMsg.value = '';
                newMsgCount.value = 0;
                showScrollBtn.value = false;
                ctx.emit('clear');
                emitMessages();
            }

            function copyMessage(msg) {
                if (!msg || !msg.content) return;
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(msg.content).then(() => {
                        if (window.NexusUtils && NexusUtils.toast) NexusUtils.toast.success('已复制');
                    }).catch(() => {});
                }
            }

            function onInput() { autoResize(); }
            function onKeydown(e) {
                if (!inputCfg.enterToSend) return;
                if (e.key === 'Enter' && !e.shiftKey && !isComposing.value) {
                    e.preventDefault();
                    send();
                }
            }
            function onCompositionStart() { isComposing.value = true; }
            function onCompositionEnd() { isComposing.value = false; }

            function clickQuickReply(item) {
                if (isStreaming.value || props.disabled) return;
                const val = item.value || item.text;
                input.value = val;
                send(val);
            }

            watch(() => props.messages, (newVal) => {
                if (newVal && newVal.length !== list.length) {
                    list.splice(0, list.length, ...newVal.map(m => reactive(Object.assign({}, m))));
                    nextTick(() => smartScroll(true));
                }
            }, { deep: false });

            onMounted(() => {
                nextTick(() => {
                    if (list.length > 0) scrollToBottomEl(scrollEl.value, false);
                    if (window.NexusMarkdown) NexusMarkdown.injectLibs();
                });
            });

            onBeforeUnmount(() => {
                if (controller) try { controller.stop(); } catch (e) {}
                if (rafId) cancelAnimationFrame(rafId);
            });

            ctx.expose({
                send, stop, clear, retry, copyMessage, scrollToBottom,
                getMessages: () => list.slice(),
                setMessages: (arr) => {
                    list.splice(0, list.length, ...arr.map(m => reactive(Object.assign({}, m))));
                    emitMessages();
                    nextTick(() => scrollToBottomEl(scrollEl.value, false));
                },
                focus: () => { if (inputEl.value) inputEl.value.focus(); }
            });

            return {
                list, input, isStreaming, isError, errorMsg, showScrollBtn, newMsgCount,
                scrollEl, inputEl, listEl, feat, inputCfg, roleCfg,
                renderMarkdown, send, stop, retry, clear, copyMessage, scrollToBottom,
                onScroll, onInput, onKeydown, onCompositionStart, onCompositionEnd,
                clickQuickReply, smartScroll
            };
        },
        template: `
        <div class="nx-ai-chat">
            <div class="nx-ai-chat-messages" ref="scrollEl" @scroll="onScroll">
                <div class="nx-ai-chat-list" ref="listEl">
                    <div v-if="!list.length && !$slots.empty && !$slots.welcome" class="nx-ai-chat-welcome">
                        <div class="nx-ai-chat-welcome-icon">{{ welcome.icon || '👋' }}</div>
                        <h3 class="nx-ai-chat-welcome-title">{{ welcome.title || 'AI助手为您服务' }}</h3>
                        <p class="nx-ai-chat-welcome-desc">{{ welcome.description || '有什么可以帮您的？请输入您的问题~' }}</p>
                        <div v-if="quickReplies.length" class="nx-ai-chat-quick">
                            <button v-for="(q,i) in quickReplies" :key="i" class="nx-ai-chat-quick-btn" @click="clickQuickReply(q)">
                                <span v-if="q.icon" class="nx-ai-chat-quick-icon">{{ q.icon }}</span>
                                <span>{{ q.text }}</span>
                            </button>
                        </div>
                    </div>
                    <slot v-if="!list.length" name="welcome"></slot>
                    <slot v-if="!list.length" name="empty"></slot>

                    <div v-for="m in list" :key="m.id" class="nx-ai-chat-msg" :class="['nx-ai-chat-' + m.role, { 'is-streaming': m.streaming, 'is-error': m.error }]">
                        <div class="nx-ai-chat-avatar">{{ roleCfg[m.role] ? roleCfg[m.role].avatar : '🤖' }}</div>
                        <div class="nx-ai-chat-main">
                            <div class="nx-ai-chat-meta">
                                <span class="nx-ai-chat-name">{{ roleCfg[m.role] ? roleCfg[m.role].label : m.role }}</span>
                                <span v-if="roleCfg[m.role] && roleCfg[m.role].aiTag && feat.aiTag" class="nx-ai-chat-aitag">AI生成</span>
                            </div>
                            <div class="nx-ai-chat-bubble">
                                <slot name="message-before" :msg="m"></slot>
                                <template v-if="m.streaming && !m.content && feat.typingIndicator">
                                    <div class="nx-ai-chat-typing"><span></span><span></span><span></span></div>
                                </template>
                                <template v-else>
                                    <div class="nx-ai-chat-content" v-html="renderMarkdown(m.content)"></div>
                                    <span v-if="m.streaming" class="nx-ai-chat-cursor"></span>
                                </template>
                                <slot name="message-after" :msg="m"></slot>
                            </div>
                            <div v-if="m.error" class="nx-ai-chat-error-bar">
                                <span>{{ errorMsg || m.errorMsg || '生成失败' }}</span>
                                <button class="nx-ai-chat-retry-btn" @click="retry(m)">重试</button>
                            </div>
                            <div v-if="!m.streaming && !m.error && m.content && feat.messageCopy" class="nx-ai-chat-actions">
                                <button class="nx-ai-chat-action-btn" @click="copyMessage(m)">复制</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <transition name="nx-ai-chat-fab">
                <button v-if="showScrollBtn" class="nx-ai-chat-scroll-btn" @click="scrollToBottom">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <span v-if="newMsgCount" class="nx-ai-chat-scroll-badge">{{ newMsgCount }}</span>
                </button>
            </transition>

            <div class="nx-ai-chat-input-wrap">
                <slot name="input-before"></slot>
                <div class="nx-ai-chat-input-row">
                    <textarea
                        ref="inputEl"
                        v-model="input"
                        class="nx-ai-chat-input"
                        :placeholder="placeholder"
                        :disabled="disabled"
                        :maxlength="inputCfg.maxLength"
                        rows="1"
                        @input="onInput"
                        @keydown="onKeydown"
                        @compositionstart="onCompositionStart"
                        @compositionend="onCompositionEnd"
                    ></textarea>
                    <button v-if="isStreaming && feat.stopButton" class="nx-ai-chat-btn nx-ai-chat-stop" @click="stop" aria-label="停止生成">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>
                    </button>
                    <button v-else class="nx-ai-chat-btn nx-ai-chat-send" :disabled="!input.trim() || isStreaming || disabled" @click="send()" aria-label="发送">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
                <slot name="input-after"></slot>
            </div>
        </div>
        `
    };

    window.NuxAiChat = NuxAiChat;
})();

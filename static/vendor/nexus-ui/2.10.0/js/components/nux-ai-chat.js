(function () {
    'use strict';

    const { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } = Vue;

    const H = window.NuxAiChatHelpers;
    const DEFAULT_FEATURES = H.defaultFeatures;
    const DEFAULT_INPUT = H.defaultInput;
    const DEFAULT_ROLES = H.defaultRoles;
    const scrollToBottomEl = H.scrollToBottomEl;
    const isNearBottom = H.isNearBottom;

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
            const elapsed = ref(0);
            let elapsedTimer = null;

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

            function startElapsed() {
                elapsed.value = 0;
                clearInterval(elapsedTimer);
                elapsedTimer = setInterval(() => { elapsed.value++; }, 1000);
            }

            function stopElapsed() {
                clearInterval(elapsedTimer);
                elapsedTimer = null;
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
                startElapsed();

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

                function finishStream(ok, msg, err) {
                    isStreaming.value = false;
                    stopElapsed();
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
                    stopElapsed();
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
                    stopElapsed();
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
                stopElapsed();
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
                stopElapsed();
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
                elapsed, scrollEl, inputEl, listEl, feat, inputCfg, roleCfg,
                renderMarkdown, send, stop, retry, clear, copyMessage, scrollToBottom,
                onScroll, onInput, onKeydown, onCompositionStart, onCompositionEnd,
                clickQuickReply, smartScroll
            };
        },
        template: window.NuxAiChatTemplate
    };

    window.NuxAiChat = NuxAiChat;
})();
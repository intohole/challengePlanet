(function () {
    'use strict';
    window.NuxAiChatTemplate = `
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
        `;
})();
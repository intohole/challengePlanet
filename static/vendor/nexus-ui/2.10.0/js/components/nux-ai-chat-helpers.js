(function () {
    'use strict';
    window.NuxAiChatHelpers = {
        defaultFeatures: {
            stopButton: true,
            streamFallback: true,
            scrollToBottomButton: true,
            smartScroll: true,
            typingIndicator: true,
            messageCopy: true,
            aiTag: true,
            timestamp: false
        },
        defaultInput: {
            enterToSend: true,
            shiftEnterNewline: true,
            autoResize: true,
            maxLength: 4000,
            rateLimit: 0,
            checkComposing: true,
            maxRows: 6
        },
        defaultRoles: {
            user: { avatar: '🧑', label: '我' },
            assistant: { avatar: '🤖', label: 'AI助手', aiTag: true }
        },
        scrollToBottomEl: function (el, smooth) {
            if (!el) return;
            el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
        },
        isNearBottom: function (el, threshold) {
            if (!el) return true;
            return el.scrollHeight - el.scrollTop - el.clientHeight < (threshold || 150);
        }
    };
})();
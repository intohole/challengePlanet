(function() {
    const NuxModal = {
        name: 'NuxModal',
        props: {
            modelValue: { type: Boolean, default: false },
            title: { type: String, default: '' },
            width: { type: String, default: '520px' },
            showFooter: { type: Boolean, default: true },
            closeOnOverlay: { type: Boolean, default: true }
        },
        emits: ['update:modelValue', 'confirm', 'cancel'],
        setup(props, { emit }) {
            const close = () => emit('update:modelValue', false);
            const onOverlayClick = () => { if (props.closeOnOverlay) close(); };
            const confirm = () => { emit('confirm'); close(); };
            const cancel = () => { emit('cancel'); close(); };
            return { close, onOverlayClick, confirm, cancel };
        },
        template: `
            <teleport to="body">
                <transition name="nux-modal">
                    <div v-if="modelValue" class="nx-modal-overlay" @click="onOverlayClick">
                        <div class="nx-modal" :style="{ maxWidth: width }" @click.stop>
                            <div v-if="title" class="nx-modal-title">{{ title }}</div>
                            <slot></slot>
                            <div v-if="showFooter" class="nux-modal-footer">
                                <slot name="footer">
                                    <button class="nx-btn nx-btn-ghost" @click="cancel">取消</button>
                                    <button class="nx-btn nx-btn-primary" @click="confirm">确定</button>
                                </slot>
                            </div>
                        </div>
                    </div>
                </transition>
            </teleport>
        `
    };

    window.NuxModal = NuxModal;
})();

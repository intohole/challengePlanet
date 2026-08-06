(function() {
    const NuxDrawer = {
        name: 'NuxDrawer',
        props: {
            modelValue: { type: Boolean, default: false },
            side: { type: String, default: 'left' },
            width: { type: String, default: '280px' }
        },
        emits: ['update:modelValue'],
        setup(props, { emit }) {
            const close = () => emit('update:modelValue', false);
            return { close };
        },
        template: `
            <teleport to="body">
                <transition name="nux-drawer-overlay">
                    <div v-if="modelValue" class="nx-drawer-overlay" :class="{'open': modelValue}" @click="close"></div>
                </transition>
                <transition :name="side === 'right' ? 'nux-drawer-right' : 'nux-drawer-left'">
                    <div v-if="modelValue"
                         :class="['nx-drawer', side === 'right' ? 'nx-drawer-right' : '']"
                         :style="{ width: width, maxWidth: '85vw', transform: modelValue ? 'translateX(0)' : '' }">
                        <slot></slot>
                    </div>
                </transition>
            </teleport>
        `
    };

    window.NuxDrawer = NuxDrawer;
})();

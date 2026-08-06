(function() {
    const NuxTabGroup = {
        name: 'NuxTabGroup',
        props: {
            modelValue: { type: [String, Number], default: '' },
            tabs: { type: Array, default: () => [] }
        },
        emits: ['update:modelValue'],
        setup(props, { emit }) {
            const select = (key) => emit('update:modelValue', key);
            return { select };
        },
        template: `
            <div class="nux-tab-group">
                <button v-for="tab in tabs" :key="tab.key"
                        :class="['nux-tab-item', { active: modelValue === tab.key }]"
                        @click="select(tab.key)">
                    <span v-if="tab.icon" class="nux-tab-icon">{{ tab.icon }}</span>
                    {{ tab.label }}
                </button>
            </div>
        `
    };

    window.NuxTabGroup = NuxTabGroup;
})();

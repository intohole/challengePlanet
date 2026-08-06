(function() {
    const NuxFormGroup = {
        name: 'NuxFormGroup',
        props: {
            label: { type: String, default: '' },
            required: { type: Boolean, default: false },
            error: { type: String, default: '' },
            hint: { type: String, default: '' },
            horizontal: { type: Boolean, default: false }
        },
        template: `
            <div :class="['nux-form-group', { 'nux-form-horizontal': horizontal, 'nux-form-error': error }]">
                <label v-if="label" class="nux-form-label">
                    {{ label }}
                    <span v-if="required" class="nux-form-required">*</span>
                </label>
                <div class="nux-form-content">
                    <slot></slot>
                    <p v-if="error" class="nux-form-error-text">{{ error }}</p>
                    <p v-else-if="hint" class="nux-form-hint">{{ hint }}</p>
                </div>
            </div>
        `
    };
    window.NuxFormGroup = NuxFormGroup;
})();

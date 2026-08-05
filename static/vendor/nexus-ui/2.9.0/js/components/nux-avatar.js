(function() {
    const NuxAvatar = {
        name: 'NuxAvatar',
        props: {
            src: { type: String, default: '' },
            name: { type: String, default: '' },
            size: { type: String, default: 'md' },
            shape: { type: String, default: 'circle' }
        },
        computed: {
            initial() {
                return this.name ? this.name.charAt(0).toUpperCase() : '?';
            },
            sizeClass() {
                return `nux-avatar-${this.size}`;
            }
        },
        template: `
            <span :class="['nux-avatar', sizeClass, shape === 'square' ? 'nux-avatar-square' : '']">
                <img v-if="src" :src="src" :alt="name" class="nux-avatar-img">
                <span v-else class="nux-avatar-initial">{{ initial }}</span>
            </span>
        `
    };
    window.NuxAvatar = NuxAvatar;
})();

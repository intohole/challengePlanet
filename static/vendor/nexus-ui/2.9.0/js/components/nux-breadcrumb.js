(function() {
    const NuxBreadcrumb = {
        name: 'NuxBreadcrumb',
        props: {
            items: { type: Array, default: () => [] }
        },
        template: `
            <nav class="nux-breadcrumb">
                <template v-for="(item, i) in items" :key="i">
                    <span v-if="i > 0" class="nux-breadcrumb-sep">/</span>
                    <a v-if="item.path && i < items.length - 1" :href="item.path" class="nux-breadcrumb-link">{{ item.label }}</a>
                    <span v-else :class="['nux-breadcrumb-text', { active: i === items.length - 1 }]">{{ item.label }}</span>
                </template>
            </nav>
        `
    };

    window.NuxBreadcrumb = NuxBreadcrumb;
})();

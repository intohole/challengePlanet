(function() {
    const NuxLayoutSidebar = {
        name: 'NuxLayoutSidebar',
        props: {
            sidebarWidth: { type: String, default: '240px' },
            headerHeight: { type: String, default: '56px' },
            appName: { type: String, default: '' },
            appIcon: { type: String, default: '' },
            themeClass: { type: String, default: '' },
            menuItems: { type: Array, default: () => [] },
            currentPath: { type: String, default: '' }
        },
        emits: ['navigate'],
        setup(props, { emit }) {
            const { isMobile, mobileMenuOpen, toggleMenu, closeMenu } = useMobile();
            return { isMobile, mobileMenuOpen, toggleMenu, closeMenu };
        },
        template: `
            <div :class="['nux-layout-sidebar', themeClass]">
                <header class="nux-layout-header">
                    <button class="nx-hamburger nx-show-mobile" @click="toggleMenu" :class="{'open': mobileMenuOpen}">
                        <span class="nx-hamburger-inner">
                            <span class="nx-hamburger-line"></span>
                            <span class="nx-hamburger-line"></span>
                            <span class="nx-hamburger-line"></span>
                        </span>
                    </button>
                    <div class="nux-layout-brand" v-if="appIcon || appName">
                        <span v-if="appIcon" class="nux-layout-brand-icon">{{ appIcon }}</span>
                        <span v-if="appName" class="nux-layout-brand-name">{{ appName }}</span>
                    </div>
                    <div class="nux-layout-header-actions">
                        <slot name="header-actions"></slot>
                    </div>
                </header>
                <div class="nx-drawer-overlay" :class="{'open': mobileMenuOpen && isMobile}" @click="closeMenu"></div>
                <aside :class="['nux-layout-aside', {'mobile-open': mobileMenuOpen && isMobile}]"
                       :style="{ width: sidebarWidth }">
                    <nav class="nux-layout-nav">
                        <slot name="sidebar">
                            <a v-for="item in menuItems" :key="item.path"
                               :class="['nux-layout-nav-item', { active: currentPath === item.path }]"
                               :href="item.path"
                               @click.prevent="emit('navigate', item.path)">
                                <span v-if="item.icon" class="nux-layout-nav-icon">{{ item.icon }}</span>
                                <span>{{ item.label }}</span>
                            </a>
                        </slot>
                    </nav>
                </aside>
                <main class="nux-layout-main">
                    <slot></slot>
                </main>
            </div>
        `
    };

    window.NuxLayoutSidebar = NuxLayoutSidebar;
})();

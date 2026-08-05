(function() {
    const NuxLayoutTopNav = {
        name: 'NuxLayoutTopNav',
        props: {
            headerHeight: { type: String, default: '56px' },
            appName: { type: String, default: '' },
            appIcon: { type: String, default: '' },
            themeClass: { type: String, default: '' },
            navItems: { type: Array, default: () => [] },
            currentPath: { type: String, default: '' }
        },
        emits: ['navigate'],
        setup(props, { emit }) {
            const { isMobile, mobileMenuOpen, toggleMenu, closeMenu } = useMobile();
            return { isMobile, mobileMenuOpen, toggleMenu, closeMenu };
        },
        template: `
            <div :class="['nux-layout-topnav', themeClass]">
                <header class="nux-layout-header" :style="{ height: headerHeight }">
                    <div class="nux-layout-brand" v-if="appIcon || appName">
                        <span v-if="appIcon" class="nux-layout-brand-icon">{{ appIcon }}</span>
                        <span v-if="appName" class="nux-layout-brand-name">{{ appName }}</span>
                    </div>
                    <nav class="nux-layout-topnav-nav nx-hide-mobile">
                        <a v-for="item in navItems" :key="item.path"
                           :class="['nux-layout-topnav-item', { active: currentPath === item.path }]"
                           :href="item.path"
                           @click.prevent="emit('navigate', item.path)">
                            <span v-if="item.icon" class="nux-layout-nav-icon">{{ item.icon }}</span>
                            <span>{{ item.label }}</span>
                        </a>
                    </nav>
                    <div class="nux-layout-header-actions">
                        <slot name="header-actions"></slot>
                    </div>
                    <button class="nx-hamburger nx-show-mobile" @click="toggleMenu" :class="{'open': mobileMenuOpen}">
                        <span class="nx-hamburger-inner">
                            <span class="nx-hamburger-line"></span>
                            <span class="nx-hamburger-line"></span>
                            <span class="nx-hamburger-line"></span>
                        </span>
                    </button>
                </header>
                <div class="nx-drawer-overlay" :class="{'open': mobileMenuOpen && isMobile}" @click="closeMenu"></div>
                <div :class="['nux-layout-topnav-drawer', {'open': mobileMenuOpen && isMobile}]">
                    <a v-for="item in navItems" :key="item.path"
                       :class="['nux-layout-nav-item', { active: currentPath === item.path }]"
                       :href="item.path"
                       @click.prevent="emit('navigate', item.path); closeMenu()">
                        <span v-if="item.icon" class="nux-layout-nav-icon">{{ item.icon }}</span>
                        <span>{{ item.label }}</span>
                    </a>
                </div>
                <main class="nux-layout-main" :style="{ paddingTop: headerHeight }">
                    <slot></slot>
                </main>
            </div>
        `
    };

    window.NuxLayoutTopNav = NuxLayoutTopNav;
})();

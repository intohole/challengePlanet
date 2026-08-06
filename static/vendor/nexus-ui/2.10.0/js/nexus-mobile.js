(function() {
    function init() {
        var sidebar = document.querySelector('.sidebar, .nx-sidebar');
        if (!sidebar) return;

        if (sidebar.dataset.nxMobileInit === '1') return;
        sidebar.dataset.nxMobileInit = '1';

        var overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay nx-drawer-overlay';
        overlay.style.display = 'none';
        document.body.appendChild(overlay);

        var hamburger = document.createElement('button');
        hamburger.className = 'mobile-menu-btn nx-hamburger';
        hamburger.style.display = 'none';
        hamburger.innerHTML = '<span class="nx-hamburger-inner"><span class="nx-hamburger-line"></span><span class="nx-hamburger-line"></span><span class="nx-hamburger-line"></span></span>';
        hamburger.setAttribute('aria-label', '菜单');

        var topbar = document.querySelector('.topbar, .nx-nav');
        if (topbar) {
            topbar.insertBefore(hamburger, topbar.firstChild);
        } else {
            sidebar.parentNode.insertBefore(hamburger, sidebar);
        }

        function toggleSidebar() {
            sidebar.classList.toggle('sidebar-open');
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
            hamburger.classList.toggle('open');
            overlay.style.display = overlay.classList.contains('active') ? 'block' : 'none';
        }

        hamburger.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleSidebar();
        });

        overlay.addEventListener('click', function() {
            toggleSidebar();
        });

        var navItems = sidebar.querySelectorAll('.nav-item, .nx-sidebar-item');
        navItems.forEach(function(item) {
            item.addEventListener('click', function() {
                if (window.innerWidth <= 768 && sidebar.classList.contains('sidebar-open')) {
                    toggleSidebar();
                }
            });
        });

        function checkMobile() {
            var isMobile = window.innerWidth <= 768;
            hamburger.style.display = isMobile ? 'inline-flex' : 'none';
            if (!isMobile) {
                sidebar.classList.remove('sidebar-open', 'open');
                overlay.classList.remove('active');
                overlay.style.display = 'none';
            }
        }

        checkMobile();
        window.addEventListener('resize', checkMobile);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

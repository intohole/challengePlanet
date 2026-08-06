(function() {
    const { ref, watch, onMounted } = Vue;

    const useTheme = (options = {}) => {
        const storageKey = options.storageKey || 'nx-theme';
        const isDark = ref(false);

        const applyTheme = (dark) => {
            document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
            document.documentElement.classList.toggle('light-mode', !dark);
            isDark.value = dark;
        };

        const toggleTheme = () => applyTheme(!isDark.value);

        onMounted(() => {
            const saved = localStorage.getItem(storageKey);
            applyTheme(saved === 'dark');
        });

        watch(isDark, (val) => localStorage.setItem(storageKey, val ? 'dark' : 'light'));

        return { isDark, toggleTheme, applyTheme };
    };

    window.useTheme = useTheme;
})();

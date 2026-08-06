(function() {
    const { ref, computed } = Vue;

    const useSearch = (options = {}) => {
        const keyword = ref('');
        const isSearchMode = computed(() => keyword.value.trim().length > 0);
        const searchFn = options.searchFn || null;

        const doSearch = async (term) => {
            if (term !== undefined) keyword.value = term;
            if (searchFn) return searchFn(keyword.value.trim());
        };

        const clearSearch = () => {
            keyword.value = '';
            if (options.onClear) options.onClear();
        };

        return { keyword, isSearchMode, doSearch, clearSearch };
    };

    window.useSearch = useSearch;
})();

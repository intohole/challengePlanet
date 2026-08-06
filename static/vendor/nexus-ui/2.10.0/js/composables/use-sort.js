(function() {
    const { ref, computed } = Vue;

    const useSort = (options = {}) => {
        const sortField = ref(options.defaultField || 'updated_at');
        const sortOrder = ref(options.defaultOrder || 'desc');

        const toggleSort = (field) => {
            if (sortField.value === field) {
                sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
            } else {
                sortField.value = field;
                sortOrder.value = 'asc';
            }
        };

        const sortList = (list) => {
            if (!list || !Array.isArray(list)) return list;
            return [...list].sort((a, b) => {
                const va = a[sortField.value];
                const vb = b[sortField.value];
                if (va == null && vb == null) return 0;
                if (va == null) return 1;
                if (vb == null) return -1;
                let cmp = 0;
                if (typeof va === 'string') cmp = va.localeCompare(vb, 'zh-CN');
                else cmp = va > vb ? 1 : va < vb ? -1 : 0;
                return sortOrder.value === 'asc' ? cmp : -cmp;
            });
        };

        return { sortField, sortOrder, toggleSort, sortList };
    };

    window.useSort = useSort;
})();

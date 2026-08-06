(function() {
    const { reactive, computed } = Vue;

    const usePagination = (options = {}) => {
        const pagination = reactive({
            page: options.defaultPage || 1,
            pageSize: options.pageSize || 20,
            total: 0
        });

        const totalPages = computed(() => Math.max(1, Math.ceil(pagination.total / pagination.pageSize)));
        const hasNext = computed(() => pagination.page < totalPages.value);
        const hasPrev = computed(() => pagination.page > 1);

        const nextPage = () => { if (hasNext.value) pagination.page++; };
        const prevPage = () => { if (hasPrev.value) pagination.page--; };
        const goToPage = (n) => { const p = Math.max(1, Math.min(n, totalPages.value)); pagination.page = p; };
        const setTotal = (t) => { pagination.total = t; if (pagination.page > totalPages.value) pagination.page = totalPages.value; };
        const reset = () => { pagination.page = 1; pagination.total = 0; };

        return { pagination, totalPages, hasNext, hasPrev, nextPage, prevPage, goToPage, setTotal, reset };
    };

    window.usePagination = usePagination;
})();

(function() {
    const { ref, reactive, computed } = Vue;

    function useCrud(config) {
        if (!config) throw new Error('useCrud: config is required');
        const crudClient = config.crud || (window.createNexusCrud ? createNexusCrud(config) : null);
        if (!crudClient) throw new Error('useCrud: config.crud or createNexusCrud factory required');
        const idField = config.idField || crudClient.idField || 'id';
        const defaultPageSize = config.defaultPageSize || 20;

        const items = ref([]);
        const total = ref(0);
        const loading = ref(false);
        const error = ref(null);
        const detail = ref(null);
        const detailLoading = ref(false);
        const lastParams = ref(null);

        const pagination = reactive({
            page: config.defaultPage || 1,
            pageSize: defaultPageSize
        });

        const search = ref('');
        const sortField = ref(config.defaultSortField || '');
        const sortOrder = ref(config.defaultSortOrder || 'desc');
        const filters = ref({});

        const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pagination.pageSize)));
        const hasNext = computed(() => pagination.page < totalPages.value);
        const hasPrev = computed(() => pagination.page > 1);
        const isEmpty = computed(() => !loading.value && items.value.length === 0);

        function _buildOptions() {
            const opts = {
                page: pagination.page,
                pageSize: pagination.pageSize
            };
            if (search.value) opts.search = search.value;
            if (sortField.value) {
                opts.sortField = sortField.value;
                opts.sortOrder = sortOrder.value;
            }
            if (Object.keys(filters.value).length) opts.filters = { ...filters.value };
            return opts;
        }

        async function fetchList(options = {}) {
            loading.value = true;
            error.value = null;
            const listOpts = Object.assign(_buildOptions(), options);
            lastParams.value = listOpts;
            try {
                const result = await crudClient.list(listOpts);
                if (result && Array.isArray(result.items)) {
                    items.value = result.items;
                    total.value = result.total !== undefined ? result.total : result.items.length;
                } else if (Array.isArray(result)) {
                    items.value = result;
                    total.value = result.length;
                } else {
                    items.value = [];
                    total.value = 0;
                }
                return result;
            } catch (e) {
                error.value = e.message || '加载失败';
                if (config.onError) config.onError(e, 'list');
                throw e;
            } finally {
                loading.value = false;
            }
        }

        async function fetchDetail(id) {
            detailLoading.value = true;
            try {
                detail.value = await crudClient.get(id);
                return detail.value;
            } catch (e) {
                error.value = e.message || '加载详情失败';
                if (config.onError) config.onError(e, 'detail');
                throw e;
            } finally {
                detailLoading.value = false;
            }
        }

        async function create(data, options = {}) {
            const result = await crudClient.create(data, options);
            if (config.onCreated) config.onCreated(result);
            if (config.refreshAfterMutation !== false) {
                await fetchList();
            }
            return result;
        }

        async function update(id, data, options = {}) {
            const result = await crudClient.update(id, data, options);
            if (config.onUpdated) config.onUpdated(result, id);
            const idx = items.value.findIndex(item => item[idField] === id);
            if (idx !== -1) items.value[idx] = Object.assign({}, items.value[idx], data, result);
            if (detail.value && detail.value[idField] === id) {
                detail.value = Object.assign({}, detail.value, data, result);
            }
            return result;
        }

        async function remove(id, options = {}) {
            const result = await crudClient.remove(id, options);
            if (config.onRemoved) config.onRemoved(id);
            items.value = items.value.filter(item => item[idField] !== id);
            total.value = Math.max(0, total.value - 1);
            if (pagination.page > totalPages.value && pagination.page > 1) {
                pagination.page = totalPages.value;
            }
            return result;
        }

        async function batchRemove(ids) {
            if (!Array.isArray(ids) || ids.length === 0) return [];
            const results = await crudClient.batchRemove(ids);
            if (config.onRemoved) ids.forEach(id => config.onRemoved(id));
            const idSet = new Set(ids);
            items.value = items.value.filter(item => !idSet.has(item[idField]));
            total.value = Math.max(0, total.value - ids.length);
            return results;
        }

        function goToPage(page) {
            const p = Math.max(1, Math.min(page, totalPages.value));
            if (p === pagination.page) return Promise.resolve();
            pagination.page = p;
            return fetchList();
        }

        function nextPage() {
            if (!hasNext.value) return Promise.resolve();
            pagination.page++;
            return fetchList();
        }

        function prevPage() {
            if (!hasPrev.value) return Promise.resolve();
            pagination.page--;
            return fetchList();
        }

        function setPageSize(size) {
            pagination.pageSize = size;
            pagination.page = 1;
            return fetchList();
        }

        function doSearch(keyword) {
            search.value = keyword || '';
            pagination.page = 1;
            return fetchList();
        }

        function clearSearch() {
            search.value = '';
            pagination.page = 1;
            return fetchList();
        }

        function toggleSort(field) {
            if (!field) return Promise.resolve();
            if (sortField.value === field) {
                sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
            } else {
                sortField.value = field;
                sortOrder.value = 'asc';
            }
            pagination.page = 1;
            return fetchList();
        }

        function setSort(field, order) {
            sortField.value = field || '';
            sortOrder.value = order || 'desc';
            pagination.page = 1;
            return fetchList();
        }

        function setFilter(key, value) {
            if (value === undefined || value === null || value === '') {
                const next = Object.assign({}, filters.value);
                delete next[key];
                filters.value = next;
            } else {
                filters.value = Object.assign({}, filters.value, { [key]: value });
            }
            pagination.page = 1;
            return fetchList();
        }

        function setFilters(obj) {
            filters.value = obj ? { ...obj } : {};
            pagination.page = 1;
            return fetchList();
        }

        function clearFilters() {
            filters.value = {};
            pagination.page = 1;
            return fetchList();
        }

        function refresh() {
            return fetchList();
        }

        function reset() {
            items.value = [];
            total.value = 0;
            error.value = null;
            detail.value = null;
            pagination.page = 1;
            pagination.pageSize = defaultPageSize;
            search.value = '';
            sortField.value = config.defaultSortField || '';
            sortOrder.value = config.defaultSortOrder || 'desc';
            filters.value = {};
        }

        if (config.autoLoad && typeof Vue.onMounted === 'function') {
            Vue.onMounted(() => { fetchList().catch(() => {}); });
        }

        return {
            crud: crudClient,
            items, total, loading, error, detail, detailLoading, lastParams,
            pagination, totalPages, hasNext, hasPrev, isEmpty,
            search, sortField, sortOrder, filters,
            fetchList, fetchDetail, create, update, remove, batchRemove,
            goToPage, nextPage, prevPage, setPageSize,
            doSearch, clearSearch, toggleSort, setSort,
            setFilter, setFilters, clearFilters,
            refresh, reset
        };
    }

    window.useCrud = useCrud;
})();

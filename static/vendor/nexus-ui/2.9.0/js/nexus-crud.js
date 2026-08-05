(function() {
    const DEFAULT_PARAM_NAMES = {
        page: 'page',
        pageSize: 'page_size',
        search: 'q',
        sort: 'sort_by',
        sortOrder: 'sort_order'
    };

    function _isObj(v) { return v && typeof v === 'object' && !Array.isArray(v); }

    function _buildParams(options, paramNames) {
        const params = {};
        if (options.page !== undefined && options.page !== null) params[paramNames.page] = options.page;
        if (options.pageSize !== undefined && options.pageSize !== null) params[paramNames.pageSize] = options.pageSize;
        if (options.search) params[paramNames.search] = options.search;
        if (options.sortField) {
            params[paramNames.sort] = options.sortField;
            if (options.sortOrder) params[paramNames.sortOrder] = options.sortOrder;
        }
        if (_isObj(options.filters)) Object.assign(params, options.filters);
        if (_isObj(options.extra)) Object.assign(params, options.extra);
        return params;
    }

    function _defaultListAdapter(resp) {
        if (Array.isArray(resp)) return { items: resp, total: resp.length };
        if (Array.isArray(resp.items)) return { items: resp.items, total: resp.total !== undefined ? resp.total : resp.items.length };
        if (Array.isArray(resp.data)) return { items: resp.data, total: resp.total !== undefined ? resp.total : resp.data.length };
        if (resp.data && Array.isArray(resp.data.items)) return { items: resp.data.items, total: resp.data.total !== undefined ? resp.data.total : resp.data.items.length };
        if (resp.list && Array.isArray(resp.list)) return { items: resp.list, total: resp.total !== undefined ? resp.total : resp.list.length };
        if (resp.results && Array.isArray(resp.results)) return { items: resp.results, total: resp.count !== undefined ? resp.count : resp.results.length };
        return { items: [], total: 0 };
    }

    function _defaultItemAdapter(resp) {
        if (resp && resp.data && !_isObj(resp.data)) return resp.data;
        return resp;
    }

    function createNexusCrud(config) {
        if (!config || !config.api) throw new Error('createNexusCrud: config.api is required');
        if (!config.basePath) throw new Error('createNexusCrud: config.basePath is required');
        const api = config.api;
        const basePath = config.basePath.replace(/\/$/, '');
        const idField = config.idField || 'id';
        const paramNames = Object.assign({}, DEFAULT_PARAM_NAMES, config.paramNames || {});
        const listAdapter = config.listAdapter || _defaultListAdapter;
        const itemAdapter = config.itemAdapter || _defaultItemAdapter;
        const idPathParam = config.idPathParam || ':id';

        function _idUrl(id) {
            return `${basePath}/${encodeURIComponent(String(id))}`;
        }

        function list(options = {}) {
            const params = _buildParams(options, paramNames);
            return api.get(basePath, params).then(listAdapter);
        }

        function listRaw(options = {}) {
            const params = _buildParams(options, paramNames);
            return api.get(basePath, params);
        }

        function get(id, options = {}) {
            const url = _idUrl(id);
            if (options.params && Object.keys(options.params).length) {
                return api.get(url, options.params).then(itemAdapter);
            }
            return api.get(url).then(itemAdapter);
        }

        function create(data, options = {}) {
            if (options.query && Object.keys(options.query).length) {
                const qs = new URLSearchParams(options.query).toString();
                return api.post(`${basePath}${qs ? '?' + qs : ''}`, data).then(itemAdapter);
            }
            return api.post(basePath, data).then(itemAdapter);
        }

        function update(id, data, options = {}) {
            const url = _idUrl(id);
            if (options.method === 'PATCH' && typeof api.patch === 'function') {
                return api.patch(url, data).then(itemAdapter);
            }
            return api.put(url, data).then(itemAdapter);
        }

        function remove(id, options = {}) {
            const url = _idUrl(id);
            if (options.query && Object.keys(options.query).length) {
                const qs = new URLSearchParams(options.query).toString();
                return api.delete(`${url}${qs ? '?' + qs : ''}`);
            }
            return api.delete(url);
        }

        function batchRemove(ids) {
            if (!Array.isArray(ids)) ids = [ids];
            return Promise.all(ids.map(id => api.delete(_idUrl(id))));
        }

        function listPaged(page, pageSize, extra = {}) {
            return list({ page, pageSize, ...extra });
        }

        function search(keyword, extra = {}) {
            return list({ search: keyword, ...extra });
        }

        function sortBy(field, order = 'desc', extra = {}) {
            return list({ sortField: field, sortOrder: order, ...extra });
        }

        function sub(resource, id) {
            const subPath = id !== undefined ? `${_idUrl(id)}/${resource}` : `${basePath}/${resource}`;
            return createNexusCrud({
                api,
                basePath: subPath,
                idField,
                paramNames,
                listAdapter,
                itemAdapter,
                idPathParam
            });
        }

        function action(name, options = {}) {
            const method = (options.method || 'POST').toUpperCase();
            const url = options.onCollection ? `${basePath}/${name}` : `${basePath}/${idPathParam}/${name}`;
            const finalUrl = url.replace(idPathParam, options.id !== undefined ? encodeURIComponent(String(options.id)) : '');
            const data = options.data || {};
            if (method === 'GET') return api.get(finalUrl, options.params || {});
            if (method === 'DELETE') return api.delete(finalUrl);
            if (method === 'PUT') return api.put(finalUrl, data);
            return api.post(finalUrl, data);
        }

        return {
            list, listRaw, get, create, update, remove, batchRemove,
            listPaged, search, sortBy, sub, action,
            basePath, idField, paramNames
        };
    }

    window.createNexusCrud = createNexusCrud;
})();

(function() {
    const DEFAULT_BASE_URL = (window.PATH_PREFIX || '') + '/api';
    const MAX_RETRY = 3;
    const MAX_ABORT_CONTROLLERS = 100;
    const BASE_DELAY = 1000;
    const MAX_DELAY = 30000;
    const ApiError = window.NexusApiError || Error;
    const NET_PATTERNS = ['Failed to fetch', 'NetworkError', 'Network request failed', 'Load failed'];

    function _isNetworkErr(err) {
        if (!err) return false;
        if (err.isNetwork === true) return true;
        const msg = err.message || '';
        return NET_PATTERNS.some(p => msg.includes(p));
    }

    class NexusApi {
        constructor(config = {}) {
            this.baseUrl = config.baseUrl !== undefined ? config.baseUrl : DEFAULT_BASE_URL;
            this.maxRetry = config.maxRetry || MAX_RETRY;
            this.tokenKey = config.tokenKey || 'token';
            this.userKey = config.userKey || 'user';
            this.refreshTokenKey = config.refreshTokenKey || null;
            this.refreshUrl = config.refreshUrl || null;
            this.refreshMethod = config.refreshMethod || 'POST';
            this.refreshBodyBuilder = config.refreshBodyBuilder || null;
            this.onUnauthorized = config.onUnauthorized || null;
            this.onRefreshSuccess = config.onRefreshSuccess || null;
            this.onError = config.onError || null;
            this.timeout = config.timeout || 30000;
            this.responseAdapter = config.responseAdapter || null;
            this.storage = config.storage || localStorage;
            this.abortControllers = new Map();
            this._requestCounter = 0;
            this._refreshPromise = null;
        }

        _generateRequestId(url) {
            this._requestCounter = (this._requestCounter + 1) % Number.MAX_SAFE_INTEGER;
            if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return `${url}_${crypto.randomUUID()}`;
            return `${url}_${Date.now()}_${this._requestCounter}_${Math.random().toString(36).substring(2)}`;
        }

        _registerController(requestId, controller) {
            if (this.abortControllers.size >= MAX_ABORT_CONTROLLERS) {
                const oldestKey = this.abortControllers.keys().next().value;
                try { this.abortControllers.get(oldestKey).abort(); } catch (e) {}
                this.abortControllers.delete(oldestKey);
            }
            this.abortControllers.set(requestId, controller);
        }

        _getToken() {
            try { return this.storage.getItem(this.tokenKey) || ''; } catch (e) { return ''; }
        }

        _setToken(token) {
            try { this.storage.setItem(this.tokenKey, token); } catch (e) {}
        }

        _getRefreshToken() {
            if (!this.refreshTokenKey) return '';
            try { return this.storage.getItem(this.refreshTokenKey) || ''; } catch (e) { return ''; }
        }

        _setRefreshToken(token) {
            if (!this.refreshTokenKey) return;
            try { this.storage.setItem(this.refreshTokenKey, token); } catch (e) {}
        }

        _clearAuth() {
            try {
                this.storage.removeItem(this.tokenKey);
                this.storage.removeItem(this.userKey);
                if (this.refreshTokenKey) this.storage.removeItem(this.refreshTokenKey);
            } catch (e) {}
        }

        _buildHeaders(extra) {
            const token = this._getToken();
            return {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` }),
                ...extra
            };
        }

        async _doFetch(url, options, controller) {
            const response = await fetch(`${this.baseUrl}${url}`, {
                ...options, headers: this._buildHeaders(options.headers), signal: controller.signal
            });
            let data;
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                data = await response.json();
            } else {
                const text = await response.text();
                try { data = JSON.parse(text); } catch { data = { detail: text }; }
            }
            if (this.responseAdapter) data = this.responseAdapter(data, response);
            return { response, data };
        }

        _extractError(data) {
            if (data.success === false) return String(data.message || data.error || '操作失败');
            if (data.error) return String(data.error);
            if (data.message) {
                return Array.isArray(data.message) ? data.message.join(', ') :
                       typeof data.message === 'object' ? JSON.stringify(data.message) :
                       String(data.message);
            }
            if (data.detail) {
                return Array.isArray(data.detail) ? data.detail.join(', ') :
                       typeof data.detail === 'object' ? JSON.stringify(data.detail) :
                       String(data.detail);
            }
            return '请求失败';
        }

        async _tryRefresh() {
            if (this._refreshPromise) return this._refreshPromise;
            const refreshToken = this._getRefreshToken();
            if (!this.refreshUrl || !refreshToken) return Promise.reject(new Error('no refresh config'));
            const body = this.refreshBodyBuilder ? this.refreshBodyBuilder(refreshToken) : { refresh_token: refreshToken };
            const refreshController = new AbortController();
            const refreshTimeoutId = setTimeout(() => refreshController.abort(), this.timeout || 30000);
            this._refreshPromise = fetch(`${this.baseUrl}${this.refreshUrl}`, {
                method: this.refreshMethod,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: refreshController.signal
            }).then(async (res) => {
                let rdata; try { rdata = await res.json(); } catch { rdata = {}; }
                if (!res.ok) throw new Error('refresh failed');
                const newToken = rdata.access_token || (rdata.data && rdata.data.access_token);
                const newRefresh = rdata.refresh_token || (rdata.data && rdata.data.refresh_token);
                if (!newToken) throw new Error('no token in refresh response');
                this._setToken(newToken);
                if (newRefresh) this._setRefreshToken(newRefresh);
                if (this.onRefreshSuccess) this.onRefreshSuccess(rdata);
                return newToken;
            }).catch((err) => {
                throw err.name === 'AbortError' ? new Error('refresh timeout') : err;
            }).finally(() => { clearTimeout(refreshTimeoutId); this._refreshPromise = null; });
            return this._refreshPromise;
        }

        async request(url, options = {}) {
            const controller = new AbortController();
            const requestId = this._generateRequestId(url);
            this._registerController(requestId, controller);

            const timeoutValue = options.timeout !== undefined ? options.timeout : this.timeout;
            const timeoutId = setTimeout(() => controller.abort(), timeoutValue);

            const isIdempotent = !options.method || options.method === 'GET';
            const maxAttempts = isIdempotent ? this.maxRetry : 1;
            const skipAuthRefresh = options.skipAuthRefresh === true;
            let lastError;

            try {
                for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                    try {
                        const { response, data } = await this._doFetch(url, options, controller);

                        if (!response.ok) {
                            const errorMsg = this._extractError(data);
                            if (response.status === 401 && !skipAuthRefresh && this.refreshUrl) {
                                try {
                                    await this._tryRefresh();
                                    const retryResult = await this._doFetch(url, options, controller);
                                    if (!retryResult.response.ok) {
                                        const retryMsg = this._extractError(retryResult.data);
                                        throw new ApiError(retryMsg, retryResult.response.status, retryResult.data);
                                    }
                                    return retryResult.data;
                                } catch (refreshErr) {
                                    this._clearAuth();
                                    if (this.onUnauthorized) this.onUnauthorized();
                                    throw new ApiError('登录已过期，请重新登录', 401, null);
                                }
                            }
                            if (response.status === 401) {
                                this._clearAuth();
                                if (this.onUnauthorized) this.onUnauthorized();
                                const msg401 = skipAuthRefresh ? (errorMsg || '认证失败') : '登录已过期，请重新登录';
                                throw new ApiError(msg401, 401, data);
                            }
                            if (this.onError) this.onError(response.status, errorMsg);
                            throw new ApiError(errorMsg, response.status, data);
                        }

                        return data;
                    } catch (error) {
                        lastError = error;
                        if (error.name === 'AbortError') throw new ApiError('请求超时，请稍后重试', 408, null);
                        if (_isNetworkErr(error)) {
                            const e = new ApiError('网络连接失败，请检查网络后重试', null, null);
                            e.isNetwork = true; throw e;
                        }
                        if (error.name === 'NexusApiError' || (error.message && error.message.includes('登录已过期'))) throw error;
                        if (attempt < maxAttempts) {
                            const delay = Math.min(MAX_DELAY, BASE_DELAY * 2 ** (attempt - 1)) * (0.5 + Math.random() * 0.5);
                            await new Promise(r => setTimeout(r, delay));
                        }
                    }
                }
                throw lastError;
            } finally {
                clearTimeout(timeoutId);
                this.abortControllers.delete(requestId);
            }
        }

        get(url, params = {}) {
            const filtered = {};
            Object.entries(params).forEach(([k, v]) => {
                if (v !== undefined && v !== null && v !== '') filtered[k] = v;
            });
            const qs = new URLSearchParams(filtered).toString();
            return this.request(qs ? `${url}?${qs}` : url, { method: 'GET' });
        }

        post(url, data = {}, options = {}) {
            return this.request(url, { method: 'POST', body: JSON.stringify(data), ...options });
        }

        put(url, data = {}) {
            return this.request(url, { method: 'PUT', body: JSON.stringify(data) });
        }

        patch(url, data = {}) {
            return this.request(url, { method: 'PATCH', body: JSON.stringify(data) });
        }

        delete(url) {
            return this.request(url, { method: 'DELETE' });
        }

        upload(url, formData, options = {}) {
            const token = this._getToken();
            const headers = { ...(token && { 'Authorization': `Bearer ${token}` }), ...options.headers };
            return fetch(`${this.baseUrl}${url}`, { method: 'POST', body: formData, headers, ...options })
            .then(async (res) => {
                let data; const ct = res.headers.get('content-type') || '';
                if (ct.includes('application/json')) data = await res.json();
                else { const t = await res.text(); try { data = JSON.parse(t); } catch { data = { detail: t }; } }
                if (!res.ok) throw new ApiError(this._extractError(data), res.status, data);
                return data;
            }).catch((err) => {
                if (err.name === 'NexusApiError') throw err;
                throw _isNetworkErr(err) ? new ApiError('网络连接失败，请检查网络后重试', null, null) : new ApiError(err.message || '上传失败', null, null);
            });
        }

        async streamPost(url, data = {}, { onEvent, onError, timeout = 60000, headers = {} } = {}) {
            const controller = new AbortController();
            const requestId = this._generateRequestId(url);
            this._registerController(requestId, controller);
            const timeoutId = setTimeout(() => controller.abort(), timeout);
            try {
                const response = await fetch(`${this.baseUrl}${url}`, {
                    method: 'POST',
                    headers: this._buildHeaders(headers),
                    body: JSON.stringify(data),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                if (!response.ok) {
                    let errData;
                    try { errData = await response.json(); } catch { errData = {}; }
                    const errorMsg = this._extractError(errData);
                    if (response.status === 401) {
                        this._clearAuth();
                        if (this.onUnauthorized) this.onUnauthorized();
                        if (onError) onError('登录已过期，请重新登录');
                        return;
                    }
                    if (this.onError) this.onError(response.status, errorMsg);
                    if (onError) onError(errorMsg);
                    return;
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let currentEvent = null;
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    let newlineIdx;
                    while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
                        const line = buffer.slice(0, newlineIdx);
                        buffer = buffer.slice(newlineIdx + 1);
                        if (line.startsWith('event:')) {
                            currentEvent = line.slice(6).trim();
                        } else if (line.startsWith('data:')) {
                            const payload = line.slice(5).trim();
                            if (payload && onEvent) {
                                try { onEvent(currentEvent, JSON.parse(payload)); }
                                catch (e) { /* ignore parse error */ }
                            }
                        } else if (line === '') {
                            currentEvent = null;
                        }
                    }
                }
            } catch (error) {
                if (error.name === 'AbortError') {
                    if (onError) onError('连接超时，请检查网络后重试');
                } else if (_isNetworkErr(error)) {
                    if (onError) onError('网络连接失败，请检查网络后重试');
                } else if (onError) {
                    onError(error.message || '网络错误');
                }
            } finally {
                clearTimeout(timeoutId);
                this.abortControllers.delete(requestId);
            }
        }

        cancel(url) {
            const keysToDelete = [];
            for (const [id, ctrl] of this.abortControllers) {
                if (id.includes(url)) { ctrl.abort(); keysToDelete.push(id); }
            }
            keysToDelete.forEach(id => this.abortControllers.delete(id));
        }

        async download(url, params = {}) {
            const qs = new URLSearchParams(params).toString();
            const fullUrl = qs ? `${url}?${qs}` : url;
            const token = this._getToken();
            let response;
            try {
                response = await fetch(`${this.baseUrl}${fullUrl}`, { headers: { ...(token && { 'Authorization': `Bearer ${token}` }) } });
            } catch (err) {
                throw _isNetworkErr(err) ? new ApiError('网络连接失败，请检查网络后重试', null, null) : new ApiError(err.message || '下载失败', null, null);
            }
            if (!response.ok) {
                const errorMsg = `下载失败 (${response.status})`;
                if (this.onError) this.onError(response.status, errorMsg);
                throw new ApiError(errorMsg, response.status, null);
            }
            return await response.blob();
        }

        createCrud(basePath) {
            return {
                create: (data) => this.post(basePath, data),
                list: (params) => this.get(basePath, params),
                get: (id) => this.get(`${basePath}/${id}`),
                update: (id, data) => this.put(`${basePath}/${id}`, data),
                delete: (id) => this.delete(`${basePath}/${id}`)
            };
        }

        crud(resource, options = {}) {
            const factory = window.createNexusCrud;
            if (typeof factory !== 'function') {
                return this.createCrud(resource);
            }
            return factory({
                api: this,
                basePath: resource,
                idField: options.idField || 'id',
                paramNames: options.paramNames,
                listAdapter: options.listAdapter,
                itemAdapter: options.itemAdapter,
                idPathParam: options.idPathParam
            });
        }

        uploadFile(url, file, options = {}) {
            const formData = new FormData();
            const fieldName = options.fieldName || 'file';
            if (file instanceof File || file instanceof Blob) {
                formData.append(fieldName, file, options.filename || file.name || 'blob');
            } else {
                throw new Error('uploadFile: file must be a File or Blob');
            }
            if (options.fields && typeof options.fields === 'object') {
                Object.entries(options.fields).forEach(([k, v]) => formData.append(k, v));
            }
            return this.upload(url, formData, { headers: options.headers || {} });
        }

        logout() {
            this._clearAuth();
            if (this.onUnauthorized) this.onUnauthorized();
        }
    }

    window.NexusApi = NexusApi;
})();

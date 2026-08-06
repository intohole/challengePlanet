(function() {
    const { ref, onUnmounted } = Vue;

    const useNotification = (options = {}) => {
        const notifyBase = options.baseUrl || window.NOTIFY_BASE_URL || '/api/notify';
        const tokenKey = options.tokenKey || 'token';
        const sseMaxReconnect = options.sseMaxReconnect !== undefined ? options.sseMaxReconnect : 3;
        const sseReconnectInterval = options.sseReconnectInterval || 5000;

        const api = new NexusApi({
            baseUrl: '',
            tokenKey: tokenKey,
            refreshTokenKey: options.refreshTokenKey || null,
            refreshUrl: options.refreshUrl || null,
            onUnauthorized: options.onUnauthorized || null,
            onRefreshSuccess: options.onRefreshSuccess || null,
            onError: options.onError || null
        });

        const notifications = ref([]);
        const unreadCount = ref(0);
        const loading = ref(false);
        const total = ref(0);

        let eventSource = null;
        let sseTimer = null;
        let sseAttempts = 0;
        let sseClosed = false;
        let notifCallback = options.onNotification || null;

        const getList = async (params = {}) => {
            loading.value = true;
            try {
                const resp = await api.get(notifyBase + '/notifications', params);
                notifications.value = resp.items || [];
                total.value = resp.total || 0;
                return resp;
            } finally {
                loading.value = false;
            }
        };

        const getUnreadCount = async () => {
            try {
                const resp = await api.get(notifyBase + '/unread-count');
                unreadCount.value = resp.count || 0;
                return resp.count || 0;
            } catch (e) {
                return unreadCount.value;
            }
        };

        const markRead = async (id) => {
            const prevRead = notifications.value.find(n => n.id === id)?.is_read;
            try {
                await api.put(notifyBase + '/' + id + '/read');
                const item = notifications.value.find(n => n.id === id);
                if (item) item.is_read = true;
                if (unreadCount.value > 0) unreadCount.value--;
                return true;
            } catch (e) {
                const item = notifications.value.find(n => n.id === id);
                if (item) item.is_read = prevRead || false;
                throw e;
            }
        };

        const markAllRead = async () => {
            const prevStates = notifications.value.map(n => ({ id: n.id, is_read: n.is_read }));
            const prevCount = unreadCount.value;
            try {
                await api.put(notifyBase + '/read-all');
                notifications.value.forEach(n => { n.is_read = true; });
                unreadCount.value = 0;
                return true;
            } catch (e) {
                prevStates.forEach(s => {
                    const item = notifications.value.find(n => n.id === s.id);
                    if (item) item.is_read = s.is_read;
                });
                unreadCount.value = prevCount;
                throw e;
            }
        };

        const deleteNotification = async (id) => {
            try {
                await api.delete(notifyBase + '/' + id);
                notifications.value = notifications.value.filter(n => n.id !== id);
                if (total.value > 0) total.value--;
                return true;
            } catch (e) {
                throw e;
            }
        };

        const onNotification = (cb) => { notifCallback = cb; };

        const disconnectSSE = () => {
            sseClosed = true;
            if (sseTimer) { clearTimeout(sseTimer); sseTimer = null; }
            if (eventSource) { eventSource.close(); eventSource = null; }
            sseAttempts = 0;
        };

        const connectSSE = () => {
            disconnectSSE();
            sseClosed = false;
            const token = localStorage.getItem(tokenKey);
            if (!token) return;
            try {
                const url = notifyBase + '/stream?token=' + encodeURIComponent(token);
                eventSource = new EventSource(url);
                eventSource.addEventListener('notification', (e) => {
                    sseAttempts = 0;
                    try {
                        const notif = JSON.parse(e.data);
                        if (notifCallback) notifCallback(notif);
                    } catch (err) {}
                });
                eventSource.onerror = () => {
                    if (eventSource) { eventSource.close(); eventSource = null; }
                    if (sseClosed) return;
                    if (sseAttempts < sseMaxReconnect) {
                        sseAttempts++;
                        sseTimer = setTimeout(connectSSE, sseReconnectInterval * sseAttempts);
                    }
                };
            } catch (e) {}
        };

        onUnmounted(() => { disconnectSSE(); });

        return {
            notifications, unreadCount, loading, total,
            getList, getUnreadCount, markRead, markAllRead, deleteNotification,
            connectSSE, disconnectSSE, onNotification
        };
    };

    window.useNotification = useNotification;
})();

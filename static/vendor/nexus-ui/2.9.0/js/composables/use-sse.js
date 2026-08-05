(function() {
    const { ref, onUnmounted } = Vue;

    const useSSE = (options = {}) => {
        const status = ref('disconnected');
        const data = ref(null);
        let eventSource = null;
        let fetchController = null;
        let reconnectTimer = null;
        let reconnectAttempts = 0;
        let manualClose = false;
        const maxReconnect = options.maxReconnect || 5;
        const reconnectInterval = options.reconnectInterval || 3000;
        const useFetch = options.useFetch || false;
        const headers = options.headers || {};

        const connect = (url) => {
            disconnect();
            manualClose = false;
            status.value = 'connecting';
            if (useFetch) {
                _connectFetch(url);
            } else {
                _connectEventSource(url);
            }
        };

        const _connectEventSource = (url) => {
            try {
                eventSource = new EventSource(url);
                eventSource.onopen = () => { status.value = 'connected'; reconnectAttempts = 0; };
                eventSource.onmessage = (e) => {
                    try { data.value = JSON.parse(e.data); } catch { data.value = e.data; }
                    if (options.onMessage) options.onMessage(data.value);
                };
                if (options.events) {
                    Object.entries(options.events).forEach(([name, handler]) => {
                        eventSource.addEventListener(name, (e) => {
                            try { handler(JSON.parse(e.data)); } catch { handler(e.data); }
                        });
                    });
                }
                eventSource.onerror = () => {
                    status.value = 'disconnected';
                    eventSource.close();
                    eventSource = null;
                    if (!manualClose) {
                        _scheduleReconnect(url);
                    }
                };
            } catch (e) { status.value = 'disconnected'; }
        };

        const _connectFetch = async (url) => {
            fetchController = new AbortController();
            const readTimeout = options.readTimeout || 30000;
            let readTimer = null;
            const resetReadTimer = () => {
                if (readTimer) clearTimeout(readTimer);
                readTimer = setTimeout(() => {
                    try { fetchController.abort(); } catch (e) {}
                }, readTimeout);
            };
            try {
                const resp = await fetch(url, {
                    method: 'GET',
                    headers: { 'Accept': 'text/event-stream', ...headers },
                    signal: fetchController.signal
                });
                if (!resp.ok) {
                    status.value = 'disconnected';
                    _scheduleReconnect(url);
                    return;
                }
                status.value = 'connected';
                reconnectAttempts = 0;
                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                resetReadTimer();
                while (true) {
                    const { done, value } = await reader.read();
                    resetReadTimer();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';
                    for (const line of lines) {
                        if (line.startsWith('data:')) {
                            const payload = line.slice(5).trim();
                            if (!payload) continue;
                            try { data.value = JSON.parse(payload); } catch { data.value = payload; }
                            if (options.onMessage) options.onMessage(data.value);
                        }
                    }
                }
                status.value = 'disconnected';
                _scheduleReconnect(url);
            } catch (e) {
                status.value = 'disconnected';
                if (!manualClose) {
                    _scheduleReconnect(url);
                }
            } finally {
                if (readTimer) { clearTimeout(readTimer); readTimer = null; }
            }
        };

        const _scheduleReconnect = (url) => {
            if (reconnectAttempts < maxReconnect) {
                reconnectAttempts++;
                reconnectTimer = setTimeout(() => connect(url), reconnectInterval * reconnectAttempts);
            }
        };

        const disconnect = () => {
            manualClose = true;
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
            if (eventSource) { eventSource.close(); eventSource = null; }
            if (fetchController) { fetchController.abort(); fetchController = null; }
            status.value = 'disconnected';
            reconnectAttempts = 0;
        };

        onUnmounted(disconnect);

        return { status, data, connect, disconnect };
    };

    window.useSSE = useSSE;
})();

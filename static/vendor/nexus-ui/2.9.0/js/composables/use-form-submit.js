(function() {
    const { ref, computed } = Vue;

    function _toast(message, type) {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else if (typeof window.nuxConfirm === 'function') {
            try { window.nuxConfirm(message); } catch (e) {}
        } else if (typeof console !== 'undefined') {
            console[type === 'error' ? 'error' : 'log'](message);
        }
    }

    function _normalizeError(e, fallbackMessage) {
        if (!e) return fallbackMessage || '操作失败';
        if (typeof e === 'string') return e;
        if (e.message) {
            if (window.mapHttpError) return window.mapHttpError(e);
            return e.message;
        }
        return fallbackMessage || '操作失败';
    }

    function useFormSubmit(options = {}) {
        const defaults = {
            successMessage: '',
            errorMessage: '',
            showToastOnSuccess: true,
            showToastOnError: true,
            resetOnSuccess: false,
            ...options
        };

        const submitting = ref(false);
        const error = ref(null);
        const errorMessage = ref('');
        const success = ref(false);
        const successMessage = ref('');
        const lastResult = ref(null);

        const submitDisabled = computed(() => submitting.value);
        const hasError = computed(() => !!error.value);
        const hasSuccess = computed(() => success.value);

        async function submit(asyncFn, runtimeOptions = {}) {
            const opts = Object.assign({}, defaults, runtimeOptions);
            submitting.value = true;
            error.value = null;
            errorMessage.value = '';
            success.value = false;
            successMessage.value = '';
            lastResult.value = null;
            try {
                const result = await asyncFn();
                lastResult.value = result;
                success.value = true;
                const sMsg = opts.successMessage;
                if (sMsg) {
                    successMessage.value = sMsg;
                    if (opts.showToastOnSuccess) _toast(sMsg, 'success');
                }
                if (opts.onSuccess) opts.onSuccess(result);
                return result;
            } catch (e) {
                error.value = e;
                const msg = _normalizeError(e, opts.errorMessage);
                errorMessage.value = msg;
                if (opts.showToastOnError) _toast(msg, 'error');
                if (opts.onError) opts.onError(e);
                throw e;
            } finally {
                submitting.value = false;
            }
        }

        function reset() {
            submitting.value = false;
            error.value = null;
            errorMessage.value = '';
            success.value = false;
            successMessage.value = '';
            lastResult.value = null;
        }

        function clearError() {
            error.value = null;
            errorMessage.value = '';
        }

        function clearSuccess() {
            success.value = false;
            successMessage.value = '';
        }

        async function run(asyncFn, runtimeOptions = {}) {
            return submit(asyncFn, runtimeOptions);
        }

        function wrap(fn, runtimeOptions = {}) {
            return async function(...args) {
                return submit(() => fn(...args), runtimeOptions);
            };
        }

        return {
            submitting, error, errorMessage, success, successMessage, lastResult,
            submitDisabled, hasError, hasSuccess,
            submit, run, wrap, reset, clearError, clearSuccess
        };
    }

    window.useFormSubmit = useFormSubmit;
})();

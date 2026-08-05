(function() {
    const { ref } = Vue;

    const useLoading = () => {
        const loading = ref(false);
        const error = ref(null);

        const withLoading = async (asyncFn) => {
            loading.value = true;
            error.value = null;
            try {
                return await asyncFn();
            } catch (e) {
                error.value = e.message || '操作失败';
                throw e;
            } finally {
                loading.value = false;
            }
        };

        return { loading, error, withLoading };
    };

    window.useLoading = useLoading;
})();

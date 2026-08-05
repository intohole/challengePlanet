(function() {
    const { ref, computed } = Vue;

    const useCollection = (options = {}) => {
        const items = ref([]);
        const loading = ref(false);
        const total = computed(() => items.value.length);

        const setItems = (list) => { items.value = list; };
        const addItem = (item) => { items.value.push(item); };
        const addItems = (list) => { items.value.push(...list); };
        const updateItem = (idOrPredicate, updates) => {
            const idx = typeof idOrPredicate === 'function'
                ? items.value.findIndex(idOrPredicate)
                : items.value.findIndex(item => item.id === idOrPredicate);
            if (idx !== -1) items.value[idx] = { ...items.value[idx], ...updates };
        };
        const deleteItem = (idOrPredicate) => {
            items.value = typeof idOrPredicate === 'function'
                ? items.value.filter((item, i) => !idOrPredicate(item, i))
                : items.value.filter(item => item.id !== idOrPredicate);
        };
        const getItem = (idOrPredicate) => {
            return typeof idOrPredicate === 'function'
                ? items.value.find(idOrPredicate)
                : items.value.find(item => item.id === idOrPredicate);
        };
        const clear = () => { items.value = []; };

        return { items, loading, total, setItems, addItem, addItems, updateItem, deleteItem, getItem, clear };
    };

    window.useCollection = useCollection;
})();

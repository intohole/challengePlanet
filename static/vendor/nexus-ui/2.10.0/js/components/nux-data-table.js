(function() {
    const NuxDataTable = {
        name: 'NuxDataTable',
        props: {
            columns: { type: Array, default: () => [] },
            data: { type: Array, default: () => [] },
            loading: { type: Boolean, default: false },
            emptyText: { type: String, default: '暂无数据' },
            emptyIcon: { type: String, default: '📭' },
            rowKey: { type: String, default: 'id' },
            selectable: { type: Boolean, default: false },
            selectedKeys: { type: Array, default: () => [] }
        },
        emits: ['row-click', 'select', 'select-all'],
        computed: {
            allSelected() {
                return this.data.length > 0 && this.data.every(row => this.selectedKeys.includes(row[this.rowKey]));
            }
        },
        methods: {
            toggleSelectAll() {
                this.$emit('select-all', this.allSelected ? [] : this.data.map(r => r[this.rowKey]));
            },
            toggleRow(row) {
                const key = row[this.rowKey];
                const keys = this.selectedKeys.includes(key)
                    ? this.selectedKeys.filter(k => k !== key)
                    : [...this.selectedKeys, key];
                this.$emit('select', keys);
            },
            isSelected(row) {
                return this.selectedKeys.includes(row[this.rowKey]);
            }
        },
        template: `
            <div class="nux-data-table-wrap">
                <table class="nux-data-table">
                    <thead>
                        <tr>
                            <th v-if="selectable" class="nux-table-check">
                                <input type="checkbox" :checked="allSelected" @change="toggleSelectAll">
                            </th>
                            <th v-for="col in columns" :key="col.key" :style="{ width: col.width || 'auto', textAlign: col.align || 'left' }">
                                {{ col.label }}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-if="loading">
                            <td :colspan="columns.length + (selectable ? 1 : 0)" class="nux-table-loading">
                                <span class="nx-spinner"></span> 加载中...
                            </td>
                        </tr>
                        <tr v-else-if="!data.length">
                            <td :colspan="columns.length + (selectable ? 1 : 0)">
                                <div class="nx-empty"><div class="nx-empty-icon">{{ emptyIcon }}</div><p class="nx-empty-text">{{ emptyText }}</p></div>
                            </td>
                        </tr>
                        <tr v-else v-for="row in data" :key="row[rowKey]"
                            :class="{ 'nux-row-selected': isSelected(row) }"
                            @click="$emit('row-click', row)">
                            <td v-if="selectable" class="nux-table-check">
                                <input type="checkbox" :checked="isSelected(row)" @click.stop="toggleRow(row)">
                            </td>
                            <td v-for="col in columns" :key="col.key" :style="{ textAlign: col.align || 'left' }">
                                <slot :name="col.key" :row="row" :value="row[col.key]">
                                    {{ col.render ? col.render(row[col.key], row) : row[col.key] }}
                                </slot>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `
    };
    window.NuxDataTable = NuxDataTable;
})();

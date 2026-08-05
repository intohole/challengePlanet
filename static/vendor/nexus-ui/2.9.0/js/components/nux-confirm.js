(function() {
    const { ref } = Vue;

    const confirmState = ref({ visible: false, title: '', message: '', resolve: null });
    const queue = [];
    let isShowing = false;

    const NuxConfirm = {
        name: 'NuxConfirm',
        setup() {
            const confirm = () => {
                confirmState.value.visible = false;
                if (confirmState.value.resolve) confirmState.value.resolve(true);
                _next();
            };
            const cancel = () => {
                confirmState.value.visible = false;
                if (confirmState.value.resolve) confirmState.value.resolve(false);
                _next();
            };
            return { confirmState, confirm, cancel };
        },
        template: `
            <teleport to="body">
                <transition name="nux-modal">
                    <div v-if="confirmState.visible" class="nx-modal-overlay" @click="cancel">
                        <div class="nx-modal" style="max-width: 400px" @click.stop>
                            <div class="nx-modal-title" v-if="confirmState.title">{{ confirmState.title }}</div>
                            <p style="color: var(--nx-text-secondary); margin: var(--nx-space-4) 0;">{{ confirmState.message }}</p>
                            <div class="nux-modal-footer">
                                <button class="nx-btn nx-btn-ghost" @click="cancel">取消</button>
                                <button class="nx-btn nx-btn-primary" @click="confirm">确定</button>
                            </div>
                        </div>
                    </div>
                </transition>
            </teleport>
        `
    };

    const _show = (item) => {
        isShowing = true;
        confirmState.value = { visible: true, title: item.title, message: item.message, resolve: item.resolve };
    };

    const _next = () => {
        isShowing = false;
        if (queue.length > 0) {
            const item = queue.shift();
            _show(item);
        }
    };

    const confirm = (message, title = '确认操作') => {
        return new Promise((resolve) => {
            const item = { message, title, resolve };
            if (isShowing) {
                queue.push(item);
            } else {
                _show(item);
            }
        });
    };

    window.NuxConfirm = NuxConfirm;
    window.nuxConfirm = confirm;
})();

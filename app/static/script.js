/*
 * Comportamentos globais: tema, transições de página, filtro de salas,
 * filtros do admin e reordenação de insumos.
 *
 * Convenção: cada bloco é isolado por uma checagem de existência do elemento
 * âncora, para que o mesmo arquivo sirva a todas as telas.
 */

/** Token CSRF da página, para as requisições JSON. */
function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

/** POST em JSON já com o cabeçalho de CSRF. */
function postJson(url, payload) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken()
        },
        body: JSON.stringify(payload)
    });
}

document.addEventListener('DOMContentLoaded', function () {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const transitionDuration = 140;

    /* ------------------------------------------------------------------ */
    /* Transições de página                                                */
    /* ------------------------------------------------------------------ */

    function startPageEnter() {
        if (reducedMotion) return;
        document.body.classList.add('page-enter');
        window.setTimeout(() => {
            document.body.classList.remove('page-enter');
        }, 240);
    }

    function shouldTransitionTo(url) {
        return url.origin === window.location.origin
            && url.pathname + url.search !== window.location.pathname + window.location.search
            && !url.hash;
    }

    function startPageExit(callback) {
        if (reducedMotion) {
            callback();
            return;
        }

        document.body.classList.add('page-exit');
        window.setTimeout(callback, transitionDuration);
    }

    startPageEnter();

    window.addEventListener('pageshow', () => {
        document.body.classList.remove('page-exit');
    });

    /* ------------------------------------------------------------------ */
    /* Seleção de escritório e sala                                        */
    /* ------------------------------------------------------------------ */

    const officeSelect = document.getElementById('office');
    const roomSelect = document.querySelector('[data-room-select]');

    if (officeSelect && roomSelect) {
        // As salas já vêm renderizadas e agrupadas por escritório, para que a
        // página funcione sem JavaScript. Aqui apenas escondemos os grupos que
        // não pertencem ao escritório escolhido.
        const groups = Array.from(roomSelect.querySelectorAll('optgroup'));
        const placeholder = roomSelect.querySelector('option[value=""]');

        function applyRoomFilter() {
            const selectedOffice = officeSelect.value;
            let available = 0;

            groups.forEach(group => {
                const matches = !selectedOffice || group.dataset.office === selectedOffice;
                group.hidden = !matches;
                group.disabled = !matches;
                Array.from(group.querySelectorAll('option')).forEach(option => {
                    option.hidden = !matches;
                    option.disabled = !matches;
                    if (matches) available += 1;
                });
            });

            const selected = roomSelect.selectedOptions[0];
            if (selected && selected.disabled) {
                roomSelect.value = '';
            }

            if (placeholder) {
                placeholder.textContent = selectedOffice && available === 0
                    ? 'Nenhuma sala disponível'
                    : 'Selecione uma sala';
            }

            roomSelect.disabled = Boolean(selectedOffice) && available === 0;
        }

        officeSelect.addEventListener('change', applyRoomFilter);
        applyRoomFilter();
    }

    /* ------------------------------------------------------------------ */
    /* Validação do pedido                                                 */
    /* ------------------------------------------------------------------ */

    const orderForm = document.querySelector('[data-order-form]');
    if (orderForm) {
        const feedback = document.createElement('div');
        feedback.className = 'alert alert-error hidden';
        feedback.setAttribute('role', 'alert');
        orderForm.prepend(feedback);

        orderForm.addEventListener('submit', function (event) {
            const quantities = Array.from(orderForm.querySelectorAll('input[type="number"]'));
            const services = Array.from(orderForm.querySelectorAll('select'));

            const hasQuantity = quantities.some(input => parseInt(input.value, 10) > 0);
            const hasService = services.some(select => select.value === 'Sim');

            if (hasQuantity || hasService) {
                feedback.classList.add('hidden');
                return;
            }

            // Mensagem no fluxo da página, e não um alert() do navegador — o
            // portal já usa modal e alertas próprios em todas as outras telas.
            event.preventDefault();
            event.stopImmediatePropagation();
            feedback.textContent = 'Selecione pelo menos um item ou serviço.';
            feedback.classList.remove('hidden');
            feedback.scrollIntoView({ block: 'nearest', behavior: reducedMotion ? 'auto' : 'smooth' });
        });
    }

    /* ------------------------------------------------------------------ */
    /* Tema                                                                */
    /* ------------------------------------------------------------------ */

    const toggleButton = document.getElementById('theme-toggle');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    const root = document.documentElement;

    function readStoredTheme() {
        try {
            const saved = localStorage.getItem('theme');
            return saved === 'dark' || saved === 'light' ? saved : null;
        } catch (error) {
            return null;
        }
    }

    function storeTheme(theme) {
        try {
            localStorage.setItem('theme', theme);
        } catch (error) {
            /* Modo privativo: o tema vale só para esta navegação. */
        }
    }

    function applyTheme() {
        const savedTheme = readStoredTheme();
        const isDark = savedTheme === 'dark' || (!savedTheme && systemPrefersDark.matches);

        if (savedTheme) {
            root.dataset.theme = savedTheme;
        } else {
            delete root.dataset.theme;
        }

        updateVisuals(isDark);
    }

    function updateVisuals(isDark) {
        if (toggleButton) {
            const iconSpan = toggleButton.querySelector('.icon');
            if (iconSpan) {
                iconSpan.textContent = isDark ? '🌙' : '☀️';
            }
            toggleButton.setAttribute(
                'aria-label',
                isDark ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'
            );
        }
    }

    function animateThemeShift() {
        if (reducedMotion) return;
        document.body.classList.remove('theme-shift');
        void document.body.offsetWidth;
        document.body.classList.add('theme-shift');
        window.setTimeout(() => {
            document.body.classList.remove('theme-shift');
        }, 220);
    }

    function toggleTheme() {
        const savedTheme = readStoredTheme();
        const newTheme = savedTheme
            ? (savedTheme === 'dark' ? 'light' : 'dark')
            : (systemPrefersDark.matches ? 'light' : 'dark');

        storeTheme(newTheme);
        applyTheme();
        animateThemeShift();
    }

    applyTheme();

    if (toggleButton) {
        toggleButton.addEventListener('click', toggleTheme);
    }

    systemPrefersDark.addEventListener('change', () => {
        if (!readStoredTheme()) {
            applyTheme();
        }
    });

    /* ------------------------------------------------------------------ */
    /* Filtros da tela de salas                                            */
    /* ------------------------------------------------------------------ */

    const spaceFilters = document.querySelector('[data-space-filters]');
    if (spaceFilters) {
        const officeFilter = spaceFilters.querySelector('[data-space-office-filter]');
        const nameFilter = spaceFilters.querySelector('[data-space-name-filter]');
        const rows = Array.from(document.querySelectorAll('[data-space-row]'));
        const emptyRow = document.querySelector('[data-filter-empty-row]');

        function normalize(value) {
            return value
                .toLowerCase()
                .normalize('NFD')
                .replace(/\p{Diacritic}/gu, '');
        }

        function applySpaceFilters() {
            const selectedOffice = officeFilter ? officeFilter.value : '';
            const query = nameFilter ? normalize(nameFilter.value.trim()) : '';
            let visibleCount = 0;

            rows.forEach(row => {
                const matchesOffice = !selectedOffice || row.dataset.officeId === selectedOffice;
                const matchesName = !query || normalize(row.dataset.spaceName || '').includes(query);
                const isVisible = matchesOffice && matchesName;
                row.classList.toggle('hidden', !isVisible);
                if (isVisible) visibleCount += 1;
            });

            if (emptyRow) {
                emptyRow.classList.toggle('hidden', visibleCount > 0);
            }
        }

        if (officeFilter) officeFilter.addEventListener('change', applySpaceFilters);
        if (nameFilter) nameFilter.addEventListener('input', applySpaceFilters);
        applySpaceFilters();
    }

    /* ------------------------------------------------------------------ */
    /* Ordenação de insumos: mouse e teclado                               */
    /* ------------------------------------------------------------------ */

    const sortableList = document.querySelector('[data-product-sort-list]');
    if (sortableList) {
        const status = document.querySelector('[data-product-sort-status]');
        let draggingRow = null;
        let orderAtDragStart = [];

        function setStatus(message, isError = false) {
            if (!status) return;
            status.textContent = message;
            status.classList.toggle('is-error', isError);
        }

        function getRows() {
            return Array.from(sortableList.querySelectorAll('[data-product-id]'));
        }

        function currentOrder() {
            return getRows().map(row => row.dataset.productId);
        }

        function getDragAfterElement(y) {
            return getRows()
                .filter(row => row !== draggingRow)
                .reduce((closest, row) => {
                    const box = row.getBoundingClientRect();
                    const offset = y - box.top - box.height / 2;

                    if (offset < 0 && offset > closest.offset) {
                        return { offset, element: row };
                    }

                    return closest;
                }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
        }

        async function saveProductOrder() {
            const productIds = currentOrder();
            setStatus('Salvando nova ordem...');

            try {
                const response = await postJson(sortableList.dataset.reorderUrl, {
                    product_ids: productIds
                });
                const result = await response.json();

                if (!response.ok || !result.success) {
                    throw new Error(result.message || 'Falha ao salvar ordem.');
                }

                setStatus('Ordem salva.');
            } catch (error) {
                console.error(error);
                setStatus('Não foi possível salvar a ordem. Recarregue a página e tente novamente.', true);
            }
        }

        function sameOrder(a, b) {
            return a.length === b.length && a.every((value, index) => value === b[index]);
        }

        /** Move a linha uma posição e devolve true se a ordem mudou. */
        function moveRow(row, direction) {
            const rows = getRows();
            const index = rows.indexOf(row);
            const target = index + direction;

            if (target < 0 || target >= rows.length) {
                setStatus(direction < 0 ? 'Já é o primeiro item.' : 'Já é o último item.');
                return false;
            }

            if (direction < 0) {
                sortableList.insertBefore(row, rows[target]);
            } else {
                sortableList.insertBefore(rows[target], row);
            }

            return true;
        }

        getRows().forEach(row => {
            row.addEventListener('dragstart', event => {
                if (event.target.closest('input, select, button') && !event.target.closest('.drag-handle')) {
                    event.preventDefault();
                    return;
                }

                draggingRow = row;
                orderAtDragStart = currentOrder();
                row.classList.add('is-dragging');
                event.dataTransfer.effectAllowed = 'move';
            });

            row.addEventListener('dragend', () => {
                row.classList.remove('is-dragging');
                draggingRow = null;

                // Só grava se a posição realmente mudou: arrastar e soltar no
                // mesmo lugar não precisa de requisição.
                if (!sameOrder(orderAtDragStart, currentOrder())) {
                    saveProductOrder();
                }
            });

            const handle = row.querySelector('[data-sort-handle]');
            if (!handle) return;

            handle.addEventListener('keydown', event => {
                const direction = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0;
                if (!direction) return;

                event.preventDefault();
                if (moveRow(row, direction)) {
                    handle.focus();
                    saveProductOrder();
                }
            });
        });

        sortableList.addEventListener('dragover', event => {
            if (!draggingRow) return;
            event.preventDefault();

            const afterElement = getDragAfterElement(event.clientY);
            if (afterElement) {
                sortableList.insertBefore(draggingRow, afterElement);
            } else {
                sortableList.appendChild(draggingRow);
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /* Transição em links e formulários                                    */
    /* ------------------------------------------------------------------ */

    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!link || event.defaultPrevented) return;
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (link.target && link.target !== '_self') return;
        if (link.hasAttribute('download') || link.dataset.noTransition === 'true') return;

        const url = new URL(link.href, window.location.href);
        if (!shouldTransitionTo(url)) return;

        event.preventDefault();
        startPageExit(() => {
            window.location.href = url.href;
        });
    });

    document.addEventListener('submit', event => {
        const submittedForm = event.target;
        if (!(submittedForm instanceof HTMLFormElement) || event.defaultPrevented) return;
        if (submittedForm.dataset.noTransition === 'true' || submittedForm.dataset.transitioning === 'true') return;

        event.preventDefault();
        submittedForm.dataset.transitioning = 'true';

        // form.submit() ignora o botão que disparou o envio, então o par
        // name/value dele seria perdido. Reinserimos como campo oculto antes
        // de reenviar, para que o formulário chegue ao servidor idêntico ao
        // que o usuário submeteu.
        const submitter = event.submitter;
        if (submitter && submitter.name) {
            const carried = document.createElement('input');
            carried.type = 'hidden';
            carried.name = submitter.name;
            carried.value = submitter.value;
            submittedForm.appendChild(carried);
        }

        startPageExit(() => {
            submittedForm.submit();
        });
    });
});

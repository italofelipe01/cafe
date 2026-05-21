document.addEventListener('DOMContentLoaded', function () {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const transitionDuration = 140;

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

    const officeSelect = document.getElementById('office');
    const roomSelect = document.getElementById('room');

    // Função para atualizar as salas com base no escritório selecionado
    if (officeSelect) {
        officeSelect.addEventListener('change', function () {
            const selectedOffice = officeSelect.value;
            roomSelect.innerHTML = '<option value="">Carregando salas...</option>';
            roomSelect.disabled = true;

            if (selectedOffice) {
                fetch('/get_rooms', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ office: selectedOffice })
                })
                .then(response => response.json())
                .then(rooms => {
                    roomSelect.innerHTML = '<option value="">Selecione uma sala</option>';
                    rooms.forEach(room => {
                        const option = document.createElement('option');
                        option.value = room;
                        option.textContent = room;
                        roomSelect.appendChild(option);
                    });
                    roomSelect.disabled = rooms.length === 0;
                })
                .catch(() => {
                    roomSelect.innerHTML = '<option value="">Erro ao carregar salas</option>';
                });
            } else {
                roomSelect.innerHTML = '<option value="">Selecione uma sala</option>';
                roomSelect.disabled = true;
            }
        });
    }

    // Task 1: Client-Side Form Validation
    const form = document.querySelector('form[action="/submit_form"]');
    if (form) {
        form.addEventListener('submit', function (e) {
            const numberInputs = form.querySelectorAll('input[type="number"]');
            const serviceSelects = form.querySelectorAll('select');

            let allZero = true;

            // Check all number inputs
            numberInputs.forEach(input => {
                if (parseInt(input.value) > 0) {
                    allZero = false;
                }
            });

            const serviceSelected = Array.from(serviceSelects).some(select => select.value === 'Sim');

            if (allZero && !serviceSelected) {
                e.preventDefault();
                alert('Por favor, selecione pelo menos um item ou serviço.');
            }
        });
    }

    // Task 2: Manual Dark/Light Mode Toggle
    const toggleButton = document.getElementById('theme-toggle');
    const logos = document.querySelectorAll('[data-theme-logo]');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)');

    function applyTheme() {
        const savedTheme = localStorage.getItem('theme');
        const isDark = savedTheme === 'dark' || (!savedTheme && systemPrefersDark.matches);

        // Apply classes to body
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
            document.body.classList.remove('light-mode');
        } else if (savedTheme === 'light') {
            document.body.classList.add('light-mode');
            document.body.classList.remove('dark-mode');
        } else {
            // System default: remove manual classes
            document.body.classList.remove('dark-mode');
            document.body.classList.remove('light-mode');
        }

        // Update Logo and Button Icon
        updateVisuals(isDark);
    }

    function updateVisuals(isDark) {
        const logoPath = isDark ? '/static/images/logo-dark.png' : '/static/images/logo-light.png';
        logos.forEach(logo => {
            logo.src = logoPath;
        });

        if (toggleButton) {
            const iconSpan = toggleButton.querySelector('.icon');
            if (iconSpan) {
                iconSpan.textContent = isDark ? '🌙' : '☀️';
            }
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
        const savedTheme = localStorage.getItem('theme');
        let newTheme;

        if (savedTheme) {
            // If already manual, switch to the other
            newTheme = savedTheme === 'dark' ? 'light' : 'dark';
        } else {
            // If system, switch to the opposite of system
            newTheme = systemPrefersDark.matches ? 'light' : 'dark';
        }

        localStorage.setItem('theme', newTheme);
        applyTheme();
        animateThemeShift();
    }

    // Initial Application
    applyTheme();

    // Event Listener for Toggle Button
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleTheme);
    }

    // Listen for System Preference Changes (only affects if no manual override)
    systemPrefersDark.addEventListener('change', () => {
        if (!localStorage.getItem('theme')) {
            applyTheme();
        }
    });

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
                .replace(/[\u0300-\u036f]/g, '');
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

    const sortableList = document.querySelector('[data-product-sort-list]');
    if (sortableList) {
        const status = document.querySelector('[data-product-sort-status]');
        let draggingRow = null;

        function setStatus(message, isError = false) {
            if (!status) return;
            status.textContent = message;
            status.classList.toggle('is-error', isError);
        }

        function getRows() {
            return Array.from(sortableList.querySelectorAll('[data-product-id]'));
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
            const productIds = getRows().map(row => row.dataset.productId);
            setStatus('Salvando nova ordem...');

            try {
                const response = await fetch(sortableList.dataset.reorderUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_ids: productIds })
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

        getRows().forEach(row => {
            row.addEventListener('dragstart', event => {
                if (event.target.closest('input, select, button') && !event.target.closest('.drag-handle')) {
                    event.preventDefault();
                    return;
                }

                draggingRow = row;
                row.classList.add('is-dragging');
                event.dataTransfer.effectAllowed = 'move';
            });

            row.addEventListener('dragend', () => {
                row.classList.remove('is-dragging');
                draggingRow = null;
                saveProductOrder();
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
        startPageExit(() => {
            submittedForm.submit();
        });
    });
});

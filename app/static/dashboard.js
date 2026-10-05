/*
 * Painel da copa: lista os pedidos pendentes, mostra há quanto tempo cada um
 * espera, avisa quando chega um novo e conclui pedidos por um modal próprio.
 *
 * Depende de csrfToken() e postJson(), definidos em script.js. Os endereços da
 * API vêm de data-* em [data-copa-dashboard], resolvidos pelo servidor.
 */

(function () {
    const root = document.querySelector('[data-copa-dashboard]');
    if (!root) return;

    const ORDERS_URL = root.dataset.ordersUrl;
    const COMPLETE_URL = root.dataset.completeUrl;
    const LOGIN_URL = root.dataset.loginUrl;
    const WARN_SECONDS = Number(root.dataset.warnMinutes || 5) * 60;
    const LATE_SECONDS = Number(root.dataset.lateMinutes || 10) * 60;

    const REFRESH_INTERVAL = 10000;
    const MAX_RETRY_INTERVAL = 30000;
    const CLOCK_INTERVAL = 15000;
    const ALERTS_KEY = 'copaAlerts';
    const BASE_TITLE = document.title;

    const ordersContainer = document.getElementById('orders-container');
    const dashboardError = document.getElementById('dashboard-error');
    const pendingCount = document.getElementById('pending-count');
    const oldestOrder = document.getElementById('oldest-order');
    const lateCount = document.getElementById('late-count');
    const statusLine = root.querySelector('[data-dashboard-status]');
    const alertsToggle = root.querySelector('[data-alerts-toggle]');
    const completeModal = document.getElementById('complete-modal');
    const modalRoom = completeModal ? completeModal.querySelector('[data-modal-room]') : null;
    const modalCancel = completeModal ? completeModal.querySelector('[data-modal-cancel]') : null;
    const modalConfirm = completeModal ? completeModal.querySelector('[data-modal-confirm]') : null;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /** Cartões na tela, por id do pedido. */
    const cards = new Map();
    /** Espera de cada pedido no momento da última consulta, em segundos. */
    const waitingAtFetch = new Map();
    const knownOrderIds = new Set();

    let fetchedAt = performance.now();
    let firstLoad = true;
    let retryDelay = REFRESH_INTERVAL;
    let refreshTimer = null;
    let pendingCompletionOrder = null;
    let lastFocusedElement = null;

    /* ------------------------------------------------------------------ */
    /* Alertas: som, notificação do sistema e tela sempre acesa            */
    /* ------------------------------------------------------------------ */

    let audioContext = null;
    let wakeLock = null;

    function readAlertsPreference() {
        try {
            return localStorage.getItem(ALERTS_KEY) === 'on';
        } catch (error) {
            return false;
        }
    }

    function storeAlertsPreference(enabled) {
        try {
            localStorage.setItem(ALERTS_KEY, enabled ? 'on' : 'off');
        } catch (error) {
            /* Sem armazenamento: vale só para esta aba. */
        }
    }

    let alertsEnabled = readAlertsPreference();

    /*
     * O navegador só libera áudio depois de um gesto na página. Por isso o
     * contexto é criado (ou retomado) dentro de um clique; antes disso, um
     * pedido novo seria silencioso sem nenhum aviso de que o som estava preso.
     */
    function unlockAudio() {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;

        try {
            if (!audioContext) audioContext = new AudioContextClass();
            if (audioContext.state === 'suspended') audioContext.resume();
        } catch (error) {
            console.debug('Som indisponível.', error);
        }
    }

    function audioReady() {
        return Boolean(audioContext) && audioContext.state === 'running';
    }

    function chime() {
        if (!audioReady()) return;

        const now = audioContext.currentTime;
        [880, 1175].forEach((frequency, index) => {
            const oscillator = audioContext.createOscillator();
            const gain = audioContext.createGain();
            const start = now + index * 0.18;

            oscillator.type = 'sine';
            oscillator.frequency.value = frequency;
            gain.gain.setValueAtTime(0.001, start);
            gain.gain.exponentialRampToValueAtTime(0.25, start + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.001, start + 0.3);

            oscillator.connect(gain);
            gain.connect(audioContext.destination);
            oscillator.start(start);
            oscillator.stop(start + 0.32);
        });
    }

    function notifySystem(newOrders) {
        if (!('Notification' in window) || Notification.permission !== 'granted') return;
        if (!document.hidden) return;

        const rooms = newOrders.map(order => order.room).join(', ');
        try {
            new Notification('Novo pedido na copa', { body: rooms, tag: 'copa-pronta' });
        } catch (error) {
            console.debug('Notificação indisponível.', error);
        }
    }

    async function requestWakeLock() {
        if (!alertsEnabled || !('wakeLock' in navigator) || document.hidden) return;
        try {
            wakeLock = await navigator.wakeLock.request('screen');
        } catch (error) {
            wakeLock = null; /* Bateria baixa ou contexto sem HTTPS: segue sem. */
        }
    }

    function releaseWakeLock() {
        if (wakeLock) {
            wakeLock.release().catch(() => {});
            wakeLock = null;
        }
    }

    function renderAlertsToggle() {
        if (!alertsToggle) return;
        alertsToggle.setAttribute('aria-pressed', String(alertsEnabled));
        alertsToggle.textContent = alertsEnabled ? 'Alertas ligados' : 'Ativar alertas';
        alertsToggle.classList.toggle('is-active', alertsEnabled);
    }

    function enableAlerts() {
        alertsEnabled = true;
        storeAlertsPreference(true);
        unlockAudio();
        window.setTimeout(chime, 60);

        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().catch(() => {});
        }

        requestWakeLock();
        renderAlertsToggle();
        updateStatus();
    }

    function disableAlerts() {
        alertsEnabled = false;
        storeAlertsPreference(false);
        releaseWakeLock();
        renderAlertsToggle();
        updateStatus();
    }

    if (alertsToggle) {
        alertsToggle.addEventListener('click', () => {
            if (alertsEnabled) disableAlerts();
            else enableAlerts();
        });
    }

    // Com os alertas ligados numa visita anterior, o primeiro toque em
    // qualquer lugar da tela já libera o som.
    function unlockOnFirstGesture() {
        if (alertsEnabled) unlockAudio();
        updateStatus();
    }
    document.addEventListener('pointerdown', unlockOnFirstGesture, { once: true });
    document.addEventListener('keydown', unlockOnFirstGesture, { once: true });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) return;
        requestWakeLock();
        refreshNow();
    });

    /* ------------------------------------------------------------------ */
    /* Tempo de espera                                                     */
    /* ------------------------------------------------------------------ */

    function currentWaiting(orderId) {
        const base = waitingAtFetch.get(orderId) || 0;
        return base + Math.floor((performance.now() - fetchedAt) / 1000);
    }

    function formatWaiting(seconds) {
        const minutes = Math.floor(seconds / 60);
        if (minutes < 1) return 'agora';
        if (minutes < 60) return `${minutes} min`;
        const hours = Math.floor(minutes / 60);
        const rest = String(minutes % 60).padStart(2, '0');
        return `${hours} h ${rest}`;
    }

    function urgencyOf(seconds) {
        if (seconds >= LATE_SECONDS) return 'late';
        if (seconds >= WARN_SECONDS) return 'warn';
        return 'ok';
    }

    function refreshClocks() {
        let longest = -1;
        let late = 0;

        cards.forEach((card, orderId) => {
            const seconds = currentWaiting(orderId);
            const urgency = urgencyOf(seconds);
            const label = card.querySelector('[data-wait]');
            if (label) label.textContent = formatWaiting(seconds);

            card.classList.toggle('is-warn', urgency === 'warn');
            card.classList.toggle('is-late', urgency === 'late');
            if (urgency === 'late') late += 1;
            longest = Math.max(longest, seconds);
        });

        pendingCount.textContent = cards.size;
        oldestOrder.textContent = longest >= 0 ? formatWaiting(longest) : '--';
        if (lateCount) lateCount.textContent = late;
        document.title = cards.size ? `(${cards.size}) ${BASE_TITLE}` : BASE_TITLE;
    }

    /* ------------------------------------------------------------------ */
    /* Cartões                                                             */
    /* ------------------------------------------------------------------ */

    function setError(message) {
        dashboardError.textContent = message || '';
        dashboardError.classList.toggle('hidden', !message);
    }

    function updateStatus(message) {
        if (!statusLine) return;
        if (message) {
            statusLine.textContent = message;
            return;
        }

        const time = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        let text = `Atualizado às ${time}`;
        if (alertsEnabled && audioContext === null) text += ' · toque na tela para liberar o som';
        statusLine.textContent = text;
    }

    function createOrderCard(order) {
        const card = document.createElement('article');
        card.className = 'order-card';
        card.dataset.orderId = order.id;

        const header = document.createElement('div');
        header.className = 'order-header';

        const title = document.createElement('h2');
        title.textContent = order.room;

        const wait = document.createElement('span');
        wait.className = 'order-wait';
        wait.dataset.wait = '';

        const office = document.createElement('span');
        office.className = 'order-office';
        office.textContent = order.office;

        const timestamp = document.createElement('small');
        timestamp.textContent = `Pedido às ${order.time} · ${order.date} · #${order.id}`;

        header.append(title, wait, office, timestamp);

        const list = document.createElement('ul');
        list.className = 'order-items';

        Object.entries(order.items).forEach(([item, quantity]) => {
            const row = document.createElement('li');
            const name = document.createElement('span');
            const value = document.createElement('strong');
            name.textContent = item;
            value.textContent = quantity;
            row.append(name, value);
            list.appendChild(row);
        });

        card.append(header, list);

        if (order.note) {
            const note = document.createElement('p');
            note.className = 'order-note';
            note.textContent = order.note;
            card.appendChild(note);
        }

        const button = document.createElement('button');
        button.className = 'btn btn-success';
        button.type = 'button';
        button.textContent = 'Concluir';
        button.addEventListener('click', () => openCompleteModal(order, button));
        card.appendChild(button);

        return card;
    }

    function showEmptyMessage(show) {
        let empty = ordersContainer.querySelector('.empty-message');
        if (show && !empty) {
            empty = document.createElement('p');
            empty.className = 'empty-message';
            empty.textContent = 'Nenhum pedido pendente.';
            ordersContainer.appendChild(empty);
        } else if (!show && empty) {
            empty.remove();
        }
    }

    /*
     * Atualiza a lista sem reconstruí-la: só entram os cartões novos e só saem
     * os que deixaram de estar pendentes. Reconstruir tudo a cada consulta
     * tirava o foco de quem navegava por teclado e desconectava o botão que
     * abriu o modal.
     */
    function renderOrders(orders) {
        const incoming = new Set(orders.map(order => order.id));

        cards.forEach((card, orderId) => {
            if (!incoming.has(orderId) && !card.classList.contains('is-completing')) {
                card.remove();
                cards.delete(orderId);
            }
        });

        waitingAtFetch.clear();
        orders.forEach((order, index) => {
            waitingAtFetch.set(order.id, order.waiting_seconds || 0);

            let card = cards.get(order.id);
            if (!card) {
                card = createOrderCard(order);
                if (!firstLoad && !reducedMotion) card.classList.add('is-new');
                cards.set(order.id, card);
            }

            const expected = ordersContainer.children[index];
            if (expected !== card) {
                ordersContainer.insertBefore(card, expected || null);
            }
        });

        showEmptyMessage(orders.length === 0);
        refreshClocks();
    }

    function announceNewOrders(orders) {
        const fresh = orders.filter(order => !knownOrderIds.has(order.id));
        fresh.forEach(order => knownOrderIds.add(order.id));

        if (fresh.length && !firstLoad && alertsEnabled) {
            chime();
            notifySystem(fresh);
        }

        firstLoad = false;
    }

    /* ------------------------------------------------------------------ */
    /* Consulta                                                            */
    /* ------------------------------------------------------------------ */

    /** A sessão da copa expirou: manda para o login preservando o destino. */
    function redirectToLogin() {
        window.location.href = `${LOGIN_URL}?next=${encodeURIComponent(window.location.pathname)}`;
    }

    function scheduleRefresh(delay) {
        window.clearTimeout(refreshTimer);
        refreshTimer = window.setTimeout(fetchOrders, delay);
    }

    function refreshNow() {
        scheduleRefresh(0);
    }

    async function fetchOrders() {
        try {
            const response = await fetch(ORDERS_URL, {
                headers: { 'Accept': 'application/json' },
                cache: 'no-store'
            });

            if (response.status === 401) {
                redirectToLogin();
                return;
            }

            if (!response.ok) throw new Error(`Falha ao carregar pedidos (${response.status}).`);

            const orders = await response.json();
            fetchedAt = performance.now();
            setError('');
            renderOrders(orders);
            announceNewOrders(orders);
            updateStatus();
            retryDelay = REFRESH_INTERVAL;
        } catch (error) {
            // Sem servidor, a lista que está na tela continua valendo; o aviso
            // diz que ela pode estar desatualizada, e as tentativas espaçam.
            setError('Sem conexão com o servidor. A lista pode estar desatualizada; tentando de novo.');
            updateStatus('Sem conexão');
            retryDelay = Math.min(retryDelay * 2, MAX_RETRY_INTERVAL);
            console.error(error);
        } finally {
            scheduleRefresh(retryDelay);
        }
    }

    /* ------------------------------------------------------------------ */
    /* Conclusão                                                           */
    /* ------------------------------------------------------------------ */

    function openCompleteModal(order, trigger) {
        if (!completeModal) {
            completeOrder(order.id);
            return;
        }

        pendingCompletionOrder = order;
        lastFocusedElement = trigger || document.activeElement;
        if (modalRoom) modalRoom.textContent = order.room;
        completeModal.classList.remove('hidden');
        document.body.classList.add('modal-open');
        if (modalConfirm) modalConfirm.focus();
    }

    function closeCompleteModal() {
        if (!completeModal) return;

        completeModal.classList.add('hidden');
        document.body.classList.remove('modal-open');
        pendingCompletionOrder = null;

        // Devolve o foco a quem abriu o modal, para não perder o contexto de quem
        // navega por teclado.
        if (lastFocusedElement && document.contains(lastFocusedElement)) {
            lastFocusedElement.focus();
        }
        lastFocusedElement = null;
    }

    function removeCard(orderId) {
        const card = cards.get(orderId);
        cards.delete(orderId);
        waitingAtFetch.delete(orderId);

        if (!card) return Promise.resolve();

        if (reducedMotion) {
            card.remove();
            return Promise.resolve();
        }

        card.classList.add('is-completing');
        return new Promise(resolve => {
            window.setTimeout(() => {
                card.remove();
                resolve();
            }, 190);
        });
    }

    async function completeOrder(orderId) {
        if (modalConfirm) modalConfirm.disabled = true;

        try {
            const response = await postJson(`${COMPLETE_URL}/${orderId}`, {});

            if (response.status === 401) {
                redirectToLogin();
                return;
            }

            const result = await response.json();

            if (response.status === 409) {
                // Outro operador chegou primeiro: recarrega em vez de reclamar.
                closeCompleteModal();
                setError('Este pedido já havia sido concluído. Lista atualizada.');
                await removeCard(orderId);
                refreshNow();
                return;
            }

            if (!response.ok || !result.success) {
                throw new Error(result.message || 'Falha ao concluir pedido.');
            }

            closeCompleteModal();
            await removeCard(orderId);
            showEmptyMessage(cards.size === 0);
            refreshClocks();
            refreshNow();
        } catch (error) {
            setError('Não foi possível concluir o pedido. Confira a conexão e tente de novo.');
            console.error(error);
        } finally {
            if (modalConfirm) modalConfirm.disabled = false;
        }
    }

    if (modalCancel) {
        modalCancel.addEventListener('click', closeCompleteModal);
    }

    if (modalConfirm) {
        modalConfirm.addEventListener('click', () => {
            if (!pendingCompletionOrder) return;
            completeOrder(pendingCompletionOrder.id);
        });
    }

    if (completeModal) {
        completeModal.addEventListener('click', event => {
            if (event.target === completeModal) closeCompleteModal();
        });

        document.addEventListener('keydown', event => {
            if (completeModal.classList.contains('hidden')) return;

            if (event.key === 'Escape') {
                closeCompleteModal();
                return;
            }

            // Mantém o Tab dentro do modal enquanto ele está aberto.
            if (event.key === 'Tab' && modalCancel && modalConfirm) {
                const first = modalCancel;
                const last = modalConfirm;
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            }
        });
    }

    renderAlertsToggle();
    requestWakeLock();
    fetchOrders();
    window.setInterval(refreshClocks, CLOCK_INTERVAL);
})();

/*
 * Painel da copa: lista os pedidos pendentes, avisa quando chega um novo e
 * conclui pedidos por um modal próprio.
 *
 * Depende de csrfToken() e postJson(), definidos em script.js.
 */

const ordersContainer = document.getElementById('orders-container');
const dashboardError = document.getElementById('dashboard-error');
const pendingCount = document.getElementById('pending-count');
const oldestOrder = document.getElementById('oldest-order');
const completeModal = document.getElementById('complete-modal');
const modalRoom = completeModal ? completeModal.querySelector('[data-modal-room]') : null;
const modalCancel = completeModal ? completeModal.querySelector('[data-modal-cancel]') : null;
const modalConfirm = completeModal ? completeModal.querySelector('[data-modal-confirm]') : null;
const knownOrderIds = new Set();
const REFRESH_INTERVAL = 10000;

let firstLoad = true;
let pendingCompletionOrder = null;
let lastFocusedElement = null;

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function notifyNewOrder() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;

        const context = new AudioContext();
        const oscillator = context.createOscillator();
        const gain = context.createGain();

        oscillator.type = 'sine';
        oscillator.frequency.value = 880;
        gain.gain.setValueAtTime(0.001, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.2, context.currentTime + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.25);

        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + 0.28);
    } catch (error) {
        console.debug('Notificação sonora indisponível.', error);
    }
}

function setError(message) {
    if (!message) {
        dashboardError.textContent = '';
        dashboardError.classList.add('hidden');
        return;
    }

    dashboardError.textContent = message;
    dashboardError.classList.remove('hidden');
}

function clearOrders() {
    while (ordersContainer.firstChild) {
        ordersContainer.removeChild(ordersContainer.firstChild);
    }
}

function createOrderCard(order) {
    const card = document.createElement('article');
    card.className = 'order-card';
    card.dataset.orderId = order.id;

    const header = document.createElement('div');
    header.className = 'order-header';

    const title = document.createElement('h2');
    title.textContent = order.room;

    const office = document.createElement('span');
    office.textContent = order.office;

    const timestamp = document.createElement('small');
    timestamp.textContent = `${order.date} - ${order.time}`;

    header.append(title, office, timestamp);

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

    const button = document.createElement('button');
    button.className = 'btn btn-success';
    button.type = 'button';
    button.textContent = 'Concluir';
    button.addEventListener('click', () => openCompleteModal(order, button));

    card.append(header, list, button);
    return card;
}

function renderOrders(orders) {
    clearOrders();
    pendingCount.textContent = orders.length;
    oldestOrder.textContent = orders[0] ? orders[0].time : '--';

    if (orders.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'empty-message';
        empty.textContent = 'Nenhum pedido pendente.';
        ordersContainer.appendChild(empty);
        return;
    }

    orders.forEach(order => {
        ordersContainer.appendChild(createOrderCard(order));
    });
}

function checkNewOrders(orders) {
    const hasNew = orders.some(order => {
        if (knownOrderIds.has(order.id)) return false;
        knownOrderIds.add(order.id);
        return true;
    });

    if (hasNew && !firstLoad) {
        notifyNewOrder();
    }

    firstLoad = false;
}

/** A sessão da copa expirou: manda para o login preservando o destino. */
function redirectToLogin() {
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
}

async function fetchOrders() {
    try {
        const response = await fetch('/api/orders', {
            headers: { 'Accept': 'application/json' }
        });

        if (response.status === 401) {
            redirectToLogin();
            return;
        }

        if (!response.ok) throw new Error('Falha ao carregar pedidos.');

        const orders = await response.json();
        setError('');
        renderOrders(orders);
        checkNewOrders(orders);
    } catch (error) {
        setError('Não foi possível carregar os pedidos. Verifique se o servidor está ativo.');
        console.error(error);
    }
}

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

function animateCompletedOrder(orderId) {
    const card = ordersContainer.querySelector(`[data-order-id="${orderId}"]`);
    if (!card || reducedMotion) {
        return Promise.resolve();
    }

    card.classList.add('is-completing');

    return new Promise(resolve => {
        window.setTimeout(resolve, 190);
    });
}

async function completeOrder(orderId) {
    if (modalConfirm) modalConfirm.disabled = true;

    try {
        const response = await postJson(`/api/complete_order/${orderId}`, {});

        if (response.status === 401) {
            redirectToLogin();
            return;
        }

        const result = await response.json();

        if (response.status === 409) {
            // Outro operador chegou primeiro: recarrega em vez de reclamar.
            closeCompleteModal();
            setError('Este pedido já havia sido concluído. Lista atualizada.');
            knownOrderIds.delete(orderId);
            fetchOrders();
            return;
        }

        if (!response.ok || !result.success) {
            throw new Error(result.message || 'Falha ao concluir pedido.');
        }

        knownOrderIds.delete(orderId);
        closeCompleteModal();
        await animateCompletedOrder(orderId);
        fetchOrders();
    } catch (error) {
        setError('Não foi possível concluir o pedido.');
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
        if (event.key === 'Escape' && !completeModal.classList.contains('hidden')) {
            closeCompleteModal();
        }
    });
}

fetchOrders();
setInterval(fetchOrders, REFRESH_INTERVAL);

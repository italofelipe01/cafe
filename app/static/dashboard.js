const ordersContainer = document.getElementById('orders-container');
const dashboardError = document.getElementById('dashboard-error');
const pendingCount = document.getElementById('pending-count');
const oldestOrder = document.getElementById('oldest-order');
const completeModal = document.getElementById('complete-modal');
const modalRoom = completeModal ? completeModal.querySelector('[data-modal-room]') : null;
const modalCancel = completeModal ? completeModal.querySelector('[data-modal-cancel]') : null;
const modalConfirm = completeModal ? completeModal.querySelector('[data-modal-confirm]') : null;
const knownOrderIds = new Set();
let firstLoad = true;
let pendingCompletionOrder = null;
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
        console.debug('Notificacao sonora indisponivel.', error);
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
    button.addEventListener('click', () => openCompleteModal(order));

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

async function fetchOrders() {
    try {
        const response = await fetch('/api/orders');
        if (!response.ok) throw new Error('Falha ao carregar pedidos.');

        const orders = await response.json();
        setError('');
        renderOrders(orders);
        checkNewOrders(orders);
    } catch (error) {
        setError('Nao foi possivel carregar os pedidos. Verifique se o servidor esta ativo.');
        console.error(error);
    }
}

function openCompleteModal(order) {
    if (!completeModal) {
        completeOrder(order.id);
        return;
    }

    pendingCompletionOrder = order;
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
        const response = await fetch(`/api/complete_order/${orderId}`, { method: 'POST' });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || 'Falha ao concluir pedido.');
        }

        knownOrderIds.delete(orderId);
        closeCompleteModal();
        await animateCompletedOrder(orderId);
        fetchOrders();
    } catch (error) {
        setError('Nao foi possivel concluir o pedido.');
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
setInterval(fetchOrders, 10000);

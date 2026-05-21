const ordersContainer = document.getElementById('orders-container');
const dashboardError = document.getElementById('dashboard-error');
const pendingCount = document.getElementById('pending-count');
const oldestOrder = document.getElementById('oldest-order');
const knownOrderIds = new Set();
let firstLoad = true;

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
    button.addEventListener('click', () => completeOrder(order.id));

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

async function completeOrder(orderId) {
    if (!window.confirm('Marcar pedido como concluido?')) return;

    try {
        const response = await fetch(`/api/complete_order/${orderId}`, { method: 'POST' });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || 'Falha ao concluir pedido.');
        }

        knownOrderIds.delete(orderId);
        fetchOrders();
    } catch (error) {
        setError('Nao foi possivel concluir o pedido.');
        console.error(error);
    }
}

fetchOrders();
setInterval(fetchOrders, 10000);

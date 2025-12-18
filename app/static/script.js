document.addEventListener('DOMContentLoaded', function () {
    const officeSelect = document.getElementById('office');
    const roomSelect = document.getElementById('room');

    // Função para atualizar as salas com base no escritório selecionado
    if (officeSelect) {
        officeSelect.addEventListener('change', function () {
            const selectedOffice = officeSelect.value;

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
                    roomSelect.innerHTML = '<option value="">Selecione uma Sala</option>';
                    rooms.forEach(room => {
                        const option = document.createElement('option');
                        option.value = room;
                        option.textContent = room;
                        roomSelect.appendChild(option);
                    });
                });
            } else {
                roomSelect.innerHTML = '<option value="">Selecione uma Sala</option>';
            }
        });
    }

    // Task 1: Client-Side Form Validation
    const form = document.querySelector('form[action="/submit_form"]');
    if (form) {
        form.addEventListener('submit', function (e) {
            const numberInputs = form.querySelectorAll('input[type="number"]');
            const cleaningSelect = form.querySelector('select[name="Limpeza da Sala"]');

            let allZero = true;

            // Check all number inputs
            numberInputs.forEach(input => {
                if (parseInt(input.value) > 0) {
                    allZero = false;
                }
            });

            // Check cleaning service
            const cleaningSelected = cleaningSelect && cleaningSelect.value === 'Sim';

            if (allZero && !cleaningSelected) {
                e.preventDefault();
                alert('Por favor, selecione pelo menos um item ou serviço.');
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const officeSelect = document.getElementById('office');
    const roomSelect = document.getElementById('room');
    
    // Função para atualizar as salas com base no escritório selecionado
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
});
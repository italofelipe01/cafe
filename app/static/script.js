document.addEventListener('DOMContentLoaded', function () {
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
});

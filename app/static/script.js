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

    // Task 2: Manual Dark/Light Mode Toggle
    const toggleButton = document.getElementById('theme-toggle');
    const logo = document.getElementById('logo');
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
        if (logo) {
            // Ensure logo src is updated based on the effective theme
            const logoPath = isDark ? '/static/images/logo-dark.png' : '/static/images/logo-light.png';
            logo.src = logoPath;
        }

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

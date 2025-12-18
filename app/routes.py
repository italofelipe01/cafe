from flask import Blueprint, render_template, request, jsonify

bp = Blueprint('main', __name__)

# Dicionário de escritórios e suas respectivas salas
offices = {
    'EBM Office Goiânia': ['Recepção', 'Sala Aton', 'Sala Chateau Marista', 'Grann Parc',
                           'Sala Metropolitan', 'Sala Nasa', 'Sala Uber',
                           'Sala Walk', 'Studio'],
    'EBM Office Campinas': ['Sala Smart Cambuí', 'Sala Wish Taquaral'],
    'EBM Espaço Goiânia': ['Auditório', 'Long Wide (Primeiro Andar)', 'Lounge Wish',
                           'Relacionamento 1', 'Relacionamento 2', 'Relacionamento 3',
                           'Sala Kazas', 'Sala Metropolitan', 'Sala Smart',
                            'Sala The Sun', 'Sala Vinhas', 'Sala Wish',
                            'Sala Wish Areião', 'Sala Wish Trinta e Sete', 'Sala Wish Vaca Brava',
                            'Wide']
}

@bp.route('/')
def index():
    return render_template('index.html', offices=offices.keys())

@bp.route('/get_rooms', methods=['POST'])
def get_rooms():
    selected_office = None
    
    # Check if request is JSON
    if request.is_json:
        data = request.get_json() # É preferível usar get_json() ao invés da propriedade .json
        # Verifica se data existe e é um dicionário para satisfazer o Pylance
        if data and isinstance(data, dict):
            selected_office = data.get('office')
    else:
        # Fallback for form data or if someone sends it differently
        selected_office = request.form.get('office')

    if not selected_office:
        return jsonify([])

    rooms = offices.get(selected_office, [])
    return jsonify(rooms)

@bp.route('/select_room', methods=['POST'])
def select_room():
    selected_office = request.form['office']
    selected_room = request.form['room']
    return render_template('sala_form.html', office=selected_office, room=selected_room)

@bp.route('/submit_form', methods=['POST'])
def submit_form():
    office = request.form['office']
    room = request.form['room']

    # Coleta os dados dos itens do formulário
    cafe_expresso_sem_acucar = request.form.get('Café expresso sem açucar', 0)
    cafe_expresso_com_acucar = request.form.get('Café expresso com açucar', 0)
    cafe_expresso_com_adocante = request.form.get('Café expresso com adoçante', 0)
    cafe_tradicional_sem_acucar = request.form.get('Café tradicional sem açucar', 0)
    cafe_tradicional_com_acucar = request.form.get('Café tradicional com açucar', 0)
    cafe_tradicional_com_adocante = request.form.get('Café tradicional com adoçante', 0)
    copo = request.form.get('Copo', 0)
    jarra_agua = request.form.get('Jarra de água', 0)
    limpeza_sala = request.form.get('Limpeza da Sala', 'Não')

    return render_template('confirm_pedido.html',
                           office=office,
                           room=room,
                           cafe_expresso_sem_acucar=cafe_expresso_sem_acucar,
                           cafe_expresso_com_acucar=cafe_expresso_com_acucar,
                           cafe_expresso_com_adocante=cafe_expresso_com_adocante,
                           cafe_tradicional_sem_acucar=cafe_tradicional_sem_acucar,
                           cafe_tradicional_com_acucar=cafe_tradicional_com_acucar,
                           cafe_tradicional_com_adocante=cafe_tradicional_com_adocante,
                           copo=copo,
                           jarra_agua=jarra_agua,
                           limpeza_sala=limpeza_sala)

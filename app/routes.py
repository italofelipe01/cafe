from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from app.extensions import db
from app.models import Order, Office, Space

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    offices = Office.query.all()
    office_names = [office.name for office in offices]
    return render_template('index.html', offices=office_names)

@bp.route('/get_rooms', methods=['POST'])
def get_rooms():
    selected_office_name = None
    
    # Check if request is JSON
    if request.is_json:
        data = request.get_json()
        if data and isinstance(data, dict):
            selected_office_name = data.get('office')
    else:
        # Fallback for form data
        selected_office_name = request.form.get('office')

    if not selected_office_name:
        return jsonify([])

    office = Office.query.filter_by(name=selected_office_name).first()
    if not office:
        return jsonify([])

    # Use relationship if possible or query Space directly
    rooms = [space.name for space in office.spaces]
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
    cafe_expresso_sem_acucar = int(request.form.get('Café expresso sem açucar', 0))
    cafe_expresso_com_acucar = int(request.form.get('Café expresso com açucar', 0))
    cafe_expresso_com_adocante = int(request.form.get('Café expresso com adoçante', 0))
    cafe_tradicional_sem_acucar = int(request.form.get('Café tradicional sem açucar', 0))
    cafe_tradicional_com_acucar = int(request.form.get('Café tradicional com açucar', 0))
    cafe_tradicional_com_adocante = int(request.form.get('Café tradicional com adoçante', 0))
    copo = int(request.form.get('Copo', 0))
    jarra_agua = int(request.form.get('Jarra de água', 0))
    limpeza_sala = request.form.get('Limpeza da Sala', 'Não')

    now = datetime.now()
    # Explicitly format time to remove microseconds
    current_time = now.time().replace(microsecond=0)

    new_order = Order(
        office=office,
        room=room,
        date_created=now.date(),
        time_created=current_time,
        cafe_expresso_sem_acucar=cafe_expresso_sem_acucar,
        cafe_expresso_com_acucar=cafe_expresso_com_acucar,
        cafe_expresso_com_adocante=cafe_expresso_com_adocante,
        cafe_tradicional_sem_acucar=cafe_tradicional_sem_acucar,
        cafe_tradicional_com_acucar=cafe_tradicional_com_acucar,
        cafe_tradicional_com_adocante=cafe_tradicional_com_adocante,
        copo=copo,
        jarra_agua=jarra_agua,
        limpeza_sala=limpeza_sala
    )

    db.session.add(new_order)
    db.session.commit()

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

@bp.route('/copa')
def copa_dashboard():
    return render_template('copa_dashboard.html')

@bp.route('/api/orders', methods=['GET'])
def get_orders():
    orders = Order.query.filter_by(status='Pending').order_by(Order.date_created.asc(), Order.time_created.asc()).all()
    return jsonify([order.to_dict() for order in orders])

@bp.route('/api/complete_order/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'Completed'
    db.session.commit()
    return jsonify({'success': True})

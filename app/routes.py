from app.extensions import db
from app.models import Office, Order, OrderItem, Product, Space, STATUS_COMPLETED, STATUS_PENDING, local_now
from flask import Blueprint, jsonify, render_template, request


bp = Blueprint("main", __name__)
MAX_QUANTITY = 1000


def active_products():
    return Product.query.filter_by(active=True).order_by(Product.sort_order.asc()).all()


def active_offices():
    return (
        Office.query.join(Office.spaces)
        .filter(Space.active.is_(True))
        .distinct()
        .order_by(Office.name.asc())
        .all()
    )


def find_space(office_name, space_name):
    return (
        Space.query.join(Space.office)
        .filter(Space.active.is_(True), Space.name == space_name)
        .filter(Office.name == office_name)
        .first()
    )


def parse_quantity(raw_value):
    if raw_value in (None, ""):
        return 0

    try:
        quantity = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError("Use apenas números inteiros nas quantidades.")

    if quantity < 0:
        raise ValueError("As quantidades não podem ser negativas.")

    if quantity > MAX_QUANTITY:
        raise ValueError(f"As quantidades não podem passar de {MAX_QUANTITY}.")

    return quantity


def collect_order_items(form):
    items = []

    for product in active_products():
        if product.input_type == "boolean":
            selected = form.get(product.form_key) == "Sim"
            if selected:
                items.append((product, 1))
            continue

        quantity = parse_quantity(form.get(product.form_key, 0))
        if quantity > 0:
            items.append((product, quantity))

    if not items:
        raise ValueError("Selecione pelo menos um item ou serviço.")

    return items


@bp.route("/")
def index():
    return render_template("index.html", offices=active_offices())


@bp.route("/get_rooms", methods=["POST"])
def get_rooms():
    selected_office_name = None

    if request.is_json:
        data = request.get_json(silent=True)
        if isinstance(data, dict):
            selected_office_name = data.get("office")
    else:
        selected_office_name = request.form.get("office")

    if not selected_office_name:
        return jsonify([])

    spaces = (
        Space.query.join(Space.office)
        .filter(Space.active.is_(True), Space.office.has(name=selected_office_name))
        .order_by(Space.name.asc())
        .all()
    )
    return jsonify([space.name for space in spaces])


@bp.route("/select_room", methods=["POST"])
def select_room():
    selected_office = request.form.get("office", "")
    selected_room = request.form.get("room", "")
    space = find_space(selected_office, selected_room)

    if not space:
        return render_template(
            "index.html",
            offices=active_offices(),
            error="Escolha um escritório e uma sala válidos.",
        ), 400

    return render_template(
        "sala_form.html",
        office=space.office,
        room=space,
        products=active_products(),
    )


@bp.route("/submit_form", methods=["POST"])
def submit_form():
    office_name = request.form.get("office", "")
    room_name = request.form.get("room", "")
    space = find_space(office_name, room_name)

    if not space:
        return render_template(
            "sala_form.html",
            office_name=office_name,
            room_name=room_name,
            products=active_products(),
            error="Escritório ou sala inválidos. Volte e selecione novamente.",
        ), 400

    try:
        requested_items = collect_order_items(request.form)
    except ValueError as exc:
        return render_template(
            "sala_form.html",
            office=space.office,
            room=space,
            products=active_products(),
            error=str(exc),
        ), 400

    new_order = Order(office=space.office, space=space, created_at=local_now())
    for product, quantity in requested_items:
        new_order.items.append(OrderItem(product=product, quantity=quantity))

    db.session.add(new_order)
    db.session.commit()

    return render_template(
        "confirm_pedido.html",
        order=new_order,
        requested_items=new_order.items,
    )


@bp.route("/copa")
def copa_dashboard():
    return render_template("copa_dashboard.html")


@bp.route("/api/orders", methods=["GET"])
def get_orders():
    orders = (
        Order.query.filter_by(status=STATUS_PENDING)
        .order_by(Order.created_at.asc())
        .all()
    )
    return jsonify([order.to_dict() for order in orders])


@bp.route("/api/complete_order/<int:order_id>", methods=["POST"])
def complete_order(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"success": False, "message": "Pedido não encontrado."}), 404

    order.status = STATUS_COMPLETED
    order.completed_at = local_now()
    db.session.commit()
    return jsonify({"success": True})

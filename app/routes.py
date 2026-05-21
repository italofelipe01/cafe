import re
import unicodedata

from app.extensions import db
from app.models import Office, Order, OrderItem, Product, Space, STATUS_COMPLETED, STATUS_PENDING, local_now
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func


bp = Blueprint("main", __name__)
MAX_QUANTITY = 1000


def active_products():
    return Product.query.filter_by(active=True).order_by(Product.sort_order.asc()).all()


def active_offices():
    return (
        Office.query.join(Office.spaces)
        .filter(Office.active.is_(True), Space.active.is_(True))
        .distinct()
        .order_by(Office.name.asc())
        .all()
    )


def find_space(office_name, space_name):
    return (
        Space.query.join(Space.office)
        .filter(Space.active.is_(True), Space.name == space_name)
        .filter(Office.active.is_(True), Office.name == office_name)
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


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    return slug or "item"


def unique_product_key(name, product_id=None):
    base_key = slugify(name)
    candidate = base_key
    suffix = 2

    while True:
        query = Product.query.filter_by(form_key=candidate)
        if product_id:
            query = query.filter(Product.id != product_id)

        if not query.first():
            return candidate

        candidate = f"{base_key}_{suffix}"
        suffix += 1


def next_product_sort_order():
    current_max = db.session.query(func.max(Product.sort_order)).scalar()
    return (current_max or 0) + 1


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
        .filter(
            Space.active.is_(True),
            Office.active.is_(True),
            Office.name == selected_office_name,
        )
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


@bp.route("/admin")
def admin_dashboard():
    stats = {
        "offices": Office.query.count(),
        "spaces": Space.query.count(),
        "products": Product.query.count(),
        "pending_orders": Order.query.filter_by(status=STATUS_PENDING).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@bp.route("/admin/offices", methods=["GET", "POST"])
def admin_offices():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Informe o nome do escritório.", "error")
            return redirect(url_for("main.admin_offices"))

        if Office.query.filter_by(name=name).first():
            flash("Já existe um escritório com esse nome.", "error")
            return redirect(url_for("main.admin_offices"))

        db.session.add(Office(name=name, active=True))
        db.session.commit()
        flash("Escritório cadastrado.", "success")
        return redirect(url_for("main.admin_offices"))

    offices = Office.query.order_by(Office.name.asc()).all()
    return render_template("admin/offices.html", offices=offices)


@bp.route("/admin/offices/<int:office_id>/update", methods=["POST"])
def admin_update_office(office_id):
    office = db.session.get(Office, office_id)
    if not office:
        flash("Escritório não encontrado.", "error")
        return redirect(url_for("main.admin_offices"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome do escritório.", "error")
        return redirect(url_for("main.admin_offices"))

    duplicate = Office.query.filter(Office.name == name, Office.id != office.id).first()
    if duplicate:
        flash("Já existe outro escritório com esse nome.", "error")
        return redirect(url_for("main.admin_offices"))

    office.name = name
    db.session.commit()
    flash("Escritório atualizado.", "success")
    return redirect(url_for("main.admin_offices"))


@bp.route("/admin/offices/<int:office_id>/toggle", methods=["POST"])
def admin_toggle_office(office_id):
    office = db.session.get(Office, office_id)
    if not office:
        flash("Escritório não encontrado.", "error")
        return redirect(url_for("main.admin_offices"))

    should_activate = not office.active
    office.active = should_activate

    if should_activate:
        for space in office.spaces:
            space.active = True
    else:
        for space in office.spaces:
            space.active = False

    db.session.commit()
    flash("Status do escritório atualizado.", "success")
    return redirect(url_for("main.admin_offices"))


@bp.route("/admin/spaces", methods=["GET", "POST"])
def admin_spaces():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        office_id = request.form.get("office_id")
        office = db.session.get(Office, int(office_id)) if office_id and office_id.isdigit() else None

        if not name or not office:
            flash("Informe escritório e nome da sala.", "error")
            return redirect(url_for("main.admin_spaces"))

        exists = Space.query.filter_by(office_id=office.id, name=name).first()
        if exists:
            flash("Já existe uma sala com esse nome nesse escritório.", "error")
            return redirect(url_for("main.admin_spaces"))

        db.session.add(Space(name=name, office=office, active=True))
        db.session.commit()
        flash("Sala cadastrada.", "success")
        return redirect(url_for("main.admin_spaces"))

    offices = Office.query.order_by(Office.name.asc()).all()
    spaces = Space.query.join(Space.office).order_by(Office.name.asc(), Space.name.asc()).all()
    return render_template("admin/spaces.html", offices=offices, spaces=spaces)


@bp.route("/admin/spaces/<int:space_id>/update", methods=["POST"])
def admin_update_space(space_id):
    space = db.session.get(Space, space_id)
    if not space:
        flash("Sala não encontrada.", "error")
        return redirect(url_for("main.admin_spaces"))

    name = request.form.get("name", "").strip()
    office_id = request.form.get("office_id")
    office = db.session.get(Office, int(office_id)) if office_id and office_id.isdigit() else None

    if not name or not office:
        flash("Informe escritório e nome da sala.", "error")
        return redirect(url_for("main.admin_spaces"))

    duplicate = Space.query.filter(
        Space.office_id == office.id,
        Space.name == name,
        Space.id != space.id,
    ).first()
    if duplicate:
        flash("Já existe outra sala com esse nome nesse escritório.", "error")
        return redirect(url_for("main.admin_spaces"))

    space.name = name
    space.office = office
    db.session.commit()
    flash("Sala atualizada.", "success")
    return redirect(url_for("main.admin_spaces"))


@bp.route("/admin/spaces/<int:space_id>/toggle", methods=["POST"])
def admin_toggle_space(space_id):
    space = db.session.get(Space, space_id)
    if not space:
        flash("Sala não encontrada.", "error")
        return redirect(url_for("main.admin_spaces"))

    if not space.active and not space.office.active:
        flash("Reative o escritório antes de ativar uma sala dele.", "error")
        return redirect(url_for("main.admin_spaces"))

    space.active = not space.active
    db.session.commit()
    flash("Status da sala atualizado.", "success")
    return redirect(url_for("main.admin_spaces"))


@bp.route("/admin/products", methods=["GET", "POST"])
def admin_products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        input_type = request.form.get("input_type", "quantity")

        if not name:
            flash("Informe o nome do insumo.", "error")
            return redirect(url_for("main.admin_products"))

        if input_type not in {"quantity", "boolean"}:
            flash("Tipo de insumo inválido.", "error")
            return redirect(url_for("main.admin_products"))

        if Product.query.filter_by(name=name).first():
            flash("Já existe um insumo com esse nome.", "error")
            return redirect(url_for("main.admin_products"))

        product = Product(
            name=name,
            form_key=unique_product_key(name),
            input_type=input_type,
            sort_order=next_product_sort_order(),
            active=True,
        )
        db.session.add(product)
        db.session.commit()
        flash("Insumo cadastrado.", "success")
        return redirect(url_for("main.admin_products"))

    products = Product.query.order_by(Product.sort_order.asc(), Product.name.asc()).all()
    return render_template("admin/products.html", products=products)


@bp.route("/admin/products/<int:product_id>/update", methods=["POST"])
def admin_update_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Insumo não encontrado.", "error")
        return redirect(url_for("main.admin_products"))

    name = request.form.get("name", "").strip()
    input_type = request.form.get("input_type", "quantity")

    if not name:
        flash("Informe o nome do insumo.", "error")
        return redirect(url_for("main.admin_products"))

    if input_type not in {"quantity", "boolean"}:
        flash("Tipo de insumo inválido.", "error")
        return redirect(url_for("main.admin_products"))

    duplicate = Product.query.filter(Product.name == name, Product.id != product.id).first()
    if duplicate:
        flash("Já existe outro insumo com esse nome.", "error")
        return redirect(url_for("main.admin_products"))

    product.name = name
    product.input_type = input_type
    db.session.commit()
    flash("Insumo atualizado.", "success")
    return redirect(url_for("main.admin_products"))


@bp.route("/admin/products/<int:product_id>/toggle", methods=["POST"])
def admin_toggle_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Insumo não encontrado.", "error")
        return redirect(url_for("main.admin_products"))

    product.active = not product.active
    db.session.commit()
    flash("Status do insumo atualizado.", "success")
    return redirect(url_for("main.admin_products"))


@bp.route("/admin/products/reorder", methods=["POST"])
def admin_reorder_products():
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("product_ids")

    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"success": False, "message": "Envie a nova ordem dos insumos."}), 400

    try:
        product_ids = [int(product_id) for product_id in raw_ids]
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Lista de insumos inválida."}), 400

    if len(product_ids) != len(set(product_ids)):
        return jsonify({"success": False, "message": "A lista de insumos contém duplicidades."}), 400

    products = Product.query.filter(Product.id.in_(product_ids)).all()
    if len(products) != len(product_ids):
        return jsonify({"success": False, "message": "Um ou mais insumos não foram encontrados."}), 404

    products_by_id = {product.id: product for product in products}
    for index, product_id in enumerate(product_ids, start=1):
        products_by_id[product_id].sort_order = index

    db.session.commit()
    return jsonify({"success": True})


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

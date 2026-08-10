"""Rotas HTTP.

Cada view faz três coisas: lê a requisição, chama uma função de ``app.services``
e escolhe a resposta. Validação e acesso a dados ficam na camada de serviço.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.typing import ResponseReturnValue

from app import audit, services
from app.extensions import csrf, limiter
from app.security import (
    ROLE_ADMIN,
    ROLE_COPA,
    ROLE_LABELS,
    authenticate,
    current_roles,
    grant_role,
    is_authenticated,
    login_required,
    revoke_roles,
    safe_redirect_target,
)
from app.services import NotFoundError, ServiceError

bp = Blueprint("main", __name__)


def order_rate_limit() -> str:
    return current_app.config["RATELIMIT_ORDER"]


def login_rate_limit() -> str:
    return current_app.config["RATELIMIT_LOGIN"]


@bp.app_context_processor
def inject_session_state() -> dict[str, object]:
    """Disponibiliza o estado de acesso para o layout base."""

    return {
        "is_authenticated": is_authenticated(),
        "session_roles": sorted(current_roles()),
        "can_admin": ROLE_ADMIN in current_roles(),
        "can_copa": ROLE_COPA in current_roles(),
        "role_labels": ROLE_LABELS,
    }


def admin_form_action(redirect_endpoint: str) -> Callable:
    """Executa uma ação de administração traduzindo falhas em mensagens flash.

    As seis telas administrativas repetiam o mesmo bloco de buscar registro,
    dar ``flash`` e redirecionar. Agora a view só descreve o que quer fazer.
    """

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                message = view(*args, **kwargs)
            except ServiceError as error:
                flash(error.message, "error")
            else:
                if message:
                    flash(message, "success")

            return redirect(url_for(redirect_endpoint))

        return wrapped

    return decorator


# --------------------------------------------------------------------------- #
# Acesso
# --------------------------------------------------------------------------- #

@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(login_rate_limit, methods=["POST"])
def login() -> ResponseReturnValue:
    destination = safe_redirect_target(request.values.get("next"))

    if request.method == "POST":
        role = authenticate(request.form.get("password", ""))

        if not role:
            audit("login.falha")
            return (
                render_template(
                    "login.html",
                    error="Senha incorreta.",
                    next_url=destination,
                ),
                401,
            )

        session.clear()
        grant_role(role)
        audit("login.sucesso", perfil=role)
        flash(f"Acesso liberado: {ROLE_LABELS[role]}.", "success")
        return redirect(destination or default_landing())

    return render_template("login.html", next_url=destination)


def default_landing() -> str:
    if ROLE_ADMIN in current_roles():
        return url_for("main.admin_dashboard")
    if ROLE_COPA in current_roles():
        return url_for("main.copa_dashboard")
    return url_for("main.index")


@bp.route("/logout", methods=["POST"])
def logout() -> ResponseReturnValue:
    audit("logout")
    revoke_roles()
    session.clear()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("main.index"))


# --------------------------------------------------------------------------- #
# Pedido (público)
# --------------------------------------------------------------------------- #

@bp.route("/")
def index() -> str:
    return render_template(
        "index.html",
        offices=services.active_offices(),
        catalog=services.active_catalog_by_office(),
    )


@bp.route("/api/rooms", methods=["GET"])
@bp.route("/get_rooms", methods=["GET", "POST"])
@csrf.exempt
def get_rooms() -> ResponseReturnValue:
    """Salas ativas de um escritório.

    Consulta sem efeito colateral, por isso isenta de CSRF. Aceita o POST
    histórico e o GET, que é a forma correta para uma leitura.
    """

    office_name = request.args.get("office")

    if not office_name and request.method == "POST":
        if request.is_json:
            data = request.get_json(silent=True)
            office_name = data.get("office") if isinstance(data, dict) else None
        else:
            office_name = request.form.get("office")

    if not office_name:
        return jsonify([])

    return jsonify([space.name for space in services.active_spaces_for(office_name)])


@bp.route("/select_room", methods=["POST"])
def select_room() -> ResponseReturnValue:
    try:
        space = services.require_space(
            request.form.get("office", ""), request.form.get("room", "")
        )
    except ServiceError as error:
        return (
            render_template(
                "index.html",
                offices=services.active_offices(),
                catalog=services.active_catalog_by_office(),
                error=error.message,
            ),
            error.status_code,
        )

    return render_template(
        "sala_form.html",
        office=space.office,
        room=space,
        products=services.active_products(),
    )


@bp.route("/submit_form", methods=["POST"])
@limiter.limit(order_rate_limit)
def submit_form() -> ResponseReturnValue:
    office_name = request.form.get("office", "")
    room_name = request.form.get("room", "")

    try:
        space = services.require_space(office_name, room_name)
    except ServiceError:
        return (
            render_template(
                "sala_form.html",
                office_name=office_name,
                room_name=room_name,
                products=services.active_products(),
                error="Escritório ou sala inválidos. Volte e selecione novamente.",
            ),
            400,
        )

    try:
        requested_items = services.collect_order_items(request.form)
    except ServiceError as error:
        return (
            render_template(
                "sala_form.html",
                office=space.office,
                room=space,
                products=services.active_products(),
                error=error.message,
            ),
            error.status_code,
        )

    order = services.create_order(space, requested_items)
    audit("pedido.criado", pedido=order.id, sala=space.name, itens=len(requested_items))

    return render_template(
        "confirm_pedido.html", order=order, requested_items=order.items
    )


# --------------------------------------------------------------------------- #
# Painel da copa
# --------------------------------------------------------------------------- #

@bp.route("/copa")
@login_required(ROLE_COPA)
def copa_dashboard() -> str:
    return render_template("copa_dashboard.html")


@bp.route("/api/orders", methods=["GET"])
@login_required(ROLE_COPA)
def get_orders() -> ResponseReturnValue:
    return jsonify([order.to_dict() for order in services.pending_orders()])


@bp.route("/api/complete_order/<int:order_id>", methods=["POST"])
@login_required(ROLE_COPA)
def complete_order(order_id: int) -> ResponseReturnValue:
    try:
        order = services.complete_order(order_id)
    except ServiceError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code

    audit("pedido.concluido", pedido=order.id, sala=order.space.name)
    return jsonify({"success": True})


# --------------------------------------------------------------------------- #
# Administração
# --------------------------------------------------------------------------- #

@bp.route("/admin")
@login_required(ROLE_ADMIN)
def admin_dashboard() -> str:
    return render_template("admin/dashboard.html", stats=services.dashboard_stats())


@bp.route("/admin/history")
@login_required(ROLE_ADMIN)
def admin_history() -> ResponseReturnValue:
    raw_office_id = request.args.get("office_id", "").strip()
    office_id = int(raw_office_id) if raw_office_id.isdecimal() else None
    page = request.args.get("page", "1")
    page_number = int(page) if page.isdecimal() and int(page) > 0 else 1

    try:
        start = services.parse_date(request.args.get("start"))
        end = services.parse_date(request.args.get("end"))
        pagination = services.completed_orders_page(
            start=start, end=end, office_id=office_id, page=page_number
        )
        summary = services.completed_orders_summary(
            start=start, end=end, office_id=office_id
        )
    except ServiceError as error:
        return (
            render_template(
                "admin/history.html",
                offices=services.all_offices(),
                pagination=None,
                summary={"orders": 0, "items": 0},
                filters={},
                error=error.message,
            ),
            error.status_code,
        )

    return render_template(
        "admin/history.html",
        offices=services.all_offices(),
        pagination=pagination,
        summary=summary,
        filters={
            "start": request.args.get("start", ""),
            "end": request.args.get("end", ""),
            "office_id": raw_office_id,
        },
    )


@bp.route("/admin/offices", methods=["GET"])
@login_required(ROLE_ADMIN)
def admin_offices() -> str:
    return render_template("admin/offices.html", offices=services.all_offices())


@bp.route("/admin/offices", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_offices")
def admin_create_office() -> str:
    office = services.create_office(request.form.get("name"))
    audit("escritorio.criado", escritorio=office.name)
    return "Escritório cadastrado."


@bp.route("/admin/offices/<int:office_id>/update", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_offices")
def admin_update_office(office_id: int) -> str:
    office = services.update_office(office_id, request.form.get("name"))
    audit("escritorio.atualizado", escritorio=office.name)
    return "Escritório atualizado."


@bp.route("/admin/offices/<int:office_id>/toggle", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_offices")
def admin_toggle_office(office_id: int) -> str:
    office = services.toggle_office(office_id)
    audit("escritorio.status", escritorio=office.name, ativo=office.active)
    return "Status do escritório atualizado."


@bp.route("/admin/spaces", methods=["GET"])
@login_required(ROLE_ADMIN)
def admin_spaces() -> str:
    return render_template(
        "admin/spaces.html",
        offices=services.all_offices(),
        spaces=services.all_spaces(),
    )


@bp.route("/admin/spaces", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_spaces")
def admin_create_space() -> str:
    space = services.create_space(
        request.form.get("office_id"), request.form.get("name")
    )
    audit("sala.criada", sala=space.name, escritorio=space.office.name)
    return "Sala cadastrada."


@bp.route("/admin/spaces/<int:space_id>/update", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_spaces")
def admin_update_space(space_id: int) -> str:
    space = services.update_space(
        space_id, request.form.get("office_id"), request.form.get("name")
    )
    audit("sala.atualizada", sala=space.name, escritorio=space.office.name)
    return "Sala atualizada."


@bp.route("/admin/spaces/<int:space_id>/toggle", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_spaces")
def admin_toggle_space(space_id: int) -> str:
    space = services.toggle_space(space_id)
    audit("sala.status", sala=space.name, ativa=space.active)
    return "Status da sala atualizado."


@bp.route("/admin/products", methods=["GET"])
@login_required(ROLE_ADMIN)
def admin_products() -> str:
    return render_template("admin/products.html", products=services.all_products())


@bp.route("/admin/products", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_products")
def admin_create_product() -> str:
    product = services.create_product(
        request.form.get("name"), request.form.get("input_type")
    )
    audit("insumo.criado", insumo=product.name, tipo=product.input_type)
    return "Insumo cadastrado."


@bp.route("/admin/products/<int:product_id>/update", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_products")
def admin_update_product(product_id: int) -> str:
    product = services.update_product(
        product_id, request.form.get("name"), request.form.get("input_type")
    )
    audit("insumo.atualizado", insumo=product.name, tipo=product.input_type)
    return "Insumo atualizado."


@bp.route("/admin/products/<int:product_id>/toggle", methods=["POST"])
@login_required(ROLE_ADMIN)
@admin_form_action("main.admin_products")
def admin_toggle_product(product_id: int) -> str:
    product = services.toggle_product(product_id)
    audit("insumo.status", insumo=product.name, ativo=product.active)
    return "Status do insumo atualizado."


@bp.route("/admin/products/reorder", methods=["POST"])
@login_required(ROLE_ADMIN)
def admin_reorder_products() -> ResponseReturnValue:
    data = request.get_json(silent=True) or {}

    try:
        product_ids = services.reorder_products(data.get("product_ids"))
    except NotFoundError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code
    except ServiceError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code

    audit("insumo.reordenado", total=len(product_ids))
    return jsonify({"success": True})


# --------------------------------------------------------------------------- #
# Operação
# --------------------------------------------------------------------------- #

@bp.route("/health")
@csrf.exempt
def health() -> ResponseReturnValue:
    """Verificação de saúde: responde 503 se o banco não estiver acessível."""

    from sqlalchemy import text

    from app.extensions import db

    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - qualquer falha aqui significa indisponível
        current_app.logger.exception("Health check falhou ao consultar o banco.")
        return jsonify({"status": "degraded", "database": "unavailable"}), 503

    return jsonify({"status": "ok", "database": "ok"})

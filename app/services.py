"""Regra de negócio do portal.

As rotas ficam responsáveis apenas por traduzir HTTP: ler o formulário, chamar
uma função daqui e escolher o template ou o JSON de resposta. Toda validação e
todo acesso a dados moram neste módulo, o que permite testá-los sem cliente HTTP
e evita que as telas de administração repitam o mesmo bloco de verificação.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import date, datetime, time
from typing import NamedTuple, TypedDict

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    NOTE_MAX_LENGTH,
    STATUS_COMPLETED,
    STATUS_PENDING,
    Office,
    Order,
    OrderItem,
    Product,
    Space,
    local_now,
)

MAX_QUANTITY = 1000
INPUT_TYPES = {"quantity", "boolean"}
HISTORY_PAGE_SIZE = 25
REQUEST_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,64}")


class ServiceError(Exception):
    """Falha esperada de negócio, já com mensagem pronta para o usuário."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class HistorySummary(NamedTuple):
    """Totais do período consultado no histórico.

    É uma tupla nomeada, e não um dicionário, por causa de como o Jinja resolve
    ``summary.items``: ele tenta o atributo antes da chave, e ``dict.items`` é
    um método — a tela chegou a exibir ``<built-in method items of dict...>``
    no lugar do total. Uma tupla não tem esse método, então o acesso por ponto
    só pode significar o campo.

    ``average_minutes`` é o tempo médio entre o pedido e a conclusão, ou
    ``None`` quando não há pedido concluído no período.
    """

    orders: int
    items: int
    average_minutes: int | None = None


class HistoryFilters(TypedDict):
    """Filtros do histórico, já convertidos a partir da query string."""

    start: date | None
    end: date | None
    office_id: int | None


class PlacedOrder(NamedTuple):
    """Resultado do envio de um pedido.

    ``created`` é falso quando o mesmo formulário já tinha gerado o pedido:
    nesse caso ``order`` é o pedido original, e nada foi gravado de novo.
    """

    order: Order
    created: bool


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #

def active_products() -> list[Product]:
    return list(
        db.session.scalars(
            select(Product).filter_by(active=True).order_by(Product.sort_order.asc())
        )
    )


def active_offices() -> list[Office]:
    """Escritórios ativos que têm ao menos uma sala ativa para receber pedidos."""

    return list(
        db.session.scalars(
            select(Office)
            .join(Office.spaces)
            .where(Office.active.is_(True), Space.active.is_(True))
            .distinct()
            .order_by(Office.name.asc())
        )
    )


def active_spaces_for(office_name: str) -> list[Space]:
    return list(
        db.session.scalars(
            select(Space)
            .join(Space.office)
            .where(
                Space.active.is_(True),
                Office.active.is_(True),
                Office.name == office_name,
            )
            .order_by(Space.name.asc())
        )
    )


def active_catalog_by_office() -> list[tuple[Office, list[Space]]]:
    """Escritórios ativos com suas salas ativas, para renderizar sem JavaScript."""

    return [
        (office, [space for space in office.spaces if space.active])
        for office in active_offices()
    ]


def require_orderable_space(space_id: int) -> Space:
    """Sala ativa, de escritório ativo, pronta para receber pedido pelo link direto."""

    space = db.session.get(Space, space_id)
    if not space or not space.active or not space.office.active:
        raise NotFoundError("Esta sala não está disponível para pedidos.")
    return space


def find_space(office_name: str, space_name: str) -> Space | None:
    return db.session.scalars(
        select(Space)
        .join(Space.office)
        .where(
            Space.active.is_(True),
            Space.name == space_name,
            Office.active.is_(True),
            Office.name == office_name,
        )
    ).first()


def require_space(office_name: str, space_name: str) -> Space:
    space = find_space(office_name, space_name)
    if not space:
        raise ServiceError("Escolha um escritório e uma sala válidos.")
    return space


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    return slug or "item"


def unique_product_key(name: str, product_id: int | None = None) -> str:
    base_key = slugify(name)
    candidate = base_key
    suffix = 2

    while True:
        query = select(Product).filter_by(form_key=candidate)
        if product_id:
            query = query.where(Product.id != product_id)

        if db.session.scalars(query).first() is None:
            return candidate

        candidate = f"{base_key}_{suffix}"
        suffix += 1


def next_product_sort_order() -> int:
    current_max = db.session.scalar(select(func.max(Product.sort_order)))
    return (current_max or 0) + 1


# --------------------------------------------------------------------------- #
# Pedidos
# --------------------------------------------------------------------------- #

def parse_quantity(raw_value: object) -> int:
    """Converte a quantidade do formulário, recusando qualquer coisa exótica.

    ``int()`` do Python aceita sinal, espaços e sublinhado como separador de
    milhar — ``int("1_0")`` vale 10. A checagem por dígitos vem antes justamente
    para que o valor gravado seja sempre o valor digitado.
    """

    if raw_value is None:
        return 0

    text = str(raw_value).strip()
    if not text:
        return 0

    if not text.isdecimal():
        raise ServiceError("Use apenas números inteiros e positivos nas quantidades.")

    quantity = int(text)

    if quantity > MAX_QUANTITY:
        raise ServiceError(f"As quantidades não podem passar de {MAX_QUANTITY}.")

    return quantity


def collect_order_items(form) -> list[tuple[Product, int]]:
    items: list[tuple[Product, int]] = []

    for product in active_products():
        if product.input_type == "boolean":
            if form.get(product.form_key) == "Sim":
                items.append((product, 1))
            continue

        quantity = parse_quantity(form.get(product.form_key, 0))
        if quantity > 0:
            items.append((product, quantity))

    if not items:
        raise ServiceError("Selecione pelo menos um item ou serviço.")

    return items


def new_request_token() -> str:
    """Identificador de um formulário de pedido, para reconhecer reenvios."""

    return secrets.token_urlsafe(24)


def clean_request_token(raw_value: object) -> str | None:
    """Token recebido do formulário, ou ``None`` se ausente ou malformado.

    Um token estranho não recusa o pedido: só desliga a proteção contra
    reenvio para aquele envio. Quem pede café não pode ficar sem pedir porque
    um campo oculto chegou diferente.
    """

    token = str(raw_value or "").strip()
    return token if REQUEST_TOKEN_PATTERN.fullmatch(token) else None


def clean_note(raw_value: object) -> str | None:
    """Observação do pedido em uma linha, sem espaços sobrando."""

    note = " ".join(str(raw_value or "").split())
    if not note:
        return None
    if len(note) > NOTE_MAX_LENGTH:
        raise ServiceError(f"A observação pode ter até {NOTE_MAX_LENGTH} caracteres.")
    return note


def find_order_by_token(request_token: str | None) -> Order | None:
    if not request_token:
        return None
    return db.session.scalars(
        select(Order).filter_by(request_token=request_token)
    ).first()


def create_order(
    space: Space,
    requested_items: list[tuple[Product, int]],
    note: str | None = None,
    request_token: str | None = None,
) -> PlacedOrder:
    """Grava o pedido, a menos que o mesmo formulário já o tenha gravado.

    Duplo clique, F5 na confirmação e reenvio por rede instável chegam com o
    mesmo ``request_token``. Em vez de abrir outro pedido para a copa atender
    duas vezes, devolve o original. Dois envios simultâneos que passem juntos
    pela consulta esbarram no índice único, e o segundo também recebe o
    original.
    """

    existing = find_order_by_token(request_token)
    if existing:
        return PlacedOrder(existing, created=False)

    order = Order(
        office=space.office,
        space=space,
        created_at=local_now(),
        note=note,
        request_token=request_token,
    )
    for product, quantity in requested_items:
        order.items.append(OrderItem(product=product, quantity=quantity))

    db.session.add(order)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = find_order_by_token(request_token)
        if existing is None:
            raise
        return PlacedOrder(existing, created=False)

    return PlacedOrder(order, created=True)


def get_order(order_id: int) -> Order:
    order = db.session.get(Order, order_id)
    if not order:
        raise NotFoundError("Pedido não encontrado.")
    return order


# Carrega sala, escritório, itens e insumos junto com o pedido. Sem isso, cada
# cartão do painel (consultado a cada poucos segundos) e cada linha do histórico
# disparavam uma consulta por relação.
ORDER_DETAILS = (
    selectinload(Order.office),
    selectinload(Order.space),
    selectinload(Order.items).selectinload(OrderItem.product),
)


def pending_orders() -> list[Order]:
    return list(
        db.session.scalars(
            select(Order)
            .options(*ORDER_DETAILS)
            .filter_by(status=STATUS_PENDING)
            .order_by(Order.created_at.asc())
        )
    )


def complete_order(order_id: int) -> Order:
    """Marca o pedido como concluído.

    Concluir duas vezes é recusado em vez de sobrescrever ``completed_at``: o
    horário da primeira conclusão é o dado que a operação usa, e perdê-lo por
    um duplo clique apagaria o histórico real do atendimento.
    """

    order = get_order(order_id)

    if order.status == STATUS_COMPLETED:
        raise ServiceError("Este pedido já foi concluído.", status_code=409)

    order.status = STATUS_COMPLETED
    order.completed_at = local_now()
    db.session.commit()
    return order


def parse_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ServiceError("Use datas no formato AAAA-MM-DD.") from exc


def _history_filters(
    start: date | None, end: date | None, office_id: int | None
) -> list:
    """Filtros comuns à tela, aos totais e à exportação do histórico."""

    if start and end and start > end:
        raise ServiceError("A data inicial não pode ser posterior à data final.")

    filters = [Order.status == STATUS_COMPLETED]
    if start:
        filters.append(Order.created_at >= datetime.combine(start, time.min))
    if end:
        filters.append(Order.created_at <= datetime.combine(end, time.max))
    if office_id:
        filters.append(Order.office_id == office_id)
    return filters


def completed_orders_page(
    start: date | None = None,
    end: date | None = None,
    office_id: int | None = None,
    page: int = 1,
    per_page: int = HISTORY_PAGE_SIZE,
):
    """Histórico paginado de pedidos concluídos, do mais recente para o mais antigo."""

    query = (
        select(Order)
        .options(*ORDER_DETAILS)
        .where(*_history_filters(start, end, office_id))
        .order_by(Order.completed_at.desc(), Order.id.desc())
    )
    return db.paginate(query, page=page, per_page=per_page, error_out=False)


def completed_orders_summary(
    start: date | None = None,
    end: date | None = None,
    office_id: int | None = None,
) -> HistorySummary:
    """Totais do período consultado, para o cabeçalho do histórico."""

    filters = _history_filters(start, end, office_id)

    total_orders = db.session.scalar(
        select(func.count(Order.id)).where(*filters)
    ) or 0

    total_items = db.session.scalar(
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .select_from(OrderItem)
        .join(OrderItem.order)
        .where(*filters)
    ) or 0

    # A diferença entre datas é escrita de um jeito em cada banco (julianday no
    # SQLite, EXTRACT no PostgreSQL). Somar em Python mantém uma consulta só,
    # e o volume de um portal de copa cabe com folga na memória.
    durations = [
        (completed_at - created_at).total_seconds()
        for created_at, completed_at in db.session.execute(
            select(Order.created_at, Order.completed_at).where(*filters)
        )
        if completed_at is not None
    ]
    average_minutes = (
        round(sum(durations) / len(durations) / 60) if durations else None
    )

    return HistorySummary(
        orders=total_orders, items=int(total_items), average_minutes=average_minutes
    )


HISTORY_EXPORT_HEADER = [
    "Pedido",
    "Escritório",
    "Sala",
    "Solicitado em",
    "Concluído em",
    "Espera (min)",
    "Itens",
    "Observação",
]


# Caracteres com que o Excel e o LibreOffice começam uma fórmula.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_safe(value: str) -> str:
    """Impede que um texto vire fórmula ao abrir o CSV numa planilha.

    A observação vem do formulário público: sem isto, quem pedisse café com a
    observação ``=HYPERLINK(...)`` plantaria um link (ou coisa pior) na planilha
    de quem administra o portal. O apóstrofo inicial faz a planilha tratar a
    célula como texto.
    """

    return f"'{value}" if value.startswith(FORMULA_PREFIXES) else value


def completed_orders_export(
    start: date | None = None,
    end: date | None = None,
    office_id: int | None = None,
) -> list[list[str]]:
    """Linhas do histórico filtrado, na ordem de ``HISTORY_EXPORT_HEADER``.

    Os textos passam por :func:`spreadsheet_safe`; números e datas, que o
    próprio sistema escreve, não precisam.
    """

    orders = db.session.scalars(
        select(Order)
        .options(*ORDER_DETAILS)
        .where(*_history_filters(start, end, office_id))
        .order_by(Order.completed_at.desc(), Order.id.desc())
    )

    rows: list[list[str]] = []
    for order in orders:
        completed = order.completed_at
        rows.append(
            [
                str(order.id),
                spreadsheet_safe(order.office.name),
                spreadsheet_safe(order.space.name),
                order.created_at.strftime("%d/%m/%Y %H:%M"),
                completed.strftime("%d/%m/%Y %H:%M") if completed else "",
                str(round(order.waiting_seconds() / 60)) if completed else "",
                spreadsheet_safe(
                    "; ".join(
                        f"{item.product.name}: {item.display_quantity()}"
                        for item in order.items
                    )
                ),
                spreadsheet_safe(order.note or ""),
            ]
        )
    return rows


def dashboard_stats() -> dict[str, int]:
    return {
        "offices": db.session.scalar(select(func.count(Office.id))) or 0,
        "spaces": db.session.scalar(select(func.count(Space.id))) or 0,
        "products": db.session.scalar(select(func.count(Product.id))) or 0,
        "pending_orders": db.session.scalar(
            select(func.count(Order.id)).where(Order.status == STATUS_PENDING)
        )
        or 0,
        "completed_orders": db.session.scalar(
            select(func.count(Order.id)).where(Order.status == STATUS_COMPLETED)
        )
        or 0,
    }


# --------------------------------------------------------------------------- #
# Administração — escritórios
# --------------------------------------------------------------------------- #

def all_offices() -> list[Office]:
    return list(db.session.scalars(select(Office).order_by(Office.name.asc())))


def get_office(office_id: int) -> Office:
    office = db.session.get(Office, office_id)
    if not office:
        raise NotFoundError("Escritório não encontrado.")
    return office


def _require_name(raw_name: str | None, message: str) -> str:
    name = (raw_name or "").strip()
    if not name:
        raise ServiceError(message)
    return name


def create_office(raw_name: str | None) -> Office:
    name = _require_name(raw_name, "Informe o nome do escritório.")

    if db.session.scalars(select(Office).filter_by(name=name)).first():
        raise ServiceError("Já existe um escritório com esse nome.")

    office = Office(name=name, active=True)
    db.session.add(office)
    db.session.commit()
    return office


def update_office(office_id: int, raw_name: str | None) -> Office:
    office = get_office(office_id)
    name = _require_name(raw_name, "Informe o nome do escritório.")

    duplicate = db.session.scalars(
        select(Office).where(Office.name == name, Office.id != office.id)
    ).first()
    if duplicate:
        raise ServiceError("Já existe outro escritório com esse nome.")

    office.name = name
    db.session.commit()
    return office


def toggle_office(office_id: int) -> Office:
    """Inverte o status do escritório e leva todas as salas dele junto."""

    office = get_office(office_id)
    office.active = not office.active

    for space in office.spaces:
        space.active = office.active

    db.session.commit()
    return office


# --------------------------------------------------------------------------- #
# Administração — salas
# --------------------------------------------------------------------------- #

def all_spaces() -> list[Space]:
    return list(
        db.session.scalars(
            select(Space).join(Space.office).order_by(Office.name.asc(), Space.name.asc())
        )
    )


def get_space(space_id: int) -> Space:
    space = db.session.get(Space, space_id)
    if not space:
        raise NotFoundError("Sala não encontrada.")
    return space


def _require_office(raw_office_id: str | None) -> Office:
    raw = (raw_office_id or "").strip()
    if not raw.isdecimal():
        raise ServiceError("Informe escritório e nome da sala.")

    office = db.session.get(Office, int(raw))
    if not office:
        raise ServiceError("Informe escritório e nome da sala.")
    return office


def create_space(raw_office_id: str | None, raw_name: str | None) -> Space:
    office = _require_office(raw_office_id)
    name = _require_name(raw_name, "Informe escritório e nome da sala.")

    exists = db.session.scalars(
        select(Space).filter_by(office_id=office.id, name=name)
    ).first()
    if exists:
        raise ServiceError("Já existe uma sala com esse nome nesse escritório.")

    space = Space(name=name, office=office, active=office.active)
    db.session.add(space)
    db.session.commit()
    return space


def update_space(space_id: int, raw_office_id: str | None, raw_name: str | None) -> Space:
    space = get_space(space_id)
    office = _require_office(raw_office_id)
    name = _require_name(raw_name, "Informe escritório e nome da sala.")

    duplicate = db.session.scalars(
        select(Space).where(
            Space.office_id == office.id,
            Space.name == name,
            Space.id != space.id,
        )
    ).first()
    if duplicate:
        raise ServiceError("Já existe outra sala com esse nome nesse escritório.")

    space.name = name
    space.office = office
    db.session.commit()
    return space


def toggle_space(space_id: int) -> Space:
    space = get_space(space_id)

    if not space.active and not space.office.active:
        raise ServiceError("Reative o escritório antes de ativar uma sala dele.")

    space.active = not space.active
    db.session.commit()
    return space


# --------------------------------------------------------------------------- #
# Administração — insumos
# --------------------------------------------------------------------------- #

def all_products() -> list[Product]:
    return list(
        db.session.scalars(
            select(Product).order_by(Product.sort_order.asc(), Product.name.asc())
        )
    )


def get_product(product_id: int) -> Product:
    product = db.session.get(Product, product_id)
    if not product:
        raise NotFoundError("Insumo não encontrado.")
    return product


def _require_input_type(raw_input_type: str | None) -> str:
    input_type = (raw_input_type or "quantity").strip()
    if input_type not in INPUT_TYPES:
        raise ServiceError("Tipo de insumo inválido.")
    return input_type


def create_product(raw_name: str | None, raw_input_type: str | None) -> Product:
    name = _require_name(raw_name, "Informe o nome do insumo.")
    input_type = _require_input_type(raw_input_type)

    if db.session.scalars(select(Product).filter_by(name=name)).first():
        raise ServiceError("Já existe um insumo com esse nome.")

    product = Product(
        name=name,
        form_key=unique_product_key(name),
        input_type=input_type,
        sort_order=next_product_sort_order(),
        active=True,
    )
    db.session.add(product)
    db.session.commit()
    return product


def update_product(
    product_id: int, raw_name: str | None, raw_input_type: str | None
) -> Product:
    product = get_product(product_id)
    name = _require_name(raw_name, "Informe o nome do insumo.")
    input_type = _require_input_type(raw_input_type)

    duplicate = db.session.scalars(
        select(Product).where(Product.name == name, Product.id != product.id)
    ).first()
    if duplicate:
        raise ServiceError("Já existe outro insumo com esse nome.")

    product.name = name
    product.input_type = input_type
    db.session.commit()
    return product


def toggle_product(product_id: int) -> Product:
    product = get_product(product_id)
    product.active = not product.active
    db.session.commit()
    return product


def reorder_products(raw_ids: object) -> list[int]:
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ServiceError("Envie a nova ordem dos insumos.")

    try:
        product_ids = [int(product_id) for product_id in raw_ids]
    except (TypeError, ValueError) as exc:
        raise ServiceError("Lista de insumos inválida.") from exc

    if len(product_ids) != len(set(product_ids)):
        raise ServiceError("A lista de insumos contém duplicidades.")

    products = list(
        db.session.scalars(select(Product).where(Product.id.in_(product_ids)))
    )
    if len(products) != len(product_ids):
        raise NotFoundError("Um ou mais insumos não foram encontrados.")

    products_by_id = {product.id: product for product in products}
    for index, product_id in enumerate(product_ids, start=1):
        products_by_id[product_id].sort_order = index

    db.session.commit()
    return product_ids

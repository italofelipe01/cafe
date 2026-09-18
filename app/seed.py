"""Catálogo inicial do portal.

A semeadura é **aditiva**: cria o que ainda não existe e nunca reescreve um
registro existente. Nome, tipo, posição na ordenação e status de um item já
gravado pertencem a quem administra o portal, não a este arquivo — antes,
o seed rodava a cada boot e devolvia todo o catálogo ao estado de fábrica,
apagando reordenações e inativações feitas na tela de administração.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.extensions import db
from app.models import Office, Product, Space

logger = logging.getLogger(__name__)


OFFICES_DATA: dict[str, list[str]] = {
    "Sede Centro": [
        "Recepção",
        "Sala Bourbon",
        "Sala Robusta",
        "Sala Mundo Novo",
        "Sala Acaiá",
        "Sala Icatu",
        "Auditório",
        "Sala Obatã",
    ],
    "Filial Sul": ["Sala Arábica", "Sala Catuaí"],
    "Espaço Eventos": [
        "Auditório",
        "Lounge",
        "Sala Geisha",
        "Sala Conilon",
        "Sala Maragogipe",
        "Sala Topázio",
        "Sala de Reunião 1",
        "Sala de Reunião 2",
    ],
}

PRODUCTS_DATA: list[tuple[str, str, str]] = [
    ("Café expresso sem açúcar", "cafe_expresso_sem_acucar", "quantity"),
    ("Café expresso com açúcar", "cafe_expresso_com_acucar", "quantity"),
    ("Café expresso com adoçante", "cafe_expresso_com_adocante", "quantity"),
    ("Café tradicional sem açúcar", "cafe_tradicional_sem_acucar", "quantity"),
    ("Café tradicional com açúcar", "cafe_tradicional_com_acucar", "quantity"),
    ("Café tradicional com adoçante", "cafe_tradicional_com_adocante", "quantity"),
    ("Copo", "copo", "quantity"),
    ("Jarra de água", "jarra_agua", "quantity"),
    ("Limpeza da sala", "limpeza_sala", "boolean"),
]


def seed_database() -> dict[str, int]:
    """Garante o catálogo inicial sem alterar nada que já exista.

    Devolve quantos registros foram efetivamente criados, para que a linha de
    comando e os testes possam afirmar que uma segunda execução não muda nada.
    """

    created = {"offices": 0, "spaces": 0, "products": 0}

    for office_name, space_names in OFFICES_DATA.items():
        office = db.session.scalars(
            select(Office).filter_by(name=office_name)
        ).first()

        if not office:
            office = Office(name=office_name, active=True)
            db.session.add(office)
            db.session.flush()
            created["offices"] += 1

        for space_name in space_names:
            exists = db.session.scalars(
                select(Space).filter_by(office_id=office.id, name=space_name)
            ).first()
            if exists:
                continue

            # Uma sala nova nasce alinhada ao escritório: se a unidade está
            # desativada, a sala não pode aparecer no formulário de pedido.
            db.session.add(
                Space(name=space_name, office_id=office.id, active=office.active)
            )
            created["spaces"] += 1

    next_sort_order = _next_sort_order()

    for name, form_key, input_type in PRODUCTS_DATA:
        exists = db.session.scalars(
            select(Product).filter_by(form_key=form_key)
        ).first()
        if exists:
            continue

        db.session.add(
            Product(
                name=name,
                form_key=form_key,
                input_type=input_type,
                sort_order=next_sort_order,
                active=True,
            )
        )
        next_sort_order += 1
        created["products"] += 1

    db.session.commit()

    if any(created.values()):
        logger.info(
            "Catálogo semeado: %s escritórios, %s salas, %s insumos criados.",
            created["offices"],
            created["spaces"],
            created["products"],
        )

    return created


def _next_sort_order() -> int:
    from sqlalchemy import func

    current_max = db.session.scalar(select(func.max(Product.sort_order)))
    return (current_max or 0) + 1

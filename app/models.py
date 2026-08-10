"""Modelos de dados do portal.

Um pedido (``Order``) é sempre feito por uma sala (``Space``) de um escritório
(``Office``) e é composto por itens (``OrderItem``) que apontam para o catálogo
de insumos (``Product``). O catálogo é editável pela administração, por isso o
pedido guarda o vínculo com o produto — e não uma cópia do nome.

O mapeamento usa o estilo declarativo tipado do SQLAlchemy 2.0
(``Mapped`` + ``mapped_column``). Além de documentar o esquema no próprio
código, é o que permite a um verificador de tipos saber que ``office.spaces``
é uma lista de ``Space`` e que ``order.completed_at`` pode ser nulo.

A anotação define a nulidade: ``Mapped[str]`` gera ``NOT NULL`` e
``Mapped[datetime | None]`` gera coluna anulável.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import ModelBase, db

BR_TZ = ZoneInfo("America/Sao_Paulo")

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"


def local_now() -> datetime:
    """Horário de Brasília, sem tzinfo.

    O banco guarda datas ingênuas; converter aqui garante que o painel da copa
    mostre o horário local mesmo quando o servidor roda em UTC.
    """

    return datetime.now(BR_TZ).replace(tzinfo=None)


class Office(ModelBase):
    """Unidade física. Inativar um escritório retira todas as salas dele do ar."""

    __tablename__ = "office"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), unique=True)
    active: Mapped[bool] = mapped_column(default=True, index=True)

    spaces: Mapped[list[Space]] = relationship(
        back_populates="office",
        lazy=True,
        order_by="Space.name",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Office {self.name}>"


class Space(ModelBase):
    """Sala que solicita itens de copa. O nome é único dentro do escritório."""

    __tablename__ = "space"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100))
    office_id: Mapped[int] = mapped_column(db.ForeignKey("office.id"), index=True)
    active: Mapped[bool] = mapped_column(default=True, index=True)

    office: Mapped[Office] = relationship(back_populates="spaces")

    __table_args__ = (
        db.UniqueConstraint("office_id", "name", name="uq_space_office_name"),
    )

    def __repr__(self) -> str:
        return f"<Space {self.name}>"


class Product(ModelBase):
    """Item do catálogo.

    ``form_key`` é o nome do campo no formulário de pedido: ele é derivado do
    nome na criação e depois nunca muda, para que renomear um insumo não invalide
    formulários abertos no navegador de alguém.

    ``input_type`` vale ``quantity`` (campo numérico) ou ``boolean`` (sim/não).
    """

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(120), unique=True)
    form_key: Mapped[str] = mapped_column(db.String(80), unique=True)
    input_type: Mapped[str] = mapped_column(db.String(20), default="quantity")
    sort_order: Mapped[int] = mapped_column(default=0, index=True)
    active: Mapped[bool] = mapped_column(default=True, index=True)

    def __repr__(self) -> str:
        return f"<Product {self.name}>"


class Order(ModelBase):
    """Pedido de uma sala, com status ``pending`` ou ``completed``."""

    __tablename__ = "order"

    id: Mapped[int] = mapped_column(primary_key=True)
    office_id: Mapped[int] = mapped_column(db.ForeignKey("office.id"), index=True)
    space_id: Mapped[int] = mapped_column(db.ForeignKey("space.id"), index=True)
    status: Mapped[str] = mapped_column(
        db.String(20), default=STATUS_PENDING, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=local_now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(default=None, index=True)

    office: Mapped[Office] = relationship()
    space: Mapped[Space] = relationship()
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )

    __table_args__ = (
        # O painel da copa consulta sempre "pendentes, do mais antigo ao mais
        # novo"; o histórico consulta "concluídos por período".
        db.Index("ix_order_status_created_at", "status", "created_at"),
    )

    def to_dict(self) -> dict[str, object]:
        """Representação usada pelo painel da copa."""

        return {
            "id": self.id,
            "office": self.office.name,
            "room": self.space.name,
            "status": self.status,
            "date": self.created_at.strftime("%d/%m/%Y"),
            "time": self.created_at.strftime("%H:%M"),
            "created_at": self.created_at.isoformat(),
            "items": {item.product.name: item.display_quantity() for item in self.items},
        }

    def __repr__(self) -> str:
        return f"<Order {self.id} {self.status}>"


class OrderItem(ModelBase):
    """Linha de um pedido: um insumo e a quantidade solicitada."""

    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(db.ForeignKey("order.id"), index=True)
    product_id: Mapped[int] = mapped_column(db.ForeignKey("product.id"), index=True)
    quantity: Mapped[int] = mapped_column()

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    def display_quantity(self) -> str | int:
        """Itens sim/não aparecem como "Sim"; os demais, pela quantidade."""

        if self.product.input_type == "boolean":
            return "Sim"
        return self.quantity

    def __repr__(self) -> str:
        return f"<OrderItem {self.product_id} x{self.quantity}>"

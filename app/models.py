from datetime import datetime
from zoneinfo import ZoneInfo

from app.extensions import db


BR_TZ = ZoneInfo("America/Sao_Paulo")
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"


def local_now():
    return datetime.now(BR_TZ).replace(tzinfo=None)


class Office(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    spaces = db.relationship(
        "Space",
        back_populates="office",
        lazy=True,
        order_by="Space.name",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Office {self.name}>"


class Space(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    office_id = db.Column(db.Integer, db.ForeignKey("office.id"), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    office = db.relationship("Office", back_populates="spaces")

    __table_args__ = (
        db.UniqueConstraint("office_id", "name", name="uq_space_office_name"),
    )

    def __repr__(self):
        return f"<Space {self.name}>"


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    form_key = db.Column(db.String(80), unique=True, nullable=False)
    input_type = db.Column(db.String(20), default="quantity", nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Product {self.name}>"


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    office_id = db.Column(db.Integer, db.ForeignKey("office.id"), nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey("space.id"), nullable=False)
    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=local_now)
    completed_at = db.Column(db.DateTime)

    office = db.relationship("Office")
    space = db.relationship("Space")
    items = db.relationship(
        "OrderItem",
        back_populates="order",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "office": self.office.name,
            "room": self.space.name,
            "status": self.status,
            "date": self.created_at.strftime("%d/%m/%Y"),
            "time": self.created_at.strftime("%H:%M"),
            "created_at": self.created_at.isoformat(),
            "items": {
                item.product.name: item.display_quantity()
                for item in self.items
            },
        }


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    def display_quantity(self):
        if self.product.input_type == "boolean":
            return "Sim"
        return self.quantity

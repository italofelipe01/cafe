from app import create_app
from app.extensions import db
from app.models import Order


app = create_app()


def normalize_order_timestamps():
    with app.app_context():
        orders = Order.query.all()
        print(f"Found {len(orders)} orders. Checking timestamps...")

        count = 0
        for order in orders:
            if order.created_at and order.created_at.microsecond:
                order.created_at = order.created_at.replace(microsecond=0)
                count += 1

            if order.completed_at and order.completed_at.microsecond:
                order.completed_at = order.completed_at.replace(microsecond=0)
                count += 1

        if count:
            db.session.commit()
            print(f"Normalized {count} timestamp values.")
        else:
            print("No timestamp values needed changes.")


if __name__ == "__main__":
    normalize_order_timestamps()

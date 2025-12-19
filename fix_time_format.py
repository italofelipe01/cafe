from app import create_app, db
from app.models import Order
from datetime import datetime, time

app = create_app()

def fix_time_format():
    with app.app_context():
        orders = Order.query.all()
        print(f"Found {len(orders)} orders. Checking for time formatting issues...")

        count = 0
        for order in orders:
            # Check if time has microseconds (although db.Time usually truncates,
            # if the object in session has it, we want to clean it)
            if isinstance(order.time_created, time) and order.time_created.microsecond != 0:
                print(f"Fixing order {order.id}: {order.time_created}")
                order.time_created = order.time_created.replace(microsecond=0)
                count += 1
            # Also ensure date is set if missing (legacy data safety)
            if order.date_created is None:
                 # fallback to now or some default if critical
                 pass

        if count > 0:
            db.session.commit()
            print(f"Fixed {count} orders.")
        else:
            print("No orders needed fixing.")

if __name__ == '__main__':
    fix_time_format()

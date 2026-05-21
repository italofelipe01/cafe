from app import create_app
from app.models import Office, Product, Space

app = create_app()

with app.app_context():
    offices = Office.query.all()
    print(f"Found {len(offices)} offices:")
    for office in offices:
        print(f" - {office.name}")
        spaces = Space.query.filter_by(office_id=office.id).all()
        print(f"   Spaces: {', '.join([s.name for s in spaces])}")

    products = Product.query.order_by(Product.sort_order).all()
    print(f"Found {len(products)} products:")
    for product in products:
        print(f" - {product.name} ({product.input_type})")

    if len(offices) == 3 and len(products) == 9:
        print("SUCCESS: Seeding verification passed.")
    else:
        print("FAILURE: Seeding verification failed.")

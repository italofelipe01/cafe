from app import create_app
from app.models import Office, Space

app = create_app()

with app.app_context():
    offices = Office.query.all()
    print(f"Found {len(offices)} offices:")
    for office in offices:
        print(f" - {office.name}")
        spaces = Space.query.filter_by(office_id=office.id).all()
        print(f"   Spaces: {', '.join([s.name for s in spaces])}")

    if len(offices) == 3: # We expect 3 offices from the hardcoded dict
        print("SUCCESS: Seeding verification passed.")
    else:
        print("FAILURE: Seeding verification failed.")

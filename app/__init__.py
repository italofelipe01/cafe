from flask import Flask
from config import Config
from app.extensions import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app import routes, models
    app.register_blueprint(routes.bp)

    with app.app_context():
        db.create_all()
        seed_database()

    return app

def seed_database():
    from app.models import Office, Space

    if Office.query.first():
        return

    offices_data = {
        'EBM Office Goiânia': ['Recepção', 'Sala Aton', 'Sala Chateau Marista', 'Grann Parc',
                               'Sala Metropolitan', 'Sala Nasa', 'Sala Uber',
                               'Sala Walk', 'Studio'],
        'EBM Office Campinas': ['Sala Smart Cambuí', 'Sala Wish Taquaral'],
        'EBM Espaço Goiânia': ['Auditório', 'Long Wide (Primeiro Andar)', 'Lounge Wish',
                               'Relacionamento 1', 'Relacionamento 2', 'Relacionamento 3',
                               'Sala Kazas', 'Sala Metropolitan', 'Sala Smart',
                                'Sala The Sun', 'Sala Vinhas', 'Sala Wish',
                                'Sala Wish Areião', 'Sala Wish Trinta e Sete', 'Sala Wish Vaca Brava',
                                'Wide']
    }

    for office_name, spaces in offices_data.items():
        office = Office(name=office_name)
        db.session.add(office)
        db.session.flush() # flush to get office.id

        for space_name in spaces:
            space = Space(name=space_name, office_id=office.id)
            db.session.add(space)

    db.session.commit()

from flask import Flask
from config import CONFIG_BY_NAME
from app.extensions import db


OFFICES_DATA = {
    "EBM Office Goiânia": [
        "Recepção",
        "Sala Aton",
        "Sala Chateau Marista",
        "Grann Parc",
        "Sala Metropolitan",
        "Sala Nasa",
        "Sala Uber",
        "Sala Walk",
        "Studio",
    ],
    "EBM Office Campinas": ["Sala Smart Cambuí", "Sala Wish Taquaral"],
    "EBM Espaço Goiânia": [
        "Auditório",
        "Long Wide (Primeiro Andar)",
        "Lounge Wish",
        "Relacionamento 1",
        "Relacionamento 2",
        "Relacionamento 3",
        "Sala Kazas",
        "Sala Metropolitan",
        "Sala Smart",
        "Sala The Sun",
        "Sala Vinhas",
        "Sala Wish",
        "Sala Wish Areião",
        "Sala Wish Trinta e Sete",
        "Sala Wish Vaca Brava",
        "Wide",
    ],
}

PRODUCTS_DATA = [
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


def create_app(config_name=None):
    app = Flask(__name__)
    config_class = CONFIG_BY_NAME.get(config_name or "default")
    app.config.from_object(config_class)

    db.init_app(app)

    from app import routes, models
    app.register_blueprint(routes.bp)
    register_commands(app)

    if app.config.get("AUTO_CREATE_DB", True):
        with app.app_context():
            init_database()

    return app


def register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        init_database()
        print("Banco inicializado com dados de exemplo.")


def init_database():
    db.create_all()
    seed_database()


def seed_database():
    from app.models import Office, Product, Space

    for office_name, spaces in OFFICES_DATA.items():
        office = Office.query.filter_by(name=office_name).first()
        if not office:
            office = Office(name=office_name)
            db.session.add(office)
            db.session.flush()
        office.active = True

        for space_name in spaces:
            exists = Space.query.filter_by(office_id=office.id, name=space_name).first()
            if not exists:
                db.session.add(Space(name=space_name, office_id=office.id))

    for index, (name, form_key, input_type) in enumerate(PRODUCTS_DATA, start=1):
        product = Product.query.filter_by(form_key=form_key).first()
        if not product:
            product = Product(form_key=form_key)
            db.session.add(product)

        product.name = name
        product.input_type = input_type
        product.sort_order = index
        product.active = True

    db.session.commit()

from datetime import datetime
from app.extensions import db

class Office(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    spaces = db.relationship('Space', backref='office', lazy=True)

class Space(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    office_id = db.Column(db.Integer, db.ForeignKey('office.id'), nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    office = db.Column(db.String(100), nullable=False)
    room = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='Pending', nullable=False)
    date_created = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    time_created = db.Column(db.Time, nullable=False, default=datetime.utcnow)

    # Order items
    cafe_expresso_sem_acucar = db.Column(db.Integer, default=0)
    cafe_expresso_com_acucar = db.Column(db.Integer, default=0)
    cafe_expresso_com_adocante = db.Column(db.Integer, default=0)
    cafe_tradicional_sem_acucar = db.Column(db.Integer, default=0)
    cafe_tradicional_com_acucar = db.Column(db.Integer, default=0)
    cafe_tradicional_com_adocante = db.Column(db.Integer, default=0)
    copo = db.Column(db.Integer, default=0)
    jarra_agua = db.Column(db.Integer, default=0)
    limpeza_sala = db.Column(db.String(10), default='Não')

    def __init__(self, office, room, date_created, time_created,
                 cafe_expresso_sem_acucar=0, cafe_expresso_com_acucar=0, cafe_expresso_com_adocante=0,
                 cafe_tradicional_sem_acucar=0, cafe_tradicional_com_acucar=0, cafe_tradicional_com_adocante=0,
                 copo=0, jarra_agua=0, limpeza_sala='Não', status='Pending'):
        self.office = office
        self.room = room
        self.date_created = date_created
        self.time_created = time_created
        self.cafe_expresso_sem_acucar = cafe_expresso_sem_acucar
        self.cafe_expresso_com_acucar = cafe_expresso_com_acucar
        self.cafe_expresso_com_adocante = cafe_expresso_com_adocante
        self.cafe_tradicional_sem_acucar = cafe_tradicional_sem_acucar
        self.cafe_tradicional_com_acucar = cafe_tradicional_com_acucar
        self.cafe_tradicional_com_adocante = cafe_tradicional_com_adocante
        self.copo = copo
        self.jarra_agua = jarra_agua
        self.limpeza_sala = limpeza_sala
        self.status = status

    def to_dict(self):
        return {
            'id': self.id,
            'office': self.office,
            'room': self.room,
            'status': self.status,
            'date': self.date_created.strftime('%d/%m/%Y'),
            'time': self.time_created.strftime('%H:%M'),
            'items': {
                'Café expresso sem açúcar': self.cafe_expresso_sem_acucar,
                'Café expresso com açúcar': self.cafe_expresso_com_acucar,
                'Café expresso com adoçante': self.cafe_expresso_com_adocante,
                'Café tradicional sem açúcar': self.cafe_tradicional_sem_acucar,
                'Café tradicional com açúcar': self.cafe_tradicional_com_acucar,
                'Café tradicional com adoçante': self.cafe_tradicional_com_adocante,
                'Copo': self.copo,
                'Jarra de água': self.jarra_agua,
                'Limpeza da sala': self.limpeza_sala
            }
        }

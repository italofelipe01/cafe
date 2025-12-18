from datetime import datetime
from app.extensions import db

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

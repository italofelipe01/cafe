"""Testes da semeadura do catálogo.

O comportamento coberto aqui é o que causava o defeito mais grave do portal: o
seed rodava a cada inicialização e reescrevia ``active``, ``sort_order``,
``name`` e ``input_type`` de registros existentes, devolvendo todo o catálogo ao
estado de fábrica e apagando o trabalho de quem administra o sistema.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import uuid

from app import create_app
from app.extensions import db
from app.models import Office, Product, Space
from app.seed import seed_database
from tests.base import get_or_fail


class TestSeedIdempotence(unittest.TestCase):
    """Usa um banco em arquivo, porque o cenário é justamente o do reinício."""

    def setUp(self) -> None:
        self.db_path = os.path.join(tempfile.gettempdir(), f"cafe-seed-{uuid.uuid4().hex}.db")
        os.environ["DATABASE_URL"] = "sqlite:///" + self.db_path.replace("\\", "/")
        self.app = create_app("testing")

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

        os.environ.pop("DATABASE_URL", None)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def restart(self):
        """Simula um reinício do servidor sobre o mesmo banco."""

        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

        self.app = create_app("testing")
        return self.app

    def test_segunda_semeadura_nao_cria_nada(self):
        with self.app.app_context():
            criados = seed_database()

        self.assertEqual(criados, {"offices": 0, "spaces": 0, "products": 0})

    def test_reinicio_preserva_a_ordem_dos_insumos(self):
        with self.app.app_context():
            product = Product.query.filter_by(form_key="copo").one()
            product.sort_order = 99
            db.session.commit()

        self.restart()

        with self.app.app_context():
            self.assertEqual(Product.query.filter_by(form_key="copo").one().sort_order, 99)

    def test_reinicio_preserva_insumo_inativado(self):
        with self.app.app_context():
            product = Product.query.filter_by(form_key="copo").one()
            product.active = False
            db.session.commit()

        self.restart()

        with self.app.app_context():
            self.assertFalse(Product.query.filter_by(form_key="copo").one().active)

    def test_reinicio_preserva_insumo_renomeado(self):
        with self.app.app_context():
            product = Product.query.filter_by(form_key="copo").one()
            product.name = "Copo descartável"
            product.input_type = "boolean"
            db.session.commit()

        self.restart()

        with self.app.app_context():
            product = Product.query.filter_by(form_key="copo").one()
            self.assertEqual(product.name, "Copo descartável")
            self.assertEqual(product.input_type, "boolean")

    def test_reinicio_preserva_escritorio_inativado(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Office Campinas").one()
            office.active = False
            for space in office.spaces:
                space.active = False
            db.session.commit()

        self.restart()

        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Office Campinas").one()
            self.assertFalse(office.active)
            self.assertTrue(all(not space.active for space in office.spaces))

    def test_reinicio_nao_deixa_escritorio_ativo_com_todas_as_salas_inativas(self):
        """O estado contraditório que fazia um escritório sumir do formulário."""

        with self.app.app_context():
            office_id = Office.query.filter_by(name="EBM Office Campinas").one().id

        client = self.app.test_client()
        client.post("/login", data={"password": "admin-teste"})
        client.post(f"/admin/offices/{office_id}/toggle")

        self.restart()

        with self.app.app_context():
            office = get_or_fail(Office, office_id)
            salas_ativas = [space for space in office.spaces if space.active]

            # Ou tudo ativo, ou tudo inativo: nunca um escritório "Ativo" no
            # admin sem nenhuma sala para receber pedido.
            self.assertFalse(office.active)
            self.assertEqual(salas_ativas, [])

    def test_sala_nova_de_escritorio_inativo_nasce_inativa(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Office Campinas").one()
            office.active = False
            for space in office.spaces:
                space.active = False
            # Simula uma sala acrescentada ao catálogo semente depois.
            Space.query.filter_by(office_id=office.id, name="Sala Wish Taquaral").delete()
            db.session.commit()

        self.restart()

        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Office Campinas").one()
            nova = Space.query.filter_by(
                office_id=office.id, name="Sala Wish Taquaral"
            ).one()
            self.assertFalse(nova.active)

    def test_catalogo_completo_apos_a_primeira_semeadura(self):
        from app.seed import OFFICES_DATA, PRODUCTS_DATA

        with self.app.app_context():
            self.assertEqual(Office.query.count(), len(OFFICES_DATA))
            self.assertEqual(Product.query.count(), len(PRODUCTS_DATA))
            self.assertEqual(
                Space.query.count(), sum(len(salas) for salas in OFFICES_DATA.values())
            )

    def test_insumo_criado_pelo_admin_sobrevive_ao_reinicio(self):
        client = self.app.test_client()
        client.post("/login", data={"password": "admin-teste"})
        client.post("/admin/products", data={"name": "Chá", "input_type": "quantity"})

        self.restart()

        with self.app.app_context():
            self.assertIsNotNone(Product.query.filter_by(name="Chá").first())


if __name__ == "__main__":
    unittest.main()

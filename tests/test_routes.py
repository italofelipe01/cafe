import unittest

from app import create_app
from app.extensions import db
from app.models import Office, Order, Product, Space, STATUS_COMPLETED


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_index_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("EBM Office Goiânia".encode(), response.data)

    def test_get_rooms(self):
        response = self.client.post("/get_rooms", json={"office": "EBM Office Goiânia"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        self.assertIn("Sala Aton", response.get_json())

    def test_get_rooms_invalid_office(self):
        response = self.client.post("/get_rooms", json={"office": "Invalid Office"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_select_room(self):
        response = self.client.post(
            "/select_room",
            data={"office": "EBM Office Goiânia", "room": "Sala Aton"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sala Aton".encode(), response.data)

    def test_submit_form_creates_order(self):
        response = self.client.post(
            "/submit_form",
            data={
                "office": "EBM Office Goiânia",
                "room": "Sala Aton",
                "cafe_expresso_sem_acucar": "1",
                "copo": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Pedido solicitado com sucesso".encode(), response.data)

        with self.app.app_context():
            order = Order.query.one()
            self.assertEqual(order.office.name, "EBM Office Goiânia")
            self.assertEqual(order.space.name, "Sala Aton")
            self.assertEqual(len(order.items), 2)

    def test_submit_form_requires_at_least_one_item(self):
        response = self.client.post(
            "/submit_form",
            data={"office": "EBM Office Goiânia", "room": "Sala Aton"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Selecione pelo menos um item".encode(), response.data)

    def test_complete_order(self):
        self.client.post(
            "/submit_form",
            data={
                "office": "EBM Office Goiânia",
                "room": "Sala Aton",
                "limpeza_sala": "Sim",
            },
        )

        with self.app.app_context():
            order_id = Order.query.one().id

        response = self.client.post(f"/api/complete_order/{order_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})

        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.status, STATUS_COMPLETED)
            self.assertIsNotNone(order.completed_at)

    def test_admin_can_create_office_space_and_product(self):
        response = self.client.post(
            "/admin/offices",
            data={"name": "EBM Teste"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("EBM Teste".encode(), response.data)

        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Teste").one()
            office_id = office.id

        response = self.client.post(
            "/admin/spaces",
            data={"office_id": str(office_id), "name": "Sala Teste"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sala Teste".encode(), response.data)

        response = self.client.post(
            "/admin/products",
            data={"name": "Chá", "input_type": "quantity", "sort_order": "99"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Chá".encode(), response.data)

        with self.app.app_context():
            self.assertIsNotNone(Space.query.filter_by(name="Sala Teste").first())
            product = Product.query.filter_by(name="Chá").one()
            self.assertEqual(product.form_key, "cha")

    def test_toggling_office_cascades_to_spaces(self):
        with self.app.app_context():
            office = Office.query.filter_by(name="EBM Office Goiânia").one()
            office_id = office.id
            space_ids = [space.id for space in office.spaces]

        response = self.client.post(
            f"/admin/offices/{office_id}/toggle",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            office = db.session.get(Office, office_id)
            spaces = Space.query.filter(Space.id.in_(space_ids)).all()
            self.assertFalse(office.active)
            self.assertTrue(all(not space.active for space in spaces))

        response = self.client.post(
            f"/admin/offices/{office_id}/toggle",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            office = db.session.get(Office, office_id)
            spaces = Space.query.filter(Space.id.in_(space_ids)).all()
            self.assertTrue(office.active)
            self.assertTrue(all(space.active for space in spaces))

    def test_public_room_list_ignores_inactive_spaces(self):
        with self.app.app_context():
            space = Space.query.filter_by(name="Sala Aton").one()
            space_id = space.id

        self.client.post(f"/admin/spaces/{space_id}/toggle", follow_redirects=True)

        response = self.client.post("/get_rooms", json={"office": "EBM Office Goiânia"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Sala Aton", response.get_json())


if __name__ == "__main__":
    unittest.main()

import unittest
from app import create_app

class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app.testing = True

    def test_index_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'EBM Office', response.data)

    def test_get_rooms(self):
        response = self.client.post('/get_rooms', json={'office': 'EBM Office Goiânia'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        self.assertIn('Sala Aton', response.get_json())

    def test_get_rooms_invalid_office(self):
        response = self.client.post('/get_rooms', json={'office': 'Invalid Office'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_select_room(self):
        response = self.client.post('/select_room', data={'office': 'EBM Office Goiânia', 'room': 'Sala Aton'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sala Aton', response.data)

    def test_submit_form(self):
        data = {
            'office': 'EBM Office Goiânia',
            'room': 'Sala Aton',
            'Café expresso sem açucar': '1',
            'Copo': '2'
        }
        response = self.client.post('/submit_form', data=data)
        self.assertEqual(response.status_code, 200)
        # Check if the data is reflected in the response (confirm_pedido.html)
        self.assertIn(b'Sala Aton', response.data)
        self.assertIn(b'1', response.data) # Check for quantity
        self.assertIn(b'2', response.data) # Check for quantity

if __name__ == '__main__':
    unittest.main()

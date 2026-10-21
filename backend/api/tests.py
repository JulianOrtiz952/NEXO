from rest_framework.test import APITestCase

class HealthTests(APITestCase):
    def test_menu_returns_products(self):
        response = self.client.get('/api/menu/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['products']), 8)
        self.assertEqual(response.data['products'][0]['n'], 'Churrasco a la brasa')
        self.assertIsInstance(response.data['products'][0]['p'], int)

    def test_health(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ok')
        self.assertIn('timestamp', response.data)

    def test_cors(self):
        response = self.client.get('/api/health/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://localhost:5173')

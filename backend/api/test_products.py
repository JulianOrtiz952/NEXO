from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import AuditLog, Category, Membership, Product, Restaurant


class ProductTests(APITestCase):
    def setUp(self):
        self.a = Restaurant.objects.create(name='A')
        self.b = Restaurant.objects.create(name='B')
        self.owner = self.user('owner', 'OWNER', self.a)
        self.admin = self.user('admin', 'ADMIN', self.a)
        self.waiter = self.user('waiter', 'WAITER', self.a)
        self.other = self.user('other', 'OWNER', self.b)
        self.first = Category.objects.create(name='Entradas', restaurant=self.a, position=1)
        self.second = Category.objects.create(name='Bebidas', restaurant=self.a, position=2)
        self.foreign = Category.objects.create(name='Otra', restaurant=self.b, position=1)
        self.payload = {'name': 'Jugo', 'price': '0.00', 'category': str(self.second.pk), 'is_active': True}
        self.client.force_authenticate(self.owner)

    def user(self, username, role, restaurant):
        user = get_user_model().objects.create_user(username=username)
        Membership.objects.create(user=user, restaurant=restaurant, role=role)
        return user

    def test_creation_and_audit_for_owner_and_admin(self):
        for user in (self.owner, self.admin):
            self.client.force_authenticate(user)
            response = self.client.post('/api/products/', self.payload, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['price'], '0.00')
            event = AuditLog.objects.get(entity_id=response.data['id'])
            self.assertEqual((event.actor, event.restaurant, event.action), (user, self.a, 'product.created'))
            self.assertEqual(event.after['category_name'], 'Bebidas')

    def test_required_fields_invalid_price_and_inactive_category(self):
        for key in self.payload:
            response = self.client.post('/api/products/', {k: v for k, v in self.payload.items() if k != key}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertIn(key, response.data)
        for price in ('-1', '1.001', 'NaN'):
            self.assertEqual(self.client.post('/api/products/', {**self.payload, 'price': price}, format='json').status_code, 400)
        self.second.is_active = False
        self.second.save()
        self.assertEqual(self.client.post('/api/products/', self.payload, format='json').status_code, 400)
        self.assertFalse(Product.objects.exists())

    def test_tenant_isolation_roles_and_no_store(self):
        Product.objects.create(category=self.foreign, name='Ajeno', price='123.45', is_active=True)
        self.assertEqual(self.client.post('/api/products/', {**self.payload, 'category': str(self.foreign.pk)}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/products/', {**self.payload, 'restaurant_id': str(self.b.pk)}, format='json').status_code, 400)
        self.assertEqual(self.client.get('/api/products/').data, [])
        self.assertEqual(self.client.post('/api/products/', self.payload, format='json').status_code, 201)
        self.client.force_authenticate(self.other)
        self.assertEqual([row['name'] for row in self.client.get('/api/products/').data], ['Ajeno'])
        self.assertEqual(self.client.post('/api/products/', self.payload, format='json').status_code, 400)
        self.client.force_authenticate(self.waiter)
        self.assertEqual(self.client.get('/api/products/').status_code, 403)
        self.assertEqual(self.client.post('/api/products/', self.payload, format='json').status_code, 403)
        response = self.client.get('/api/menu/')
        self.assertEqual([row['name'] for row in response.data['products']], ['Jugo'])
        self.assertIn('no-store', response['Cache-Control'])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/menu/').status_code, 401)
        self.assertEqual(self.client.get('/api/products/').status_code, 401)

    def test_menu_category_order_and_visibility(self):
        self.client.post('/api/products/', self.payload, format='json')
        Product.objects.create(category=self.first, name='Arepa', price='1000.05', is_active=True)
        Product.objects.create(category=self.first, name='Oculto', price='1200.00', is_active=False)
        def names():
            return [row['name'] for row in self.client.get('/api/menu/').data['products']]
        self.assertEqual(names(), ['Arepa', 'Jugo'])
        first, second = str(self.first.pk), str(self.second.pk)
        response = self.client.post('/api/categories/reorder/', {'order': [second, first], 'expected_order': [first, second]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(names(), ['Jugo', 'Arepa'])
        response = self.client.patch(f'/api/categories/{second}/', {'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(names(), ['Arepa'])
        self.assertEqual(len(self.client.get('/api/products/').data), 3)

    def test_rollback_when_audit_fails(self):
        with patch('api.products.AuditLog.objects.create', side_effect=RuntimeError('Audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/products/', self.payload, format='json')
        self.assertFalse(Product.objects.exists())

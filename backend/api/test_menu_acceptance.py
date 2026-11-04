from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from . import test_product_editing
from .models import Category, Product


class MenuAcceptanceTests(APITestCase):
    # RF-031: a real tenant catalog, equally readable by Mesero and Caja.
    setUp = test_product_editing.ProductEditingTests.setUp
    member = test_product_editing.ProductEditingTests.member

    def test_waiter_and_cashier_receive_same_ordered_catalog(self):
        Product.objects.create(category=self.second, name='Jugo', price='12000.85', description='Fruta fresca', is_active=True)
        expected = None
        for role in ('WAITER', 'CASHIER'):
            self.client.force_authenticate(self.member(role, role, self.a))
            response = self.client.get('/api/menu/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            rows = response.data['products']
            self.assertEqual([row['category_name'] for row in rows], ['Entradas', 'Bebidas'])
            self.assertEqual(rows[1]['price'], '12000.85')
            self.assertEqual(rows[1]['description'], 'Fruta fresca')
            if expected is not None:
                self.assertEqual(rows, expected)
            expected = rows

    def test_filters_inactive_products_categories_and_respects_order(self):
        Product.objects.create(category=self.second, name='Jugo', price='12000', is_active=True)
        Product.objects.create(category=self.second, name='Oculto', price='1', is_active=False)
        self.second.position = 0
        self.second.save()
        rows = self.client.get('/api/menu/').data['products']
        self.assertEqual([row['name'] for row in rows], ['Jugo', 'Sopa'])
        self.category.is_active = False
        self.category.save()
        self.assertEqual([row['name'] for row in self.client.get('/api/menu/').data['products']], ['Jugo'])
        self.second.is_active = False
        self.second.save()
        self.assertEqual(self.client.get('/api/menu/').data['products'], [])

    def test_bidirectional_isolation_ignores_tenant_and_category_parameters(self):
        for actor, visible, hidden in ((self.owner, self.product, self.foreign), (self.other, self.foreign, self.product)):
            self.client.force_authenticate(actor)
            response = self.client.get('/api/menu/', {'restaurant_id': str(hidden.category.restaurant_id),
                                      'category': str(hidden.category_id), 'product_id': str(hidden.pk), 'search': hidden.name})
            self.assertEqual([row['id'] for row in response.data['products']], [str(visible.pk)])
            self.assertNotIn(str(hidden.pk), str(response.data))
            self.assertNotIn(str(hidden.category_id), str(response.data))

    def test_forbidden_roles_and_write_methods(self):
        for actor in (self.member('kitchen', 'KITCHEN', self.a), get_user_model().objects.create_user(username='global', is_superuser=True)):
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get('/api/menu/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/menu/').status_code, 401)
        self.client.force_authenticate(self.owner)
        for method in ('post', 'patch', 'put', 'delete'):
            self.assertEqual(getattr(self.client, method)('/api/menu/').status_code, 405)

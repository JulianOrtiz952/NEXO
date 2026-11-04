from rest_framework.test import APITestCase

from . import test_product_editing
from .models import Membership, Table, Zone


class CashierInheritanceTests(APITestCase):
    # RF-004 partial: only existing operational flows; metadata is not a working cashier module.
    setUp = test_product_editing.ProductEditingTests.setUp
    member = test_product_editing.ProductEditingTests.member

    def test_cashier_contains_waiter_modules_and_same_real_menu(self):
        profiles, catalogs = {}, {}
        for role in ('WAITER', 'CASHIER'):
            actor = self.member(role, role, self.a)
            self.client.force_authenticate(actor)
            response = self.client.get('/api/auth/me/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['restaurant']['id'], str(self.a.pk))
            self.assertEqual(response.data['role'], role)
            profiles[role] = set(response.data['modules'])
            response = self.client.get('/api/menu/')
            self.assertEqual(response.status_code, 200)
            catalogs[role] = response.data
        self.assertTrue(profiles['WAITER'] <= profiles['CASHIER'])
        self.assertEqual(profiles['CASHIER'] - profiles['WAITER'], {'cashier'})
        self.assertEqual(catalogs['CASHIER'], catalogs['WAITER'])
        self.assertEqual([row['id'] for row in catalogs['CASHIER']['products']], [str(self.product.pk)])

    def test_both_roles_remain_tenant_scoped_with_manipulated_parameters(self):
        for restaurant, expected, hidden in ((self.a, self.product, self.foreign), (self.b, self.foreign, self.product)):
            for role in ('WAITER', 'CASHIER'):
                actor = self.member(f'{role}-{restaurant.pk}', role, restaurant)
                self.client.force_authenticate(actor)
                response = self.client.get('/api/menu/', {'restaurant_id': str(hidden.category.restaurant_id), 'id': str(hidden.pk)})
                self.assertEqual([row['id'] for row in response.data['products']], [str(expected.pk)])
                self.assertNotIn(str(hidden.pk), str(response.data))

    def test_inheritance_does_not_grant_management_permissions(self):
        zone = Zone.objects.create(restaurant=self.a, name='Salón', name_key='salón')
        table = Table.objects.create(zone=zone, name='Ventana')
        for role in ('WAITER', 'CASHIER'):
            self.client.force_authenticate(self.member(role, role, self.a))
            for path in ('/api/products/', '/api/categories/', '/api/zones/', '/api/users/', '/api/history/',
                         f'/api/zones/{zone.pk}/tables/', f'/api/tables/{table.pk}/'):
                self.assertEqual(self.client.get(path).status_code, 403, (role, path))
            for path, body in ((self.path, {'name': 'No'}), (self.path+'price/', {'price': '0'}),
                               (self.path+'status/', {'is_active': False})):
                self.assertEqual(self.client.patch(path, body, format='json').status_code, 403)

    def test_revocation_blocks_existing_menu_access_for_both_roles(self):
        for role in ('WAITER', 'CASHIER'):
            actor = self.member(role, role, self.a)
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get('/api/menu/').status_code, 200)
            Membership.objects.filter(user=actor).update(is_active=False)
            self.assertEqual(self.client.get('/api/menu/').status_code, 403)
            self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)

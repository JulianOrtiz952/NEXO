from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from . import test_product_editing
from .models import AuditLog, Membership, Product


class ProductPriceTests(APITestCase):
    # RF-027: use the same two-tenant fixture, without inheriting unrelated tests.
    setUp = test_product_editing.ProductEditingTests.setUp
    member = test_product_editing.ProductEditingTests.member

    def price_path(self, product=None):
        return f'/api/products/{(product or self.product).pk}/price/'

    def test_exact_price_persistence_audit_and_noop(self):
        for actor, value in ((self.owner, '20000.85'), (self.admin, '0.00'), (self.owner, '9999999999.99')):
            self.client.force_authenticate(actor)
            response = self.client.patch(self.price_path(), {'price': value}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['price'], value)
            self.assertEqual(self.client.get(self.path).data['price'], value)
            self.assertEqual((response.data['name'], response.data['category'], response.data['is_active']),
                             ('Sopa', str(self.category.pk), True))
            event = AuditLog.objects.filter(action='product.price_changed').latest('pk')
            self.assertEqual((event.actor, event.restaurant), (actor, self.a))
            self.assertEqual(event.after['price'], value)
        count = AuditLog.objects.count()
        self.client.patch(self.price_path(), {'price': '9999999999.99'}, format='json')
        self.assertEqual(AuditLog.objects.count(), count)
        self.assertEqual(self.client.get('/api/menu/').data['products'][0]['price'], '9999999999.99')
        self.assertEqual(self.client.get('/api/history/?action=product.price_changed').data['count'], 3)

    def test_invalid_values_and_unrelated_fields_are_rejected(self):
        for value in ('-1', '1.001', 'NaN', 'Infinity', '10000000000', '', None, '20,000.00'):
            self.assertEqual(self.client.patch(self.price_path(), {'price': value}, format='json').status_code, 400, value)
        for payload in ({}, {'price': '10', 'name': 'Otro'}, {'price': '10', 'is_active': False}, {'price': '10', 'restaurant_id': str(self.b.pk)}):
            self.assertEqual(self.client.patch(self.price_path(), payload, format='json').status_code, 400)
        self.assertFalse(AuditLog.objects.exists())

    def test_bidirectional_cross_tenant_access_and_roles(self):
        for actor, hidden in ((self.owner, self.foreign), (self.other, self.product)):
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.patch(self.price_path(hidden), {'price': '10'}, format='json').status_code, 404)
        for role in ('CASHIER', 'WAITER', 'KITCHEN'):
            self.client.force_authenticate(self.member(role, role, self.a))
            self.assertEqual(self.client.patch(self.price_path(), {'price': '10'}, format='json').status_code, 403)
        self.client.force_authenticate(get_user_model().objects.create_user(username='global', is_superuser=True))
        self.assertEqual(self.client.patch(self.price_path(), {'price': '10'}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(self.price_path(), {'price': '10'}, format='json').status_code, 401)
        self.assertFalse(AuditLog.objects.exists())

    def test_rollback_and_previous_snapshots_preserved(self):
        original = AuditLog.objects.create(restaurant=self.a, actor=self.owner, action='product.created',
                   entity_id=str(self.product.pk), after={'name': 'Sopa', 'price': '18000.25'})
        with patch('api.products.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.patch(self.price_path(), {'price': '20000'}, format='json')
        self.product.refresh_from_db()
        self.assertEqual(str(self.product.price), '18000.25')
        self.client.patch(self.price_path(), {'price': '20000'}, format='json')
        original.refresh_from_db()
        self.assertEqual(original.after['price'], '18000.25')
        self.assertEqual(Product.objects.count(), 2)
        Membership.objects.filter(user=self.owner).update(is_active=False)
        self.assertEqual(self.client.patch(self.price_path(), {'price': '10'}, format='json').status_code, 403)

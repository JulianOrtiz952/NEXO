from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient, APITestCase

from . import test_product_editing
from .models import AuditLog, Membership, Product


class ProductAvailabilityTests(APITestCase):
    # RF-028: availability affects future catalog reads, without deletion.
    setUp = test_product_editing.ProductEditingTests.setUp
    member = test_product_editing.ProductEditingTests.member

    def status_path(self, product=None):
        return f'/api/products/{(product or self.product).pk}/status/'

    def test_deactivate_reactivate_and_noop_with_audit(self):
        for actor, active in ((self.owner, False), (self.admin, True)):
            self.client.force_authenticate(actor)
            response = self.client.patch(self.status_path(), {'is_active': active}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['is_active'], active)
            self.assertEqual((response.data['name'], response.data['price']), ('Sopa', '18000.25'))
            self.assertEqual(self.client.get(self.path).data, response.data)
            self.assertEqual(len(self.client.get('/api/menu/').data['products']), 1 if active else 0)
            event = AuditLog.objects.filter(action='product.status_changed').latest('pk')
            self.assertEqual((event.actor, event.restaurant, event.entity_id), (actor, self.a, str(self.product.pk)))
            self.assertEqual((event.before['is_active'], event.after['is_active']), (not active, active))
        count = AuditLog.objects.count()
        self.client.patch(self.status_path(), {'is_active': True}, format='json')
        self.assertEqual(AuditLog.objects.count(), count)
        self.assertEqual(Product.objects.count(), 2)

    def test_inactive_category_still_hides_reactivated_product(self):
        self.category.is_active = False
        self.category.save()
        for active in (False, True):
            self.assertEqual(self.client.patch(self.status_path(), {'is_active': active}, format='json').status_code, 200)
            self.assertEqual(self.client.get('/api/menu/').data['products'], [])
        self.assertEqual(len(self.client.get('/api/products/').data), 1)

    def test_cross_tenant_ids_and_roles(self):
        for actor, hidden in ((self.owner, self.foreign), (self.other, self.product)):
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.patch(self.status_path(hidden), {'is_active': False}, format='json').status_code, 404)
        for role in ('CASHIER', 'WAITER', 'KITCHEN'):
            self.client.force_authenticate(self.member(role, role, self.a))
            self.assertEqual(self.client.patch(self.status_path(), {'is_active': False}, format='json').status_code, 403)
        self.client.force_authenticate(get_user_model().objects.create_user(username='platform', is_superuser=True))
        self.assertEqual(self.client.patch(self.status_path(), {'is_active': False}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(self.status_path(), {'is_active': False}, format='json').status_code, 401)
        self.assertFalse(AuditLog.objects.exists())

    def test_invalid_payload_delete_and_revoked_membership(self):
        for body in ({}, {'is_active': None}, {'is_active': 'invalid'}, {'is_active': False, 'name': 'Otro'},
                     {'is_active': False, 'restaurant_id': str(self.b.pk)}, {'is_active': False, 'price': '0'}):
            self.assertEqual(self.client.patch(self.status_path(), body, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.path).status_code, 405)
        Membership.objects.filter(user=self.owner).update(is_active=False)
        self.assertEqual(self.client.patch(self.status_path(), {'is_active': False}, format='json').status_code, 403)
        self.assertTrue(Product.objects.get(pk=self.product.pk).is_active)

    def test_status_and_audit_rollback_together(self):
        with patch('api.products.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.patch(self.status_path(), {'is_active': False}, format='json')
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)
        self.assertFalse(AuditLog.objects.exists())

    def test_shared_mutation_reauthorizes_under_lock(self):
        from .products import manager

        def revoke(user):
            if mocked.call_count == 2:
                Membership.objects.filter(user=user).update(role='WAITER')
            return manager(user)

        with patch('api.products.manager', side_effect=revoke) as mocked:
            self.assertEqual(self.client.patch(self.status_path(), {'is_active': False}, format='json').status_code, 403)
        self.assertTrue(Product.objects.get(pk=self.product.pk).is_active)
        self.assertFalse(AuditLog.objects.exists())


class ProductMutationConcurrencyTests(TransactionTestCase):
    def test_concurrent_deactivation_has_one_effect_and_one_audit(self):
        # RF-028, RNF-019/020: explicit state is idempotent even for simultaneous sessions.
        from .models import Category, Restaurant

        restaurant = Restaurant.objects.create(name='Concurrent')
        owner = get_user_model().objects.create_user(username='concurrent-owner')
        Membership.objects.create(user=owner, restaurant=restaurant, role='OWNER')
        category = Category.objects.create(restaurant=restaurant, name='Carta', position=1)
        product = Product.objects.create(category=category, name='Sopa', price='1', is_active=True)
        barrier = Barrier(2)
        path = f'/api/products/{product.pk}/status/'

        def deactivate():
            try:
                client = APIClient()
                client.force_authenticate(get_user_model().objects.get(pk=owner.pk))
                barrier.wait(timeout=10)
                return client.patch(path, {'is_active': False}, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(deactivate) for _ in range(2)]
            statuses = [future.result(timeout=20) for future in futures]
        self.assertTrue(all(status in (200, 409) for status in statuses), statuses)
        client = APIClient()
        client.force_authenticate(owner)
        self.assertEqual(client.patch(path, {'is_active': False}, format='json').status_code, 200)
        product.refresh_from_db()
        self.assertFalse(product.is_active)
        self.assertEqual(AuditLog.objects.filter(action='product.status_changed').count(), 1)

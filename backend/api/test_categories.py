from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import connections, transaction, IntegrityError
from django.test import TransactionTestCase
from rest_framework.test import APITestCase, APIClient
from .models import AuditLog, Category, Membership, Restaurant


def member(name, role='OWNER', restaurant=None):
    user = get_user_model().objects.create_user(username=name, email=f'{name}@example.com')
    restaurant = restaurant or Restaurant.objects.create(name=name, initial_owner=user)
    Membership.objects.create(user=user, role=role, restaurant=restaurant)
    return user


class CategoryTests(APITestCase):
    """DN-39 / RF-023, RNF-004/007/019/020: approved category criteria."""

    def setUp(self):
        self.owner = member('owner')
        self.restaurant = self.owner.membership.restaurant
        self.other = member('other')
        self.client.force_authenticate(self.owner)

    def create(self, name='Bebidas'):
        response = self.client.post('/api/categories/', {'name': name}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def reorder(self, order, expected=None):
        return self.client.post('/api/categories/reorder/', {'order': order, 'expected_order': expected if expected is not None else order}, format='json')

    def test_lifecycle_owner_admin_persistence_audit_and_no_delete(self):
        for actor in [self.owner, member('admin', 'ADMIN', self.restaurant)]:
            self.client.force_authenticate(actor)
            category_id = self.create(actor.username)
            path = f'/api/categories/{category_id}/'
            for payload in [{'name': f'{actor.username} nuevo'}, {'is_active': False}, {'is_active': True}]:
                self.assertEqual(self.client.patch(path, payload, format='json').status_code, 200)
            events = AuditLog.objects.filter(entity_id=category_id).order_by('pk')
            self.assertEqual(list(events.values_list('action', flat=True)), ['category.created', 'category.updated', 'category.status_changed', 'category.status_changed'])
            self.assertTrue(all(e.actor_id == actor.pk and e.restaurant_id == self.restaurant.pk for e in events))
            self.assertEqual(events[2].before['is_active'], True)
            self.assertEqual(events[2].after['is_active'], False)
            self.assertEqual(self.client.get(path).data['name'], f'{actor.username} nuevo')
            self.client.patch(path, {'is_active': True}, format='json')
            self.assertEqual(events.count(), 4)
            self.assertEqual(self.client.delete(path).status_code, 405)

    def test_unique_trimmed_unicode_name_and_strict_fields(self):
        first = self.create('  Bebidas  ')
        self.assertEqual(Category.objects.get(pk=first).name, 'Bebidas')
        for payload in [{}, {'name': ' '}, {'name': 'x' * 101}, {'name': ' BEBIDAS '}, {'name': 'X', 'restaurant_id': str(self.restaurant.pk)}, {'name': 'X', 'position': 1}, {'name': 'X', 'is_active': False}]:
            self.assertEqual(self.client.post('/api/categories/', payload, format='json').status_code, 400, payload)
        self.client.patch(f'/api/categories/{first}/', {'is_active': False}, format='json')
        self.assertEqual(self.client.post('/api/categories/', {'name': 'bebidas'}).status_code, 400)
        self.create('ß' * 100)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(restaurant=self.restaurant, name='BEBIDAS', position=3)

    def test_bidirectional_isolation_query_parameters_ids_and_batch(self):
        own = self.create()
        self.client.force_authenticate(self.other)
        foreign = self.create()
        for actor, visible, hidden in [(self.owner, own, foreign), (self.other, foreign, own)]:
            self.client.force_authenticate(actor)
            self.assertEqual([r['id'] for r in self.client.get('/api/categories/', {'restaurant_id': str(self.restaurant.pk)}).data], [visible])
            self.assertEqual(self.client.get(f'/api/categories/{hidden}/').status_code, 404)
            self.assertEqual(self.client.patch(f'/api/categories/{hidden}/', {'name': 'Intrusión', 'is_active': False}, format='json').status_code, 404)
            self.assertEqual(self.reorder([visible, hidden]).status_code, 400)
            self.assertEqual(self.reorder([hidden]).status_code, 400)
            self.assertEqual(self.client.get('/api/history/').data['count'], 1)
        self.assertEqual(Category.objects.filter(name='Bebidas', is_active=True).count(), 2)

    def test_permissions_revocation_and_anonymous(self):
        category_id = self.create()
        platform = get_user_model().objects.create_user(username='platform', is_superuser=True)
        for actor in [member('cashier', 'CASHIER', self.restaurant), member('waiter', 'WAITER', self.restaurant), member('kitchen', 'KITCHEN', self.restaurant), platform]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get('/api/categories/').status_code, 403)
            self.assertEqual(self.client.post('/api/categories/', {'name': 'No'}).status_code, 403)
            self.assertEqual(self.client.patch(f'/api/categories/{category_id}/', {'is_active': False}, format='json').status_code, 403)
            self.assertEqual(self.reorder([category_id]).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/categories/').status_code, 401)
        self.client.force_authenticate(self.owner)
        membership = self.owner.membership
        membership.is_active = False
        membership.save()
        self.assertEqual(self.client.get('/api/categories/').status_code, 403)
        membership.is_active = True
        membership.save()
        self.restaurant.is_active = False
        self.restaurant.save()
        self.assertEqual(self.reorder([category_id]).status_code, 403)

    def test_reorder_inactive_append_stale_batch_and_history(self):
        a, b, c = [self.create(name) for name in ['Entradas', 'Fuertes', 'Bebidas']]
        self.client.patch(f'/api/categories/{b}/', {'is_active': False}, format='json')
        response = self.reorder([c, a, b], [a, b, c])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['id'] for r in self.client.get('/api/categories/').data], [c, a, b])
        events = self.client.get('/api/history/?action=category.reordered').data
        self.assertEqual(events['count'], 3)
        self.assertEqual(events['results'][0]['category'], 'Categorías')
        self.assertIn('position', events['results'][0]['after'])
        self.assertEqual(self.reorder([b, a, c], [a, b, c]).status_code, 409)
        for ids in [[a, b], [a, a, c], [a, b, 'invalid']]:
            self.assertEqual(self.reorder(ids).status_code, 400)
        self.assertEqual(self.reorder([c, a, b]).status_code, 200)
        self.assertEqual(AuditLog.objects.filter(action='category.reordered').count(), 3)
        d = self.create('Postres')
        self.assertEqual(list(Category.objects.values_list('position', flat=True)), [1, 2, 3, 4])
        self.assertEqual(self.client.get(f'/api/categories/{d}/').data['position'], 4)
        self.assertEqual(self.reorder([c, a, b]).status_code, 400)

    def test_audit_failure_rolls_back_all_mutations(self):
        a, b = self.create('A'), self.create('B')
        with patch('api.categories.AuditLog.objects.create', side_effect=RuntimeError('unavailable')):
            for operation in [lambda: self.create('C'), lambda: self.client.patch(f'/api/categories/{a}/', {'name': 'Changed'}, format='json'), lambda: self.reorder([b, a], [a, b])]:
                with self.assertRaises(RuntimeError):
                    operation()
        self.assertEqual(list(Category.objects.values_list('name', 'position')), [('A', 1), ('B', 2)])
        self.assertEqual(AuditLog.objects.count(), 2)


class CategoryConcurrencyTests(TransactionTestCase):
    def test_competing_reorders_cannot_overwrite_a_newer_order(self):
        # RF-023, RNF-020: competing sessions must keep one consistent order.
        owner = member('reordering')
        tenant = owner.membership.restaurant
        rows = [Category.objects.create(restaurant=tenant, name=name, position=index) for index, name in enumerate(['A', 'B', 'C'], 1)]
        expected = [str(row.pk) for row in rows]
        orders = [[expected[1], expected[0], expected[2]], list(reversed(expected))]
        barrier = Barrier(2)

        def reorder(order):
            try:
                client = APIClient()
                client.force_authenticate(get_user_model().objects.get(pk=owner.pk))
                barrier.wait(timeout=10)
                return client.post('/api/categories/reorder/', {'order': order, 'expected_order': expected}, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reorder, order) for order in orders]
            outcomes = [future.result(timeout=20) for future in futures]
        self.assertTrue(all(status in [200, 409] for status in outcomes), outcomes)
        self.assertLessEqual(outcomes.count(200), 1, outcomes)
        client = APIClient()
        client.force_authenticate(owner)
        if 200 not in outcomes:
            self.assertEqual(client.post('/api/categories/reorder/', {'order': orders[0], 'expected_order': expected}, format='json').status_code, 200)
        self.assertIn([str(pk) for pk in Category.objects.values_list('pk', flat=True)], orders)
        self.assertEqual(list(Category.objects.values_list('position', flat=True)), [1, 2, 3])
        self.assertEqual(client.post('/api/categories/reorder/', {'order': expected, 'expected_order': expected}, format='json').status_code, 409)

    def test_simultaneous_creations_have_distinct_positions_and_atomic_audit(self):
        # RF-023, RNF-019/020: serialize append positions inside each restaurant.
        owner = member('concurrent')
        barrier = Barrier(2)

        def create(name):
            try:
                client = APIClient()
                client.force_authenticate(get_user_model().objects.get(pk=owner.pk))
                barrier.wait(timeout=10)
                return client.post('/api/categories/', {'name': name}, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create, name) for name in ['A', 'B']]
            outcomes = [f.result(timeout=20) for f in futures]
        self.assertTrue(all(s in [201, 409] for s in outcomes), outcomes)
        client = APIClient()
        client.force_authenticate(owner)
        for name in ['A', 'B']:
            if not Category.objects.filter(name=name).exists():
                self.assertEqual(client.post('/api/categories/', {'name': name}).status_code, 201)
        self.assertEqual(list(Category.objects.values_list('position', flat=True)), [1, 2])
        self.assertEqual(AuditLog.objects.filter(action='category.created').count(), 2)

from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from .models import AuditLog, Membership, PaymentMethod, Restaurant


class PaymentMethodTests(APITestCase):
    # RF-020, RNF-004/007/019: configuration only, sales integration remains pending.
    def setUp(self):
        self.a = Restaurant.objects.create(name='A')
        self.b = Restaurant.objects.create(name='B')
        self.owner = self.member('owner', 'OWNER', self.a)
        self.other = self.member('other', 'OWNER', self.b)
        self.client.force_authenticate(self.owner)

    def member(self, name, role, restaurant):
        user = get_user_model().objects.create_user(username=name)
        Membership.objects.create(user=user, role=role, restaurant=restaurant)
        return user

    def test_lifecycle_history_and_no_delete(self):
        for user in [self.owner, self.member('admin', 'ADMIN', self.a)]:
            self.client.force_authenticate(user)
            result = self.client.post('/api/payment-methods/', {'name': 'Efectivo'})
            self.assertEqual(result.status_code, 201)
            path = f"/api/payment-methods/{result.data['id']}/"
            for data in [{'name': 'Transferencia'}, {'is_active': False}, {'is_active': True}]:
                self.assertEqual(self.client.patch(path, data, format='json').status_code, 200)
            self.assertEqual(self.client.get(path).data['name'], 'Transferencia')
            events = AuditLog.objects.filter(entity_id=result.data['id']).order_by('pk')
            self.assertEqual(events.count(), 4)
            self.assertEqual(events[2].before['is_active'], True)
            self.assertEqual(events[2].after['is_active'], False)
            self.assertTrue(all(e.actor_id == user.pk and e.restaurant_id == self.a.pk for e in events))
            self.assertEqual(self.client.delete(path).status_code, 405)
        history = self.client.get('/api/history/?action=payment_method.status_changed').data
        self.assertEqual(history['count'], 4)
        self.assertTrue(all(row['category'] == 'Métodos de pago' for row in history['results']))

    def test_cross_tenant_read_write_and_validation(self):
        own = PaymentMethod.objects.create(restaurant=self.a, name='Efectivo')
        foreign = PaymentMethod.objects.create(restaurant=self.b, name='Ajeno')
        for user, visible, hidden in [(self.owner, own, foreign), (self.other, foreign, own)]:
            self.client.force_authenticate(user)
            self.assertEqual([row['id'] for row in self.client.get('/api/payment-methods/', {'restaurant_id': str(self.b.pk)}).data], [str(visible.pk)])
            path = f'/api/payment-methods/{hidden.pk}/'
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.patch(path, {'is_active': False}, format='json').status_code, 404)
        for payload in [{}, {'name': ' '}, {'name': 'x' * 101}, {'name': 'X', 'restaurant': str(self.a.pk)}]:
            self.assertEqual(self.client.post('/api/payment-methods/', payload, format='json').status_code, 400)

    def test_roles_inactive_and_anonymous(self):
        row = PaymentMethod.objects.create(restaurant=self.a, name='Efectivo')
        users = [self.member(role, role, self.a) for role in ['CASHIER', 'WAITER', 'KITCHEN']]
        users.append(get_user_model().objects.create_user(username='platform', is_superuser=True))
        for user in users:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/payment-methods/').status_code, 403)
            self.assertEqual(self.client.post('/api/payment-methods/', {'name': 'X'}).status_code, 403)
            self.assertEqual(self.client.patch(f'/api/payment-methods/{row.pk}/', {'name': 'X'}).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/payment-methods/').status_code, 401)
        self.client.force_authenticate(self.owner)
        self.a.is_active = False
        self.a.save()
        self.assertEqual(self.client.get('/api/payment-methods/').status_code, 403)

    def test_atomic_audit(self):
        row = PaymentMethod.objects.create(restaurant=self.a, name='Efectivo')
        with patch('api.payment_methods.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/payment-methods/', {'name': 'No guardar'})
            with self.assertRaises(RuntimeError):
                self.client.patch(f'/api/payment-methods/{row.pk}/', {'is_active': False}, format='json')
        row.refresh_from_db()
        self.assertTrue(row.is_active)
        self.assertEqual(PaymentMethod.objects.count(), 1)

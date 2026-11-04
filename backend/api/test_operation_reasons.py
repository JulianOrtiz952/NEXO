from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from .models import AuditLog, Membership, OperationReason, Restaurant


class OperationReasonTests(APITestCase):
    # RF-021, RNF-004/007/019: types and tenant-scoped configuration, without operational flows.
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

    def test_five_types_edit_filter_audit_and_no_delete(self):
        for operation_type in OperationReason.OperationType.values:
            result = self.client.post('/api/operation-reasons/', {'name': 'Motivo', 'operation_type': operation_type}, format='json')
            self.assertEqual(result.status_code, 201, result.data)
            self.assertEqual(self.client.get('/api/operation-reasons/', {'operation_type': operation_type}).data['results'][0]['operation_type'], operation_type)
        self.assertEqual(len(self.client.get('/api/operation-reasons/').data['operation_types']), 5)
        row = OperationReason.objects.get(operation_type='VOID')
        path = f'/api/operation-reasons/{row.pk}/'
        self.client.force_authenticate(self.member('admin', 'ADMIN', self.a))
        result = self.client.patch(path, {'name': 'Corregido', 'operation_type': 'RETURN'}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get(path).data['name'], 'Corregido')
        event = AuditLog.objects.get(action='reason.updated')
        self.assertEqual(event.before['operation_type'], 'VOID')
        self.assertEqual(event.after['operation_type'], 'RETURN')
        self.assertEqual(event.restaurant, self.a)
        response = self.client.get('/api/history/?action=reason.updated')
        self.assertEqual(response.data['results'][0]['after']['operation_type_label'], 'Devolución')
        self.assertEqual(self.client.delete(path).status_code, 405)
        count = AuditLog.objects.count()
        self.client.patch(path, {'name': 'Corregido'}, format='json')
        self.assertEqual(AuditLog.objects.count(), count)

    def test_tenant_isolation_and_invalid_fields(self):
        a = OperationReason.objects.create(restaurant=self.a, name='A', operation_type='WASTE')
        b = OperationReason.objects.create(restaurant=self.b, name='B', operation_type='WASTE')
        for user, visible, hidden in [(self.owner, a, b), (self.other, b, a)]:
            self.client.force_authenticate(user)
            response = self.client.get('/api/operation-reasons/', {'restaurant_id': str(self.b.pk), 'operation_type': 'WASTE'})
            self.assertEqual([r['id'] for r in response.data['results']], [str(visible.pk)])
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(self.client.get(f'/api/operation-reasons/{hidden.pk}/').status_code, 404)
            self.assertEqual(self.client.patch(f'/api/operation-reasons/{hidden.pk}/', {'name': 'Ajeno'}, format='json').status_code, 404)
        for data in [{}, {'name': 'X'}, {'name': ' ', 'operation_type': 'WASTE'}, {'name': 'X', 'operation_type': 'OTHER'}, {'name': 'X', 'operation_type': 'WASTE', 'restaurant_id': str(self.a.pk)}]:
            self.assertEqual(self.client.post('/api/operation-reasons/', data, format='json').status_code, 400)
        self.assertEqual(self.client.get('/api/operation-reasons/?operation_type=INVALID').status_code, 400)

    def test_roles_revocation_and_anonymous(self):
        row = OperationReason.objects.create(restaurant=self.a, name='A', operation_type='WASTE')
        users = [self.member(role, role, self.a) for role in ['CASHIER', 'WAITER', 'KITCHEN']]
        users.append(get_user_model().objects.create_user(username='platform', is_superuser=True))
        for user in users:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/operation-reasons/').status_code, 403)
            self.assertEqual(self.client.post('/api/operation-reasons/', {'name': 'X', 'operation_type': 'WASTE'}, format='json').status_code, 403)
            self.assertEqual(self.client.patch(f'/api/operation-reasons/{row.pk}/', {'name': 'X'}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/operation-reasons/').status_code, 401)
        self.client.force_authenticate(self.owner)
        Membership.objects.filter(user=self.owner).update(is_active=False)
        self.assertEqual(self.client.get('/api/operation-reasons/').status_code, 403)

    def test_audit_failure_rolls_back(self):
        row = OperationReason.objects.create(restaurant=self.a, name='Original', operation_type='WASTE')
        with patch('api.operation_reasons.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/operation-reasons/', {'name': 'X', 'operation_type': 'VOID'}, format='json')
            with self.assertRaises(RuntimeError):
                self.client.patch(f'/api/operation-reasons/{row.pk}/', {'name': 'Cambio'}, format='json')
        row.refresh_from_db()
        self.assertEqual(row.name, 'Original')
        self.assertEqual(OperationReason.objects.count(), 1)

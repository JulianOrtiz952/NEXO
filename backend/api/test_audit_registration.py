from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import AuditLog, Membership, Restaurant


User = get_user_model()


class AuditRegistrationTests(APITestCase):
    """DN-239 / RF-223, RNF-007/019: sensitive writes and audit commit together."""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', email='owner@example.com')
        self.restaurant = Restaurant.objects.create(name='A', initial_owner=self.owner)
        Membership.objects.create(user=self.owner, restaurant=self.restaurant, role='OWNER')
        self.platform = User.objects.create_user(username='platform', is_superuser=True)
        self.candidate = User.objects.create_user(username='candidate', email='candidate@example.com')
        self.client.force_authenticate(self.platform)

    def test_global_sensitive_operations_register_audit(self):
        response = self.client.post('/api/platform/owners/', {
            'email': 'future@example.com', 'password': 'Temporary-audit-958!safe',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        future_owner_id = response.data['id']
        event = AuditLog.objects.get(action='prospective_owner.created')
        self.assertEqual(event.actor_id, self.platform.pk)
        self.assertEqual(event.entity_id, str(response.data['id']))
        self.assertIsNone(event.restaurant_id)

        response = self.client.post('/api/platform/restaurants/', {
            'name': 'B', 'owner': self.candidate.pk,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        restaurant_id = response.data['id']
        event = AuditLog.objects.get(action='restaurant.created')
        self.assertEqual(event.restaurant_id, restaurant_id)
        self.assertEqual(event.actor_id, self.platform.pk)
        self.assertEqual(event.entity_id, str(restaurant_id))

        for data, action in [
            ({'is_active': False}, 'restaurant.status_changed'),
            ({'owner': future_owner_id}, 'restaurant.owner_assigned'),
        ]:
            with self.subTest(action=action):
                response = self.client.patch('/api/platform/restaurants/', {
                    'id': str(restaurant_id), **data,
                }, format='json')
                self.assertEqual(response.status_code, 200)
                event = AuditLog.objects.get(action=action)
                self.assertEqual(event.restaurant_id, restaurant_id)
                self.assertEqual(event.actor_id, self.platform.pk)

    def test_failed_audit_rolls_back_account_and_membership_creation(self):
        for actor, endpoint, email, extra in [
            (self.platform, '/api/platform/owners/', 'new-owner@example.com', {}),
            (self.owner, '/api/users/', 'new-user@example.com', {'role': 'WAITER'}),
        ]:
            with self.subTest(endpoint=endpoint):
                self.client.force_authenticate(actor)
                with patch('api.identity.AuditLog.objects.create', side_effect=RuntimeError('audit unavailable')):
                    with self.assertRaises(RuntimeError):
                        self.client.post(endpoint, {
                            'email': email, 'password': 'Temporary-audit-958!safe', **extra,
                        }, format='json')
                self.assertFalse(User.objects.filter(email=email).exists())
                self.assertEqual(Membership.objects.count(), 1)
                self.assertFalse(AuditLog.objects.exists())

    def test_failed_audit_rolls_back_restaurant_creation_assignment_and_state(self):
        cases = [
            ('post', {'name': 'B', 'owner': self.candidate.pk}),
            ('patch', {'id': str(self.restaurant.pk), 'owner': self.candidate.pk}),
            ('patch', {'id': str(self.restaurant.pk), 'is_active': False}),
        ]
        for method, data in cases:
            with self.subTest(method=method, data=data):
                with patch('api.identity.AuditLog.objects.create', side_effect=RuntimeError('audit unavailable')):
                    with self.assertRaises(RuntimeError):
                        getattr(self.client, method)('/api/platform/restaurants/', data, format='json')
                self.restaurant.refresh_from_db()
                self.assertTrue(self.restaurant.is_active)
                self.assertEqual(Restaurant.objects.count(), 1)
                self.assertFalse(Membership.objects.filter(user=self.candidate).exists())
                self.assertFalse(AuditLog.objects.exists())

    def test_history_rejects_every_write_without_changing_either_tenant(self):
        foreign = Restaurant.objects.create(name='B')
        events = [AuditLog.objects.create(
            restaurant=restaurant, actor=self.owner, action='user.created',
            entity_id=str(self.owner.pk), after={'email': self.owner.email},
        ) for restaurant in [self.restaurant, foreign]]
        original = list(AuditLog.objects.order_by('pk').values())
        self.client.force_authenticate(self.owner)
        for method in ['post', 'put', 'patch', 'delete']:
            with self.subTest(method=method):
                response = getattr(self.client, method)('/api/history/', {
                    'id': events[1].pk, 'restaurant_id': str(foreign.pk), 'after': {},
                }, format='json')
                self.assertEqual(response.status_code, 405)
        response = self.client.get('/api/history/', {'restaurant_id': str(foreign.pk), 'id': events[1].pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([event['id'] for event in response.data['results']], [events[0].pk])
        self.assertEqual(list(AuditLog.objects.order_by('pk').values()), original)

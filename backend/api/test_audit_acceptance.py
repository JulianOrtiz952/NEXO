from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import AuditLog, Membership, Restaurant


User = get_user_model()


class AuditAcceptanceTests(APITestCase):
    """RF-224/233/234/235: audit acceptance for existing Sprint 01 entities."""

    def setUp(self):
        self.owner = self.member('owner', 'OWNER')
        self.restaurant = self.owner.membership.restaurant
        self.admin = self.member('admin', 'ADMIN', self.restaurant)
        self.employee = self.member('employee', 'WAITER', self.restaurant)
        self.foreign = self.member('foreign', 'OWNER')
        self.platform = User.objects.create_user(username='platform', email='platform@example.com', is_superuser=True)
        self.client.force_authenticate(self.owner)

    def member(self, name, role, restaurant=None):
        user = User.objects.create_user(username=name, email=f'{name}@example.com')
        if restaurant is None:
            restaurant = Restaurant.objects.create(name=name, initial_owner=user)
        Membership.objects.create(user=user, restaurant=restaurant, role=role)
        return user

    def test_dn240_saved_and_returned_fields_describe_real_change(self):
        # RF-224: persisted actor/action/time/entity and before/after, not fabricated history.
        started = timezone.now()
        response = self.client.patch(f'/api/users/{self.employee.pk}/', {'email': 'updated@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        event = AuditLog.objects.get()
        self.assertEqual((event.actor_id, event.restaurant_id, event.entity_id),
                         (self.owner.pk, self.restaurant.pk, str(self.employee.pk)))
        self.assertEqual(event.action, 'user.email_changed')
        self.assertGreaterEqual(event.created_at, started)
        self.assertLessEqual(event.created_at, timezone.now())
        self.assertTrue(timezone.is_aware(event.created_at))
        self.assertEqual(event.before, {'email': 'employee@example.com'})
        self.assertEqual(event.after, {'email': 'updated@example.com'})
        row = self.client.get('/api/history/').data['results'][0]
        self.assertEqual(row['actor'], self.owner.email)
        self.assertEqual(row['target'], 'updated@example.com')
        self.assertEqual(row['created_at'], event.created_at)
        for key in ['id', 'action', 'before', 'after']:
            self.assertEqual(row[key], getattr(event, 'pk' if key == 'id' else key))

    def test_dn249_user_lifecycle_records_each_successful_change(self):
        # RF-233: the public endpoints audit creation, edit, role and state transitions.
        response = self.client.post('/api/users/', {
            'email': 'new@example.com', 'password': 'Temporary-audit-958!safe', 'role': 'WAITER',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        user_id = response.data['id']
        operations = [
            (f'/api/users/{user_id}/', {'email': 'edited@example.com'}, 'user.email_changed',
             {'email': 'new@example.com'}, {'email': 'edited@example.com'}),
            ('/api/users/', {'id': user_id, 'role': 'KITCHEN'}, 'user.role_changed',
             {'role': 'WAITER'}, {'role': 'KITCHEN'}),
            (f'/api/users/{user_id}/status/', {'is_active': False}, 'user.status_changed',
             {'is_active': True}, {'is_active': False, 'cascading': False}),
            (f'/api/users/{user_id}/status/', {'is_active': True}, 'user.status_changed',
             {'is_active': False}, {'is_active': True, 'cascading': False}),
        ]
        for endpoint, payload, action, before, after in operations:
            with self.subTest(action=action, payload=payload):
                self.assertEqual(self.client.patch(endpoint, payload, format='json').status_code, 200)
                event = AuditLog.objects.latest('pk')
                self.assertEqual((event.action, event.before, event.after), (action, before, after))
        events = list(AuditLog.objects.order_by('pk'))
        self.assertEqual(len(events), 5)
        self.assertEqual(events[0].action, 'user.created')
        self.assertEqual(events[0].after, {'email': 'new@example.com', 'role': 'WAITER'})
        self.assertTrue(all(event.actor_id == self.owner.pk and event.restaurant_id == self.restaurant.pk
                            and event.entity_id == str(user_id) for event in events))
        self.assertNotIn('Temporary-audit', str([event.after for event in events]))
        self.assertEqual(self.client.get('/api/history/').data['count'], 5)

    def test_dn251_history_permissions_and_foreign_identifiers(self):
        # RF-235, RNF-004: each role is checked in the server; client filters grant nothing.
        local = AuditLog.objects.create(restaurant=self.restaurant, actor=self.owner,
                                       action='user.created', entity_id=str(self.employee.pk))
        foreign = AuditLog.objects.create(restaurant=self.foreign.membership.restaurant, actor=self.foreign,
                                         action='user.created', entity_id=str(self.foreign.pk))
        for actor in [self.owner, self.admin, self.foreign]:
            self.client.force_authenticate(actor)
            response = self.client.get('/api/history/', {'restaurant_id': str(self.foreign.membership.restaurant_id), 'id': foreign.pk})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row['id'] for row in response.data['results']],
                             [foreign.pk if actor == self.foreign else local.pk])
        for role in ['CASHIER', 'WAITER', 'KITCHEN']:
            with self.subTest(role=role):
                actor = self.member(role.lower(), role, self.restaurant)
                self.client.force_authenticate(actor)
                self.assertEqual(self.client.get('/api/history/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/history/').status_code, 401)
        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.get('/api/history/').data['count'], 0)

    def test_dn250_deactivation_preserves_events_and_identifiable_entities(self):
        # RF-234: limited to existing users/restaurants; products/tables remain future work.
        self.assertEqual(self.client.patch('/api/users/', {
            'id': self.employee.pk, 'role': 'KITCHEN',
        }, format='json').status_code, 200)
        original = list(AuditLog.objects.values())
        self.assertEqual(self.client.patch(f'/api/users/{self.employee.pk}/status/', {
            'is_active': False,
        }, format='json').status_code, 200)
        rows = self.client.get('/api/history/').data['results']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['target'] == self.employee.email for row in rows))
        self.client.force_authenticate(self.platform)
        for active in [False, True]:
            self.assertEqual(self.client.patch('/api/platform/restaurants/', {
                'id': str(self.restaurant.pk), 'is_active': active,
            }, format='json').status_code, 200)
            for previous in original:
                self.assertEqual(AuditLog.objects.values().get(pk=previous['id']), previous)
            self.assertTrue(User.objects.filter(pk=self.employee.pk, is_active=False).exists())
            rows = self.client.get('/api/history/').data['results']
            self.assertTrue(all(row['target'] == self.restaurant.name for row in rows))
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/history/').data['count'], 4)

from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from .models import AccessToken, AuditLog, Membership, Restaurant

User = get_user_model()


class UserEmailEditTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner@example.com', email='owner@example.com')
        self.restaurant = Restaurant.objects.create(name='A', initial_owner=self.owner)
        Membership.objects.create(user=self.owner, restaurant=self.restaurant, role='OWNER')
        self.target = self.make_member('employee@example.com', 'WAITER')
        self.other = User.objects.create_user(username='other@example.com', email='other@example.com')
        self.other_restaurant = Restaurant.objects.create(name='B', initial_owner=self.other)
        Membership.objects.create(user=self.other, restaurant=self.other_restaurant, role='OWNER')

    def make_member(self, email, role):
        user = User.objects.create_user(username=email, email=email)
        Membership.objects.create(user=user, restaurant=self.restaurant, role=role)
        return user

    def edit(self, target=None, **payload):
        return self.client.patch(f'/api/users/{(target or self.target).pk}/', payload, format='json')

    def test_owner_and_admin_edit_persist_and_preserve_history_password_and_membership(self):
        historical = AuditLog.objects.create(restaurant=self.restaurant, actor=self.target, action='user.created', entity_id=str(self.target.pk), after={'email': self.target.email})
        original_password = self.target.password
        for actor in [self.owner, self.make_member('admin@example.com', 'ADMIN')]:
            previous = User.objects.get(pk=self.target.pk).email
            self.client.force_authenticate(actor)
            email = f'edited-{actor.pk}@example.com'
            response = self.edit(email=email.upper())
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['email'], email)
            rows = self.client.get('/api/users/').data
            self.assertEqual(next(row['email'] for row in rows if row['id'] == self.target.pk), email)
            event = AuditLog.objects.latest('pk')
            self.assertEqual((event.actor, event.restaurant, event.entity_id), (actor, self.restaurant, str(self.target.pk)))
            self.assertEqual(event.before, {'email': previous})
            self.assertEqual(event.after, {'email': email})
        historical.refresh_from_db()
        self.assertEqual(historical.actor_id, self.target.pk)
        self.assertEqual(historical.after, {'email': 'employee@example.com'})
        self.target.refresh_from_db()
        self.assertEqual(self.target.password, original_password)
        self.assertEqual(self.target.membership.role, 'WAITER')
        self.assertEqual(self.target.membership.restaurant_id, self.restaurant.pk)
        self.assertTrue(self.target.is_active)
        self.assertFalse(self.target.is_superuser)

    def test_duplicate_invalid_and_extra_fields_rejected_without_changes(self):
        self.client.force_authenticate(self.owner)
        for payload in [
            {'email': 'OTHER@EXAMPLE.COM'}, {'email': 'invalid'}, {'email': ''}, {},
            {'email': 'changed@example.com', 'role': 'OWNER'},
            {'email': 'changed@example.com', 'restaurant_id': str(self.other_restaurant.pk)},
            {'email': 'changed@example.com', 'is_superuser': True},
            {'email': 'changed@example.com', 'password': 'Ignored?'},
            {'email': 'changed@example.com', 'is_active': False},
        ]:
            self.assertEqual(self.edit(**payload).status_code, 400, payload)
        self.target.refresh_from_db()
        self.assertEqual(self.target.email, 'employee@example.com')
        self.assertFalse(AuditLog.objects.exists())

    def test_cross_tenant_missing_and_global_targets_not_exposed(self):
        self.client.force_authenticate(self.owner)
        platform = User.objects.create_user(username='platform', is_superuser=True)
        for target in [self.other, platform]:
            self.assertEqual(self.edit(target, email='new@example.com').status_code, 404)
        self.assertEqual(self.client.patch('/api/users/999999/', {'email': 'new@example.com'}, format='json').status_code, 404)
        self.other.refresh_from_db()
        self.assertEqual(self.other.email, 'other@example.com')
        self.assertFalse(AuditLog.objects.exists())

    def test_anonymous_operational_roles_and_global_admin_cannot_edit(self):
        self.assertEqual(self.edit(email='new@example.com').status_code, 401)
        platform = User.objects.create_user(username='platform', is_superuser=True)
        for actor in [platform] + [self.make_member(f'{role}@example.com', role) for role in ['WAITER', 'CASHIER', 'KITCHEN']]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.edit(email='new@example.com').status_code, 403)
        self.assertFalse(AuditLog.objects.exists())

    def test_audit_failure_rolls_back_and_unchanged_email_is_noop(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.edit(email=self.target.email).status_code, 200)
        self.assertFalse(AuditLog.objects.exists())
        with patch('api.user_management.AuditLog.objects.create', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.edit(email='new@example.com')
        self.target.refresh_from_db()
        self.assertEqual(self.target.email, 'employee@example.com')
        self.assertEqual(self.target.username, 'employee@example.com')

    def test_self_edit_updates_existing_session_and_login_uses_new_email(self):
        password = 'Nexo-edit-837!temporary'
        self.owner.set_password(password)
        self.owner.save(update_fields=['password'])
        login = self.client.post('/api/auth/login/', {'email': self.owner.email, 'password': password})
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login.data['token'])
        self.assertEqual(self.edit(self.owner, email='new-owner@example.com').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').data['email'], 'new-owner@example.com')
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.initial_owner_id, self.owner.pk)
        self.assertTrue(AccessToken.objects.filter(user=self.owner).exists())
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/login/', {'email': 'owner@example.com', 'password': password}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login/', {'email': 'new-owner@example.com', 'password': password}).status_code, 200)

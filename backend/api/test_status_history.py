import hashlib
import secrets
from datetime import timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connections
from django.test import TransactionTestCase
from rest_framework.exceptions import APIException
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from .models import AccessToken, AuditLog, Membership, Restaurant
from .ownership import change_role
from .user_management import change_user_status

User = get_user_model()


class StatusHistoryTests(APITestCase):
    def setUp(self):
        self.first = User.objects.create_user(username='first@example.com', email='first@example.com')
        self.a = Restaurant.objects.create(name='A', initial_owner=self.first)
        Membership.objects.create(user=self.first, restaurant=self.a, role='OWNER')
        self.admin = self.member('admin', 'ADMIN')
        self.employee = self.member('employee', 'WAITER')
        self.second = self.member('second', 'OWNER')
        self.platform = User.objects.create_user(username='global', email='global@example.com', is_superuser=True)
        self.other = User.objects.create_user(username='foreign', email='foreign@example.com')
        self.b = Restaurant.objects.create(name='B', initial_owner=self.other)
        Membership.objects.create(user=self.other, restaurant=self.b, role='OWNER')

    def member(self, name, role):
        user = User.objects.create_user(username=name, email=f'{name}@example.com')
        Membership.objects.create(user=user, restaurant=self.a, role=role)
        return user

    def status(self, actor, target, active):
        self.client.force_authenticate(actor)
        return self.client.patch(f'/api/users/{target.pk}/status/', {'is_active': active}, format='json')

    def global_status(self, active):
        self.client.force_authenticate(self.platform)
        return self.client.patch('/api/platform/initial-owner-status/', {'restaurant': str(self.a.pk), 'is_active': active}, format='json')

    def token(self, user):
        raw = secrets.token_urlsafe(32)
        AccessToken.objects.create(digest=hashlib.sha256(raw.encode()).hexdigest(), user=user, expires_at=timezone.now()+timedelta(hours=1))
        return raw

    def use_token(self, raw):
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+raw)

    def test_local_owner_and_admin_can_toggle_without_losing_history(self):
        entry = AuditLog.objects.create(restaurant=self.a, actor=self.employee, action='user.created', entity_id=str(self.employee.pk), after={'email': self.employee.email})
        for actor in [self.first, self.admin]:
            self.assertEqual(self.status(actor, self.employee, False).status_code, 200)
            self.assertEqual(self.status(actor, self.employee, True).status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.actor_id, self.employee.pk)
        self.assertEqual(Membership.objects.get(user=self.employee).role, 'WAITER')
        self.assertEqual(AuditLog.objects.filter(action='user.status_changed').count(), 4)
        self.assertEqual(self.status(self.admin, self.employee, True).status_code, 200)
        self.assertEqual(AuditLog.objects.filter(action='user.status_changed').count(), 4)

    def test_unauthorized_cross_tenant_and_forged_status_requests_rejected(self):
        for actor in [self.employee, self.platform]:
            self.assertEqual(self.status(actor, self.admin, False).status_code, 403)
        self.assertEqual(self.status(self.first, self.other, False).status_code, 404)
        self.assertEqual(self.status(self.admin, self.first, False).status_code, 403)
        self.client.force_authenticate(self.employee)
        self.assertEqual(self.client.patch('/api/platform/initial-owner-status/', {'restaurant': str(self.a.pk), 'is_active': False}, format='json').status_code, 403)
        self.client.force_authenticate(self.first)
        for extra in [{'restaurant': str(self.b.pk)}, {'role': 'OWNER'}, {'is_superuser': True}]:
            self.assertEqual(self.client.patch(f'/api/users/{self.employee.pk}/status/', {'is_active': False, **extra}, format='json').status_code, 400)
        self.assertFalse(AuditLog.objects.exists())

    def test_individual_deactivation_blocks_login_and_revokes_existing_token(self):
        password = 'QA-status-439!temporary'
        self.employee.set_password(password)
        self.employee.save(update_fields=['password'])
        token = self.token(self.employee)
        self.assertEqual(self.status(self.first, self.employee, False).status_code, 200)
        self.use_token(token)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/login/', {'email': self.employee.email, 'password': password}).status_code, 401)
        self.assertEqual(self.status(self.first, self.employee, True).status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/auth/login/', {'email': self.employee.email, 'password': password}).status_code, 200)

    def test_global_suspension_blocks_all_roles_despite_another_owner_and_preserves_individual_states(self):
        self.status(self.first, self.employee, False)
        tokens = [(user, self.token(user)) for user in [self.first, self.admin, self.second]]
        other_token = self.token(self.other)
        self.assertEqual(self.global_status(False).status_code, 200)
        for user, token in tokens:
            self.use_token(token)
            self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        # Even a token issued outside the API cannot bypass the cascade.
        self.use_token(self.token(self.second))
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)
        self.use_token(other_token)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        self.assertEqual(self.global_status(True).status_code, 200)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
        self.assertTrue(User.objects.get(pk=self.admin.pk).is_active)
        for user, token in tokens:
            self.use_token(token)
            self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.use_token(self.token(self.admin))
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)

    def test_cascade_blocks_login_and_suspension_is_exception_to_last_owner_rule(self):
        Membership.objects.filter(user=self.second).update(role='KITCHEN')
        password = 'QA-chain-492!temporary'
        self.admin.set_password(password)
        self.admin.save(update_fields=['password'])
        self.assertEqual(self.global_status(False).status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/auth/login/', {'email': self.admin.email, 'password': password}).status_code, 403)
        self.assertEqual(self.global_status(True).status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post('/api/auth/login/', {'email': self.admin.email, 'password': password}).status_code, 200)

    def test_status_audit_failure_rolls_back_user_and_token_revocation(self):
        token = self.token(self.employee)
        with patch('api.user_management.AuditLog.objects.create', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.status(self.first, self.employee, False)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)
        self.use_token(token)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)

    def test_local_cannot_deactivate_last_owner_and_global_reactivation_preserves_restaurant_state(self):
        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.patch('/api/platform/initial-owner-role/', {'restaurant': str(self.a.pk), 'role': 'ADMIN'}, format='json').status_code, 200)
        self.assertEqual(self.status(self.admin, self.second, False).status_code, 400)
        self.assertEqual(self.global_status(False).status_code, 200)
        Restaurant.objects.filter(pk=self.a.pk).update(is_active=False)
        self.assertEqual(self.global_status(True).status_code, 200)
        self.a.refresh_from_db()
        self.assertFalse(self.a.is_active)

    def test_history_is_paginated_read_only_and_tenant_scoped(self):
        for number in range(23):
            AuditLog.objects.create(restaurant=self.a, actor=self.first, action='user.email_changed', entity_id=str(self.employee.pk), before={'email': f'old-{number}@example.com', 'password': 'never expose'}, after={'email': f'new-{number}@example.com', 'token': 'never expose'})
        foreign = AuditLog.objects.create(restaurant=self.b, actor=self.other, action='user.created', entity_id=str(self.other.pk), after={'email': self.other.email})
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/history/', {'restaurant_id': str(self.b.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 23)
        self.assertEqual(len(response.data['results']), 20)
        self.assertNotIn(foreign.pk, [entry['id'] for entry in response.data['results']])
        self.assertNotIn('never expose', str(response.data))
        self.assertEqual(len(self.client.get('/api/history/?page=2').data['results']), 3)
        self.assertEqual(self.client.patch('/api/history/', {'id': foreign.pk}, format='json').status_code, 405)
        self.assertEqual(self.client.delete('/api/history/').status_code, 405)

    def test_global_history_excludes_local_employee_changes_and_roles_cannot_enumerate_it(self):
        self.status(self.first, self.employee, False)
        local = AuditLog.objects.get()
        self.global_status(False)
        self.client.force_authenticate(self.platform)
        entries = self.client.get('/api/history/').data['results']
        self.assertNotIn(local.pk, [entry['id'] for entry in entries])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['target'], self.first.email)
        self.global_status(True)
        self.client.force_authenticate(self.employee)
        self.assertEqual(self.client.get('/api/history/').status_code, 403)


class StatusConcurrencyTests(TransactionTestCase):
    def test_deactivation_and_demotion_cannot_remove_both_active_owners(self):
        first = User.objects.create_user(username='first')
        second = User.objects.create_user(username='second')
        admin = User.objects.create_user(username='admin')
        platform = User.objects.create_user(username='platform', is_superuser=True)
        restaurant = Restaurant.objects.create(name='Concurrent status', initial_owner=first)
        for user, role in [(first, 'OWNER'), (second, 'OWNER'), (admin, 'ADMIN')]:
            Membership.objects.create(user=user, restaurant=restaurant, role=role)
        barrier = Barrier(2)

        def run(global_role_change):
            try:
                actor = User.objects.get(pk=platform.pk if global_role_change else admin.pk)
                barrier.wait(timeout=10)
                try:
                    if global_role_change:
                        change_role(actor=actor, restaurant_id=restaurant.pk, user_id=None, role='ADMIN', platform=True)
                    else:
                        change_user_status(actor=actor, restaurant_id=restaurant.pk, user_id=second.pk, is_active=False)
                    return 200
                except APIException as exc:
                    return exc.status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, value) for value in [True, False]]
            outcomes = [future.result(timeout=20) for future in futures]
        self.assertTrue(all(code in [200, 400, 409] for code in outcomes), outcomes)
        self.assertLessEqual(outcomes.count(200), 1, outcomes)
        self.assertTrue(Membership.objects.filter(restaurant=restaurant, role='OWNER', is_active=True, user__is_active=True).exists())

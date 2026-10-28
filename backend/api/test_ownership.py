from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.exceptions import APIException
from rest_framework.test import APITestCase
from .models import AuditLog, Membership, Restaurant
from .ownership import change_role

User = get_user_model()


class OwnershipTests(APITestCase):
    def setUp(self):
        self.first = User.objects.create_user(username='first', email='first@example.com')
        self.restaurant = Restaurant.objects.create(name='A', initial_owner=self.first)
        Membership.objects.create(user=self.first, restaurant=self.restaurant, role='OWNER')
        self.second = self.make_member('second', 'OWNER')
        self.admin = self.make_member('admin', 'ADMIN')
        self.platform = User.objects.create_user(username='platform', is_superuser=True)

    def make_member(self, name, role):
        user = User.objects.create_user(username=name, email=f'{name}@example.com')
        Membership.objects.create(user=user, restaurant=self.restaurant, role=role)
        return user

    def local_change(self, actor, target, role='ADMIN'):
        self.client.force_authenticate(actor)
        return self.client.patch('/api/users/', {'id': target.pk, 'role': role}, format='json')

    def global_change(self, role='ADMIN', **extra):
        self.client.force_authenticate(self.platform)
        return self.client.patch('/api/platform/initial-owner-role/', {'restaurant': str(self.restaurant.pk), 'role': role, **extra}, format='json')

    def test_first_owner_cannot_be_demoted_by_any_local_manager_including_self(self):
        for actor in [self.first, self.second, self.admin]:
            self.assertEqual(self.local_change(actor, self.first).status_code, 403)
        self.assertEqual(Membership.objects.get(user=self.first).role, 'OWNER')
        self.assertFalse(AuditLog.objects.exists())

    def test_global_exception_preserves_initial_identity_and_audits(self):
        self.assertEqual(self.global_change().status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.initial_owner_id, self.first.pk)
        self.assertEqual(Membership.objects.get(user=self.first).role, 'ADMIN')
        log = AuditLog.objects.get()
        self.assertEqual((log.restaurant_id, log.actor_id, log.entity_id), (self.restaurant.pk, self.platform.pk, str(self.first.pk)))
        self.assertEqual(log.before, {'role': 'OWNER'})
        self.assertEqual(log.after, {'role': 'ADMIN'})
        self.assertEqual(self.global_change('OWNER').status_code, 200)
        self.assertEqual(self.local_change(self.second, self.first).status_code, 403)

    def test_last_owner_protected_for_global_and_local_changes(self):
        self.assertEqual(self.local_change(self.admin, self.second).status_code, 200)
        self.assertEqual(self.global_change().status_code, 400)
        self.assertEqual(Membership.objects.get(user=self.first).role, 'OWNER')
        self.assertEqual(self.local_change(self.admin, self.second, 'OWNER').status_code, 200)
        self.assertEqual(self.global_change().status_code, 200)
        self.assertEqual(self.local_change(self.admin, self.second, 'KITCHEN').status_code, 400)
        self.assertEqual(Membership.objects.get(user=self.second).role, 'OWNER')

    def test_inactive_account_or_membership_does_not_count_as_remaining_owner(self):
        self.second.is_active = False
        self.second.save(update_fields=['is_active'])
        self.assertEqual(self.global_change().status_code, 400)
        self.second.is_active = True
        self.second.save(update_fields=['is_active'])
        Membership.objects.filter(user=self.second).update(is_active=False)
        self.assertEqual(self.global_change().status_code, 400)

    def test_global_endpoint_rejects_local_roles_extra_target_and_invalid_roles(self):
        for role in Membership.Role.values:
            actor = self.make_member(f'local-{role}', role)
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.patch('/api/platform/initial-owner-role/', {'restaurant': str(self.restaurant.pk), 'role': 'ADMIN'}, format='json').status_code, 403)
        self.assertEqual(self.global_change(user_id=self.second.pk).status_code, 400)
        self.assertEqual(self.global_change('PLATFORM_ADMIN').status_code, 400)
        self.assertFalse(AuditLog.objects.exists())

    def test_cross_tenant_owner_never_counts_and_global_has_no_employee_directory(self):
        other = Restaurant.objects.create(name='B')
        foreign = User.objects.create_user(username='foreign')
        Membership.objects.create(user=foreign, restaurant=other, role='OWNER')
        self.assertEqual(self.local_change(self.admin, foreign).status_code, 404)
        Membership.objects.filter(user=self.second).update(role='WAITER')
        self.assertEqual(self.global_change().status_code, 400)
        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.get('/api/users/').status_code, 403)

    def test_local_metadata_and_global_metadata_are_narrowly_scoped(self):
        self.client.force_authenticate(self.admin)
        rows = self.client.get('/api/users/').data
        self.assertTrue(next(row for row in rows if row['id'] == self.first.pk)['is_initial_owner'])
        self.assertEqual(self.global_change().status_code, 200)
        self.client.force_authenticate(self.platform)
        row = self.client.get('/api/platform/restaurants/').data[0]
        self.assertEqual(row['initial_owner'], {'email': self.first.email, 'role': 'ADMIN', 'is_active': True})
        self.assertEqual(row['owners'], [{'id': self.second.pk, 'email': self.second.email}])


class OwnershipConcurrencyTests(TransactionTestCase):
    def test_concurrent_demotions_cannot_remove_both_owners(self):
        first = User.objects.create_user(username='first')
        second = User.objects.create_user(username='second')
        admin = User.objects.create_user(username='admin')
        platform = User.objects.create_user(username='platform', is_superuser=True)
        restaurant = Restaurant.objects.create(name='Concurrent', initial_owner=first)
        for user, role in [(first, 'OWNER'), (second, 'OWNER'), (admin, 'ADMIN')]:
            Membership.objects.create(user=user, restaurant=restaurant, role=role)
        barrier = Barrier(2)

        def demote(actor_id, target_id, platform_access):
            try:
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    change_role(actor=actor, restaurant_id=restaurant.pk, user_id=target_id, role='KITCHEN', platform=platform_access)
                    return 200
                except APIException as exc:
                    return exc.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(demote, platform.pk, first.pk, True)
            two = pool.submit(demote, admin.pk, second.pk, False)
            outcomes = [one.result(timeout=20), two.result(timeout=20)]
        self.assertTrue(all(code in [200, 400, 409] for code in outcomes), outcomes)
        self.assertLessEqual(outcomes.count(200), 1, outcomes)
        self.assertGreaterEqual(Membership.objects.filter(restaurant=restaurant, role='OWNER', is_active=True, user__is_active=True).count(), 1)


class InitialOwnerMigrationTests(TransactionTestCase):
    def test_backfill_uses_audit_and_reverse_preserves_accounts_and_roles(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate([('api', '0002_auditlog')])
        old = executor.loader.project_state([('api', '0002_auditlog')]).apps
        user = User.objects.create_user(username='historical')
        restaurant = old.get_model('api', 'Restaurant').objects.create(name='Historical')
        old.get_model('api', 'Membership').objects.create(restaurant_id=restaurant.pk, user_id=user.pk, role='OWNER')
        try:
            executor = MigrationExecutor(connection)
            with self.assertRaisesRegex(RuntimeError, 'falta evidencia'):
                executor.migrate([('api', '0003_restaurant_initial_owner')])
            old.get_model('api', 'AuditLog').objects.create(restaurant_id=restaurant.pk, actor_id=user.pk, action='restaurant.created', entity_id=str(restaurant.pk), after={'owner': user.pk})
            executor = MigrationExecutor(connection)
            executor.migrate([('api', '0003_restaurant_initial_owner')])
            self.assertEqual(Restaurant.objects.get(pk=restaurant.pk).initial_owner_id, user.pk)
            executor = MigrationExecutor(connection)
            executor.migrate([('api', '0002_auditlog')])
            self.assertEqual(old.get_model('api', 'Membership').objects.get(user_id=user.pk).role, 'OWNER')
            self.assertTrue(User.objects.filter(pk=user.pk).exists())
        finally:
            MigrationExecutor(connection).migrate(latest)

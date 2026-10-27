import hashlib
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase
from .models import Restaurant, Membership, AccessToken, AuditLog

User = get_user_model()


class IdentityTests(APITestCase):
    def setUp(self):
        self.a = Restaurant.objects.create(name='A')
        self.b = Restaurant.objects.create(name='B')
        self.owner = self.make_user('owner@a.co', self.a, 'OWNER')
        self.other = self.make_user('owner@b.co', self.b, 'OWNER')
        self.platform = self.make_user('dev@nexo.co', superuser=True)

    def make_user(self, email, restaurant=None, role='WAITER', superuser=False):
        user = User.objects.create_user(username=email, email=email, password='Nexo-test-987!good', is_superuser=superuser)
        if restaurant:
            Membership.objects.create(user=user, restaurant=restaurant, role=role)
        return user

    def login(self, user):
        self.client.credentials()
        response = self.client.post('/api/auth/login/', {'email': user.email, 'password': 'Nexo-test-987!good'})
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['token'])
        return response

    def test_token_is_hashed_expires_in_one_hour_and_does_not_slide(self):
        start = timezone.now()
        response = self.login(self.owner)
        token = AccessToken.objects.get()
        self.assertEqual(token.digest, hashlib.sha256(response.data['token'].encode()).hexdigest())
        self.assertAlmostEqual((token.expires_at - start).total_seconds(), 3600, delta=5)
        expiry = token.expires_at
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        token.refresh_from_db()
        self.assertEqual(expiry, token.expires_at)
        token.expires_at = timezone.now() - timedelta(seconds=1)
        token.save()
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_bad_password_and_inactive_identity_create_no_token(self):
        self.assertEqual(self.client.post('/api/auth/login/', {'email': self.owner.email, 'password': 'wrong'}).status_code, 401)
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.client.post('/api/auth/login/', {'email': self.owner.email, 'password': 'Nexo-test-987!good'}).status_code, 401)
        self.assertFalse(AccessToken.objects.exists())

    def test_logout_revokes_token(self):
        self.login(self.owner)
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_create_and_read_users_ignore_forged_tenant_and_privileges(self):
        self.login(self.owner)
        response = self.client.post('/api/users/', {'email': 'new@a.co', 'password': 'Nexo-test-487!other', 'role': 'ADMIN', 'restaurant_id': str(self.b.pk), 'is_superuser': True})
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(pk=response.data['id'])
        self.assertTrue(user.check_password('Nexo-test-487!other'))
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.membership.restaurant, self.a)
        rows = self.client.get('/api/users/', {'restaurant_id': str(self.b.pk)}).data
        self.assertNotIn(self.other.email, [row['email'] for row in rows])
        self.assertEqual(AuditLog.objects.get().restaurant, self.a)
        self.assertNotIn('password', str(AuditLog.objects.get().after))

    def test_roles_and_permissions_are_checked_server_side(self):
        for role in Membership.Role.values:
            user = self.make_user(f'role-{role.lower()}@a.co', self.a, role)
            self.login(user)
            expected = 200 if role in ['OWNER', 'ADMIN'] else 403
            self.assertEqual(self.client.get('/api/users/').status_code, expected)
            if expected == 403:
                self.assertEqual(self.client.post('/api/users/', {'email': 'forbidden@a.co', 'password': 'Nexo-test-789!', 'role': 'OWNER'}).status_code, 403)
            self.assertEqual(self.client.get('/api/platform/restaurants/').status_code, 403)
        self.assertFalse(User.objects.filter(email='forbidden@a.co').exists())

    def test_invalid_roles_and_weak_passwords_rejected(self):
        self.login(self.owner)
        for payload in [dict(role='PLATFORM_ADMIN', password='Nexo-test-456!'), dict(role='WAITER', password='123')]:
            self.assertEqual(self.client.post('/api/users/', {'email': 'invalid@a.co', **payload}).status_code, 400)
        self.assertFalse(User.objects.filter(email='invalid@a.co').exists())

    def test_global_admin_can_manage_restaurants_but_not_operational_users(self):
        self.login(self.platform)
        owner = self.make_user('newowner@nexo.co')
        response = self.client.post('/api/platform/restaurants/', {'name': 'C', 'owner': owner.pk})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(owner.membership.role, 'OWNER')
        self.assertEqual(self.client.get('/api/users/').status_code, 403)
        self.assertEqual(self.client.get('/api/auth/me/').data['modules'], ['restaurants'])
        self.assertEqual(self.client.patch('/api/platform/restaurants/', {'id': response.data['id'], 'is_active': False}, format='json').status_code, 200)
        self.assertFalse(Restaurant.objects.get(pk=response.data['id']).is_active)

    def test_cannot_move_existing_owner_across_restaurants(self):
        self.login(self.platform)
        response = self.client.patch('/api/platform/restaurants/', {'id': str(self.a.pk), 'owner': self.other.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.other.membership.refresh_from_db()
        self.assertEqual(self.other.membership.restaurant, self.b)

    def test_deactivation_and_role_change_take_effect_on_existing_token(self):
        self.login(self.owner)
        m = self.owner.membership
        m.role = 'KITCHEN'
        m.save()
        self.assertEqual(self.client.get('/api/users/').status_code, 403)
        m.is_active = False
        m.save()
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)

    def test_restaurant_deactivation_blocks_login_and_existing_token(self):
        self.login(self.owner)
        self.a.is_active = False
        self.a.save()
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/login/', {'email': self.owner.email, 'password': 'Nexo-test-987!good'}).status_code, 403)

    def test_cashier_inherits_waiter_modules(self):
        from .identity import ROLE_MODULES
        self.assertTrue(set(ROLE_MODULES['WAITER']).issubset(ROLE_MODULES['CASHIER']))

    def test_anonymous_and_forged_tokens_are_rejected(self):
        self.assertEqual(self.client.get('/api/users/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer forged')
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_membership_unique_per_user(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(user=self.owner, restaurant=self.b, role='OWNER')

    def test_platform_creates_owner_then_owner_creates_local_user(self):
        self.login(self.platform)
        response = self.client.post('/api/platform/owners/', {'email': 'future@example.com', 'password': 'Nexo-test-987!good', 'is_superuser': True, 'role': 'PLATFORM_ADMIN', 'restaurant_id': str(self.b.pk)})
        self.assertEqual(response.status_code, 201, response.data)
        owner = User.objects.get(pk=response.data['id'])
        self.assertFalse(owner.is_superuser)
        self.assertFalse(owner.is_staff)
        self.assertFalse(Membership.objects.filter(user=owner).exists())
        self.assertTrue(owner.check_password('Nexo-test-987!good'))
        self.assertEqual(self.client.get('/api/platform/owners/').data, [{'id': owner.pk, 'email': owner.email}])
        restaurant = self.client.post('/api/platform/restaurants/', {'name': 'Nuevo', 'owner': owner.pk})
        self.assertEqual(restaurant.status_code, 201)
        self.assertEqual(self.client.get('/api/platform/owners/').data, [])
        self.assertTrue(any(row['owners'] == [{'id': owner.pk, 'email': owner.email}] for row in self.client.get('/api/platform/restaurants/').data))
        self.login(owner)
        employee = self.client.post('/api/users/', {'email': 'staff@example.com', 'password': 'Staff-975!different', 'role': 'WAITER', 'restaurant_id': str(self.b.pk)})
        self.assertEqual(employee.status_code, 201)
        self.assertEqual(User.objects.get(pk=employee.data['id']).membership.restaurant_id, owner.membership.restaurant_id)
        self.assertNotIn(self.other.email, [row['email'] for row in self.client.get('/api/users/').data])

    def test_pending_owner_cannot_login_until_assigned_and_is_audited(self):
        self.login(self.platform)
        data = {'email': 'pending@example.com', 'password': 'Nexo-test-987!good'}
        self.assertEqual(self.client.post('/api/platform/owners/', data).status_code, 201)
        entry = AuditLog.objects.get(action='prospective_owner.created')
        self.assertIsNone(entry.restaurant)
        self.assertNotIn('password', str(entry.after))
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/login/', data).status_code, 403)
        self.login(self.platform)
        self.assertEqual(self.client.post('/api/platform/owners/', data).status_code, 400)
        self.assertEqual(self.client.post('/api/platform/owners/', {'email': 'weak@example.com', 'password': '123'}).status_code, 400)

    def test_local_roles_cannot_create_or_list_prospective_owners(self):
        for role in Membership.Role.values:
            user = self.make_user(f'local-{role.lower()}@example.com', self.a, role)
            self.login(user)
            self.assertEqual(self.client.get('/api/platform/owners/').status_code, 403)
            self.assertEqual(self.client.post('/api/platform/owners/', {'email': 'illegal@example.com', 'password': 'Nexo-test-987!good'}).status_code, 403)
        self.assertFalse(User.objects.filter(email='illegal@example.com').exists())

    def test_platform_links_pending_owner_to_existing_restaurant(self):
        self.login(self.platform)
        created = self.client.post('/api/platform/owners/', {'email': 'existing-owner@example.com', 'password': 'Nexo-test-987!good'})
        self.assertEqual(created.status_code, 201)
        response = self.client.patch('/api/platform/restaurants/', {'id': str(self.a.pk), 'owner': created.data['id']}, format='json')
        self.assertEqual(response.status_code, 200)
        membership = Membership.objects.get(user_id=created.data['id'])
        self.assertEqual(membership.restaurant, self.a)
        self.assertEqual(membership.role, 'OWNER')
        self.assertEqual(self.client.get('/api/platform/owners/').data, [])
        self.assertEqual(self.client.get('/api/users/').status_code, 403)

from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import AuditLog, Category, Membership, Product, Restaurant


class ProductEditingTests(APITestCase):
    # RF-026: edits retain product identity and never rewrite previous audit snapshots.
    def setUp(self):
        self.a = Restaurant.objects.create(name='A')
        self.b = Restaurant.objects.create(name='B')
        self.owner = self.member('owner', 'OWNER', self.a)
        self.admin = self.member('admin', 'ADMIN', self.a)
        self.other = self.member('other', 'OWNER', self.b)
        self.category = Category.objects.create(restaurant=self.a, name='Entradas', position=1)
        self.second = Category.objects.create(restaurant=self.a, name='Bebidas', position=2)
        foreign = Category.objects.create(restaurant=self.b, name='Privada', position=1)
        self.product = Product.objects.create(category=self.category, name='Sopa', price='18000.25', is_active=True)
        self.foreign = Product.objects.create(category=foreign, name='Ajeno', price='1', is_active=True)
        self.path = f'/api/products/{self.product.pk}/'
        self.client.force_authenticate(self.owner)

    def member(self, name, role, restaurant):
        user = get_user_model().objects.create_user(username=name)
        Membership.objects.create(user=user, role=role, restaurant=restaurant)
        return user

    def test_manager_edits_persist_and_keep_original_event(self):
        original = AuditLog.objects.create(restaurant=self.a, actor=self.owner, action='product.created',
                  entity_id=str(self.product.pk), after={'name': 'Sopa', 'price': '18000.25'})
        for actor, name in ((self.owner, 'Sopa casera'), (self.admin, 'Sopa del día')):
            self.client.force_authenticate(actor)
            response = self.client.patch(self.path, {'name': name, 'description': 'Con verduras', 'category': str(self.second.pk)}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['price'], '18000.25')
            self.assertTrue(response.data['is_active'])
            self.assertEqual(response.data['id'], str(self.product.pk))
            self.assertEqual(self.client.get(self.path).data, response.data)
            event = AuditLog.objects.filter(action='product.updated').latest('pk')
            self.assertEqual((event.actor, event.restaurant, event.entity_id), (actor, self.a, str(self.product.pk)))
            self.assertEqual(event.after['name'], name)
        original.refresh_from_db()
        self.assertEqual(original.after, {'name': 'Sopa', 'price': '18000.25'})
        count = AuditLog.objects.count()
        self.assertEqual(self.client.patch(self.path, {'name': 'Sopa del día'}, format='json').status_code, 200)
        self.assertEqual(AuditLog.objects.count(), count)
        self.assertEqual(self.client.get('/api/history/?action=product.updated').data['count'], 2)

    def test_bidirectional_tenant_isolation_and_cache(self):
        for actor, visible, hidden in ((self.owner, self.product, self.foreign), (self.other, self.foreign, self.product)):
            self.client.force_authenticate(actor)
            own = self.client.get(f'/api/products/{visible.pk}/', {'restaurant_id': str(hidden.category.restaurant_id)})
            self.assertEqual(own.status_code, 200)
            self.assertIn('no-store', own['Cache-Control'])
            path = f'/api/products/{hidden.pk}/'
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.patch(path, {'name': 'Intrusión'}, format='json').status_code, 404)
        self.product.refresh_from_db()
        self.foreign.refresh_from_db()
        self.assertEqual((self.product.name, self.foreign.name), ('Sopa', 'Ajeno'))
        self.assertFalse(AuditLog.objects.exists())

    def test_category_ownership_and_inactive_category_retention(self):
        self.category.is_active = False
        self.category.save()
        self.assertEqual(self.client.patch(self.path, {'category': str(self.category.pk), 'name': 'Sopa nueva'}, format='json').status_code, 200)
        self.second.is_active = False
        self.second.save()
        for category in (self.second, self.foreign.category):
            self.assertEqual(self.client.patch(self.path, {'category': str(category.pk)}, format='json').status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.category_id, self.category.pk)

    def test_validation_and_disallowed_mutations(self):
        for body in ({}, {'name': ''}, {'name': ' '}, {'name': 'x' * 161}, {'description': None},
                     {'category': 'invalid'}, {'price': '1'}, {'is_active': False}, {'restaurant_id': str(self.b.pk)},
                     {'name': 'Otro', 'id': str(self.foreign.pk)}):
            self.assertEqual(self.client.patch(self.path, body, format='json').status_code, 400, body)
        for method in ('delete', 'post', 'put'):
            self.assertEqual(getattr(self.client, method)(self.path).status_code, 405)
        self.assertFalse(AuditLog.objects.exists())

    def test_roles_anonymous_and_revocation(self):
        actors = [self.member(role, role, self.a) for role in ('WAITER', 'CASHIER', 'KITCHEN')]
        actors.append(get_user_model().objects.create_user(username='platform', is_superuser=True))
        for actor in actors:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get(self.path).status_code, 403)
            self.assertEqual(self.client.patch(self.path, {'name': 'No'}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(self.path, {'name': 'No'}, format='json').status_code, 401)
        self.client.force_authenticate(self.owner)
        Membership.objects.filter(user=self.owner).update(is_active=False)
        self.assertEqual(self.client.patch(self.path, {'name': 'No'}, format='json').status_code, 403)

    def test_audit_failure_rolls_back_all_fields(self):
        with patch('api.products.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.patch(self.path, {'name': 'Otro', 'description': 'Otra', 'category': str(self.second.pk)}, format='json')
        self.product.refresh_from_db()
        self.assertEqual((self.product.name, self.product.description, self.product.category_id), ('Sopa', '', self.category.pk))
        self.assertFalse(AuditLog.objects.exists())

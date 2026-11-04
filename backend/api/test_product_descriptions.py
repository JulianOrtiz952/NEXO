from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from .models import AuditLog, Category, Membership, Product, Restaurant


class ProductDescriptionTests(APITestCase):
    # RF-025: persistence, independent editing, permissions and tenant isolation.
    def setUp(self):
        self.a = Restaurant.objects.create(name='A')
        self.b = Restaurant.objects.create(name='B')
        self.owner = self.member('owner', 'OWNER', self.a)
        self.admin = self.member('admin', 'ADMIN', self.a)
        self.other = self.member('other', 'OWNER', self.b)
        self.category = Category.objects.create(restaurant=self.a, name='Carta', position=1)
        other_category = Category.objects.create(restaurant=self.b, name='Otra', position=1)
        self.product = Product.objects.create(category=self.category, name='Sopa', price='18000.25', is_active=True)
        self.foreign = Product.objects.create(category=other_category, name='Ajeno', description='Privado B', price='1', is_active=True)
        self.path = f'/api/products/{self.product.pk}/description/'
        self.client.force_authenticate(self.owner)

    def member(self, username, role, restaurant):
        user = get_user_model().objects.create_user(username=username)
        Membership.objects.create(user=user, restaurant=restaurant, role=role)
        return user

    def test_optional_description_creation_and_queries(self):
        payload = {'name': 'Jugo', 'price': '0.00', 'category': str(self.category.pk), 'is_active': True}
        for description in (None, '', 'Fruta fresca\nSin azúcar añadida.'):
            values = payload if description is None else {**payload, 'description': description}
            response = self.client.post('/api/products/', values, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            expected = description or ''
            self.assertEqual(response.data['description'], expected)
            product = Product.objects.get(pk=response.data['id'])
            self.assertEqual(product.description, expected)
            self.assertEqual(AuditLog.objects.get(entity_id=str(product.pk)).after['description'], expected)
        self.assertEqual(len(self.client.get('/api/products/').data), 4)
        for role in ('WAITER', 'CASHIER'):
            self.client.force_authenticate(self.member(role, role, self.a))
            response = self.client.get('/api/menu/')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertIn('Fruta fresca\nSin azúcar añadida.', [p['description'] for p in response.data['products']])
            self.assertNotIn('Privado B', str(response.data))

    def test_edit_clear_noop_and_immutable_creation_audit(self):
        self.product.refresh_from_db()
        original = (self.product.name, self.product.price, self.product.category_id, self.product.is_active)
        creation = AuditLog.objects.create(restaurant=self.a, actor=self.owner, action='product.created',
                                          entity_id=str(self.product.pk), after={'name': 'Sopa', 'description': ''})
        snapshot = creation.after.copy()
        for actor, description in ((self.owner, 'Caldo del día\nCon verduras.'), (self.admin, '')):
            self.client.force_authenticate(actor)
            response = self.client.patch(self.path, {'description': description}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIn('no-store', response['Cache-Control'])
            self.product.refresh_from_db()
            self.assertEqual(self.product.description, description)
            self.assertEqual((self.product.name, self.product.price, self.product.category_id, self.product.is_active), original)
            event = AuditLog.objects.filter(action='product.description_changed').latest('pk')
            self.assertEqual((event.actor, event.restaurant, event.entity_id), (actor, self.a, str(self.product.pk)))
            self.assertEqual(event.after, {'name': 'Sopa', 'description': description})
            self.assertEqual(self.client.get('/api/products/').data[0]['description'], description)
        count = AuditLog.objects.count()
        self.assertEqual(self.client.patch(self.path, {'description': ''}, format='json').status_code, 200)
        self.assertEqual(AuditLog.objects.count(), count)
        history = self.client.get('/api/history/?action=product.description_changed').data
        self.assertEqual(history['count'], 2)
        self.assertEqual(history['results'][0]['before']['description'], 'Caldo del día\nCon verduras.')
        self.assertEqual(history['results'][0]['after']['description'], '')
        self.assertEqual(history['results'][0]['action_type'], 'Cambio de descripción')
        creation.refresh_from_db()
        self.assertEqual(creation.after, snapshot)

    def test_cross_tenant_ids_query_parameters_and_history(self):
        for actor, visible, hidden in ((self.owner, self.product, self.foreign), (self.other, self.foreign, self.product)):
            self.client.force_authenticate(actor)
            path = f'/api/products/{hidden.pk}/description/'
            for body in ({'description': 'Intrusión'}, {'description': 'Intrusión', 'restaurant_id': str(self.b.pk)}):
                self.assertEqual(self.client.patch(path, body, format='json').status_code, 404)
            response = self.client.get('/api/products/', {'restaurant_id': str(hidden.category.restaurant_id)})
            self.assertEqual([p['id'] for p in response.data], [str(visible.pk)])
            if hidden.description:
                self.assertNotIn(hidden.description, str(response.data))
        self.assertFalse(AuditLog.objects.exists())
        self.product.refresh_from_db()
        self.foreign.refresh_from_db()
        self.assertEqual((self.product.description, self.foreign.description), ('', 'Privado B'))
        self.client.force_authenticate(self.owner)
        self.client.patch(self.path, {'description': 'Solo A'}, format='json')
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/history/?action=product.description_changed').data['count'], 0)

    def test_roles_revocation_and_anonymous(self):
        actors = [self.member(role, role, self.a) for role in ('WAITER', 'CASHIER', 'KITCHEN')]
        actors.append(get_user_model().objects.create_user(username='global', is_superuser=True))
        for actor in actors:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.patch(self.path, {'description': 'No'}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(self.path, {'description': 'No'}, format='json').status_code, 401)
        self.client.force_authenticate(self.owner)
        Membership.objects.filter(user=self.owner).update(is_active=False)
        self.assertEqual(self.client.patch(self.path, {'description': 'No'}, format='json').status_code, 403)
        self.assertFalse(AuditLog.objects.exists())

    def test_reauthorize_inside_transaction(self):
        from .products import manager

        def revoke(user):
            if mock.call_count == 2:
                Membership.objects.filter(user=user).update(role='WAITER')
            return manager(user)

        with patch('api.products.manager', side_effect=revoke) as mock:
            self.assertEqual(self.client.patch(self.path, {'description': 'No'}, format='json').status_code, 403)
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, '')
        self.assertFalse(AuditLog.objects.exists())

    def test_validation_and_audit_failure_preserve_product(self):
        for body in ({}, {'description': None}, {'description': []}, {'description': 'X', 'name': 'Otro'},
                     {'description': 'X', 'price': '20'}, {'description': 'X', 'category': str(self.foreign.category_id)},
                     {'description': 'X', 'is_active': False}, {'description': 'X', 'restaurant_id': str(self.b.pk)}):
            self.assertEqual(self.client.patch(self.path, body, format='json').status_code, 400)
        for method in ('get', 'put', 'post', 'delete'):
            self.assertEqual(getattr(self.client, method)(self.path).status_code, 405)
        with patch('api.products.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.patch(self.path, {'description': 'No persistir'}, format='json')
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, '')
        self.assertFalse(AuditLog.objects.exists())


class ProductDescriptionMigrationTests(TransactionTestCase):
    def test_forward_reverse_reapply_preserve_products_and_history(self):
        # RF-025: rollback removes descriptions only; all pre-existing business data survives.
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('api', '0011_operationreason')]
        target = [('api', '0012_product_description')]
        try:
            executor.migrate(previous)
            apps = executor.loader.project_state(previous).apps
            restaurant = apps.get_model('api', 'Restaurant').objects.create(name='Anterior')
            category = apps.get_model('api', 'Category').objects.create(restaurant=restaurant, name='Carta', name_key='carta', position=1)
            product = apps.get_model('api', 'Product').objects.create(category=category, name='Sopa', price='18000.25', is_active=True)
            user = apps.get_model('auth', 'User').objects.create(username='migration-owner')
            event = apps.get_model('api', 'AuditLog').objects.create(restaurant=restaurant, actor=user,
                      entity_id=str(product.pk), action='product.created', after={'name': 'Sopa', 'price': '18000.25'})
            product.refresh_from_db()
            original = {field.attname: getattr(product, field.attname) for field in product._meta.concrete_fields}
            for destination in (target, previous, target):
                current_executor = MigrationExecutor(connection)
                current_executor.migrate(destination)
                current = current_executor.loader.project_state(destination).apps
                record = current.get_model('api', 'Product').objects.get(pk=product.pk)
                self.assertEqual({key: getattr(record, key) for key in original}, original)
                self.assertEqual(current.get_model('api', 'AuditLog').objects.get(pk=event.pk).after, event.after)
                if destination == target:
                    self.assertEqual(record.description, '')
                    record.description = 'Descripción de prueba'
                    record.save(update_fields=['description'])
        finally:
            MigrationExecutor(connection).migrate(latest)

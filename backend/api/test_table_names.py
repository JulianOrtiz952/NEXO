from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APITestCase
from .models import AuditLog, Membership, Restaurant, Table, Zone
from .test_table_capacity import fixture


class TableNameTests(APITestCase):
    """DN-31 / RF-015: visible names, immutable identity and scoped edits."""

    def setUp(self):
        self.owner, self.restaurant, self.zone = fixture()
        self.client.force_authenticate(self.owner)
        self.path = f'/api/zones/{self.zone.pk}/tables/'

    def create(self, name='Ventana'):
        response = self.client.post(self.path, {'name': name}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Table.objects.get(pk=response.data['id'])

    def test_create_name_or_number_and_trim(self):
        for name in [' Ventana ', '12', 'OWNER', 'toString', 'x' * 100]:
            table = self.create(name)
            self.assertEqual(table.name, name.strip())
            detail = self.client.get(f'/api/tables/{table.pk}/').data
            self.assertEqual(detail['name'], name.strip())
        self.assertEqual(len(self.client.get(self.path).data), 5)

    def test_create_and_rename_validate_name_without_mutating(self):
        table = self.create()
        for payload in [{}, {'name': ''}, {'name': '  '}, {'name': None}, {'name': 'x' * 101}, {'name': {}}, {'name': True}]:
            self.assertEqual(self.client.post(self.path, payload, format='json').status_code, 400)
            self.assertEqual(self.client.patch(f'/api/tables/{table.pk}/', payload, format='json').status_code, 400)
        table.refresh_from_db()
        self.assertEqual(table.name, 'Ventana')
        self.assertEqual(Table.objects.count(), 1)
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_owner_and_admin_rename_preserve_identity_and_earlier_audit(self):
        table = self.create()
        creation = AuditLog.objects.get(entity_id=str(table.pk))
        initial = creation.after.copy()
        original_date = table.created_at
        admin = get_user_model().objects.create_user(username='name-admin')
        Membership.objects.create(user=admin, restaurant=self.restaurant, role='ADMIN')
        for actor, name in [(self.owner, '12'), (admin, ' Barra lateral ')]:
            self.client.force_authenticate(actor)
            before = table.name
            response = self.client.patch(f'/api/tables/{table.pk}/', {'name': name}, format='json')
            self.assertEqual(response.status_code, 200)
            table.refresh_from_db()
            self.assertEqual(table.name, name.strip())
            self.assertEqual(table.created_at, original_date)
            self.assertEqual(table.zone_id, self.zone.pk)
            self.assertEqual(response.data['id'], str(table.pk))
            event = AuditLog.objects.latest('pk')
            self.assertEqual((event.action, event.actor_id, event.restaurant_id, event.entity_id),
                             ('table.name_changed', actor.pk, self.restaurant.pk, str(table.pk)))
            self.assertEqual(event.before['name'], before)
            self.assertEqual(event.after['name'], name.strip())
        creation.refresh_from_db()
        self.assertEqual(creation.after, initial)
        self.assertEqual(Table.objects.count(), 1)
        count = AuditLog.objects.count()
        self.assertEqual(self.client.patch(f'/api/tables/{table.pk}/', {'name': table.name}, format='json').status_code, 200)
        self.assertEqual(AuditLog.objects.count(), count)
        rows = self.client.get('/api/history/?action=table.name_changed').data
        self.assertEqual(rows['count'], 2)
        self.assertEqual(rows['results'][0]['target'], 'Barra lateral')
        self.assertEqual(rows['results'][0]['action_type'], 'Cambio de nombre')

    def test_other_tenants_and_roles_cannot_rename(self):
        table = self.create()
        foreign = get_user_model().objects.create_user(username='name-foreign')
        restaurant = Restaurant.objects.create(name='Other', initial_owner=foreign)
        Membership.objects.create(user=foreign, restaurant=restaurant, role='OWNER')
        zone = Zone.objects.create(restaurant=restaurant, name='Other', name_key='other')
        other = Table.objects.create(zone=zone, name='Ajena')
        self.assertEqual(self.client.patch(f'/api/tables/{other.pk}/', {'name': 'Intrusión'}, format='json').status_code, 404)
        self.client.force_authenticate(foreign)
        self.assertEqual(self.client.patch(f'/api/tables/{table.pk}/', {'name': 'Intrusión'}, format='json').status_code, 404)
        actors = [get_user_model().objects.create_user(username='name-platform', is_superuser=True)]
        for role in ['WAITER', 'CASHIER', 'KITCHEN']:
            user = get_user_model().objects.create_user(username=f'name-{role}')
            Membership.objects.create(user=user, role=role, restaurant=self.restaurant)
            actors.append(user)
        for actor in actors:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.patch(f'/api/tables/{table.pk}/', {'name': 'Intrusión'}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(f'/api/tables/{table.pk}/', {'name': 'Intrusión'}, format='json').status_code, 401)
        table.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((table.name, other.name), ('Ventana', 'Ajena'))
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_cannot_change_identity_zone_or_privileges_with_name(self):
        table = self.create()
        for field, value in [('zone', str(self.zone.pk)), ('restaurant', str(self.restaurant.pk)), ('id', str(table.pk)), ('role', 'OWNER'), ('created_at', '2026-01-01')]:
            payload = {'name': 'Intento', field: value}
            self.assertEqual(self.client.patch(f'/api/tables/{table.pk}/', payload, format='json').status_code, 400)
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_rename_audit_failure_rolls_back_and_inactive_membership_denied(self):
        table = self.create()
        with patch('api.tables.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.patch(f'/api/tables/{table.pk}/', {'name': 'No persistir'}, format='json')
        table.refresh_from_db()
        self.assertEqual(table.name, 'Ventana')
        Membership.objects.filter(user=self.owner).update(is_active=False)
        self.assertEqual(self.client.patch(f'/api/tables/{table.pk}/', {'name': 'No persistir'}, format='json').status_code, 403)
        self.assertEqual(AuditLog.objects.count(), 1)


class TableNameMigrationTests(TransactionTestCase):
    def test_backfill_per_zone_and_reverse_preserve_ids_dates_and_history(self):
        # RF-015: the approved migration changes labels only, never past events.
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('api', '0005_table')])
            old = executor.loader.project_state([('api', '0005_table')]).apps
            OldTable = old.get_model('api', 'Table')
            owner, restaurant, zone = fixture()
            second = Zone.objects.create(restaurant=restaurant, name='Terraza', name_key='terraza')
            other_restaurant = Restaurant.objects.create(name='Other')
            third = Zone.objects.create(restaurant=other_restaurant, name='Salón', name_key='salón')
            for target, amount in [(zone, 2), (second, 1), (third, 2)]:
                for _ in range(amount):
                    OldTable.objects.create(zone_id=target.pk)
            originals = list(OldTable.objects.order_by('zone_id', 'created_at', 'pk').values('id', 'zone_id', 'created_at'))
            event = AuditLog.objects.create(restaurant=restaurant, actor=owner, action='table.created', entity_id=str(originals[0]['id']), after={'zone_name': 'Nombre histórico'})
            snapshot = event.after.copy()
            MigrationExecutor(connection).migrate([('api', '0006_table_name')])
            self.assertEqual(list(Table.objects.order_by('zone_id', 'created_at', 'pk').values('id', 'zone_id', 'created_at')), originals)
            for target, expected in [(zone, ['Mesa 1', 'Mesa 2']), (second, ['Mesa 1']), (third, ['Mesa 1', 'Mesa 2'])]:
                self.assertEqual(list(Table.objects.filter(zone=target).order_by('created_at', 'pk').values_list('name', flat=True)), expected)
            event.refresh_from_db()
            self.assertEqual(event.after, snapshot)
            self.assertEqual(AuditLog.objects.count(), 1)
            MigrationExecutor(connection).migrate([('api', '0005_table')])
            self.assertEqual(list(OldTable.objects.order_by('zone_id', 'created_at', 'pk').values('id', 'zone_id', 'created_at')), originals)
            event.refresh_from_db()
            self.assertEqual(event.after, snapshot)
        finally:
            MigrationExecutor(connection).migrate(latest)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APITestCase, APIClient
from .models import AuditLog, Table, Zone, Restaurant, Membership
from django.contrib.auth import get_user_model
from .test_table_capacity import fixture


class TableUniquenessTests(APITestCase):
    """DN-32 / RF-016: zone-local canonical names, immutable rejected changes."""

    def setUp(self):
        self.owner, self.restaurant, self.zone = fixture()
        self.client.force_authenticate(self.owner)
        self.path = f'/api/zones/{self.zone.pk}/tables/'

    def create(self, name, zone=None):
        response = self.client.post(f'/api/zones/{(zone or self.zone).pk}/tables/', {'name': name}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Table.objects.get(pk=response.data['id'])

    def test_create_duplicate_case_spaces_and_unicode_is_rejected(self):
        self.create('Ventana')
        self.create('Straße')
        before = list(Table.objects.order_by('pk').values())
        events = list(AuditLog.objects.order_by('pk').values())
        for name in ['Ventana', ' VENTANA ', 'ventana', 'STRASSE']:
            response = self.client.post(self.path, {'name': name}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertIn('esta zona', str(response.data))
        self.assertEqual(list(Table.objects.order_by('pk').values()), before)
        self.assertEqual(list(AuditLog.objects.order_by('pk').values()), events)

    def test_rename_rejects_collision_preserving_all_rows_and_history(self):
        self.create('Ventana')
        target = self.create('12')
        before = list(Table.objects.order_by('pk').values())
        events = list(AuditLog.objects.order_by('pk').values())
        response = self.client.patch(f'/api/tables/{target.pk}/', {'name': ' vENTANA '}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(Table.objects.order_by('pk').values()), before)
        self.assertEqual(list(AuditLog.objects.order_by('pk').values()), events)

    def test_same_table_can_keep_or_change_case_of_its_own_name(self):
        target = self.create('Ventana')
        self.assertEqual(self.client.patch(f'/api/tables/{target.pk}/', {'name': 'Ventana'}, format='json').status_code, 200)
        self.assertEqual(AuditLog.objects.count(), 1)
        self.assertEqual(self.client.patch(f'/api/tables/{target.pk}/', {'name': 'VENTANA'}, format='json').status_code, 200)
        target.refresh_from_db()
        self.assertEqual((target.name, target.name_key), ('VENTANA', 'ventana'))
        self.assertEqual(AuditLog.objects.filter(action='table.name_changed').count(), 1)

    def test_same_name_allowed_in_other_zones_and_tenants_without_exposure(self):
        local = self.create('Ventana')
        second = Zone.objects.create(restaurant=self.restaurant, name='Terraza', name_key='terraza')
        other = self.create('VENTANA', second)
        foreign = get_user_model().objects.create_user(username='unique-foreign')
        restaurant = Restaurant.objects.create(name='Foreign', initial_owner=foreign)
        Membership.objects.create(user=foreign, restaurant=restaurant, role='OWNER')
        zone = Zone.objects.create(restaurant=restaurant, name='Salón', name_key='salón')
        self.client.force_authenticate(foreign)
        foreign_table = self.create('ventana', zone)
        self.assertEqual(self.client.patch(f'/api/tables/{local.pk}/', {'name': 'Ventana'}, format='json').status_code, 404)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(f'/api/tables/{foreign_table.pk}/', {'name': 'Ventana'}, format='json').status_code, 404)
        self.assertEqual(self.client.get(f'/api/zones/{zone.pk}/tables/').status_code, 404)
        self.assertEqual(len({local.pk, other.pk, foreign_table.pk}), 3)

    def test_database_constraint_and_partial_save_keep_key_in_sync(self):
        target = self.create('Ventana')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Table.objects.create(zone=self.zone, name=' VENTANA ')
        target.name = 'Barra'
        target.save(update_fields=['name'])
        target.refresh_from_db()
        self.assertEqual(target.name_key, 'barra')
        self.create('Ventana')
        long_name = 'ΐ' * 100
        expanded = self.create(long_name)
        self.assertEqual(expanded.name_key, long_name.casefold())
        self.assertEqual(len(expanded.name_key), 300)


class TableUniqueMigrationTests(TransactionTestCase):
    def test_collision_aborts_then_forward_reverse_preserve_names_and_history(self):
        # RF-016: duplicate data requires a human decision; no automatic renaming.
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('api', '0006_table_name')])
            old = executor.loader.project_state([('api', '0006_table_name')]).apps
            OldTable = old.get_model('api', 'Table')
            owner, restaurant, zone = fixture()
            first = OldTable.objects.create(zone_id=zone.pk, name='Ventana')
            second = OldTable.objects.create(zone_id=zone.pk, name=' vENTANA ')
            event = AuditLog.objects.create(restaurant=restaurant, actor=owner, action='table.created', entity_id=str(first.pk), after={'name': 'Ventana'})
            before = list(OldTable.objects.order_by('pk').values())
            with self.assertRaisesRegex(RuntimeError, 'duplicados'):
                MigrationExecutor(connection).migrate([('api', '0007_table_unique_name')])
            self.assertEqual(list(OldTable.objects.order_by('pk').values()), before)
            self.assertNotIn(('api', '0007_table_unique_name'), MigrationExecutor(connection).loader.applied_migrations)
            OldTable.objects.filter(pk=second.pk).update(name='Barra')
            another_zone = Zone.objects.create(restaurant=restaurant, name='Terraza', name_key='terraza')
            OldTable.objects.create(zone_id=another_zone.pk, name='VENTANA')
            before = list(OldTable.objects.order_by('pk').values())
            MigrationExecutor(connection).migrate([('api', '0007_table_unique_name')])
            self.assertEqual(list(Table.objects.order_by('pk').values('id', 'name', 'zone_id', 'created_at')), before)
            self.assertEqual(Table.objects.get(pk=first.pk).name_key, 'ventana')
            MigrationExecutor(connection).migrate([('api', '0006_table_name')])
            self.assertEqual(list(OldTable.objects.order_by('pk').values()), before)
            event.refresh_from_db()
            self.assertEqual(event.after, {'name': 'Ventana'})
            self.assertEqual(AuditLog.objects.count(), 1)
        finally:
            MigrationExecutor(connection).migrate(latest)


class TableUniqueConcurrencyTests(TransactionTestCase):
    def race(self, rename=False):
        # RF-016, RNF-019: separate requests/connections race for one canonical key.
        owner, restaurant, zone = fixture()
        targets = [Table.objects.create(zone=zone, name=f'Inicial {index}') for index in range(2)] if rename else []
        barrier = Barrier(2)

        def change(index):
            try:
                actor = get_user_model().objects.get(pk=owner.pk)
                client = APIClient()
                client.force_authenticate(actor)
                barrier.wait(timeout=10)
                payload = {'name': 'Ventana' if index == 0 else ' VENTANA '}
                if rename:
                    return client.patch(f'/api/tables/{targets[index].pk}/', payload, format='json').status_code
                return client.post(f'/api/zones/{zone.pk}/tables/', payload, format='json').status_code
            finally:
                connections.close_all()

        success = 200 if rename else 201
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(change, index) for index in range(2)]
            outcomes = [future.result(timeout=20) for future in futures]
        self.assertTrue(all(status in [success, 400, 409] for status in outcomes), outcomes)
        self.assertLessEqual(outcomes.count(success), 1)
        client = APIClient()
        client.force_authenticate(owner)
        if success not in outcomes:
            retry = client.patch(f'/api/tables/{targets[0].pk}/', {'name': 'Ventana'}, format='json') if rename else client.post(f'/api/zones/{zone.pk}/tables/', {'name': 'Ventana'}, format='json')
            self.assertEqual(retry.status_code, success)
        self.assertEqual(Table.objects.filter(zone=zone, name_key='ventana').count(), 1)
        self.assertEqual(Table.objects.filter(zone=zone).count(), 2 if rename else 1)
        self.assertEqual(AuditLog.objects.filter(restaurant=restaurant).count(), 1)

    def test_concurrent_duplicate_creation(self):
        self.race()

    def test_concurrent_duplicate_rename(self):
        self.race(rename=True)

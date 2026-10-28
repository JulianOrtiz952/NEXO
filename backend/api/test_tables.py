from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from rest_framework.test import APITestCase
from .models import AuditLog, Membership, Restaurant, Table, Zone


class TableTests(APITestCase):
    """DN-29 / RF-013: creation, membership, isolation and atomic audit."""

    def setUp(self):
        self.owner = self.member('owner', 'OWNER')
        self.restaurant = self.owner.membership.restaurant
        self.admin = self.member('admin', 'ADMIN', self.restaurant)
        self.foreign = self.member('foreign', 'OWNER')
        self.zone = Zone.objects.create(restaurant=self.restaurant, name='Salón', name_key='salón')
        self.other_zone = Zone.objects.create(restaurant=self.restaurant, name='Terraza', name_key='terraza')
        self.foreign_zone = Zone.objects.create(restaurant=self.foreign.membership.restaurant, name='Salón', name_key='salón')
        self.client.force_authenticate(self.owner)

    def member(self, name, role, restaurant=None):
        user = get_user_model().objects.create_user(username=name, email=f'{name}@example.com')
        restaurant = restaurant or Restaurant.objects.create(name=name, initial_owner=user)
        Membership.objects.create(user=user, restaurant=restaurant, role=role)
        return user

    def path(self, zone=None):
        return f'/api/zones/{(zone or self.zone).pk}/tables/'

    def create(self, zone=None):
        response = self.client.post(self.path(zone), {'name': 'Mesa'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_managers_create_and_consult_only_selected_zone_with_atomic_audit(self):
        for actor in [self.owner, self.admin]:
            self.client.force_authenticate(actor)
            table_id = self.create()
            table = Table.objects.get(pk=table_id)
            self.assertEqual(table.zone_id, self.zone.pk)
            event = AuditLog.objects.get(entity_id=table_id)
            self.assertEqual(event.action, 'table.created')
            self.assertEqual(event.actor_id, actor.pk)
            self.assertEqual(event.restaurant_id, self.restaurant.pk)
            self.assertEqual(event.before, {})
            self.assertEqual(event.after, {'name': 'Mesa', 'zone_id': str(self.zone.pk), 'zone_name': 'Salón'})
            self.assertIn(table_id, [row['id'] for row in self.client.get(self.path()).data])
            self.assertEqual(self.client.get(self.path(self.other_zone)).data, [])
            detail = self.client.get(f'/api/tables/{table_id}/').data
            self.assertEqual(detail['zone'], str(self.zone.pk))
            self.assertEqual(detail['created_at'], table.created_at)
        self.assertEqual(Table.objects.count(), 2)

    def test_cross_tenant_enumeration_and_writes_cannot_expose_foreign_resources(self):
        table_id = self.create()
        self.client.force_authenticate(self.foreign)
        foreign_id = self.create(self.foreign_zone)
        for actor, own_zone, own_id, other_zone, other_id in [
            (self.owner, self.zone, table_id, self.foreign_zone, foreign_id),
            (self.foreign, self.foreign_zone, foreign_id, self.zone, table_id),
        ]:
            self.client.force_authenticate(actor)
            response = self.client.get(self.path(own_zone), {'restaurant_id': str(other_zone.restaurant_id), 'zone': str(other_zone.pk)})
            self.assertEqual([row['id'] for row in response.data], [own_id])
            self.assertEqual(self.client.get(self.path(other_zone)).status_code, 404)
            self.assertEqual(self.client.post(self.path(other_zone), {'name': 'Mesa'}, format='json').status_code, 404)
            self.assertEqual(self.client.get(f'/api/tables/{other_id}/').status_code, 404)
        self.assertEqual(Table.objects.count(), 2)
        self.assertEqual(AuditLog.objects.count(), 2)

    def test_permissions_anonymous_global_and_operational_roles(self):
        table_id = self.create()
        platform = get_user_model().objects.create_user(username='platform', is_superuser=True)
        actors = [platform] + [self.member(role, role, self.restaurant) for role in ['CASHIER', 'WAITER', 'KITCHEN']]
        for actor in actors:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get(self.path()).status_code, 403)
            self.assertEqual(self.client.post(self.path(), {'name': 'Mesa'}, format='json').status_code, 403)
            self.assertEqual(self.client.get(f'/api/tables/{table_id}/').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.path()).status_code, 401)
        self.assertEqual(self.client.post(self.path(), {'name': 'Mesa'}, format='json').status_code, 401)

    def test_inactive_membership_user_and_restaurant_cannot_manage(self):
        for model in [self.admin, self.admin.membership, self.restaurant]:
            model.is_active = False
            model.save()
            self.client.force_authenticate(self.admin)
            self.assertEqual(self.client.get(self.path()).status_code, 403)
            self.assertEqual(self.client.post(self.path(), {'name': 'Mesa'}, format='json').status_code, 403)
            model.is_active = True
            model.save()
        self.assertEqual(Table.objects.count(), 0)

    def test_zone_inactivation_preserves_tables_and_blocks_new_creation(self):
        table_id = self.create()
        self.assertEqual(self.client.patch(f'/api/zones/{self.zone.pk}/', {'is_active': False}, format='json').status_code, 200)
        response = self.client.post(self.path(), {'name': 'Mesa'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('inactiva', str(response.data))
        self.assertEqual([row['id'] for row in self.client.get(self.path()).data], [table_id])
        self.assertEqual(self.client.get(f'/api/tables/{table_id}/').status_code, 200)
        self.assertEqual(self.client.patch(f'/api/zones/{self.zone.pk}/', {'is_active': True}, format='json').status_code, 200)
        self.create()
        self.assertEqual(Table.objects.count(), 2)

    def test_reject_unknown_zones_extra_fields_and_unsupported_mutations(self):
        for data in [{'zone': str(self.foreign_zone.pk)}, {'restaurant': str(self.restaurant.pk)}, {'name': 'Mesa', 'role': 'OWNER'}, {'id': str(uuid4())}, {'is_active': False}]:
            self.assertEqual(self.client.post(self.path(), data, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/zones/{uuid4()}/tables/', {'name': 'Mesa'}, format='json').status_code, 404)
        table_id = self.create()
        for method in ['post', 'put', 'delete']:
            self.assertEqual(getattr(self.client, method)(f'/api/tables/{table_id}/', {'name': 'Mesa'}, format='json').status_code, 405)
        self.assertEqual(Table.objects.count(), 1)
        with self.assertRaises(ProtectedError):
            self.zone.delete()

    def test_audit_failure_rolls_back_table(self):
        with patch('api.tables.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.path(), {'name': 'Mesa'}, format='json')
        self.assertEqual(Table.objects.count(), 0)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_history_classifies_table_events_and_keeps_snapshot_and_tenant(self):
        table_id = self.create()
        self.zone.name = 'Salón renombrado'
        self.zone.save()
        self.client.force_authenticate(self.foreign)
        self.create(self.foreign_zone)
        self.client.force_authenticate(self.owner)
        history = self.client.get('/api/history/?action=table.created').data
        self.assertEqual(history['count'], 1)
        row = history['results'][0]
        self.assertEqual((row['category'], row['action_type']), ('Mesas', 'Creación'))
        self.assertEqual(row['target'], 'Mesa')
        self.assertEqual(row['after'], {'name': 'Mesa', 'zone_name': 'Salón'})
        self.assertEqual(AuditLog.objects.get(entity_id=table_id).after['zone_id'], str(self.zone.pk))

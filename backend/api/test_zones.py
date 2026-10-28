from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APITestCase
from .models import AuditLog, Membership, Restaurant, Zone


class ZoneTests(APITestCase):
    """DN-28 / RF-012, RNF-004/007/019: tenant isolation and atomic management."""

    def setUp(self):
        self.owner = self.member('owner', 'OWNER')
        self.restaurant = self.owner.membership.restaurant
        self.admin = self.member('admin', 'ADMIN', self.restaurant)
        self.foreign = self.member('foreign', 'OWNER')
        self.platform = get_user_model().objects.create_user(username='platform', is_superuser=True)
        self.client.force_authenticate(self.owner)

    def member(self, name, role, restaurant=None):
        user = get_user_model().objects.create_user(username=name, email=f'{name}@example.com')
        restaurant = restaurant or Restaurant.objects.create(name=name, initial_owner=user)
        Membership.objects.create(user=user, role=role, restaurant=restaurant)
        return user

    def create(self, name='Terraza'):
        response = self.client.post('/api/zones/', {'name': name}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_lifecycle_persistence_and_audit(self):
        for actor in [self.owner, self.admin]:
            self.client.force_authenticate(actor)
            zone_id = self.create(actor.username)
            path = f'/api/zones/{zone_id}/'
            for payload in [{'name': f'{actor.username} editado'}, {'is_active': False}, {'is_active': True}]:
                self.assertEqual(self.client.patch(path, payload, format='json').status_code, 200)
            zone = Zone.objects.get(pk=zone_id)
            self.assertTrue(zone.is_active)
            self.assertEqual(zone.name, f'{actor.username} editado')
            events = AuditLog.objects.filter(entity_id=zone_id).order_by('pk')
            self.assertEqual(list(events.values_list('action', flat=True)), ['zone.created', 'zone.updated', 'zone.status_changed', 'zone.status_changed'])
            self.assertTrue(all(event.actor_id == actor.pk and event.restaurant_id == self.restaurant.pk for event in events))
            self.assertEqual(events[2].before, {'name': zone.name, 'is_active': True})
            self.assertEqual(events[2].after, {'name': zone.name, 'is_active': False})
            self.assertEqual(self.client.get(path).data['name'], zone.name)
            count = events.count()
            self.assertEqual(self.client.patch(path, {'name': zone.name}, format='json').status_code, 200)
            self.assertEqual(events.count(), count)
            self.assertEqual(self.client.delete(path).status_code, 405)

    def test_cross_tenant_reads_writes_lists_and_name_reuse(self):
        local_id = self.create()
        self.client.force_authenticate(self.foreign)
        foreign_id = self.create()
        for actor, own_id, other_id in [(self.owner, local_id, foreign_id), (self.foreign, foreign_id, local_id)]:
            self.client.force_authenticate(actor)
            self.assertEqual([row['id'] for row in self.client.get('/api/zones/', {'restaurant_id': str(self.restaurant.pk)}).data], [own_id])
            self.assertEqual(self.client.get(f'/api/zones/{other_id}/').status_code, 404)
            self.assertEqual(self.client.patch(f'/api/zones/{other_id}/', {'name': 'Intrusión', 'is_active': False}, format='json').status_code, 404)
        self.assertEqual(Zone.objects.filter(name='Terraza', is_active=True).count(), 2)

    def test_forbidden_roles_and_inactive_access(self):
        zone_id = self.create()
        for actor in [self.member('cashier', 'CASHIER', self.restaurant), self.member('waiter', 'WAITER', self.restaurant), self.member('kitchen', 'KITCHEN', self.restaurant), self.platform]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get('/api/zones/').status_code, 403)
            self.assertEqual(self.client.post('/api/zones/', {'name': 'Forbidden'}).status_code, 403)
            self.assertEqual(self.client.patch(f'/api/zones/{zone_id}/', {'is_active': False}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/zones/').status_code, 401)
        self.restaurant.is_active = False
        self.restaurant.save()
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/zones/').status_code, 403)

    def test_validation_duplicates_and_database_constraint(self):
        zone_id = self.create('  Terraza  ')
        path = f'/api/zones/{zone_id}/'
        for payload in [{}, {'name': ''}, {'name': '  '}, {'name': 'x' * 101}, {'name': 'Other', 'restaurant': str(self.restaurant.pk)}, {'name': 'Other', 'is_active': False}]:
            self.assertEqual(self.client.post('/api/zones/', payload, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/zones/', {'name': ' tERRAZA '}).status_code, 400)
        self.assertEqual(self.client.patch(path, {'is_active': False}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/zones/', {'name': 'Terraza'}).status_code, 400)
        second = self.create('Salón')
        self.assertEqual(self.client.patch(f'/api/zones/{second}/', {'name': 'terraza'}, format='json').status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Zone.objects.create(restaurant=self.restaurant, name='TERRAZA', name_key='terraza')

    def test_audit_failure_rolls_back_creation_and_update(self):
        zone_id = self.create()
        with patch('api.zones.AuditLog.objects.create', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/zones/', {'name': 'No persistir'}, format='json')
            with self.assertRaises(RuntimeError):
                self.client.patch(f'/api/zones/{zone_id}/', {'name': 'No persistir', 'is_active': False}, format='json')
        self.assertEqual(Zone.objects.count(), 1)
        self.assertEqual(Zone.objects.get().name, 'Terraza')
        self.assertTrue(Zone.objects.get().is_active)

    def test_history_classification_filters_pagination_and_isolation(self):
        zone_id = self.create()
        for index in range(24):
            AuditLog.objects.create(actor=self.owner, restaurant=self.restaurant, action='zone.updated', entity_id=zone_id,
                                    before={'name': 'Anterior'}, after={'name': f'Zona {index}', 'password': 'secret'})
        AuditLog.objects.create(actor=self.foreign, restaurant=self.foreign.membership.restaurant, action='zone.updated', entity_id='foreign', after={'name': 'Ajena'})
        AuditLog.objects.create(actor=self.owner, restaurant=self.restaurant, action='user.created', entity_id=str(self.owner.pk))
        first = self.client.get('/api/history/?action=zone.updated').data
        self.assertEqual(first['count'], 24)
        self.assertEqual(len(first['results']), 20)
        self.assertTrue(first['next'])
        self.assertTrue(all(row['category'] == 'Zonas' and row['action_type'] == 'Edición' for row in first['results']))
        self.assertNotIn('secret', str(first))
        second = self.client.get('/api/history/?action=zone.updated&page=2').data
        self.assertEqual(len(second['results']), 4)
        self.assertEqual(self.client.get('/api/history/?action=invalid').status_code, 400)
        self.client.force_authenticate(self.foreign)
        self.assertEqual(self.client.get('/api/history/?action=zone.updated').data['count'], 1)
        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.get('/api/history/').data['count'], 0)
        self.assertEqual(self.client.get('/api/history/?action=zone.updated').status_code, 400)

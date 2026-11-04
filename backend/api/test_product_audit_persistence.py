from rest_framework.test import APITestCase

from . import test_product_editing
from .models import AuditLog, Product, Table


class ProductAuditPersistenceTests(APITestCase):
    # RF-234: exercise real lifecycle endpoints and compare complete persisted events.
    setUp = test_product_editing.ProductEditingTests.setUp
    member = test_product_editing.ProductEditingTests.member

    def test_product_deactivation_retains_all_previous_events_and_identity(self):
        response = self.client.post('/api/products/', {'name': 'Jugo', 'description': 'Fruta', 'price': '18000',
                   'category': str(self.second.pk), 'is_active': True}, format='json')
        self.assertEqual(response.status_code, 201)
        product_id = response.data['id']
        path = f'/api/products/{product_id}/'
        self.assertEqual(self.client.patch(path, {'name': 'Jugo fresco'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(path + 'price/', {'price': '20000.85'}, format='json').status_code, 200)
        original = list(AuditLog.objects.filter(entity_id=product_id).order_by('pk').values())
        for active in (False, True, False):
            self.assertEqual(self.client.patch(path + 'status/', {'is_active': active}, format='json').status_code, 200)
            for event in original:
                self.assertEqual(AuditLog.objects.values().get(pk=event['id']), event)
            self.assertTrue(Product.objects.filter(pk=product_id).exists())
        rows = self.client.get('/api/history/').data['results']
        original_ids = {event['id'] for event in original}
        returned = [row for row in rows if row['id'] in original_ids]
        self.assertEqual(len(returned), 3)
        self.assertEqual({row['target'] for row in returned}, {'Jugo', 'Jugo fresco'})
        self.assertTrue(all(row['actor'] == self.owner.email and row['restaurant'] == 'A' for row in returned))
        self.client.force_authenticate(self.other)
        foreign = self.client.get('/api/history/', {'restaurant_id': str(self.a.pk), 'entity_id': product_id})
        self.assertEqual(foreign.data['results'], [])

    def test_deactivating_actor_keeps_product_events_identifiable(self):
        self.admin.email = 'admin@audit.test'
        self.admin.save(update_fields=['email'])
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(self.path, {'name': 'Sopa por Admin'}, format='json').status_code, 200)
        event = AuditLog.objects.get(action='product.updated')
        snapshot = AuditLog.objects.values().get(pk=event.pk)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(f'/api/users/{self.admin.pk}/status/', {'is_active': False}, format='json').status_code, 200)
        self.assertEqual(AuditLog.objects.values().get(pk=event.pk), snapshot)
        row = self.client.get('/api/history/?action=product.updated').data['results'][0]
        self.assertEqual((row['actor'], row['target']), ('admin@audit.test', 'Sopa por Admin'))

    def test_zone_deactivation_keeps_table_history_without_claiming_table_status(self):
        # RF-234 partial: Table has no individual active flag yet. Parent-zone coverage is distinct.
        zone = self.client.post('/api/zones/', {'name': 'Salón'}, format='json')
        self.assertEqual(zone.status_code, 201)
        zone_id = zone.data['id']
        table = self.client.post(f'/api/zones/{zone_id}/tables/', {'name': 'Ventana'}, format='json')
        self.assertEqual(table.status_code, 201)
        event = AuditLog.objects.get(action='table.created')
        snapshot = AuditLog.objects.values().get(pk=event.pk)
        self.assertEqual(self.client.patch(f'/api/zones/{zone_id}/', {'is_active': False}, format='json').status_code, 200)
        self.assertEqual(AuditLog.objects.values().get(pk=event.pk), snapshot)
        self.assertTrue(Table.objects.filter(pk=table.data['id']).exists())
        row = self.client.get('/api/history/?action=table.created').data['results'][0]
        self.assertEqual((row['target'], row['after']['zone_name']), ('Ventana', 'Salón'))

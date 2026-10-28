from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from rest_framework.test import APITestCase, APIClient
from .models import AuditLog, Membership, Restaurant, Table, Zone


def fixture():
    owner = get_user_model().objects.create_user(username='capacity-owner')
    restaurant = Restaurant.objects.create(name='Capacity', initial_owner=owner)
    Membership.objects.create(user=owner, restaurant=restaurant, role='OWNER')
    zone = Zone.objects.create(restaurant=restaurant, name='Salón', name_key='salón')
    return owner, restaurant, zone


class TableCapacityTests(APITestCase):
    """DN-30 / RF-014: fixed 0–100 range with tenant-scoped counts."""

    def setUp(self):
        self.owner, self.restaurant, self.zone = fixture()
        self.client.force_authenticate(self.owner)
        self.path = f'/api/zones/{self.zone.pk}/tables/'

    def test_empty_zone_and_hundredth_creation_then_reject_without_changes(self):
        self.assertEqual(self.client.get(self.path).data, [])
        first = self.client.post(self.path, {'name': 'Mesa'}, format='json')
        self.assertEqual(first.status_code, 201)
        Table.objects.bulk_create([Table(zone=self.zone, name='Mesa') for _ in range(98)])
        hundredth = self.client.post(self.path, {'name': 'Mesa'}, format='json')
        self.assertEqual(hundredth.status_code, 201)
        ids = set(Table.objects.values_list('pk', flat=True))
        self.assertEqual(len(ids), 100)
        events = AuditLog.objects.count()
        response = self.client.post(self.path, {'name': 'Mesa'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('100 mesas', str(response.data))
        self.assertEqual(set(Table.objects.values_list('pk', flat=True)), ids)
        self.assertEqual(AuditLog.objects.count(), events)
        self.assertEqual(len(self.client.get(self.path).data), 100)

    def test_capacity_is_per_zone_and_foreign_counts_never_grant_access(self):
        Table.objects.bulk_create([Table(zone=self.zone, name='Mesa') for _ in range(100)])
        other_zone = Zone.objects.create(restaurant=self.restaurant, name='Terraza', name_key='terraza')
        self.assertEqual(self.client.post(f'/api/zones/{other_zone.pk}/tables/', {'name': 'Mesa'}, format='json').status_code, 201)
        foreign = get_user_model().objects.create_user(username='capacity-foreign')
        restaurant = Restaurant.objects.create(name='Foreign', initial_owner=foreign)
        Membership.objects.create(user=foreign, restaurant=restaurant, role='OWNER')
        zone = Zone.objects.create(restaurant=restaurant, name='Salón', name_key='salón')
        Table.objects.bulk_create([Table(zone=zone, name='Mesa') for _ in range(100)])
        self.assertEqual(self.client.post(f'/api/zones/{zone.pk}/tables/', {'name': 'Mesa'}, format='json').status_code, 404)
        self.assertEqual(self.client.get(f'/api/zones/{zone.pk}/tables/').status_code, 404)
        self.assertEqual(Table.objects.filter(zone=zone).count(), 100)
        self.client.force_authenticate(foreign)
        self.assertEqual(self.client.post(self.path, {'name': 'Mesa'}, format='json').status_code, 404)
        self.assertEqual(self.client.post(f'/api/zones/{zone.pk}/tables/', {'name': 'Mesa'}, format='json').status_code, 400)


class TableCapacityConcurrencyTests(TransactionTestCase):
    def test_two_simultaneous_creations_cannot_exceed_hundred(self):
        # RF-014, RNF-019/027: last slot is checked inside the creation transaction.
        owner, restaurant, zone = fixture()
        Table.objects.bulk_create([Table(zone=zone, name='Mesa') for _ in range(99)])
        barrier = Barrier(2)
        path = f'/api/zones/{zone.pk}/tables/'

        def create():
            try:
                actor = get_user_model().objects.get(pk=owner.pk)
                client = APIClient()
                client.force_authenticate(actor)
                barrier.wait(timeout=10)
                return client.post(path, {'name': 'Mesa'}, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create) for _ in range(2)]
            outcomes = [future.result(timeout=20) for future in futures]
        self.assertTrue(all(status in [201, 400, 409] for status in outcomes), outcomes)
        self.assertLessEqual(outcomes.count(201), 1, outcomes)
        client = APIClient()
        client.force_authenticate(owner)
        retry = client.post(path, {'name': 'Mesa'}, format='json')
        self.assertEqual(retry.status_code, 400 if 201 in outcomes else 201)
        self.assertEqual(Table.objects.filter(zone=zone).count(), 100)
        self.assertEqual(AuditLog.objects.filter(action='table.created', restaurant=restaurant).count(), 1)
        self.assertEqual(client.post(path, {'name': 'Mesa'}, format='json').status_code, 400)

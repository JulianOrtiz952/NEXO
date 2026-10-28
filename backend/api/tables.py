from django.db import OperationalError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .authentication import membership_for
from .models import AuditLog, Restaurant, Table, Zone


# RF-014: fixed product limit, identical for every zone and restaurant.
MAX_TABLES_PER_ZONE = 100


def manager(user):
    membership = membership_for(user)
    if membership.role not in ['OWNER', 'ADMIN']:
        raise PermissionDenied('No tienes permiso para gestionar mesas.')
    return membership


def output(table):
    return {'id': str(table.pk), 'zone': str(table.zone_id), 'zone_name': table.zone.name, 'created_at': table.created_at}


@api_view(['GET', 'POST'])
def zone_tables(request, zone_id):
    try:
        membership = manager(request.user)
        if request.method == 'GET':
            zone = get_object_or_404(Zone, pk=zone_id, restaurant=membership.restaurant)
            return Response([output(table) for table in Table.objects.filter(zone=zone).select_related('zone').order_by('created_at', 'pk')])
        if request.data:
            raise ValidationError({'detail': 'Selecciona la zona y crea una mesa sin campos adicionales.'})
        # RF-013, RNF-004/007/019: authorize again after acquiring the tenant lock.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            zone = get_object_or_404(Zone, pk=zone_id, restaurant=membership.restaurant)
            if not zone.is_active:
                raise ValidationError({'detail': 'La zona está inactiva. Actívala desde Zonas antes de crear mesas.'})
            # RF-014: count under the same lock as creation, never from client data.
            if Table.objects.filter(zone=zone).count() >= MAX_TABLES_PER_ZONE:
                raise ValidationError({'detail': 'Esta zona ya tiene el máximo de 100 mesas. Selecciona otra zona para crear una nueva mesa.'})
            table = Table.objects.create(zone=zone)
            AuditLog.objects.create(restaurant=membership.restaurant, actor=request.user, action='table.created',
                                    entity_id=str(table.pk), after={'zone_id': str(zone.pk), 'zone_name': zone.name})
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return Response({'detail': 'Otra operación está actualizando el restaurante. Intenta de nuevo.'}, status=409)
    return Response(output(table), status=201)


@api_view(['GET'])
def table_details(request, table_id):
    membership = manager(request.user)
    table = get_object_or_404(Table.objects.select_related('zone'), pk=table_id, zone__restaurant=membership.restaurant)
    return Response(output(table))

from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .authentication import membership_for
from .models import AuditLog, Restaurant, Zone


def manager(user):
    membership = membership_for(user)
    if membership.role not in ['OWNER', 'ADMIN']:
        raise PermissionDenied('No tienes permiso para gestionar zonas.')
    return membership


class ZoneInput(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    is_active = serializers.BooleanField(required=False)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Solo puedes modificar el nombre y el estado de la zona.')
        if 'name' in data and len(data['name'].casefold()) > 100:
            raise serializers.ValidationError('El nombre de la zona es demasiado largo.')
        return data


def snapshot(zone):
    return {'name': zone.name, 'is_active': zone.is_active}


def output(zone):
    return {'id': str(zone.pk), **snapshot(zone)}


@api_view(['GET', 'POST', 'PATCH'])
def zones(request, zone_id=None):
    membership = manager(request.user)
    if request.method == 'GET':
        if zone_id:
            return Response(output(get_object_or_404(Zone, pk=zone_id, restaurant=membership.restaurant)))
        return Response([output(zone) for zone in Zone.objects.filter(restaurant=membership.restaurant).order_by('name_key', 'pk')])
    if (request.method == 'PATCH') != bool(zone_id):
        return Response({'detail': 'Usa una zona existente para editar o la lista para crear.'}, status=405)
    serializer = ZoneInput(data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if request.method == 'POST' and 'is_active' in request.data:
        return Response({'detail': 'Las zonas nuevas se crean activas.'}, status=400)
    try:
        # RF-012, RNF-004/007/019: serialize permission check, change and audit.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            zone = get_object_or_404(Zone, pk=zone_id, restaurant=membership.restaurant) if zone_id else Zone(restaurant=membership.restaurant)
            before = snapshot(zone) if zone_id else {}
            if 'name' in data:
                zone.name = data['name']
                zone.name_key = zone.name.casefold()
            if 'is_active' in request.data:
                zone.is_active = data['is_active']
            after = snapshot(zone)
            if before != after:
                zone.save()
                action = 'zone.created' if not zone_id else 'zone.updated' if before['name'] != after['name'] else 'zone.status_changed'
                AuditLog.objects.create(restaurant=membership.restaurant, actor=request.user, action=action, entity_id=str(zone.pk), before=before, after=after)
    except IntegrityError:
        return Response({'detail': 'Ya existe una zona con ese nombre en tu restaurante. Usa otro nombre o reactiva la existente.'}, status=400)
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return Response({'detail': 'Otra operación está actualizando el restaurante. Intenta de nuevo.'}, status=409)
    return Response(output(zone), status=200 if zone_id else 201)

from django.db import OperationalError, transaction
from django.db.models import F
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .authentication import membership_for
from .models import AuditLog, PaymentMethod, Restaurant


def manager(user):
    membership = membership_for(user)
    if membership.role not in ['OWNER', 'ADMIN']:
        raise PermissionDenied('No tienes permiso para gestionar métodos de pago.')
    return membership


class PaymentMethodInput(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    is_active = serializers.BooleanField(required=False)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Solo puedes modificar el nombre y el estado del método de pago.')
        return data


def snapshot(payment_method):
    return {'name': payment_method.name, 'is_active': payment_method.is_active}


def output(payment_method):
    return {'id': str(payment_method.pk), **snapshot(payment_method)}


def conflict():
    return Response({'detail': 'Otra operación está actualizando los métodos de pago. Actualiza la lista e intenta de nuevo.'}, status=409)


@never_cache
@api_view(['GET', 'POST', 'PATCH'])
def payment_methods(request, payment_method_id=None):
    membership = manager(request.user)
    if request.method == 'GET':
        rows = PaymentMethod.objects.filter(restaurant=membership.restaurant).order_by('name', 'pk')
        return Response(output(get_object_or_404(rows, pk=payment_method_id)) if payment_method_id else [output(row) for row in rows])
    if (request.method == 'PATCH') != bool(payment_method_id):
        return Response({'detail': 'Selecciona un método de pago para editar o la lista para crear.'}, status=405)
    serializer = PaymentMethodInput(data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    if request.method == 'POST' and 'is_active' in request.data:
        return Response({'detail': 'Los métodos de pago nuevos se crean activos.'}, status=400)
    try:
        # RF-020, RNF-004/007/019: lock the restaurant before reading mutable data.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            rows = PaymentMethod.objects.filter(restaurant=membership.restaurant).order_by('name', 'pk')
            payment_method = get_object_or_404(rows, pk=payment_method_id) if payment_method_id else PaymentMethod(
                restaurant=membership.restaurant)
            before = snapshot(payment_method) if payment_method_id else {}
            for field, value in serializer.validated_data.items():
                if field == 'is_active' and field not in request.data:
                    continue
                setattr(payment_method, field, value)
            after = snapshot(payment_method)
            if before != after:
                payment_method.save()
                action = 'payment_method.created' if not payment_method_id else 'payment_method.updated' if before['name'] != after['name'] else 'payment_method.status_changed'
                AuditLog.objects.create(restaurant=membership.restaurant, actor=request.user, action=action,
                                        entity_id=str(payment_method.pk), before=before, after=after)
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return conflict()
    return Response(output(payment_method), status=200 if payment_method_id else 201)



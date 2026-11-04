from django.db import OperationalError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .authentication import membership_for
from .models import AuditLog, OperationReason, Restaurant


class ReasonInput(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    operation_type = serializers.ChoiceField(choices=OperationReason.OperationType.choices)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Solo puedes modificar el nombre y el tipo de operación del motivo.')
        return data


def snapshot(row):
    return {'name': row.name, 'operation_type': row.operation_type,
            'operation_type_label': row.get_operation_type_display()}


def output(row):
    return {'id': str(row.pk), **snapshot(row)}


def manager(user):
    membership = membership_for(user)
    if membership.role not in ['OWNER', 'ADMIN']:
        raise PermissionDenied('No tienes permiso para configurar motivos.')
    return membership


@never_cache
@api_view(['GET', 'POST', 'PATCH'])
def operation_reasons(request, reason_id=None):
    membership = manager(request.user)
    if request.method == 'GET':
        rows = OperationReason.objects.filter(restaurant=membership.restaurant).order_by('operation_type', 'name', 'pk')
        if reason_id:
            return Response(output(get_object_or_404(rows, pk=reason_id)))
        operation_type = request.query_params.get('operation_type')
        if operation_type is not None:
            if operation_type not in OperationReason.OperationType.values:
                raise serializers.ValidationError({'detail': 'Selecciona un tipo de operación válido.'})
            rows = rows.filter(operation_type=operation_type)
        return Response({'results': [output(row) for row in rows],
                         'operation_types': [{'value': value, 'label': label} for value, label in OperationReason.OperationType.choices]})
    if (request.method == 'PATCH') != bool(reason_id):
        return Response({'detail': 'Selecciona un motivo para editar o la lista para crear.'}, status=405)
    serializer = ReasonInput(data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    try:
        # RF-021, RNF-004/007/019: recheck membership under the same tenant write lock.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            row = get_object_or_404(OperationReason, pk=reason_id, restaurant=membership.restaurant) if reason_id else OperationReason(restaurant=membership.restaurant)
            before = snapshot(row) if reason_id else {}
            for field, value in serializer.validated_data.items():
                setattr(row, field, value)
            after = snapshot(row)
            if before != after:
                row.save()
                AuditLog.objects.create(restaurant=membership.restaurant, actor=request.user,
                                        action='reason.updated' if reason_id else 'reason.created',
                                        entity_id=str(row.pk), before=before, after=after)
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return Response({'detail': 'Otra operación está actualizando los motivos. Actualiza la lista e intenta de nuevo.'}, status=409)
    return Response(output(row), status=200 if reason_id else 201)

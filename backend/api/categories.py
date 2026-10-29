from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Max
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .authentication import membership_for
from .models import AuditLog, Category, Restaurant


def manager(user):
    membership = membership_for(user)
    if membership.role not in ['OWNER', 'ADMIN']:
        raise PermissionDenied('No tienes permiso para gestionar categorías.')
    return membership


class CategoryInput(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    is_active = serializers.BooleanField(required=False)

    def validate(self, data):
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Solo puedes modificar el nombre y el estado de la categoría.')
        return data


class ReorderInput(serializers.Serializer):
    order = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)
    expected_order = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)

    def validate(self, data):
        if set(self.initial_data) != set(self.fields):
            raise serializers.ValidationError('Envía el orden nuevo y el orden consultado anteriormente.')
        for ids in data.values():
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError('No repitas categorías en el orden.')
        return data


def snapshot(category):
    return {'name': category.name, 'is_active': category.is_active, 'position': category.position}


def output(category):
    return {'id': str(category.pk), **snapshot(category)}


def conflict():
    return Response({'detail': 'Otra operación está actualizando las categorías. Actualiza la lista e intenta de nuevo.'}, status=409)


@api_view(['GET', 'POST', 'PATCH'])
def categories(request, category_id=None):
    membership = manager(request.user)
    if request.method == 'GET':
        rows = Category.objects.filter(restaurant=membership.restaurant)
        return Response(output(get_object_or_404(rows, pk=category_id)) if category_id else [output(row) for row in rows])
    if (request.method == 'PATCH') != bool(category_id):
        return Response({'detail': 'Selecciona una categoría para editar o la lista para crear.'}, status=405)
    serializer = CategoryInput(data=request.data, partial=request.method == 'PATCH')
    serializer.is_valid(raise_exception=True)
    if request.method == 'POST' and 'is_active' in request.data:
        return Response({'detail': 'Las categorías nuevas se crean activas.'}, status=400)
    try:
        # RF-023, RNF-004/007/019: lock the restaurant before reading mutable data.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            rows = Category.objects.filter(restaurant=membership.restaurant)
            category = get_object_or_404(rows, pk=category_id) if category_id else Category(
                restaurant=membership.restaurant, position=(rows.aggregate(last=Max('position'))['last'] or 0) + 1)
            before = snapshot(category) if category_id else {}
            for field, value in serializer.validated_data.items():
                setattr(category, field, value)
            after = snapshot(category)
            if before != after:
                category.save()
                action = 'category.created' if not category_id else 'category.updated' if before['name'] != after['name'] else 'category.status_changed'
                AuditLog.objects.create(restaurant=membership.restaurant, actor=request.user, action=action,
                                        entity_id=str(category.pk), before=before, after=after)
    except IntegrityError:
        return Response({'detail': 'Ya existe una categoría con ese nombre en tu restaurante. Usa otro nombre o reactiva la existente.'}, status=400)
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return conflict()
    return Response(output(category), status=200 if category_id else 201)


@api_view(['POST'])
def reorder_categories(request):
    membership = manager(request.user)
    serializer = ReorderInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        # RF-023, RNF-019/020: reject stale or cross-tenant batches atomically.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            rows = list(Category.objects.filter(restaurant=membership.restaurant))
            current = [row.pk for row in rows]
            if set(data['order']) != set(current) or set(data['expected_order']) != set(current):
                return Response({'detail': 'El orden debe incluir una vez cada categoría de tu restaurante. Actualiza la lista.'}, status=400)
            if data['expected_order'] != current:
                return conflict()
            indexed = {row.pk: row for row in rows}
            for position, category_id in enumerate(data['order'], 1):
                row = indexed[category_id]
                if row.position != position:
                    before = snapshot(row)
                    row.position = position
                    row.save(update_fields=['position'])
                    AuditLog.objects.create(restaurant=membership.restaurant, actor=request.user,
                                            action='category.reordered', entity_id=str(row.pk), before=before, after=snapshot(row))
            return Response([output(indexed[category_id]) for category_id in data['order']])
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return conflict()

from decimal import Decimal

from django.db import OperationalError, transaction
from django.db.models import F
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from .authentication import membership_for
from .identity import ROLE_MODULES
from .models import AuditLog, Category, Product, Restaurant


def manager(user):
    membership = membership_for(user)
    if membership.role not in ('OWNER', 'ADMIN'):
        raise PermissionDenied('No tienes permiso para gestionar productos.')
    return membership


class ProductInput(serializers.Serializer):
    description = serializers.CharField(required=False, allow_blank=True, default='', error_messages={
        'invalid': 'Ingresa una descripción de texto.', 'null': 'Usa texto o deja la descripción vacía.'})
    name = serializers.CharField(max_length=160, error_messages={
        'required': 'Ingresa el nombre.', 'blank': 'Ingresa el nombre.',
        'max_length': 'Usa hasta 160 caracteres.'})
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'), error_messages={
        'required': 'Ingresa el precio.', 'invalid': 'Ingresa un precio válido.',
        'min_value': 'El precio no puede ser negativo.', 'max_digits': 'El precio es demasiado alto.',
        'max_whole_digits': 'El precio es demasiado alto.', 'max_decimal_places': 'Usa hasta dos decimales.'})
    category = serializers.UUIDField(error_messages={
        'required': 'Selecciona la categoría.', 'invalid': 'Selecciona una categoría válida.'})
    is_active = serializers.BooleanField(error_messages={
        'required': 'Selecciona el estado.', 'invalid': 'Selecciona un estado válido.'})

    def validate(self, data):
        if 'is_active' not in self.initial_data:
            raise serializers.ValidationError({'is_active': 'Selecciona el estado.'})
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Solo se admiten nombre, descripción, precio, categoría y estado.')
        return data


def catalog(membership):
    # RF-024: the category is the sole ownership relation; no client tenant field.
    return Product.objects.filter(category__restaurant_id=membership.restaurant_id).select_related('category').order_by(
        'category__position', 'category_id', 'name', 'pk')


def output(product):
    return {'id': str(product.pk), 'name': product.name, 'description': product.description, 'price': format(product.price, '.2f'),
            'category': str(product.category_id), 'category_name': product.category.name,
            'is_active': product.is_active}


@never_cache
@api_view(['GET', 'POST'])
def products(request):
    membership = manager(request.user)
    if request.method == 'GET':
        return Response([output(product) for product in catalog(membership)])
    serializer = ProductInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    try:
        # RF-024, RNF-019: serialize with category status changes and audit the creation atomically.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            category = Category.objects.filter(pk=values['category'], restaurant_id=membership.restaurant_id,
                                               is_active=True).first()
            if category is None:
                raise serializers.ValidationError({'category': 'Selecciona una categoría activa de tu restaurante.'})
            product = Product.objects.create(**{**values, 'category': category})
            result = output(product)
            AuditLog.objects.create(restaurant_id=membership.restaurant_id, actor=request.user,
                                    action='product.created', entity_id=str(product.pk),
                                    before={}, after={key: value for key, value in result.items() if key != 'id'})
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return Response({'detail': 'Hay otra operación en curso. Intenta guardar de nuevo.'}, status=409)
    return Response(result, status=201)


class DescriptionInput(serializers.Serializer):
    description = serializers.CharField(allow_blank=True, error_messages={
        'required': 'Envía la descripción; puedes dejarla vacía.',
        'invalid': 'Ingresa una descripción de texto.', 'null': 'Usa texto o deja la descripción vacía.'})

    def validate(self, data):
        if set(self.initial_data) != {'description'}:
            raise serializers.ValidationError('Solo se admite la descripción en esta operación.')
        return data


class ProductEditInput(ProductInput):
    allowed_fields = ('name', 'description', 'category')

    def get_fields(self):
        return {key: field for key, field in super().get_fields().items() if key in self.allowed_fields}

    def validate(self, data):
        if not data or set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError('Envía únicamente los campos permitidos para esta edición.')
        return data


class ProductPriceInput(ProductEditInput):
    allowed_fields = ('price',)


def update_product(request, product_id, input_class, action):
    membership = manager(request.user)
    try:
        # RF-026, RNF-004/007/019: serialize edits and reauthorize before touching tenant data.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            product = catalog(membership).filter(pk=product_id).first()
            if product is None:
                raise NotFound('No se encontró el producto en tu restaurante.')
            serializer = input_class(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data.copy()
            if 'category' in values:
                category = Category.objects.filter(pk=values['category'], restaurant_id=membership.restaurant_id).first()
                if category is None or (not category.is_active and category.pk != product.category_id):
                    raise serializers.ValidationError({'category': 'Selecciona una categoría activa de tu restaurante.'})
                values['category'] = category
            before = {key: value for key, value in output(product).items() if key != 'id'}
            changed = [key for key, value in values.items() if getattr(product, key) != value]
            if changed:
                for key in changed:
                    setattr(product, key, values[key])
                product.save(update_fields=changed)
                after = {key: value for key, value in output(product).items() if key != 'id'}
                AuditLog.objects.create(restaurant_id=membership.restaurant_id, actor=request.user,
                                        action=action, entity_id=str(product.pk), before=before, after=after)
            result = output(product)
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return Response({'detail': 'Hay otra operación en curso. Intenta guardar de nuevo.'}, status=409)
    return Response(result)


@never_cache
@api_view(['GET', 'PATCH'])
def product_details(request, product_id):
    if request.method == 'GET':
        membership = manager(request.user)
        product = catalog(membership).filter(pk=product_id).first()
        if product is None:
            raise NotFound('No se encontró el producto en tu restaurante.')
        return Response(output(product))
    return update_product(request, product_id, ProductEditInput, 'product.updated')


@never_cache
@api_view(['PATCH'])
def product_price(request, product_id):
    # RF-027: exact Decimal input; existing records and snapshots are never rewritten.
    return update_product(request, product_id, ProductPriceInput, 'product.price_changed')


@never_cache
@api_view(['PATCH'])
def product_description(request, product_id):
    membership = manager(request.user)
    try:
        # RF-025, RNF-004/007/019: reauthorize under the restaurant lock and audit atomically.
        with transaction.atomic():
            Restaurant.objects.filter(pk=membership.restaurant_id).update(is_active=F('is_active'))
            membership = manager(request.user)
            product = catalog(membership).filter(pk=product_id).first()
            if product is None:
                raise NotFound('No se encontró el producto en tu restaurante.')
            serializer = DescriptionInput(data=request.data)
            serializer.is_valid(raise_exception=True)
            description = serializer.validated_data['description']
            if product.description != description:
                before = {'name': product.name, 'description': product.description}
                product.description = description
                product.save(update_fields=['description'])
                AuditLog.objects.create(restaurant_id=membership.restaurant_id, actor=request.user,
                                        action='product.description_changed', entity_id=str(product.pk),
                                        before=before, after={'name': product.name, 'description': description})
            result = output(product)
    except OperationalError as error:
        if 'locked' not in str(error).lower():
            raise
        return Response({'detail': 'Hay otra operación en curso. Intenta guardar de nuevo.'}, status=409)
    return Response(result)


@never_cache
@api_view(['GET'])
def menu(request):
    membership = membership_for(request.user)
    if 'menu' not in ROLE_MODULES[membership.role]:
        raise PermissionDenied('No tienes permiso para consultar la carta.')
    rows = catalog(membership).filter(is_active=True, category__is_active=True)
    return Response({'products': [output(product) for product in rows]})

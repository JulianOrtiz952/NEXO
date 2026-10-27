import hashlib
import secrets
from datetime import timedelta
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from .authentication import membership_for
from .models import AccessToken, Membership, Restaurant, AuditLog
from .ownership import active_owners, change_role

User = get_user_model()
ROLE_MODULES = {
    'OWNER': ['users', 'tables', 'kitchen', 'menu', 'cashier'],
    'ADMIN': ['users', 'tables', 'kitchen', 'menu', 'cashier'],
    'CASHIER': ['tables', 'menu', 'cashier'],
    'WAITER': ['tables', 'menu'],
    'KITCHEN': ['kitchen'],
}


def profile(user):
    if user.is_superuser:
        return {'id': user.pk, 'email': user.email, 'role': 'PLATFORM_ADMIN', 'restaurant': None, 'modules': ['restaurants']}
    m = membership_for(user)
    return {'id': user.pk, 'email': user.email, 'role': m.role, 'restaurant': {'id': str(m.restaurant_id), 'name': m.restaurant.name}, 'modules': ROLE_MODULES[m.role]}


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = str(request.data.get('email', '')).strip().lower()
    candidate = User.objects.filter(email__iexact=email).first()
    user = authenticate(request, username=candidate.username if candidate else '', password=request.data.get('password', ''))
    if not user:
        return Response({'detail': 'Correo o contraseña incorrectos.'}, status=401)
    data = profile(user)
    raw = secrets.token_urlsafe(48)
    expiry = timezone.now() + timedelta(hours=1)
    AccessToken.objects.create(digest=hashlib.sha256(raw.encode()).hexdigest(), user=user, expires_at=expiry)
    return Response({'token': raw, 'expires_at': expiry.isoformat(), 'user': data})


@api_view(['POST'])
def logout(request):
    request.auth.delete()
    return Response(status=204)


@api_view(['GET'])
def me(request):
    return Response(profile(request.user))


class AccountInput(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Este correo ya está registrado.')
        return value

    def validate(self, data):
        try:
            validate_password(data['password'], User(username=data['email'], email=data['email']))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return data


class UserInput(AccountInput):
    role = serializers.ChoiceField(choices=Membership.Role.choices)


@api_view(['GET', 'POST'])
def prospective_owners(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Esta operación requiere un administrador global.')
    if request.method == 'GET':
        candidates = User.objects.filter(is_active=True, is_superuser=False, is_staff=False, membership__isnull=True)
        return Response(list(candidates.order_by('email').values('id', 'email')))
    serializer = AccountInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'])
            AuditLog.objects.create(actor=request.user, action='prospective_owner.created', entity_id=str(user.pk), after={'email': user.email})
    except IntegrityError:
        return Response({'detail': 'Este correo ya está registrado.'}, status=400)
    return Response({'id': user.pk, 'email': user.email}, status=201)


def manager(request):
    membership = membership_for(request.user)
    if membership.role not in ['OWNER', 'ADMIN']:
        raise PermissionDenied('No tienes permiso para administrar usuarios.')
    return membership


@api_view(['GET', 'POST', 'PATCH'])
def users(request):
    m = manager(request)
    if request.method == 'PATCH':
        # RF-007, RNF-004, RNF-007: local authorization and atomic role audit.
        class RoleUpdate(serializers.Serializer):
            id = serializers.IntegerField(min_value=1)
            role = serializers.ChoiceField(choices=Membership.Role.choices)

            def validate(self, data):
                if set(self.initial_data) - {'id', 'role'}:
                    raise serializers.ValidationError('Solo puedes modificar el rol en esta operación.')
                return data

        serializer = RoleUpdate(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        target = change_role(actor=request.user, restaurant_id=m.restaurant_id, user_id=data['id'], role=data['role'])
        return Response({'id': target.user_id, 'email': target.user.email, 'role': target.role})
    if request.method == 'GET':
        return Response([{'id': x.user_id, 'email': x.user.email, 'role': x.role, 'is_initial_owner': x.user_id == m.restaurant.initial_owner_id, 'is_last_owner': x.role == 'OWNER' and not active_owners(m.restaurant).exclude(pk=x.pk).exists()} for x in Membership.objects.filter(restaurant=m.restaurant).select_related('user')])
    serializer = UserInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'])
            Membership.objects.create(user=user, restaurant=m.restaurant, role=data['role'])
            AuditLog.objects.create(restaurant=m.restaurant, actor=request.user, action='user.created', entity_id=str(user.pk), after={'email': user.email, 'role': data['role']})
    except IntegrityError:
        return Response({'detail': 'Este correo ya está registrado.'}, status=400)
    return Response({'id': user.pk, 'email': user.email, 'role': data['role']}, status=status.HTTP_201_CREATED)


class RestaurantInput(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    owner = serializers.IntegerField(min_value=1)


@api_view(['GET', 'POST', 'PATCH'])
def restaurants(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Esta operación requiere un administrador global.')
    if request.method == 'GET':
        return Response([{
            'id': restaurant.pk, 'name': restaurant.name, 'is_active': restaurant.is_active,
            'owners': [{'id': m.user_id, 'email': m.user.email} for m in restaurant.membership_set.all() if m.role == 'OWNER' and m.is_active and m.user.is_active and not m.user.is_superuser],
            'initial_owner': next(({'email': m.user.email, 'role': m.role} for m in restaurant.membership_set.all() if m.user_id == restaurant.initial_owner_id), None),
        } for restaurant in Restaurant.objects.order_by('name').prefetch_related('membership_set__user')])
    if request.method == 'PATCH':
        class Update(serializers.Serializer):
            id = serializers.UUIDField()
            is_active = serializers.BooleanField(required=False)
            owner = serializers.IntegerField(min_value=1, required=False)
        serializer = Update(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            restaurant = Restaurant.objects.select_for_update().filter(pk=data['id']).first()
            if not restaurant:
                return Response({'detail': 'Restaurante no encontrado.'}, status=404)
            if 'owner' in data:
                owner = User.objects.select_for_update().filter(pk=data['owner'], is_active=True, is_superuser=False).first()
                if not owner or Membership.objects.filter(user=owner).exclude(restaurant=restaurant).exists():
                    return Response({'detail': 'El Dueño debe ser un usuario operativo sin otro restaurante.'}, status=400)
                previous = Membership.objects.filter(user=owner).values('role', 'is_active').first() or {}
                Membership.objects.update_or_create(user=owner, defaults={'restaurant': restaurant, 'role': 'OWNER', 'is_active': True})
                AuditLog.objects.create(restaurant=restaurant, actor=request.user, action='restaurant.owner_assigned', entity_id=str(owner.pk), before=previous, after={'role': 'OWNER', 'is_active': True})
            if 'is_active' in data:
                previous = restaurant.is_active
                restaurant.is_active = data['is_active']
                restaurant.save(update_fields=['is_active'])
                AuditLog.objects.create(restaurant=restaurant, actor=request.user, action='restaurant.status_changed', entity_id=str(restaurant.pk), before={'is_active': previous}, after={'is_active': restaurant.is_active})
        return Response({'id': restaurant.pk, 'name': restaurant.name, 'is_active': restaurant.is_active})
    serializer = RestaurantInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        owner = User.objects.select_for_update().filter(pk=data['owner'], is_active=True, is_superuser=False).first()
        if not owner or Membership.objects.filter(user=owner).exists():
            return Response({'detail': 'El Dueño debe ser un usuario operativo sin restaurante.'}, status=400)
        restaurant = Restaurant.objects.create(name=data['name'], initial_owner=owner)
        Membership.objects.create(user=owner, restaurant=restaurant, role='OWNER')
        AuditLog.objects.create(restaurant=restaurant, actor=request.user, action='restaurant.created', entity_id=str(restaurant.pk), after={'name': restaurant.name, 'owner': owner.pk})
    return Response({'id': restaurant.pk, 'name': restaurant.name}, status=201)


@api_view(['PATCH'])
def initial_owner_role(request):
    # RF-007: narrowly scoped global exception, no employee directory access.
    if not request.user.is_superuser:
        raise PermissionDenied('Esta operación requiere un administrador global.')
    class InitialOwnerUpdate(serializers.Serializer):
        restaurant = serializers.UUIDField()
        role = serializers.ChoiceField(choices=Membership.Role.choices)

        def validate(self, data):
            if set(self.initial_data) - {'restaurant', 'role'}:
                raise serializers.ValidationError('Solo puedes cambiar el rol del primer Dueño del restaurante seleccionado.')
            return data
    serializer = InitialOwnerUpdate(data=request.data)
    serializer.is_valid(raise_exception=True)
    target = change_role(actor=request.user, restaurant_id=serializer.validated_data['restaurant'],
                         user_id=None, role=serializer.validated_data['role'], platform=True)
    return Response({'role': target.role})

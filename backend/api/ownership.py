from django.db import connection, transaction, OperationalError
from django.db.models import F
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from .models import AuditLog, Membership, Restaurant
from .authentication import ensure_restaurant_access


def active_owners(restaurant):
    return Membership.objects.filter(restaurant=restaurant, role='OWNER', is_active=True,
                                     user__is_active=True, user__is_superuser=False)


def change_role(**kwargs):
    try:
        return _change_role(**kwargs)
    except OperationalError as exc:
        if connection.vendor != 'sqlite' or 'locked' not in str(exc).lower():
            raise
        conflict = APIException('Otro cambio de usuarios está en curso. Actualiza la página y vuelve a intentarlo.')
        conflict.status_code = 409
        raise conflict from exc


def _change_role(*, actor, restaurant_id, user_id, role, platform=False):
    """RF-007, RNF-004/007/019: serialize role decisions per restaurant."""
    with transaction.atomic():
        # First statement is a write: SQLite serializes writers; row locks also
        # serialize the same operation on PostgreSQL, before counting owners.
        if not Restaurant.objects.filter(pk=restaurant_id).update(is_active=F('is_active')):
            raise NotFound('Restaurante no encontrado.')
        restaurant = Restaurant.objects.get(pk=restaurant_id)
        if platform:
            if not actor.is_superuser or not actor.is_active:
                raise PermissionDenied('Esta operación requiere un administrador global.')
            user_id = restaurant.initial_owner_id
        else:
            ensure_restaurant_access(restaurant)
            manager = Membership.objects.filter(restaurant=restaurant, user=actor, user__is_active=True,
                                                is_active=True, role__in=['OWNER', 'ADMIN']).first()
            if not manager or not restaurant.is_active or actor.is_superuser:
                raise PermissionDenied('No tienes permiso para administrar usuarios.')
        target = Membership.objects.select_related('user').filter(restaurant=restaurant, user_id=user_id,
                                                                  user__is_superuser=False).first()
        if not target:
            raise NotFound('Usuario no encontrado en tu restaurante.')
        if role not in Membership.Role.values:
            raise ValidationError({'role': 'Selecciona un rol local válido.'})
        if target.role == role:
            return target
        if not restaurant.initial_owner_id:
            raise ValidationError('Falta identificar al primer Dueño. Contacta al administrador global.')
        if target.user_id == restaurant.initial_owner_id and target.role == 'OWNER' and not platform:
            raise PermissionDenied('Solo el administrador global puede cambiar el rol del primer Dueño.')
        if target.role == 'OWNER' and role != 'OWNER' and not active_owners(restaurant).exclude(pk=target.pk).exists():
            raise ValidationError('El restaurante debe conservar al menos un Dueño activo. Asigna otro Dueño antes de continuar.')
        previous = target.role
        target.role = role
        target.save(update_fields=['role'])
        AuditLog.objects.create(restaurant=restaurant, actor=actor, action='user.role_changed',
                                entity_id=str(target.user_id), before={'role': previous}, after={'role': role})
        return target

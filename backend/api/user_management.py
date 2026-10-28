from django.contrib.auth import get_user_model
from django.db import connection, transaction, IntegrityError, OperationalError
from django.db.models import F, Q
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from .models import AccessToken, AuditLog, Membership, Restaurant
from .authentication import ensure_restaurant_access
from .ownership import active_owners


def edit_email(*, actor, restaurant_id, user_id, email):
    """RF-006, RNF-004/007: preserve identity and audit email edits atomically."""
    User = get_user_model()
    try:
        with transaction.atomic():
            Restaurant.objects.filter(pk=restaurant_id).update(is_active=F('is_active'))
            ensure_restaurant_access(Restaurant.objects.get(pk=restaurant_id))
            if actor.is_superuser or not Membership.objects.filter(
                restaurant_id=restaurant_id, restaurant__is_active=True, user=actor,
                user__is_active=True, is_active=True, role__in=['OWNER', 'ADMIN'],
            ).exists():
                raise PermissionDenied('No tienes permiso para editar usuarios.')
            target = Membership.objects.select_related('user').filter(
                restaurant_id=restaurant_id, user_id=user_id, user__is_superuser=False,
            ).first()
            if not target:
                raise NotFound('Usuario no encontrado en tu restaurante.')
            email = email.strip().lower()
            if User.objects.exclude(pk=user_id).filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
                raise ValidationError({'email': 'Este correo no está disponible. Usa otro correo.'})
            user = target.user
            if user.email != email:
                previous = user.email
                user.email = email
                user.username = email
                user.save(update_fields=['email', 'username'])
                AuditLog.objects.create(restaurant_id=restaurant_id, actor=actor, action='user.email_changed',
                                        entity_id=str(user.pk), before={'email': previous}, after={'email': email})
            return {'id': user.pk, 'email': user.email, 'role': target.role}
    except IntegrityError as exc:
        raise ValidationError({'email': 'Este correo no está disponible. Usa otro correo.'}) from exc
    except OperationalError as exc:
        if connection.vendor != 'sqlite' or 'locked' not in str(exc).lower():
            raise
        conflict = APIException('Otro cambio de usuarios está en curso. Actualiza la página y vuelve a intentarlo.')
        conflict.status_code = 409
        raise conflict from exc


def change_user_status(*, actor, restaurant_id, user_id, is_active, platform=False):
    """RF-008/009, RNF-007/019: scoped state change and cascading suspension."""
    try:
        with transaction.atomic():
            if not Restaurant.objects.filter(pk=restaurant_id).update(is_active=F('is_active')):
                raise NotFound('Restaurante no encontrado.')
            restaurant = Restaurant.objects.get(pk=restaurant_id)
            if platform:
                if not actor.is_superuser or not actor.is_active:
                    raise PermissionDenied('Esta operación requiere un administrador global.')
                user_id = restaurant.initial_owner_id
            else:
                ensure_restaurant_access(restaurant)
                if actor.is_superuser or not Membership.objects.filter(
                    restaurant=restaurant, restaurant__is_active=True, user=actor,
                    user__is_active=True, is_active=True, role__in=['OWNER', 'ADMIN'],
                ).exists():
                    raise PermissionDenied('No tienes permiso para administrar usuarios.')
            target = Membership.objects.select_related('user').filter(
                restaurant=restaurant, user_id=user_id, user__is_superuser=False,
            ).first()
            if not target:
                raise NotFound('Usuario no encontrado en tu restaurante.')
            if not platform and target.user_id == restaurant.initial_owner_id:
                raise PermissionDenied('Solo el administrador global puede activar o desactivar al primer Dueño.')
            user = target.user
            if user.is_active == is_active:
                return {'id': user.pk, 'is_active': user.is_active}
            if not is_active and target.role == 'OWNER' and not platform and not active_owners(restaurant).exclude(pk=target.pk).exists():
                raise ValidationError('Debe conservarse al menos un Dueño activo. Asigna otro antes de continuar.')
            previous = user.is_active
            user.is_active = is_active
            user.save(update_fields=['is_active'])
            if is_active and platform and not active_owners(restaurant).exists():
                raise ValidationError('Asigna un Dueño activo antes de reactivar el acceso del restaurante.')
            if not is_active:
                tokens = AccessToken.objects.filter(user=user)
                if platform:
                    tokens = AccessToken.objects.filter(user__membership__restaurant=restaurant)
                tokens.delete()
            AuditLog.objects.create(restaurant=restaurant, actor=actor, action='user.status_changed',
                                    entity_id=str(user.pk), before={'is_active': previous},
                                    after={'is_active': is_active, 'cascading': platform})
            return {'id': user.pk, 'is_active': user.is_active}
    except OperationalError as exc:
        if connection.vendor != 'sqlite' or 'locked' not in str(exc).lower():
            raise
        conflict = APIException('Otro cambio de usuarios está en curso. Actualiza la página y vuelve a intentarlo.')
        conflict.status_code = 409
        raise conflict from exc

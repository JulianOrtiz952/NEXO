from django.contrib.auth import get_user_model
from django.db import connection, transaction, IntegrityError, OperationalError
from django.db.models import F, Q
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from .models import AuditLog, Membership, Restaurant


def edit_email(*, actor, restaurant_id, user_id, email):
    """RF-006, RNF-004/007: preserve identity and audit email edits atomically."""
    User = get_user_model()
    try:
        with transaction.atomic():
            Restaurant.objects.filter(pk=restaurant_id).update(is_active=F('is_active'))
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

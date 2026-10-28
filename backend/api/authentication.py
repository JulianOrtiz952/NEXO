import hashlib
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from .models import AccessToken, Membership


def ensure_restaurant_access(restaurant):
    # RF-009: the initial owner's suspension blocks every local identity.
    if restaurant.initial_owner_id and not Membership.objects.filter(
        restaurant=restaurant, user_id=restaurant.initial_owner_id,
        user__is_active=True, is_active=True,
    ).exists():
        raise PermissionDenied('El acceso de este restaurante está suspendido. Contacta al administrador global.')


def membership_for(user):
    try:
        membership = Membership.objects.select_related('restaurant').get(user=user, user__is_active=True, is_active=True, restaurant__is_active=True)
    except Membership.DoesNotExist:
        raise PermissionDenied('No tienes una membresía activa en un restaurante.')
    if user.is_superuser:
        raise PermissionDenied('El administrador global no tiene acceso operativo.')
    ensure_restaurant_access(membership.restaurant)
    return membership


class ExpiringTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != b'bearer':
            raise AuthenticationFailed('Credenciales no válidas. Inicia sesión de nuevo.')
        digest = hashlib.sha256(header[1]).hexdigest()
        try:
            token = AccessToken.objects.select_related('user').get(digest=digest, expires_at__gt=timezone.now(), user__is_active=True)
        except AccessToken.DoesNotExist:
            raise AuthenticationFailed('La sesión venció o no es válida. Inicia sesión de nuevo.')
        if not token.user.is_superuser:
            membership_for(token.user)
        return token.user, token

    def authenticate_header(self, request):
        return 'Bearer'

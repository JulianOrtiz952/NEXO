import hashlib
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from .models import AccessToken, Membership


def membership_for(user):
    try:
        membership = Membership.objects.select_related('restaurant').get(user=user, is_active=True, restaurant__is_active=True)
    except Membership.DoesNotExist:
        raise PermissionDenied('No tienes una membresía activa en un restaurante.')
    if user.is_superuser:
        raise PermissionDenied('El administrador global no tiene acceso operativo.')
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

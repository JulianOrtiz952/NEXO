from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from .authentication import membership_for
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import AuditLog


# RF-012, RNF-007: register each supported action with its category and type.
ACTION_TYPES = {
    'user.created': ('Usuarios', 'Creación'),
    'user.email_changed': ('Usuarios', 'Edición'),
    'user.role_changed': ('Usuarios', 'Cambio de rol'),
    'user.status_changed': ('Usuarios', 'Cambio de estado'),
    'prospective_owner.created': ('Dueños', 'Creación'),
    'restaurant.created': ('Restaurantes', 'Creación'),
    'restaurant.owner_assigned': ('Restaurantes', 'Vinculación de Dueño'),
    'restaurant.status_changed': ('Restaurantes', 'Cambio de estado'),
    'zone.created': ('Zonas', 'Creación'),
    'zone.updated': ('Zonas', 'Edición'),
    'zone.status_changed': ('Zonas', 'Cambio de estado'),
    'table.created': ('Mesas', 'Creación'),
}
GLOBAL_ACTIONS = {key for key in ACTION_TYPES if key.startswith(('user.', 'restaurant.', 'prospective_owner.'))}


@api_view(['GET'])
def history(request):
    # RNF-007: immutable, tenant-scoped history. Global access excludes local actions.
    rows = AuditLog.objects.select_related('actor', 'restaurant')
    if request.user.is_superuser:
        actions = GLOBAL_ACTIONS
        rows = rows.filter(actor__is_superuser=True, action__in=actions)
    else:
        membership = membership_for(request.user)
        if membership.role not in ['OWNER', 'ADMIN']:
            raise PermissionDenied('No tienes permiso para consultar el historial.')
        actions = set(ACTION_TYPES)
        rows = rows.filter(restaurant=membership.restaurant, action__in=actions)
    options = [{'value': action, 'label': f'{ACTION_TYPES[action][0]} · {ACTION_TYPES[action][1]}'} for action in sorted(actions)]
    selected = request.query_params.get('action', '')
    if selected:
        if selected not in actions:
            raise ValidationError({'detail': 'Selecciona un tipo de acción válido.'})
        rows = rows.filter(action=selected)
    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(rows.order_by('-created_at', '-pk'), request)
    visible_keys = {'email', 'role', 'is_active', 'name', 'owner', 'cascading', 'zone_name'}
    results = []
    for event in page:
        target = event.after.get('email') or event.before.get('email')
        if event.action.startswith('user.') or event.action == 'restaurant.owner_assigned':
            candidates = get_user_model().objects.filter(membership__restaurant_id=event.restaurant_id)
            if event.entity_id.isdigit():
                target = target or candidates.filter(pk=int(event.entity_id)).values_list('email', flat=True).first()
        if event.action in ['restaurant.created', 'restaurant.status_changed']:
            target = event.restaurant.name if event.restaurant else 'Restaurante'
        if event.action.startswith('zone.'):
            target = event.after.get('name') or event.before.get('name') or 'Zona'
        if event.action == 'table.created':
            target = f"Mesa en {event.after.get('zone_name', 'su zona')}"
        results.append({'id': event.pk, 'created_at': event.created_at, 'action': event.action,
                        'category': ACTION_TYPES[event.action][0], 'action_type': ACTION_TYPES[event.action][1],
                        'actor': event.actor.email, 'target': target or 'Cuenta de usuario',
                        'restaurant': event.restaurant.name if event.restaurant else 'Plataforma',
                        'before': {key: value for key, value in event.before.items() if key in visible_keys},
                        'after': {key: value for key, value in event.after.items() if key in visible_keys}})
    response = paginator.get_paginated_response(results)
    response.data['action_options'] = options
    return response

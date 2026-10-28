from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from .authentication import membership_for
from rest_framework.exceptions import PermissionDenied
from .models import AuditLog


@api_view(['GET'])
def history(request):
    # RNF-007: immutable, tenant-scoped history. Global access excludes local actions.
    rows = AuditLog.objects.select_related('actor', 'restaurant')
    actions = ['user.created', 'user.email_changed', 'user.role_changed', 'user.status_changed',
               'prospective_owner.created', 'restaurant.created', 'restaurant.owner_assigned', 'restaurant.status_changed']
    if request.user.is_superuser:
        rows = rows.filter(actor__is_superuser=True, action__in=actions)
    else:
        membership = membership_for(request.user)
        if membership.role not in ['OWNER', 'ADMIN']:
            raise PermissionDenied('No tienes permiso para consultar el historial de usuarios.')
        rows = rows.filter(restaurant=membership.restaurant, action__in=actions)
    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(rows.order_by('-created_at', '-pk'), request)
    visible_keys = {'email', 'role', 'is_active', 'name', 'owner', 'cascading'}
    results = []
    for event in page:
        target = event.after.get('email') or event.before.get('email')
        if event.action.startswith('user.') or event.action == 'restaurant.owner_assigned':
            candidates = get_user_model().objects.filter(membership__restaurant_id=event.restaurant_id)
            if event.entity_id.isdigit():
                target = target or candidates.filter(pk=int(event.entity_id)).values_list('email', flat=True).first()
        if event.action in ['restaurant.created', 'restaurant.status_changed']:
            target = event.restaurant.name if event.restaurant else 'Restaurante'
        results.append({'id': event.pk, 'created_at': event.created_at, 'action': event.action,
                        'actor': event.actor.email, 'target': target or 'Cuenta de usuario',
                        'restaurant': event.restaurant.name if event.restaurant else 'Plataforma',
                        'before': {key: value for key, value in event.before.items() if key in visible_keys},
                        'after': {key: value for key, value in event.after.items() if key in visible_keys}})
    return paginator.get_paginated_response(results)

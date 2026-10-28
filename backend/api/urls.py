from django.urls import path
from .views import health, menu
from . import identity
from .history import history
from .zones import zones
from .tables import zone_tables, table_details

urlpatterns = [path('menu/', menu, name='menu'), path('health/', health, name='health')]
urlpatterns += [
    path('auth/login/', identity.login),
    path('auth/logout/', identity.logout),
    path('auth/me/', identity.me),
    path('users/', identity.users),
    path('users/<int:user_id>/', identity.user_details),
    path('users/<int:user_id>/status/', identity.user_status),
    path('history/', history),
    path('zones/', zones),
    path('zones/<uuid:zone_id>/', zones),
    path('zones/<uuid:zone_id>/tables/', zone_tables),
    path('tables/<uuid:table_id>/', table_details),
    path('platform/initial-owner-status/', identity.user_status),
    path('platform/restaurants/', identity.restaurants),
    path('platform/owners/', identity.prospective_owners),
    path('platform/initial-owner-role/', identity.initial_owner_role),
]

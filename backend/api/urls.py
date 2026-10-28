from django.urls import path
from .views import health, menu
from . import identity

urlpatterns = [path('menu/', menu, name='menu'), path('health/', health, name='health')]
urlpatterns += [
    path('auth/login/', identity.login),
    path('auth/logout/', identity.logout),
    path('auth/me/', identity.me),
    path('users/', identity.users),
    path('users/<int:user_id>/', identity.user_details),
    path('platform/restaurants/', identity.restaurants),
    path('platform/owners/', identity.prospective_owners),
    path('platform/initial-owner-role/', identity.initial_owner_role),
]

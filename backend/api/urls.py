from django.urls import path
from .views import health, demo_menu
from .products import products, menu, product_description, product_details, product_price, product_status
from . import identity
from .history import history
from .zones import zones
from .categories import categories, reorder_categories
from .operation_reasons import operation_reasons
from .payment_methods import payment_methods
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
    path('operation-reasons/', operation_reasons),
    path('operation-reasons/<uuid:reason_id>/', operation_reasons),
    path('payment-methods/', payment_methods),
    path('payment-methods/<uuid:payment_method_id>/', payment_methods),
    path('products/', products),
    path('products/<uuid:product_id>/', product_details),
    path('products/<uuid:product_id>/price/', product_price),
    path('products/<uuid:product_id>/status/', product_status),
    path('products/<uuid:product_id>/description/', product_description),
    path('demo/menu/', demo_menu),
    path('categories/', categories),
    path('categories/reorder/', reorder_categories),
    path('categories/<uuid:category_id>/', categories),
    path('zones/<uuid:zone_id>/', zones),
    path('zones/<uuid:zone_id>/tables/', zone_tables),
    path('tables/<uuid:table_id>/', table_details),
    path('platform/initial-owner-status/', identity.user_status),
    path('platform/restaurants/', identity.restaurants),
    path('platform/owners/', identity.prospective_owners),
    path('platform/initial-owner-role/', identity.initial_owner_role),
]

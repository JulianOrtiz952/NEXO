from django.urls import path
from .views import health, menu

urlpatterns = [path('menu/', menu, name='menu'), path('health/', health, name='health')]

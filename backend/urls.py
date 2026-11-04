from django.urls import path, re_path
from backend import views

urlpatterns = [
    path('api/health', views.health),
    path('api/auth/login', views.login),
    path('api/auth/register', views.register),
    path('api/auth/me', views.me),
    path('api/auth/logout', views.logout),
    path('api/products', views.products),
    path('api/products/<str:sku>', views.edit_product),
    path('api/customers', views.customers),
    path('api/orders', views.orders),
    path('api/orders/<str:oid>/<str:action>', views.transition),
    path('api/stock/<str:action>', views.change_stock),
    path('api/movements', views.history),
    path('api/staff', views.list_staff),
    path('api/staff/<int:staff_id>', views.update_staff),
    path('api/backups', views.backups),
    path('api/backups/<str:name>', views.download_backup),
    re_path(r'^api(?:/.*)?$', views.api_not_found),
    path('', views.frontend),
    path('<path:path>', views.frontend),
]

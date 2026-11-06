from django.contrib import admin
from django.urls import path
from inventory import views as v

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/csrf", v.csrf),
    path("api/auth/me", v.me),
    path("api/auth/logout", v.logout),
    path("api/auth/<str:action>", v.account),
    path("api/products", v.products),
    path("api/products/<str:sku>", v.product_edit),
    path("api/customers", v.customers),
    path("api/orders", v.orders),
    path("api/orders/<str:oid>/<str:action>", v.order_action),
    path("api/stock/<str:action>", v.stock),
    path("api/movements", v.history),
    path("", v.frontend),
    path("<path:path>", v.frontend),
]

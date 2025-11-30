from django.contrib import admin
from django.urls import path
from inventario.views import lista_articulos

urlpatterns = [
    path("admin/", admin.site.urls),

    # Vista principal: listado de artículos
    path("", lista_articulos, name="lista_articulos"),
]

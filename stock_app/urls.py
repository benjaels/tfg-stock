from django.contrib import admin
from django.urls import path

from inventario.views import (
    lista_articulos,
    registrar_recepcion_simple,
    registrar_movimiento_simple,
    lista_movimientos,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", lista_articulos, name="lista_articulos"),
    path("recepciones/nueva/", registrar_recepcion_simple, name="registrar_recepcion"),
    path("movimientos/nuevo/", registrar_movimiento_simple, name="registrar_movimiento"),
    path("movimientos/", lista_movimientos, name="lista_movimientos"),
]

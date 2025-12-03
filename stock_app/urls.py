from django.contrib import admin
from django.urls import path

from inventario.views import (
    lista_articulos,        # va a ser el Dashboard
    lista_insumos,          # nueva vista de Insumos
    registrar_recepcion_simple,
    registrar_movimiento_simple,
    lista_movimientos,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # Dashboard en la raíz
    path("", lista_articulos, name="dashboard"),

    # Insumos
    path("insumos/", lista_insumos, name="lista_insumos"),

    # Recepciones y movimientos
    path("recepciones/nueva/", registrar_recepcion_simple, name="registrar_recepcion"),
    path("movimientos/nuevo/", registrar_movimiento_simple, name="registrar_movimiento"),
    path("movimientos/", lista_movimientos, name="lista_movimientos"),
]

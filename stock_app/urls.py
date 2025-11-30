from django.contrib import admin
from django.urls import path

from inventario.views import lista_articulos, registrar_recepcion_simple

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", lista_articulos, name="lista_articulos"),
    path("recepciones/nueva/", registrar_recepcion_simple, name="registrar_recepcion"),
]

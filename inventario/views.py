from django.shortcuts import render
from .models import Articulo


def lista_articulos(request):
    """
    Muestra el listado de artículos con su stock actual
    y una marca visual cuando están por debajo del stock mínimo.
    """
    articulos = Articulo.objects.all().order_by("codigo")
    contexto = {
        "articulos": articulos,
    }
    return render(request, "inventario/lista_articulos.html", contexto)

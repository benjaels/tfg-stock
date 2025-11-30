from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Articulo, MovimientoStock, Recepcion, RecepcionItem


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


@login_required
def registrar_recepcion_simple(request):
    """
    Registro simplificado de una recepción usando el código QR del artículo.
    - El usuario ingresa proveedor, nro de documento, código QR y cantidad.
    - Se crea una recepción confirmada, un ítem y un movimiento de stock.
    """
    if request.method == "POST":
        proveedor = request.POST.get("proveedor", "").strip()
        numero_documento = request.POST.get("numero_documento", "").strip()
        valor_qr = request.POST.get("valor_qr", "").strip()
        cantidad_str = request.POST.get("cantidad", "").strip()

        if not proveedor or not valor_qr or not cantidad_str:
            messages.error(request, "Proveedor, código QR y cantidad son obligatorios.")
            return redirect("registrar_recepcion")

        # Parsear cantidad como Decimal (no float)
        try:
            cantidad = Decimal(cantidad_str.replace(",", "."))
            if cantidad <= 0:
                raise InvalidOperation()
        except (InvalidOperation, ValueError):
            messages.error(request, "La cantidad debe ser un número mayor que cero.")
            return redirect("registrar_recepcion")

        try:
            articulo = Articulo.objects.get(codigo_qr=valor_qr)
        except Articulo.DoesNotExist:
            messages.error(request, "No se encontró un artículo con ese código QR.")
            return redirect("registrar_recepcion")

        # Crear recepción confirmada
        recepcion = Recepcion.objects.create(
            proveedor=proveedor,
            numero_documento=numero_documento,
            estado=Recepcion.ESTADO_CONFIRMADA,
            fecha_confirmacion=timezone.now(),
            creado_por=request.user,
        )

        # Crear ítem de recepción
        RecepcionItem.objects.create(
            recepcion=recepcion,
            articulo=articulo,
            cantidad=cantidad,
            valor_qr_leido=valor_qr,
        )

        # Actualizar stock y registrar movimiento
        articulo.stock_actual = (articulo.stock_actual or Decimal("0")) + cantidad
        articulo.save()

        MovimientoStock.objects.create(
            articulo=articulo,
            tipo=MovimientoStock.TIPO_INGRESO,
            cantidad=cantidad,
            observaciones=f"Recepción #{recepcion.id} - {numero_documento}",
            usuario=request.user,
        )

        messages.success(
            request,
            f"Recepción #{recepcion.id} registrada. Se ingresaron {cantidad} {articulo.unidad_medida} de {articulo.codigo}."
        )
        return redirect("lista_articulos")

    # GET: mostrar formulario vacío
    return render(request, "inventario/registrar_recepcion.html")

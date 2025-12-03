from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import F,Case, When, Value, IntegerField
from .models import Articulo, MovimientoStock, Recepcion, RecepcionItem


def lista_articulos(request):
    # Cantidad de artículos con stock por debajo del mínimo
    items_bajo_minimo = Articulo.objects.filter(
        stock_actual__lt=F("stock_minimo")
    ).count()

    # Placeholder: cuando tengas el modelo OrdenCompra, reemplazás este cálculo
    ordenes_pendientes = 0

    # Ordenar los artículos: primero los críticos (stock < mínimo), luego el resto
    articulos = (
        Articulo.objects
        .annotate(
            critico=Case(
                When(stock_actual__lt=F("stock_minimo"), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-critico", "codigo")
    )

    contexto = {
        "articulos": articulos,
        "items_bajo_minimo": items_bajo_minimo,
        "ordenes_pendientes": ordenes_pendientes,
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
@login_required
def registrar_movimiento_simple(request):
    if request.method != "POST":
        return redirect("lista_movimientos")
    """
    Registro simplificado de un movimiento de stock usando el código QR del artículo.
    Permite egresos y ajustes.
    """
    if request.method == "POST":
        tipo = request.POST.get("tipo")
        valor_qr = request.POST.get("valor_qr", "").strip()
        cantidad_str = request.POST.get("cantidad", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()

        if not tipo or not valor_qr or not cantidad_str:
            messages.error(request, "Tipo de movimiento, código QR y cantidad son obligatorios.")
            return redirect("registrar_movimiento")

        # Parsear cantidad como Decimal
        try:
            cantidad = Decimal(cantidad_str.replace(",", "."))
        except (InvalidOperation, ValueError):
            messages.error(request, "La cantidad debe ser un número válido.")
            return redirect("registrar_movimiento")

        if cantidad == 0:
            messages.error(request, "La cantidad debe ser distinta de cero.")
            return redirect("registrar_movimiento")

        # Para INGRESO y EGRESO trabajamos con valor absoluto
        cantidad_abs = cantidad.copy_abs()

        try:
            articulo = Articulo.objects.get(codigo_qr=valor_qr)
        except Articulo.DoesNotExist:
            messages.error(request, "No se encontró un artículo con ese código QR.")
            return redirect("registrar_movimiento")

        stock_actual = articulo.stock_actual or Decimal("0")

        # Calcular nuevo stock según tipo
        if tipo == MovimientoStock.TIPO_INGRESO:
            nuevo_stock = stock_actual + cantidad_abs
            cantidad_mov = cantidad_abs

        elif tipo == MovimientoStock.TIPO_EGRESO:
            # Egreso no puede dejar el stock negativo
            if cantidad_abs > stock_actual:
                messages.error(
                    request,
                    f"No hay stock suficiente para egresar {cantidad_abs}. Stock actual: {stock_actual}."
                )
                return redirect("registrar_movimiento")
            nuevo_stock = stock_actual - cantidad_abs
            cantidad_mov = cantidad_abs

        elif tipo == MovimientoStock.TIPO_AJUSTE:
            # En ajuste permitimos cantidades positivas o negativas
            nuevo_stock = stock_actual + cantidad
            if nuevo_stock < 0:
                messages.error(
                    request,
                    f"El ajuste dejaría el stock negativo ({nuevo_stock}). Operación cancelada."
                )
                return redirect("registrar_movimiento")
            cantidad_mov = cantidad  # en movimientos guardamos el ajuste tal cual (puede ser negativo)
        else:
            messages.error(request, "Tipo de movimiento inválido.")
            return redirect("registrar_movimiento")

        # Actualizar stock
        articulo.stock_actual = nuevo_stock
        articulo.save()

        # Registrar movimiento
        MovimientoStock.objects.create(
            articulo=articulo,
            tipo=tipo,
            cantidad=cantidad_mov,
            observaciones=observaciones,
            usuario=request.user,
        )

        messages.success(
            request,
            f"Movimiento registrado. Nuevo stock de {articulo.codigo}: {nuevo_stock}."
        )
        return redirect("lista_articulos")

    # GET: mostrar formulario
    return render(request, "inventario/registrar_movimiento.html")
from django.core.paginator import Paginator  # al principio del archivo, junto con los otros imports
@login_required
def lista_movimientos(request):
    # Últimos 50 movimientos, más recientes primero
    movimientos = (
        MovimientoStock.objects
        .select_related("articulo", "usuario")
        .order_by("-fecha_hora")[:50]
    )

    # Para el buscador manual de artículos (se usa en los modales)
    articulos = Articulo.objects.all().order_by("codigo")

    contexto = {
        "movimientos": movimientos,
        "articulos": articulos,
    }
    return render(request, "inventario/lista_movimientos.html", contexto)

@login_required
def lista_movimientos_parcial(request):
    """
    Vista parcial utilizada por htmx para recargar solo la tabla de movimientos.
    """
    movimientos = MovimientoStock.objects.select_related("articulo", "usuario").all()
    paginator = Paginator(movimientos, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    contexto = {
        "page_obj": page_obj,
    }
    return render(request, "inventario/_lista_movimientos_table.html", contexto)
@login_required
def lista_insumos(request):
    articulos = Articulo.objects.all().order_by("codigo")
    contexto = {
        "articulos": articulos,
    }
    return render(request, "inventario/lista_insumos.html", contexto)

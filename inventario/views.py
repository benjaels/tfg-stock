from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import F,Case, When, Value, IntegerField, Q
from .models import Articulo, MovimientoStock, Recepcion, RecepcionItem, Categoria


@login_required
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
            return redirect("registrar_recepcion_simple")

        # Parsear cantidad como Decimal (no float)
        try:
            cantidad = Decimal(cantidad_str.replace(",", "."))
            if cantidad <= 0:
                raise InvalidOperation()
        except (InvalidOperation, ValueError):
            messages.error(request, "La cantidad debe ser un número mayor que cero.")
            return redirect("registrar_recepcion_simple")

        try:
            articulo = Articulo.objects.get(codigo_qr=valor_qr)
        except Articulo.DoesNotExist:
            messages.error(request, "No se encontró un artículo con ese código QR.")
            return redirect("registrar_recepcion_simple")

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
    """
    Registro simplificado de un movimiento de stock usando el código QR del artículo.
    Permite ingresos, egresos y ajustes.
    """
    if request.method != "POST":
        return redirect("lista_movimientos")
    
    tipo = request.POST.get("tipo")
    valor_qr = request.POST.get("valor_qr", "").strip()
    cantidad_str = request.POST.get("cantidad", "").strip()
    observaciones = request.POST.get("observaciones", "").strip()

    if not tipo or not valor_qr or not cantidad_str:
        messages.error(request, "Tipo de movimiento, código QR y cantidad son obligatorios.")
        return redirect("lista_movimientos")

    # Parsear cantidad como Decimal
    try:
        cantidad = Decimal(cantidad_str.replace(",", "."))
    except (InvalidOperation, ValueError):
        messages.error(request, "La cantidad debe ser un número válido.")
        return redirect("lista_movimientos")

    if cantidad == 0:
        messages.error(request, "La cantidad debe ser distinta de cero.")
        return redirect("lista_movimientos")

    # Para INGRESO y EGRESO trabajamos con valor absoluto
    cantidad_abs = cantidad.copy_abs()

    try:
        articulo = Articulo.objects.get(codigo_qr=valor_qr)
    except Articulo.DoesNotExist:
        messages.error(request, "No se encontró un artículo con ese código QR.")
        return redirect("lista_movimientos")

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
            return redirect("lista_movimientos")
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
            return redirect("lista_movimientos")
        cantidad_mov = cantidad  # en movimientos guardamos el ajuste tal cual (puede ser negativo)
    else:
        messages.error(request, "Tipo de movimiento inválido.")
        return redirect("lista_movimientos")

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
    return redirect("lista_movimientos")
    return render(request, "inventario/registrar_movimiento.html")

@login_required
def dashboard(request):
    # Cantidad de artículos con stock por debajo del mínimo
    items_bajo_minimo = Articulo.objects.filter(
        stock_actual__lt=F("stock_minimo")
    ).count()

    # Placeholder: cuando tengas el modelo OrdenCompra, reemplazás este cálculo
    ordenes_pendientes = 0

    # Últimos 50 movimientos, más recientes primero
    movimientos = (
        MovimientoStock.objects
        .select_related("articulo", "usuario")
        .order_by("-fecha_hora")[:50]
    )

    # Artículos ordenados por código
    articulos = Articulo.objects.all().order_by("codigo")

    contexto = {
        "items_bajo_minimo": items_bajo_minimo,
        "ordenes_pendientes": ordenes_pendientes,
        "movimientos": movimientos,
        "articulos": articulos,
    }
    return render(request, "inventario/dashboard.html", contexto)

@login_required
def lista_movimientos(request):
    # Últimos 50 movimientos, más recientes primero
    movimientos = (
        MovimientoStock.objects
        .select_related("articulo", "usuario")
        .order_by("-fecha_hora")[:50]
    )

    # Artículos ordenados por código
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
    # Filtros desde query string
    q = request.GET.get("q", "").strip()
    categoria_sel = request.GET.get("categoria", "").strip()

    articulos_qs = Articulo.objects.all()
    if q:
        articulos_qs = articulos_qs.filter(
            Q(codigo__icontains=q) | Q(descripcion__icontains=q)
        )
    if categoria_sel:
        articulos_qs = articulos_qs.filter(categoria_id=categoria_sel)

    articulos = articulos_qs.order_by("codigo")
    categorias = Categoria.objects.filter(activa=True).order_by("nombre")
    contexto = {
        "articulos": articulos,
        "categorias": categorias,
        "q": q,
        "categoria_selected": categoria_sel,
    }
    
    # Si es AJAX, devolver solo el fragmento de artículos
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "inventario/_lista_articulos.html", contexto)
    
    return render(request, "inventario/lista_insumos.html", contexto)

@login_required
def crear_articulo(request):
    """
    Crea un nuevo artículo en el sistema.
    """
    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        stock_minimo_str = request.POST.get("stock_minimo", "").strip()
        ubicacion = request.POST.get("ubicacion", "").strip()
        categoria_id = request.POST.get("categoria", "").strip()

        # Validaciones básicas
        if not codigo or not descripcion or not stock_minimo_str:
            messages.error(request, "Código, nombre y stock mínimo son obligatorios.")
            return redirect("lista_insumos")

        # Verificar si el código ya existe
        if Articulo.objects.filter(codigo=codigo).exists():
            messages.error(request, f"Ya existe un artículo con el código '{codigo}'.")
            return redirect("lista_insumos")

        # Parsear stock mínimo
        try:
            stock_minimo = Decimal(stock_minimo_str.replace(",", "."))
            if stock_minimo < 0:
                raise InvalidOperation()
        except (InvalidOperation, ValueError):
            messages.error(request, "El stock mínimo debe ser un número válido.")
            return redirect("lista_insumos")

        # Obtener la categoría si se proporcionó
        categoria = None
        if categoria_id:
            try:
                categoria = Categoria.objects.get(id=categoria_id)
            except Categoria.DoesNotExist:
                messages.warning(request, "Categoría no válida, se omitió.")

        # Generar código QR simple (puede mejorarse)
        codigo_qr = f"QR-{codigo}"

        # Crear el artículo
        articulo = Articulo.objects.create(
            codigo=codigo,
            descripcion=descripcion,
            categoria=categoria,
            stock_minimo=stock_minimo,
            ubicacion=ubicacion,
            codigo_qr=codigo_qr,
            stock_actual=Decimal("0"),
        )

        messages.success(request, f"Artículo '{codigo}' creado exitosamente.")
        return redirect("lista_insumos")

    # GET: no debería llegar aquí normalmente
    return redirect("lista_insumos")


@login_required
def crear_categoria(request):
    """
    Crea una categoría rápida desde el modal.
    """
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        if not nombre:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": "El nombre de la categoría es obligatorio."}, status=400)
            messages.error(request, "El nombre de la categoría es obligatorio.")
            return redirect("lista_insumos")

        # Evitar duplicados
        if Categoria.objects.filter(nombre__iexact=nombre).exists():
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": f"La categoría '{nombre}' ya existe."}, status=400)
            messages.error(request, f"La categoría '{nombre}' ya existe.")
            return redirect("lista_insumos")

        cat = Categoria.objects.create(nombre=nombre, descripcion=descripcion)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"id": cat.id, "nombre": cat.nombre}, status=201)

        messages.success(request, f"Categoría '{nombre}' creada.")
        return redirect("lista_insumos")

    return redirect("lista_insumos")

@login_required
def buscar_articulos_ajax(request):
    """
    Retorna lista de artículos filtrados por código, nombre o QR.
    Se usa para autocompletado en movimientos.
    """
    q = request.GET.get("q", "").strip()
    
    if len(q) < 2:
        return JsonResponse([], safe=False)
    
    articulos = Articulo.objects.filter(
        Q(codigo__icontains=q) | 
        Q(descripcion__icontains=q) | 
        Q(codigo_qr__icontains=q)
    ).values("id", "codigo", "descripcion", "codigo_qr", "ubicacion", "stock_actual", "unidad_medida")[:20]
    
    return JsonResponse(list(articulos), safe=False)

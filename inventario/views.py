from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import F,Case, When, Value, IntegerField, Q
from django.db import transaction
from .models import Articulo, MovimientoStock, Recepcion, RecepcionItem, Categoria, OrdenCompra, OrdenCompraItem, Proveedor


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

    articulos_qs = Articulo.objects.filter(activo=True)
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
        unidad_medida = request.POST.get("unidad_medida", "unidad").strip() or "unidad"

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
            unidad_medida=unidad_medida,
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
        prefijo = request.POST.get("prefijo", "").strip()
        
        print(f"DEBUG: Creando categoría - nombre={nombre}, prefijo={prefijo}, descripcion={descripcion}")

        if not nombre:
            error_msg = "El nombre de la categoría es obligatorio."
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect("lista_insumos")

        # Verificar si ya existe una categoría activa con ese nombre
        if Categoria.objects.filter(nombre__iexact=nombre, activa=True).exists():
            error_msg = f"La categoría '{nombre}' ya existe."
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect("lista_insumos")

        # Si existe una categoría inactiva con ese nombre, reactivarla
        categoria_inactiva = Categoria.objects.filter(nombre__iexact=nombre, activa=False).first()
        
        try:
            if categoria_inactiva:
                # Reactivar la categoría existente
                categoria_inactiva.activa = True
                categoria_inactiva.descripcion = descripcion
                categoria_inactiva.prefijo = prefijo
                categoria_inactiva.save()
                cat = categoria_inactiva
                print(f"DEBUG: Categoría reactivada con ID={cat.id}")
                mensaje = f"Categoría '{nombre}' reactivada"
            else:
                # Crear nueva categoría
                cat = Categoria.objects.create(nombre=nombre, descripcion=descripcion, prefijo=prefijo)
                print(f"DEBUG: Categoría creada con ID={cat.id}")
                mensaje = f"Categoría '{nombre}' creada"
            
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "id": cat.id, 
                    "nombre": cat.nombre, 
                    "prefijo": cat.prefijo
                }, status=201)

            messages.success(request, mensaje)
            return redirect("lista_insumos")
        except Exception as e:
            print(f"DEBUG: Error al crear categoría: {str(e)}")
            error_msg = f"Error al crear categoría: {str(e)}"
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": error_msg}, status=500)
            messages.error(request, error_msg)
            return redirect("lista_insumos")
            print(f"DEBUG: Categoría creada con ID={cat.id}")
            
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "id": cat.id, 
                    "nombre": cat.nombre, 
                    "prefijo": cat.prefijo
                }, status=201)

            messages.success(request, f"Categoría '{nombre}' creada.")
            return redirect("lista_insumos")
        except Exception as e:
            print(f"DEBUG: Error al crear categoría: {str(e)}")
            error_msg = f"Error al crear categoría: {str(e)}"
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": error_msg}, status=500)
            messages.error(request, error_msg)
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

@login_required
def obtener_articulo_ajax(request, articulo_id):
    """
    Retorna los datos de un artículo en JSON para editar.
    """
    try:
        articulo = Articulo.objects.select_related('categoria').get(id=articulo_id)
        categoria_prefijo = articulo.categoria.prefijo if articulo.categoria else ""
        data = {
            "id": articulo.id,
            "codigo": articulo.codigo,
            "descripcion": articulo.descripcion,
            "ubicacion": articulo.ubicacion,
            "stock_minimo": str(articulo.stock_minimo),
            "stock_actual": str(articulo.stock_actual),
            "unidad_medida": articulo.unidad_medida,
            "categoria_id": articulo.categoria_id,
            "categoria_prefijo": categoria_prefijo,
            "codigo_qr": articulo.codigo_qr,
        }
        return JsonResponse(data)
    except Articulo.DoesNotExist:
        return JsonResponse({"error": "Artículo no encontrado"}, status=404)

@login_required
def actualizar_articulo(request):
    """
    Actualiza un artículo existente.
    """
    if request.method != "POST":
        return redirect("lista_insumos")
    
    articulo_id = request.POST.get("articulo_id")
    
    try:
        articulo = Articulo.objects.get(id=articulo_id)
    except Articulo.DoesNotExist:
        messages.error(request, "Artículo no encontrado.")
        return redirect("lista_insumos")
    
    codigo = request.POST.get("codigo", "").strip()
    descripcion = request.POST.get("descripcion", "").strip()
    ubicacion = request.POST.get("ubicacion", "").strip()
    stock_minimo = request.POST.get("stock_minimo", "0")
    unidad_medida = request.POST.get("unidad_medida", "").strip()
    categoria_id = request.POST.get("categoria", "")
    
    # Validaciones
    if not codigo or not descripcion:
        messages.error(request, "Código y descripción son obligatorios.")
        return redirect("lista_insumos")
    
    # Verificar que el código sea único (permitiendo el mismo artículo)
    if Articulo.objects.filter(codigo=codigo).exclude(id=articulo_id).exists():
        messages.error(request, f"Ya existe un artículo con el código '{codigo}'.")
        return redirect("lista_insumos")
    
    try:
        stock_minimo = Decimal(stock_minimo)
    except (InvalidOperation, ValueError):
        messages.error(request, "Stock mínimo debe ser un número válido.")
        return redirect("lista_insumos")
    
    # Actualizar artículo
    articulo.codigo = codigo
    articulo.descripcion = descripcion
    articulo.ubicacion = ubicacion
    articulo.stock_minimo = stock_minimo
    articulo.unidad_medida = unidad_medida
    if categoria_id:
        articulo.categoria_id = categoria_id
    articulo.save()
    
    messages.success(request, f"Artículo '{codigo}' actualizado correctamente.")
    return redirect("lista_insumos")

@login_required
def eliminar_articulo(request, articulo_id):
    """
    Marca un artículo como inactivo y registra un movimiento en el historial.
    Renombra el código agregando [INACTIVO-ID] para permitir reutilizar el código.
    """
    try:
        articulo = Articulo.objects.get(id=articulo_id)
        codigo_original = articulo.codigo
        descripcion = articulo.descripcion
        
        # Renombrar el código agregando [INACTIVO-ID] para permitir reutilizar
        articulo.codigo = f"{codigo_original} [INACTIVO-{articulo.id}]"
        articulo.activo = False
        articulo.save()
        
        # Registrar movimiento de eliminación en el historial
        MovimientoStock.objects.create(
            articulo=articulo,
            tipo=MovimientoStock.TIPO_ELIMINACION,
            cantidad=0,
            observaciones=f"Artículo '{codigo_original} - {descripcion}' marcado como inactivo. Código renombrado para permitir reutilización.",
            usuario=request.user,
        )
        
        messages.success(
            request, 
            f"Artículo '{codigo_original}' marcado como inactivo. Ahora puedes crear un nuevo artículo con el código '{codigo_original}'."
        )
    except Articulo.DoesNotExist:
        messages.error(request, "Artículo no encontrado.")
    
    return redirect("lista_insumos")


@login_required
def eliminar_categoria(request, categoria_id):
    """
    Marca una categoría como inactiva.
    Verifica que no tenga artículos activos antes de permitir la eliminación.
    """
    try:
        categoria = Categoria.objects.get(id=categoria_id)
        nombre_categoria = categoria.nombre
        
        # Verificar si hay artículos activos en esta categoría
        articulos_activos = Articulo.objects.filter(categoria=categoria, activo=True)
        
        if articulos_activos.exists():
            # Si hay artículos, listar los códigos
            codigos = ", ".join([art.codigo for art in articulos_activos])
            messages.error(
                request,
                f"No se puede eliminar '{nombre_categoria}' porque tiene artículos activos: {codigos}. "
                f"Marca primero estos artículos como inactivos."
            )
        else:
            # Marcar como inactiva
            categoria.activa = False
            categoria.save()
            messages.success(request, f"Categoría '{nombre_categoria}' marcada como inactiva.")
    except Categoria.DoesNotExist:
        messages.error(request, "Categoría no encontrada.")
    
    return redirect("lista_insumos")


@login_required
def lista_proveedores(request):
    """
    Lista y crea proveedores.
    """
    proveedores = Proveedor.objects.all().order_by("razon_social")

    if request.method == "POST":
        razon_social = request.POST.get("razon_social", "").strip()
        cuit = request.POST.get("cuit", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        correo = request.POST.get("correo", "").strip()
        forma_pago = request.POST.get("forma_pago", Proveedor.FORMA_CONTADO)

        if not razon_social or not cuit or not telefono or not correo or not forma_pago:
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect("lista_proveedores")

        if forma_pago not in dict(Proveedor.FORMA_PAGO_CHOICES):
            messages.error(request, "Forma de pago inválida.")
            return redirect("lista_proveedores")

        if Proveedor.objects.filter(cuit=cuit).exists():
            messages.error(request, "Ya existe un proveedor con ese CUIT.")
            return redirect("lista_proveedores")

        Proveedor.objects.create(
            razon_social=razon_social,
            cuit=cuit,
            telefono=telefono,
            correo=correo,
            forma_pago=forma_pago,
        )
        messages.success(request, f"Proveedor '{razon_social}' creado.")
        return redirect("lista_proveedores")

    contexto = {
        "proveedores": proveedores,
        "section": "proveedores",
    }
    return render(request, "inventario/lista_proveedores.html", contexto)


@login_required
def lista_ordenes(request):
    """
    Lista y crea órdenes de compra.
    """
    articulos = Articulo.objects.filter(activo=True).order_by("codigo")
    proveedor_sel = request.GET.get("proveedor", "").strip()

    ordenes_qs = OrdenCompra.objects.select_related("proveedor").prefetch_related("items__articulo")
    if proveedor_sel:
        ordenes_qs = ordenes_qs.filter(proveedor_id=proveedor_sel)
    ordenes = (
        ordenes_qs
        .annotate(
            pendiente_first=Case(
                When(estado=OrdenCompra.ESTADO_PENDIENTE, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("pendiente_first", "-fecha_creacion")
    )
    proveedores = Proveedor.objects.all().order_by("razon_social")

    if request.method == "POST":
        proveedor_id = request.POST.get("proveedor", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()
        articulos_ids = request.POST.getlist("item_articulo")
        cantidades_str = request.POST.getlist("item_cantidad")

        if not proveedor_id:
            messages.error(request, "El proveedor es obligatorio.")
            return redirect("lista_ordenes")

        try:
            proveedor = Proveedor.objects.get(id=proveedor_id)
        except Proveedor.DoesNotExist:
            messages.error(request, "Proveedor inválido.")
            return redirect("lista_ordenes")

        items = []
        for art_id, cant_str in zip(articulos_ids, cantidades_str):
            art_id = art_id.strip()
            cant_str = cant_str.strip()
            if not art_id or not cant_str:
                continue
            try:
                cantidad = Decimal(cant_str.replace(",", "."))
                if cantidad <= 0:
                    raise InvalidOperation()
            except (InvalidOperation, ValueError):
                messages.error(request, "Las cantidades deben ser números mayores que cero.")
                return redirect("lista_ordenes")
            try:
                articulo = Articulo.objects.get(id=art_id, activo=True)
            except Articulo.DoesNotExist:
                messages.error(request, "Alguno de los artículos seleccionados no es válido.")
                return redirect("lista_ordenes")
            items.append((articulo, cantidad))

        if not items:
            messages.error(request, "Debe agregar al menos un artículo a la orden.")
            return redirect("lista_ordenes")

        try:
            with transaction.atomic():
                orden = OrdenCompra.objects.create(
                    proveedor=proveedor,
                    observaciones=observaciones,
                    creado_por=request.user,
                )
                for articulo, cantidad in items:
                    OrdenCompraItem.objects.create(
                        orden=orden,
                        articulo=articulo,
                        cantidad=cantidad,
                    )
            messages.success(request, f"Orden de compra #{orden.numero} creada. Queda pendiente de recepción.")
        except Exception as e:
            messages.error(request, f"No se pudo crear la orden: {e}")

        return redirect("lista_ordenes")

    contexto = {
        "articulos": articulos,
        "ordenes": ordenes,
        "section": "ordenes",
        "proveedores": proveedores,
        "proveedor_sel": proveedor_sel,
    }
    return render(request, "inventario/lista_ordenes.html", contexto)


@login_required
def recibir_orden_compra(request, orden_id):
    """
    Registra la recepción de una orden de compra y actualiza stock.
    """
    try:
        orden = OrdenCompra.objects.prefetch_related("items__articulo").get(id=orden_id)
    except OrdenCompra.DoesNotExist:
        messages.error(request, "Orden de compra no encontrada.")
        return redirect("lista_ordenes")

    if orden.estado == OrdenCompra.ESTADO_RECIBIDA:
        messages.info(request, f"La orden #{orden.numero} ya fue recibida.")
        return redirect("lista_ordenes")

    if request.method != "POST":
        messages.error(request, "Acción no permitida.")
        return redirect("lista_ordenes")

    try:
        with transaction.atomic():
            recepcion = Recepcion.objects.create(
                proveedor=orden.proveedor.razon_social if orden.proveedor else "",
                numero_documento=f"OC-{orden.numero}",
                estado=Recepcion.ESTADO_CONFIRMADA,
                fecha_confirmacion=timezone.now(),
                creado_por=request.user,
            )

            for item in orden.items.all():
                articulo = item.articulo
                cantidad = item.cantidad

                articulo.stock_actual = (articulo.stock_actual or Decimal("0")) + cantidad
                articulo.save()

                RecepcionItem.objects.create(
                    recepcion=recepcion,
                    articulo=articulo,
                    cantidad=cantidad,
                    valor_qr_leido=articulo.codigo_qr,
                )

                MovimientoStock.objects.create(
                    articulo=articulo,
                    tipo=MovimientoStock.TIPO_INGRESO,
                    cantidad=cantidad,
                    observaciones=f"Recepción de OC #{orden.numero}",
                    usuario=request.user,
                )

            orden.estado = OrdenCompra.ESTADO_RECIBIDA
            orden.fecha_recepcion = timezone.now()
            orden.save(update_fields=["estado", "fecha_recepcion"])

        messages.success(request, f"Orden #{orden.numero} recibida y stock actualizado.")
    except Exception as e:
        messages.error(request, f"No se pudo registrar la recepción: {e}")

    return redirect("lista_ordenes")


@login_required
def eliminar_orden_compra(request, orden_id):
    """
    Elimina una orden de compra pendiente.
    """
    try:
        orden = OrdenCompra.objects.get(id=orden_id)
    except OrdenCompra.DoesNotExist:
        messages.error(request, "Orden de compra no encontrada.")
        return redirect("lista_ordenes")

    if request.method != "POST":
        messages.error(request, "Acción no permitida.")
        return redirect("lista_ordenes")

    if orden.estado == OrdenCompra.ESTADO_RECIBIDA:
        messages.error(request, f"La orden #{orden.numero} ya está recibida y no puede eliminarse.")
        return redirect("lista_ordenes")

    orden.delete()
    messages.success(request, f"Orden #{orden.numero} eliminada.")
    return redirect("lista_ordenes")


from django.contrib import admin
from .models import (
    Articulo,
    MovimientoStock,
    Recepcion,
    RecepcionItem,
    OrdenCompra,
    OrdenCompraItem,
    Proveedor,
)


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion", "stock_actual", "stock_minimo", "ubicacion", "activo")
    search_fields = ("codigo", "descripcion", "codigo_qr")
    list_filter = ("activo",)
    ordering = ("codigo",)
    actions = ["delete_selected"]
    actions_on_top = True
    actions_on_bottom = True


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("fecha_hora", "articulo", "tipo", "cantidad", "usuario")
    list_filter = ("tipo", "fecha_hora")
    search_fields = ("articulo__codigo", "articulo__descripcion")
    ordering = ("-fecha_hora",)
    actions = ["delete_selected"]
    actions_on_top = True
    actions_on_bottom = True


class RecepcionItemInline(admin.TabularInline):
    model = RecepcionItem
    extra = 0


@admin.register(Recepcion)
class RecepcionAdmin(admin.ModelAdmin):
    list_display = ("id", "proveedor", "estado", "fecha_creacion", "fecha_confirmacion", "creado_por")
    list_filter = ("estado", "fecha_creacion")
    search_fields = ("proveedor", "numero_documento")
    inlines = [RecepcionItemInline]
    actions = ["delete_selected"]
    actions_on_top = True
    actions_on_bottom = True


class OrdenCompraItemInline(admin.TabularInline):
    model = OrdenCompraItem
    extra = 0


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ("numero", "proveedor", "estado", "fecha_creacion", "fecha_recepcion", "creado_por")
    list_filter = ("estado", "fecha_creacion")
    search_fields = ("proveedor", "numero")
    inlines = [OrdenCompraItemInline]
    actions = ["delete_selected"]
    actions_on_top = True
    actions_on_bottom = True


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "cuit", "telefono", "correo", "forma_pago")
    search_fields = ("razon_social", "cuit", "correo")
    list_filter = ("forma_pago",)
    ordering = ("razon_social",)
    actions = ["delete_selected"]

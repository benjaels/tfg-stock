from django.contrib import admin
from .models import Articulo, MovimientoStock, Recepcion, RecepcionItem


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion", "stock_actual", "stock_minimo", "ubicacion", "activo")
    search_fields = ("codigo", "descripcion", "codigo_qr")
    list_filter = ("activo",)
    ordering = ("codigo",)


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("fecha_hora", "articulo", "tipo", "cantidad", "usuario")
    list_filter = ("tipo", "fecha_hora")
    search_fields = ("articulo__codigo", "articulo__descripcion")
    ordering = ("-fecha_hora",)


class RecepcionItemInline(admin.TabularInline):
    model = RecepcionItem
    extra = 0


@admin.register(Recepcion)
class RecepcionAdmin(admin.ModelAdmin):
    list_display = ("id", "proveedor", "estado", "fecha_creacion", "fecha_confirmacion", "creado_por")
    list_filter = ("estado", "fecha_creacion")
    search_fields = ("proveedor", "numero_documento")
    inlines = [RecepcionItemInline]

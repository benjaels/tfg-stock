# stock_app/urls.py  (URLS DEL PROYECTO)
from django.contrib import admin
from django.urls import path, include

# Acá importamos las vistas DESDE LA APP inventario
from inventario import views

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),

    # Autenticación: /accounts/login/, /accounts/logout/, etc.
    path('accounts/', include('django.contrib.auth.urls')),

    # --------- RUTAS PRINCIPALES DEL SISTEMA ---------
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    path('insumos/', views.lista_insumos, name='lista_insumos'),
    path('insumos/crear/', views.crear_articulo, name='crear_articulo'),
    path('insumos/actualizar/', views.actualizar_articulo, name='actualizar_articulo'),
    path('insumos/<int:articulo_id>/obtener/', views.obtener_articulo_ajax, name='obtener_articulo_ajax'),
    path('insumos/<int:articulo_id>/eliminar/', views.eliminar_articulo, name='eliminar_articulo'),
    path('insumos/categorias/crear/', views.crear_categoria, name='crear_categoria'),
    path('insumos/categorias/<int:categoria_id>/eliminar/', views.eliminar_categoria, name='eliminar_categoria'),
    path('api/articulos/buscar/', views.buscar_articulos_ajax, name='buscar_articulos_ajax'),

    path('recepciones/nueva/', views.registrar_recepcion_simple, name='registrar_recepcion_simple'),
    path('movimientos/nuevo/', views.registrar_movimiento_simple, name='registrar_movimiento'),
    path('movimientos/', views.lista_movimientos, name='lista_movimientos'),

    path('ordenes/', views.lista_ordenes, name='lista_ordenes'),
    path('ordenes/<int:orden_id>/recibir/', views.recibir_orden_compra, name='recibir_orden_compra'),
    path('ordenes/<int:orden_id>/eliminar/', views.eliminar_orden_compra, name='eliminar_orden_compra'),

    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
]

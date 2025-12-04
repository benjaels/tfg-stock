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
    path('insumos/categorias/crear/', views.crear_categoria, name='crear_categoria'),
    path('api/articulos/buscar/', views.buscar_articulos_ajax, name='buscar_articulos_ajax'),

    path('recepciones/nueva/', views.registrar_recepcion_simple, name='registrar_recepcion_simple'),
    path('movimientos/nuevo/', views.registrar_movimiento_simple, name='registrar_movimiento'),
    path('movimientos/', views.lista_movimientos, name='lista_movimientos'),
]

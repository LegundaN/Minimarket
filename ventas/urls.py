from django.urls import path

from . import views

app_name = "ventas"

urlpatterns = [
    # Cajero (la pantalla principal de cobro está en minimarket/urls.py con el nombre "caja")
    path("caja/abrir/", views.abrir_caja, name="abrir_caja"),
    path("caja/buscar/", views.buscar_producto, name="buscar_producto"),
    path("caja/clientes/buscar/", views.buscar_cliente, name="buscar_cliente"),
    path("caja/clientes/nuevo/", views.crear_cliente, name="crear_cliente"),
    path("caja/confirmar/", views.confirmar_venta, name="confirmar_venta"),
    path("caja/precios/", views.consultar_precio, name="consultar_precio"),
    path("caja/caja-chica/", views.caja_chica, name="caja_chica"),
    path("caja/cerrar/", views.cerrar_caja, name="cerrar_caja"),

    # Anular venta (cajero o administrador)
    path("ventas/<int:pk>/anular/", views.anular_venta, name="anular_venta"),

    # Administrador
    path("panel/cobros/", views.historial, name="historial"),
    path("panel/cobros/descargar/", views.descargar_movimientos, name="descargar_movimientos"),
    path("panel/cobros/<int:pk>/", views.detalle_venta, name="detalle_venta"),
    path("panel/cajas/", views.cajas, name="cajas"),
    path("panel/cajas/<int:pk>/", views.detalle_caja, name="detalle_caja"),
    path("panel/clientes/", views.clientes, name="clientes"),
    path("panel/clientes/<int:pk>/editar/", views.editar_cliente, name="editar_cliente"),
]

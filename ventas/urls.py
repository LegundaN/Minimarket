from django.urls import path

from . import views

app_name = "ventas"

urlpatterns = [
    # Cajero (la pantalla principal de cobro está en minimarket/urls.py con el nombre "caja")
    path("caja/abrir/", views.abrir_caja, name="abrir_caja"),
    path("caja/buscar/", views.buscar_producto, name="buscar_producto"),
    path("caja/confirmar/", views.confirmar_venta, name="confirmar_venta"),
    path("caja/precios/", views.consultar_precio, name="consultar_precio"),
    path("caja/caja-chica/", views.caja_chica, name="caja_chica"),
    path("caja/cerrar/", views.cerrar_caja, name="cerrar_caja"),

    # Administrador
    path("panel/cobros/", views.historial, name="historial"),
    path("panel/cobros/<int:pk>/", views.detalle_venta, name="detalle_venta"),
    path("panel/cajas/", views.cajas, name="cajas"),
    path("panel/cajas/<int:pk>/", views.detalle_caja, name="detalle_caja"),
]

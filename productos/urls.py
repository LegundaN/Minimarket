from django.urls import path

from . import views

app_name = "productos"

# Todo cuelga de /panel/ (ver minimarket/urls.py)
urlpatterns = [
    path("productos/", views.lista, name="lista"),
    path("productos/nuevo/", views.nuevo, name="nuevo"),
    path("productos/<int:pk>/editar/", views.editar, name="editar"),
    path("productos/<int:pk>/eliminar/", views.eliminar, name="eliminar"),
    path("productos/importar/", views.importar, name="importar"),
    path("productos/exportar/", views.exportar, name="exportar"),
    path("productos/planilla-modelo/", views.descargar_modelo, name="planilla_modelo"),

    # Sprint 4 - Promociones
    path("promociones/", views.promociones, name="promociones"),
    path("promociones/nueva/", views.nueva_promocion, name="nueva_promocion"),
    path("promociones/<int:pk>/editar/", views.editar_promocion, name="editar_promocion"),
    path("promociones/<int:pk>/eliminar/", views.eliminar_promocion, name="eliminar_promocion"),
]

from django.urls import path

from . import views

app_name = "productos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar, name="eliminar"),
    path("importar/", views.importar, name="importar"),
    path("exportar/", views.exportar, name="exportar"),
    path("planilla-modelo/", views.descargar_modelo, name="planilla_modelo"),
]

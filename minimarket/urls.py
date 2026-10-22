from django.contrib import admin
from django.urls import include, path

from ventas.views import cobro

urlpatterns = [
    path("admin/", admin.site.urls),  # panel técnico de Django (solo el administrador)
    path("caja/", cobro, name="caja"),  # pantalla principal del cajero
    path("panel/productos/", include("productos.urls")),
    path("", include("ventas.urls")),
    path("", include("usuarios.urls")),
]

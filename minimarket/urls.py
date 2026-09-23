from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),  # panel técnico de Django (solo el administrador)
    path("", include("usuarios.urls")),
]

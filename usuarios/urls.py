from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # HU01 - Login / logout
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # HU10 - Cada rol va a su pantalla
    path("", views.inicio, name="inicio"),
    path("panel/", views.panel_admin, name="panel_admin"),
    path("caja/", views.caja, name="caja"),

    # HU02 - Gestión de cajeros
    path("panel/cajeros/", views.lista_cajeros, name="lista_cajeros"),
    path("panel/cajeros/nuevo/", views.alta_cajero, name="alta_cajero"),
    path("panel/cajeros/<int:pk>/editar/", views.editar_cajero, name="editar_cajero"),
    path("panel/cajeros/<int:pk>/password/", views.resetear_password, name="resetear_password"),
    path("panel/cajeros/<int:pk>/estado/", views.cambiar_estado_cajero, name="cambiar_estado_cajero"),
]

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # HU01 - Login / logout
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Recuperación de contraseña por mail (pedido de la revisión del Sprint 1)
    # (los nombres de plantilla van explícitos: si no, Django usa las del panel /admin)
    path("recuperar/", auth_views.PasswordResetView.as_view(
        template_name="usuarios/recuperar_form.html",
        subject_template_name="registration/recuperar_asunto.txt",
        email_template_name="registration/recuperar_mail.txt"), name="password_reset"),
    path("recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(
        template_name="usuarios/recuperar_done.html"), name="password_reset_done"),
    path("recuperar/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="usuarios/recuperar_confirm.html"), name="password_reset_confirm"),
    path("recuperar/listo/", auth_views.PasswordResetCompleteView.as_view(
        template_name="usuarios/recuperar_complete.html"), name="password_reset_complete"),

    # HU10 - Cada rol va a su pantalla
    path("", views.inicio, name="inicio"),
    path("panel/", views.panel_admin, name="panel_admin"),
    path("panel/mi-mail/", views.mi_mail, name="mi_mail"),

    # HU02 - Gestión de cajeros
    path("panel/cajeros/", views.lista_cajeros, name="lista_cajeros"),
    path("panel/cajeros/nuevo/", views.alta_cajero, name="alta_cajero"),
    path("panel/cajeros/<int:pk>/editar/", views.editar_cajero, name="editar_cajero"),
    path("panel/cajeros/<int:pk>/password/", views.resetear_password, name="resetear_password"),
    path("panel/cajeros/<int:pk>/estado/", views.cambiar_estado_cajero, name="cambiar_estado_cajero"),
]

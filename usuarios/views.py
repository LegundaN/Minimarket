from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CajeroAltaForm, CajeroEdicionForm, ResetearPasswordForm
from .roles import CAJERO, es_administrador, es_cajero, solo_administrador, solo_cajero


# ---------- HU01 / HU10: a dónde va cada rol después del login ----------

@login_required
def inicio(request):
    if es_administrador(request.user):
        return redirect("panel_admin")
    if es_cajero(request.user):
        return redirect("caja")
    # Usuario sin rol asignado: no debería pasar, pero por las dudas no lo dejamos entrar
    raise PermissionDenied


@solo_administrador
def panel_admin(request):
    return render(request, "usuarios/panel_admin.html")


@solo_cajero
def caja(request):
    # Pantalla provisoria: la pantalla de cobro real se arma en el Sprint 2
    return render(request, "usuarios/caja.html")


# ---------- HU02: gestión de cajeros (solo administrador) ----------

def _cajeros():
    return User.objects.filter(groups__name=CAJERO)


def _obtener_cajero(pk):
    # Solo se pueden gestionar cajeros: el administrador no puede
    # desactivarse ni editarse a sí mismo desde acá.
    return get_object_or_404(_cajeros(), pk=pk)


@solo_administrador
def lista_cajeros(request):
    cajeros = _cajeros().order_by("-is_active", "last_name", "first_name")
    return render(request, "usuarios/lista_cajeros.html", {"cajeros": cajeros})


@solo_administrador
def alta_cajero(request):
    form = CajeroAltaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cajero = form.save()
        cajero.groups.add(Group.objects.get(name=CAJERO))
        messages.success(request, f"Cajero {cajero.get_full_name()} creado.")
        return redirect("lista_cajeros")
    return render(request, "usuarios/form_cajero.html", {"form": form, "titulo": "Nuevo cajero"})


@solo_administrador
def editar_cajero(request, pk):
    cajero = _obtener_cajero(pk)
    form = CajeroEdicionForm(request.POST or None, instance=cajero)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos actualizados.")
        return redirect("lista_cajeros")
    return render(request, "usuarios/form_cajero.html",
                  {"form": form, "titulo": f"Editar a {cajero.get_full_name()}"})


@solo_administrador
def resetear_password(request, pk):
    cajero = _obtener_cajero(pk)
    form = ResetearPasswordForm(cajero, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Contraseña de {cajero.get_full_name()} reseteada.")
        return redirect("lista_cajeros")
    return render(request, "usuarios/form_cajero.html",
                  {"form": form, "titulo": f"Nueva contraseña para {cajero.get_full_name()}"})


@require_POST
@solo_administrador
def cambiar_estado_cajero(request, pk):
    """Activa o desactiva. Nunca se borra, para conservar el historial de turnos y ventas."""
    cajero = _obtener_cajero(pk)
    cajero.is_active = not cajero.is_active
    cajero.save(update_fields=["is_active"])
    estado = "activado" if cajero.is_active else "desactivado"
    messages.success(request, f"{cajero.get_full_name()} {estado}.")
    return redirect("lista_cajeros")

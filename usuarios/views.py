from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import CajeroAltaForm, CajeroEdicionForm, MiMailForm, ResetearPasswordForm
from .roles import CAJERO, es_administrador, es_cajero, solo_administrador


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
    accesos = [
        (reverse("productos:lista"), "bi-box-seam", "Productos", "Precios, costos, stock y planillas de Excel."),
        (reverse("productos:promociones"), "bi-tags", "Promociones", "Armá combos de productos con un precio especial."),
        (reverse("ventas:historial"), "bi-receipt", "Historial de cobros", "Ventas con fecha, hora y cajero. Descargá los movimientos del día."),
        (reverse("ventas:cajas"), "bi-cash-stack", "Cajas", "Aperturas, cierres, faltantes y sobrantes de cada turno."),
        (reverse("ventas:clientes"), "bi-person-vcard", "Clientes", "Clientes que piden comprobante con CUIT o DNI."),
        (reverse("lista_cajeros"), "bi-people", "Cajeros", "Altas, mails, contraseñas y estado."),
    ]
    return render(request, "usuarios/panel_admin.html", {"accesos": accesos})


@solo_administrador
def mi_mail(request):
    """El administrador carga su mail para poder recuperar su contraseña."""
    form = MiMailForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tu mail quedó guardado.")
        return redirect("panel_admin")
    return render(request, "usuarios/form_cajero.html", {"form": form, "titulo": "Mi mail", "volver": "panel_admin"})


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

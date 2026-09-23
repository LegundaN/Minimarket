"""
HU10 - Roles y permisos.

Hay dos roles, guardados como Grupos de Django:
- Administrador: uno solo, gestiona todo.
- Cajero: solo cobra.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ADMINISTRADOR = "Administrador"
CAJERO = "Cajero"


def es_administrador(user):
    return user.is_authenticated and user.groups.filter(name=ADMINISTRADOR).exists()


def es_cajero(user):
    return user.is_authenticated and user.groups.filter(name=CAJERO).exists()


def solo_administrador(vista):
    """Bloquea la vista para cualquiera que no sea el administrador.
    Si un cajero escribe la URL a mano, recibe un error 403 (acceso denegado)."""
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_administrador(request.user):
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


def solo_cajero(vista):
    """Bloquea la vista para cualquiera que no sea cajero."""
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_cajero(request.user):
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura

"""Pone en todas las plantillas las variables es_admin y es_cajero (para armar el menú)."""
from .roles import es_administrador, es_cajero


def rol(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"es_admin": False, "es_cajero": False}
    return {"es_admin": es_administrador(user), "es_cajero": es_cajero(user)}

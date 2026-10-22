import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from productos.models import Producto
from usuarios.roles import CAJERO, solo_administrador, solo_cajero

from .forms import AbrirCajaForm, MovimientoForm
from .models import Caja, DetalleVenta, Venta


def caja_abierta_de(usuario):
    return Caja.objects.filter(cajero=usuario, cerrada_en__isnull=True).first()


def producto_a_dict(p):
    return {"id": p.pk, "codigo": p.codigo, "nombre": p.nombre, "precio": str(p.precio),
            "categoria": p.categoria.nombre if p.categoria else ""}


# =====================================================================
#  CAJERO
# =====================================================================

@solo_cajero
def cobro(request):
    """Pantalla principal del cajero. Si no abrió la caja, primero le pide el fondo inicial."""
    caja = caja_abierta_de(request.user)
    if caja is None:
        return render(request, "ventas/abrir_caja.html", {"form": AbrirCajaForm()})
    return render(request, "ventas/cobro.html", {"caja": caja})


@require_POST
@solo_cajero
def abrir_caja(request):
    if caja_abierta_de(request.user):
        return redirect("caja")
    form = AbrirCajaForm(request.POST)
    if not form.is_valid():
        return render(request, "ventas/abrir_caja.html", {"form": form})
    Caja.objects.create(cajero=request.user, fondo_inicial=form.cleaned_data["fondo_inicial"])
    messages.success(request, "Caja abierta. ¡Buen turno!")
    return redirect("caja")


@solo_cajero
def buscar_producto(request):
    """Lo usa la pantalla de cobro:
    ?codigo=XXX -> busca el código exacto (lector de código de barras)
    ?q=texto    -> busca por nombre o parte del código (hasta 15 resultados)"""
    codigo = request.GET.get("codigo", "").strip()
    if codigo:
        producto = Producto.objects.select_related("categoria").filter(codigo=codigo).first()
        if producto is None:
            return JsonResponse({"error": f"No existe un producto con el código {codigo}."}, status=404)
        return JsonResponse({"producto": producto_a_dict(producto)})

    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"productos": []})
    productos = Producto.objects.select_related("categoria").filter(
        Q(nombre__icontains=q) | Q(codigo__icontains=q))[:15]
    return JsonResponse({"productos": [producto_a_dict(p) for p in productos]})


@require_POST
@solo_cajero
def confirmar_venta(request):
    """Recibe el carrito y el monto con el que pagó el cliente.
    IMPORTANTE: los precios NO se toman del navegador; se vuelven a leer de la base de datos."""
    caja = caja_abierta_de(request.user)
    if caja is None:
        return JsonResponse({"error": "No tenés una caja abierta."}, status=400)

    try:
        datos = json.loads(request.body)
        items = datos["items"]
        monto_recibido = Decimal(str(datos["monto_recibido"])).quantize(Decimal("0.01"))
        if not isinstance(items, list) or not items:
            raise ValueError
        cantidades = {}
        for item in items:
            pk, cantidad = int(item["id"]), int(item["cantidad"])
            if not 1 <= cantidad <= 999:
                raise ValueError
            cantidades[pk] = cantidades.get(pk, 0) + cantidad
    except (ValueError, KeyError, TypeError, InvalidOperation, json.JSONDecodeError):
        return JsonResponse({"error": "Los datos de la venta no son válidos."}, status=400)

    productos = {p.pk: p for p in Producto.objects.filter(pk__in=cantidades)}
    if len(productos) != len(cantidades):
        return JsonResponse({"error": "Algún producto del carrito ya no existe. Recargá la página."}, status=400)

    total = sum((productos[pk].precio * cant for pk, cant in cantidades.items()), Decimal("0.00"))
    if monto_recibido < total:
        return JsonResponse({"error": f"El monto recibido no alcanza. Total: ${total}."}, status=400)

    with transaction.atomic():
        venta = Venta.objects.create(caja=caja, cajero=request.user, total=total,
                                     monto_recibido=monto_recibido, vuelto=monto_recibido - total)
        DetalleVenta.objects.bulk_create([
            DetalleVenta(venta=venta, producto=productos[pk], codigo_producto=productos[pk].codigo,
                         nombre_producto=productos[pk].nombre, cantidad=cant,
                         precio_unitario=productos[pk].precio)
            for pk, cant in cantidades.items()
        ])

    return JsonResponse({"ok": True, "venta_id": venta.pk, "total": str(venta.total),
                         "vuelto": str(venta.vuelto)})


@solo_cajero
def consultar_precio(request):
    """Consulta de precios para el cajero: solo lectura."""
    q = request.GET.get("q", "").strip()
    productos = []
    if q:
        productos = Producto.objects.select_related("categoria").filter(
            Q(nombre__icontains=q) | Q(codigo__icontains=q))[:50]
    return render(request, "ventas/consultar_precio.html", {"q": q, "productos": productos})


@solo_cajero
def caja_chica(request):
    caja = caja_abierta_de(request.user)
    if caja is None:
        return redirect("caja")
    form = MovimientoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        movimiento = form.save(commit=False)
        movimiento.caja = caja
        movimiento.save()
        messages.success(request, f"{movimiento.get_tipo_display()} de ${movimiento.monto} registrado.")
        return redirect("ventas:caja_chica")
    return render(request, "ventas/caja_chica.html", {"caja": caja, "form": form})


@require_POST
@solo_cajero
def cerrar_caja(request):
    caja = caja_abierta_de(request.user)
    if caja is None:
        return redirect("caja")
    caja.cerrada_en = timezone.now()
    caja.save(update_fields=["cerrada_en"])
    return render(request, "ventas/caja_cerrada.html", {"caja": caja})


# =====================================================================
#  ADMINISTRADOR
# =====================================================================

def _cajeros():
    return User.objects.filter(groups__name=CAJERO).order_by("first_name", "last_name")


@solo_administrador
def historial(request):
    """Historial de cobros con fecha, hora y cajero."""
    ventas = Venta.objects.select_related("cajero")
    fecha = request.GET.get("fecha", "")
    cajero = request.GET.get("cajero", "")
    if fecha:
        ventas = ventas.filter(fecha_hora__date=fecha)
    if cajero.isdigit():
        ventas = ventas.filter(cajero_id=cajero)
    resumen = ventas.aggregate(total=Sum("total"))
    pagina = Paginator(ventas, 50).get_page(request.GET.get("pagina"))
    return render(request, "ventas/historial.html", {
        "pagina": pagina, "cajeros": _cajeros(), "fecha": fecha, "cajero_elegido": cajero,
        "cantidad": pagina.paginator.count, "total": resumen["total"] or 0,
    })


@solo_administrador
def detalle_venta(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("cajero", "caja"), pk=pk)
    return render(request, "ventas/detalle_venta.html", {"venta": venta})


@solo_administrador
def cajas(request):
    lista = Caja.objects.select_related("cajero")
    cajero = request.GET.get("cajero", "")
    if cajero.isdigit():
        lista = lista.filter(cajero_id=cajero)
    pagina = Paginator(lista, 30).get_page(request.GET.get("pagina"))
    return render(request, "ventas/cajas.html", {"pagina": pagina, "cajeros": _cajeros(),
                                                 "cajero_elegido": cajero})


@solo_administrador
def detalle_caja(request, pk):
    caja = get_object_or_404(Caja.objects.select_related("cajero"), pk=pk)
    return render(request, "ventas/detalle_caja.html", {"caja": caja})

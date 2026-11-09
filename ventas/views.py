import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, F, IntegerField, Q, Sum, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from productos.models import Producto, Promocion
from usuarios.roles import CAJERO, es_administrador, es_cajero, solo_administrador, solo_cajero

from .excel import movimientos_del_dia
from .forms import (AbrirCajaForm, AnularVentaForm, CerrarCajaForm, ClienteForm, MovimientoForm,
                    limpiar_documento)
from .models import Caja, Cliente, DetalleVenta, MovimientoItem, Venta

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def caja_abierta_de(usuario):
    return Caja.objects.filter(cajero=usuario, cerrada_en__isnull=True).first()


def producto_a_dict(p):
    # Ojo: nunca se manda el precio de costo al cajero
    return {"id": p.pk, "codigo": p.codigo, "nombre": p.nombre, "precio": str(p.precio),
            "categoria": p.categoria.nombre if p.categoria else "", "stock": p.stock}


def cliente_a_dict(c):
    return {"id": c.pk, "documento": c.documento, "tipo": c.tipo_documento, "nombre": c.nombre}


def promociones_activas():
    lista = []
    for promo in Promocion.objects.filter(activa=True).prefetch_related("items__producto"):
        items = list(promo.items.all())
        if items:
            # Cuántas promos se pueden armar con el stock actual
            disponibles = min(i.producto.stock // i.cantidad for i in items)
            lista.append({"id": promo.pk, "nombre": promo.nombre, "precio": str(promo.precio),
                          "detalle": promo.descripcion, "precio_normal": str(promo.precio_normal),
                          "disponibles": disponibles})
    return lista


def buscar_productos_por_texto(q, limite=15):
    """Busca por nombre o código y muestra primero los que EMPIEZAN con lo escrito
    (si escribís «alf», primero los alfajores)."""
    return (Producto.objects.select_related("categoria")
            .filter(Q(nombre__icontains=q) | Q(codigo__icontains=q))
            .annotate(orden=Case(When(Q(nombre__istartswith=q) | Q(codigo__startswith=q), then=Value(0)),
                                 default=Value(1), output_field=IntegerField()))
            .order_by("orden", "nombre")[:limite])


# =====================================================================
#  CAJERO
# =====================================================================

@solo_cajero
def cobro(request):
    """Pantalla principal del cajero. Si no abrió la caja, primero le pide el fondo inicial."""
    caja = caja_abierta_de(request.user)
    if caja is None:
        return render(request, "ventas/abrir_caja.html", {"form": AbrirCajaForm()})
    return render(request, "ventas/cobro.html", {"caja": caja, "promociones": promociones_activas()})


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
    ?q=texto    -> busca por nombre o parte del código (hasta 15 resultados). La pantalla lo va
                   llamando mientras se escribe, sin apretar Enter."""
    codigo = request.GET.get("codigo", "").strip()
    if codigo:
        producto = Producto.objects.select_related("categoria").filter(codigo=codigo).first()
        if producto is None:
            return JsonResponse({"error": f"No existe un producto con el código {codigo}."}, status=404)
        return JsonResponse({"producto": producto_a_dict(producto)})

    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"productos": []})
    return JsonResponse({"productos": [producto_a_dict(p) for p in buscar_productos_por_texto(q)]})


@solo_cajero
def buscar_cliente(request):
    """Sprint 4 - Busca clientes.
    ?q=38          -> sugerencias mientras se escribe: documentos que EMPIEZAN con esos números,
                      o nombres que contienen el texto (hasta 10)
    ?documento=XXX -> CUIT o DNI exacto"""
    if "q" in request.GET:
        texto = request.GET["q"].strip()
        numeros = limpiar_documento(texto)
        if any(c.isalpha() for c in texto):          # escribió letras: busca por nombre
            filtro = Q(nombre__icontains=texto) if len(texto) >= 2 else None
        else:                                         # escribió números: DNI/CUIT que empiezan así
            filtro = Q(documento__startswith=numeros) if len(numeros) >= 2 else None
        clientes = Cliente.objects.filter(filtro).order_by("documento")[:10] if filtro else []
        return JsonResponse({"clientes": [cliente_a_dict(c) for c in clientes]})
    documento = limpiar_documento(request.GET.get("documento"))
    cliente = Cliente.objects.filter(documento=documento).first() if documento else None
    if cliente is None:
        return JsonResponse({"error": "No hay ningún cliente con ese CUIT/DNI."}, status=404)
    return JsonResponse({"cliente": cliente_a_dict(cliente)})


@require_POST
@solo_cajero
def crear_cliente(request):
    """Sprint 4 - Alta rápida de cliente desde la ventanita del cobro."""
    try:
        datos = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos no válidos."}, status=400)
    form = ClienteForm({"documento": datos.get("documento", ""), "nombre": datos.get("nombre", ""),
                        "telefono": datos.get("telefono", ""), "email": datos.get("email", "")})
    if not form.is_valid():
        errores = " ".join(e for lista in form.errors.values() for e in lista)
        return JsonResponse({"error": errores}, status=400)
    cliente = form.save()
    return JsonResponse({"cliente": cliente_a_dict(cliente)})


def _leer_carrito(datos):
    """Devuelve ({id_producto: cantidad}, {id_promocion: cantidad}) o lanza ValueError."""
    items = datos["items"]
    if not isinstance(items, list) or not items:
        raise ValueError
    productos, promos = {}, {}
    for item in items:
        tipo = item.get("tipo", "producto")
        pk, cantidad = int(item["id"]), int(item["cantidad"])
        if not 1 <= cantidad <= 999:
            raise ValueError
        destino = promos if tipo == "promo" else productos
        if tipo not in ("producto", "promo"):
            raise ValueError
        destino[pk] = destino.get(pk, 0) + cantidad
    return productos, promos


@require_POST
@solo_cajero
def confirmar_venta(request):
    """Recibe el carrito, el medio de pago, el cliente (opcional) y el monto con el que pagó.
    IMPORTANTE: los precios NO se toman del navegador; se vuelven a leer de la base de datos."""
    caja = caja_abierta_de(request.user)
    if caja is None:
        return JsonResponse({"error": "No tenés una caja abierta."}, status=400)

    try:
        datos = json.loads(request.body)
        cant_productos, cant_promos = _leer_carrito(datos)
        medio_pago = datos.get("medio_pago", Venta.EFECTIVO)
        if medio_pago not in dict(Venta.MEDIOS_PAGO):
            raise ValueError
        cliente_id = datos.get("cliente_id")
        cliente = Cliente.objects.get(pk=int(cliente_id)) if cliente_id else None
        if medio_pago == Venta.EFECTIVO:
            monto_recibido = Decimal(str(datos["monto_recibido"])).quantize(Decimal("0.01"))
    except (ValueError, KeyError, TypeError, InvalidOperation, json.JSONDecodeError, Cliente.DoesNotExist):
        return JsonResponse({"error": "Los datos de la venta no son válidos."}, status=400)

    productos = {p.pk: p for p in Producto.objects.filter(pk__in=cant_productos)}
    promos = {p.pk: p for p in Promocion.objects.filter(pk__in=cant_promos, activa=True)
              .prefetch_related("items__producto")}
    if len(productos) != len(cant_productos) or len(promos) != len(cant_promos):
        return JsonResponse({"error": "Algún producto o promoción ya no está disponible. Recargá la página."},
                            status=400)

    total = sum((productos[pk].precio * c for pk, c in cant_productos.items()), Decimal("0.00"))
    total += sum((promos[pk].precio * c for pk, c in cant_promos.items()), Decimal("0.00"))
    if medio_pago == Venta.TARJETA:
        monto_recibido = total  # con tarjeta se cobra justo, no hay vuelto
    if monto_recibido < total:
        return JsonResponse({"error": f"El monto recibido no alcanza. Total: ${total}."}, status=400)

    # Cuánto stock hace falta de cada producto (sueltos + los que vienen dentro de las promos)
    descontar = dict(cant_productos)
    for pk, cant in cant_promos.items():
        for item in promos[pk].items.all():
            descontar[item.producto_id] = descontar.get(item.producto_id, 0) + item.cantidad * cant

    with transaction.atomic():
        # El stock nunca baja de 0: se bloquean las filas y se controla antes de vender
        en_stock = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=descontar)}
        faltan = [f"«{en_stock[pk].nombre}» (hay {en_stock[pk].stock}, pediste {cant})"
                  for pk, cant in descontar.items() if en_stock[pk].stock < cant]
        if faltan:
            return JsonResponse({"error": "No hay stock suficiente de " + ", ".join(faltan) + "."}, status=400)

        venta = Venta.objects.create(caja=caja, cajero=request.user, cliente=cliente, medio_pago=medio_pago,
                                     total=total, monto_recibido=monto_recibido, vuelto=monto_recibido - total)
        detalles = []
        for pk, cant in cant_productos.items():
            p = productos[pk]
            detalles.append(DetalleVenta(venta=venta, producto=p, codigo_producto=p.codigo, nombre_producto=p.nombre,
                                         cantidad=cant, precio_unitario=p.precio))
        for pk, cant in cant_promos.items():
            promo = promos[pk]
            componentes = [{"producto_id": i.producto_id, "cantidad": i.cantidad} for i in promo.items.all()]
            detalles.append(DetalleVenta(venta=venta, promocion=promo, codigo_producto="PROMO",
                                         nombre_producto=f"Promo: {promo.nombre}", cantidad=cant,
                                         precio_unitario=promo.precio, componentes=componentes))
        DetalleVenta.objects.bulk_create(detalles)
        # Sprint 3 - HU06: se descuenta el stock (ya se controló que alcanza)
        for pk, cant in descontar.items():
            Producto.objects.filter(pk=pk).update(stock=F("stock") - cant)

    return JsonResponse({"ok": True, "venta_id": venta.pk, "total": str(venta.total),
                         "vuelto": str(venta.vuelto), "medio_pago": venta.get_medio_pago_display()})


@solo_cajero
def consultar_precio(request):
    """Consulta de precios para el cajero: solo lectura."""
    q = request.GET.get("q", "").strip()
    productos = []
    if q:
        productos = buscar_productos_por_texto(q, limite=50)
    return render(request, "ventas/consultar_precio.html", {"q": q, "productos": productos})


@solo_cajero
def caja_chica(request):
    caja = caja_abierta_de(request.user)
    if caja is None:
        return redirect("caja")
    form = MovimientoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            movimiento = form.save(commit=False)
            movimiento.caja = caja
            movimiento.save()
            # Egreso = compra de mercadería: los productos que entraron suman stock
            MovimientoItem.objects.bulk_create([
                MovimientoItem(movimiento=movimiento, producto=p, codigo_producto=p.codigo,
                               nombre_producto=p.nombre, cantidad=cant) for p, cant in form.items])
            for p, cant in form.items:
                Producto.objects.filter(pk=p.pk).update(stock=F("stock") + cant)
        texto = f"{movimiento.get_tipo_display()} de ${movimiento.monto} registrado."
        if form.items:
            texto += f" Se sumó al stock: {movimiento.detalle_productos}."
        messages.success(request, texto)
        return redirect("ventas:caja_chica")
    return render(request, "ventas/caja_chica.html", {
        "caja": caja, "form": form, "form_cierre": CerrarCajaForm(),
        "ventas": caja.ventas.select_related("cliente")[:100],
    })


@require_POST
@solo_cajero
def cerrar_caja(request):
    """Sprint 4 - Cierre del día: se registra lo contado y queda el faltante o sobrante a nombre del cajero."""
    caja = caja_abierta_de(request.user)
    if caja is None:
        return redirect("caja")
    form = CerrarCajaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Para cerrar la caja, indicá cuánto efectivo contaste.")
        return redirect("ventas:caja_chica")
    caja.efectivo_contado = form.cleaned_data["efectivo_contado"]
    caja.cerrada_en = timezone.now()
    caja.save(update_fields=["efectivo_contado", "cerrada_en"])
    return render(request, "ventas/caja_cerrada.html", {"caja": caja})


# =====================================================================
#  ANULAR VENTA (cajero: solo las suyas; administrador: cualquiera) — siempre con la caja abierta
# =====================================================================

def _puede_anular(usuario, venta):
    if venta.anulada or not venta.caja.esta_abierta:
        return False
    if es_administrador(usuario):
        return True
    return es_cajero(usuario) and venta.cajero_id == usuario.pk


def _volver(request, venta):
    if es_administrador(request.user):
        return redirect("ventas:detalle_venta", pk=venta.pk)
    return redirect("ventas:caja_chica")


@login_required
def anular_venta(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("caja", "cajero", "cliente"), pk=pk)
    if not (es_administrador(request.user) or es_cajero(request.user)):
        raise PermissionDenied
    if es_cajero(request.user) and venta.cajero_id != request.user.pk:
        raise PermissionDenied

    if not _puede_anular(request.user, venta):
        if venta.anulada:
            messages.warning(request, f"La venta #{venta.pk} ya estaba anulada.")
        else:
            messages.error(request, "Solo se pueden anular ventas de una caja que todavía está abierta.")
        return _volver(request, venta)

    form = AnularVentaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            venta = Venta.objects.select_for_update().get(pk=venta.pk)
            if venta.anulada:  # por si dos personas la anulan al mismo tiempo
                return _volver(request, venta)
            venta.anulada = True
            venta.anulada_en = timezone.now()
            venta.anulada_por = request.user
            venta.motivo_anulacion = form.cleaned_data["motivo"]
            venta.save(update_fields=["anulada", "anulada_en", "anulada_por", "motivo_anulacion"])
            # Los productos vuelven al stock
            for d in venta.detalles.all():
                if d.componentes:
                    for comp in d.componentes:
                        Producto.objects.filter(pk=comp["producto_id"]).update(
                            stock=F("stock") + comp["cantidad"] * d.cantidad)
                elif d.producto_id:
                    Producto.objects.filter(pk=d.producto_id).update(stock=F("stock") + d.cantidad)
        devolver = f" Devolvele al cliente ${venta.total}." if venta.medio_pago == Venta.EFECTIVO else \
            " Recordá anular también el pago con tarjeta en el posnet."
        messages.success(request, f"Venta #{venta.pk} anulada.{devolver}")
        return _volver(request, venta)
    return render(request, "ventas/anular_venta.html", {"venta": venta, "form": form})


# =====================================================================
#  ADMINISTRADOR
# =====================================================================

def _cajeros():
    return User.objects.filter(groups__name=CAJERO).order_by("first_name", "last_name")


@solo_administrador
def historial(request):
    """Historial de cobros con fecha, hora y cajero."""
    ventas = Venta.objects.select_related("cajero", "cliente")
    fecha = request.GET.get("fecha", "")
    cajero = request.GET.get("cajero", "")
    estado = request.GET.get("estado", "")
    if fecha:
        ventas = ventas.filter(fecha_hora__date=fecha)
    if cajero.isdigit():
        ventas = ventas.filter(cajero_id=cajero)
    if estado == "anuladas":
        ventas = ventas.filter(anulada=True)
    elif estado == "validas":
        ventas = ventas.filter(anulada=False)
    resumen = ventas.filter(anulada=False).aggregate(total=Sum("total"))
    pagina = Paginator(ventas, 50).get_page(request.GET.get("pagina"))
    return render(request, "ventas/historial.html", {
        "pagina": pagina, "cajeros": _cajeros(), "fecha": fecha, "cajero_elegido": cajero, "estado": estado,
        "cantidad": pagina.paginator.count, "total": resumen["total"] or 0,
        "hoy": timezone.localdate().isoformat(),
    })


@solo_administrador
def detalle_venta(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("cajero", "caja", "cliente", "anulada_por"), pk=pk)
    return render(request, "ventas/detalle_venta.html", {"venta": venta,
                                                         "puede_anular": _puede_anular(request.user, venta)})


@solo_administrador
def descargar_movimientos(request):
    """Excel con los movimientos de un día: resumen, cobros, productos vendidos y movimientos de caja."""
    try:
        dia = date.fromisoformat(request.GET.get("fecha") or timezone.localdate().isoformat())
    except ValueError:
        dia = timezone.localdate()
    respuesta = HttpResponse(movimientos_del_dia(dia), content_type=TIPO_XLSX)
    respuesta["Content-Disposition"] = f'attachment; filename="movimientos_{dia.isoformat()}.xlsx"'
    return respuesta


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


@solo_administrador
def clientes(request):
    q = request.GET.get("q", "").strip()
    lista = Cliente.objects.annotate(compras=Count("ventas", filter=Q(ventas__anulada=False)),
                                     total_compras=Sum("ventas__total", filter=Q(ventas__anulada=False)))
    if q:
        lista = lista.filter(Q(nombre__icontains=q) | Q(documento__icontains=limpiar_documento(q) or q))
    pagina = Paginator(lista, 50).get_page(request.GET.get("pagina"))
    return render(request, "ventas/clientes.html", {"pagina": pagina, "q": q})


@solo_administrador
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=cliente)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error("documento", "Ya hay otro cliente con ese CUIT/DNI.")
        else:
            messages.success(request, "Cliente actualizado.")
            return redirect("ventas:clientes")
    return render(request, "ventas/form_cliente.html", {"form": form, "cliente": cliente})

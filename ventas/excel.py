"""
Descargar los movimientos de un día en Excel (administrador).

Hojas:
1. Resumen             -> totales del día y por cajero
2. Cobros              -> cada venta (también las anuladas, marcadas)
3. Productos vendidos  -> cuánto se vendió de cada producto o promoción
4. Movimientos de caja -> aperturas, ingresos, egresos y cierres con su diferencia
"""
from collections import defaultdict
from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .models import Caja, DetalleVenta, MovimientoCaja, Venta

CERO = Decimal("0.00")
FORMATO_PLATA = '"$" #,##0.00'


def _encabezado(hoja, titulos, anchos):
    hoja.append(titulos)
    for celda in hoja[hoja.max_row]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="064E3B")
    for i, ancho in enumerate(anchos):
        hoja.column_dimensions[chr(65 + i)].width = ancho
    hoja.freeze_panes = f"A{hoja.max_row + 1}"  # deja fijos los títulos al bajar


def _plata(hoja, columnas, desde=2):
    for fila in hoja.iter_rows(min_row=desde):
        for c in columnas:
            if fila[c].value is not None and not isinstance(fila[c].value, str):
                fila[c].number_format = FORMATO_PLATA


def _nombre(usuario):
    return usuario.get_full_name() or usuario.username


def _hora(dt):
    return timezone.localtime(dt).strftime("%H:%M") if dt else ""


def movimientos_del_dia(dia):
    ventas = list(Venta.objects.filter(fecha_hora__date=dia).select_related("cajero", "cliente")
                  .order_by("fecha_hora"))
    validas = [v for v in ventas if not v.anulada]
    movimientos = list(MovimientoCaja.objects.filter(fecha_hora__date=dia).select_related("caja__cajero")
                       .prefetch_related("items").order_by("fecha_hora"))
    cajas_abiertas = list(Caja.objects.filter(abierta_en__date=dia).select_related("cajero"))
    cajas_cerradas = list(Caja.objects.filter(cerrada_en__date=dia).select_related("cajero"))

    libro = Workbook()

    # ---------- 1. Resumen ----------
    hoja = libro.active
    hoja.title = "Resumen"
    hoja.append([f"Movimientos del {dia:%d/%m/%Y}"])
    hoja["A1"].font = Font(bold=True, size=14, color="064E3B")
    hoja.append([])
    _encabezado(hoja, ["Cajero", "Cobros", "Efectivo", "Tarjeta", "Total vendido", "Anulados", "Ingresos", "Egresos"],
                (24, 10, 14, 14, 16, 11, 14, 14))
    por_cajero = defaultdict(lambda: {"cobros": 0, "efectivo": CERO, "tarjeta": CERO, "anulados": 0,
                                      "ingresos": CERO, "egresos": CERO})
    for v in ventas:
        fila = por_cajero[_nombre(v.cajero)]
        if v.anulada:
            fila["anulados"] += 1
            continue
        fila["cobros"] += 1
        fila["efectivo" if v.medio_pago == Venta.EFECTIVO else "tarjeta"] += v.total
    for m in movimientos:
        fila = por_cajero[_nombre(m.caja.cajero)]
        fila["ingresos" if m.tipo == MovimientoCaja.INGRESO else "egresos"] += m.monto
    total = {"cobros": 0, "efectivo": CERO, "tarjeta": CERO, "anulados": 0, "ingresos": CERO, "egresos": CERO}
    for nombre, f in sorted(por_cajero.items()):
        hoja.append([nombre, f["cobros"], f["efectivo"], f["tarjeta"], f["efectivo"] + f["tarjeta"],
                     f["anulados"], f["ingresos"], f["egresos"]])
        for k in total:
            total[k] += f[k]
    hoja.append(["TOTAL", total["cobros"], total["efectivo"], total["tarjeta"], total["efectivo"] + total["tarjeta"],
                 total["anulados"], total["ingresos"], total["egresos"]])
    for celda in hoja[hoja.max_row]:
        celda.font = Font(bold=True)
    _plata(hoja, (2, 3, 4, 6, 7), desde=4)
    if not ventas and not movimientos:
        hoja.append([])
        hoja.append(["No hubo movimientos este día."])

    # ---------- 2. Cobros ----------
    hoja = libro.create_sheet("Cobros")
    _encabezado(hoja, ["N°", "Hora", "Cajero", "Cliente", "Medio de pago", "Total", "Pagó con", "Vuelto",
                       "Estado", "Motivo de anulación"], (8, 8, 22, 28, 14, 13, 13, 12, 11, 34))
    for v in ventas:
        cliente = f"{v.cliente.nombre} ({v.cliente.documento})" if v.cliente else "Consumidor final"
        hoja.append([v.pk, _hora(v.fecha_hora), _nombre(v.cajero), cliente, v.get_medio_pago_display(), v.total,
                     v.monto_recibido, v.vuelto, "Anulada" if v.anulada else "Válida", v.motivo_anulacion])
    _plata(hoja, (5, 6, 7))

    # ---------- 3. Productos vendidos ----------
    hoja = libro.create_sheet("Productos vendidos")
    _encabezado(hoja, ["Código", "Producto / Promoción", "Cantidad", "Total vendido"], (18, 42, 11, 15))
    vendidos = defaultdict(lambda: {"cantidad": 0, "total": CERO})
    for d in DetalleVenta.objects.filter(venta__in=validas):
        clave = (d.codigo_producto, d.nombre_producto)
        vendidos[clave]["cantidad"] += d.cantidad
        vendidos[clave]["total"] += d.subtotal
    for (codigo, nombre), f in sorted(vendidos.items(), key=lambda x: -x[1]["cantidad"]):
        hoja.append([codigo, nombre, f["cantidad"], f["total"]])
    _plata(hoja, (3,))
    for fila in hoja.iter_rows(min_row=2):
        fila[0].number_format = "@"

    # ---------- 4. Movimientos de caja ----------
    hoja = libro.create_sheet("Movimientos de caja")
    _encabezado(hoja, ["Hora", "Cajero", "Tipo", "Detalle", "Monto"], (8, 22, 18, 60, 14))
    eventos = []
    for c in cajas_abiertas:
        eventos.append((c.abierta_en, _nombre(c.cajero), "Apertura de caja", "Fondo inicial", c.fondo_inicial))
    for m in movimientos:
        detalle = f"{m.motivo} · Entró: {m.detalle_productos}" if m.detalle_productos else m.motivo
        eventos.append((m.fecha_hora, _nombre(m.caja.cajero), m.get_tipo_display(), detalle,
                        m.monto if m.tipo == MovimientoCaja.INGRESO else -m.monto))
    for c in cajas_cerradas:
        detalle = f"Esperado ${c.efectivo_esperado} · Contado ${c.efectivo_contado}" if c.efectivo_contado is not None \
            else f"Esperado ${c.efectivo_esperado}"
        eventos.append((c.cerrada_en, _nombre(c.cajero), "Cierre de caja", detalle, c.efectivo_contado))
        if c.diferencia:
            eventos.append((c.cerrada_en, _nombre(c.cajero), "Faltante" if c.diferencia < 0 else "Sobrante",
                            "Diferencia entre lo contado y lo esperado", c.diferencia))
    for momento, cajero, tipo, detalle, monto in sorted(eventos, key=lambda e: e[0]):
        hoja.append([_hora(momento), cajero, tipo, detalle, monto])
    _plata(hoja, (4,))

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()

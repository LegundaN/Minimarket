"""Tests de anular venta, stock, tarjeta, clientes, promociones en el cobro, cierre del día y
descarga de movimientos del día."""
import json
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from productos.models import Producto, Promocion, PromocionItem

from .models import Caja, Cliente, Venta


def crear_usuario(nombre, grupo):
    u = User.objects.create_user(nombre, password="Clave12345!")
    u.groups.add(Group.objects.get(name=grupo))
    return u


class Base(TestCase):
    def setUp(self):
        User.objects.all().delete()
        self.admin = crear_usuario("admin_test", "Administrador")
        self.cajero = crear_usuario("cajero_test", "Cajero")
        self.otro_cajero = crear_usuario("otro_cajero", "Cajero")
        self.coca = Producto.objects.create(codigo="C", nombre="Coca", precio=Decimal("1500"), stock=10)
        self.alfajor = Producto.objects.create(codigo="A", nombre="Alfajor", precio=Decimal("1000"), stock=10)
        self.client.force_login(self.cajero)
        self.client.post(reverse("ventas:abrir_caja"), {"fondo_inicial": "5000"})
        self.caja = Caja.objects.get(cajero=self.cajero)

    def cobrar(self, items, monto="", medio="efectivo", cliente_id=None):
        return self.client.post(reverse("ventas:confirmar_venta"), json.dumps(
            {"items": items, "monto_recibido": monto, "medio_pago": medio, "cliente_id": cliente_id}),
            content_type="application/json")

    def anular(self, venta, motivo="Se arrepintió"):
        return self.client.post(reverse("ventas:anular_venta", args=[venta.pk]), {"motivo": motivo})


class Stock(Base):
    def test_la_venta_descuenta_stock(self):
        self.cobrar([{"id": self.coca.pk, "cantidad": 3}], "5000")
        self.coca.refresh_from_db()
        self.assertEqual(self.coca.stock, 7)

    def test_no_se_vende_mas_de_lo_que_hay(self):
        r = self.cobrar([{"id": self.coca.pk, "cantidad": 12}], "20000")
        self.assertEqual(r.status_code, 400)
        self.assertIn("No hay stock suficiente", r.json()["error"])
        self.coca.refresh_from_db()
        self.assertEqual(self.coca.stock, 10)
        self.assertFalse(Venta.objects.exists())

    def test_se_puede_vender_justo_lo_que_queda(self):
        self.cobrar([{"id": self.coca.pk, "cantidad": 10}], "15000")
        self.coca.refresh_from_db()
        self.assertEqual(self.coca.stock, 0)

    def test_promo_sin_stock_de_un_componente(self):
        promo = Promocion.objects.create(nombre="Combo", precio=Decimal("2000"))
        PromocionItem.objects.create(promocion=promo, producto=self.alfajor, cantidad=6)
        # 1 promo usa 6 alfajores; con 6 sueltos más se piden 12 y hay 10
        r = self.cobrar([{"tipo": "promo", "id": promo.pk, "cantidad": 1}, {"id": self.alfajor.pk, "cantidad": 6}], "9000")
        self.assertEqual(r.status_code, 400)
        self.alfajor.refresh_from_db()
        self.assertEqual(self.alfajor.stock, 10)

    def test_el_admin_no_puede_cargar_stock_negativo(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("productos:editar", args=[self.coca.pk]),
                         {"codigo": "C", "nombre": "Coca", "precio": "1500", "stock": "-3"})
        self.coca.refresh_from_db()
        self.assertEqual(self.coca.stock, 10)


class Tarjeta(Base):
    def test_cobro_con_tarjeta_no_entra_a_la_caja(self):
        r = self.cobrar([{"id": self.coca.pk, "cantidad": 1}], medio="tarjeta")
        self.assertEqual(r.status_code, 200)
        venta = Venta.objects.get()
        self.assertEqual((venta.monto_recibido, venta.vuelto), (Decimal("1500"), Decimal("0")))
        self.assertEqual(self.caja.total_ventas_tarjeta, Decimal("1500"))
        self.assertEqual(self.caja.efectivo_esperado, Decimal("5000"))

    def test_medio_de_pago_invalido(self):
        self.assertEqual(self.cobrar([{"id": self.coca.pk, "cantidad": 1}], "2000", medio="cheque").status_code, 400)


class Clientes(Base):
    def test_alta_rapida_busqueda_y_venta_con_cliente(self):
        r = self.client.post(reverse("ventas:crear_cliente"), json.dumps(
            {"documento": "20-12345678-9", "nombre": "Oficina SA"}), content_type="application/json")
        cliente = Cliente.objects.get(documento="20123456789")
        self.assertEqual(r.json()["cliente"]["tipo"], "CUIT")
        r = self.client.get(reverse("ventas:buscar_cliente"), {"documento": "20.123.456.789"})
        self.assertEqual(r.json()["cliente"]["nombre"], "Oficina SA")
        self.cobrar([{"id": self.coca.pk, "cantidad": 1}], "1500", cliente_id=cliente.pk)
        self.assertEqual(Venta.objects.get().cliente, cliente)

    def test_documento_invalido_o_repetido(self):
        Cliente.objects.create(documento="12345678", nombre="Ana")
        for doc in ("123", "12345678"):
            r = self.client.post(reverse("ventas:crear_cliente"), json.dumps({"documento": doc, "nombre": "X"}),
                                 content_type="application/json")
            self.assertEqual(r.status_code, 400, doc)

    def test_por_defecto_es_consumidor_final(self):
        self.cobrar([{"id": self.coca.pk, "cantidad": 1}], "1500")
        self.assertIsNone(Venta.objects.get().cliente)


class PromocionesEnElCobro(Base):
    def setUp(self):
        super().setUp()
        self.promo = Promocion.objects.create(nombre="Merienda", precio=Decimal("2000"))
        PromocionItem.objects.create(promocion=self.promo, producto=self.alfajor, cantidad=2)
        PromocionItem.objects.create(promocion=self.promo, producto=self.coca, cantidad=1)

    def test_cobrar_promo_usa_su_precio_y_descuenta_componentes(self):
        self.cobrar([{"tipo": "promo", "id": self.promo.pk, "cantidad": 2}], "4000")
        venta = Venta.objects.get()
        self.assertEqual(venta.total, Decimal("4000"))
        self.alfajor.refresh_from_db(); self.coca.refresh_from_db()
        self.assertEqual((self.alfajor.stock, self.coca.stock), (6, 8))
        self.assertEqual(venta.detalles.get().nombre_producto, "Promo: Merienda")

    def test_promo_inactiva_no_se_puede_cobrar(self):
        self.promo.activa = False
        self.promo.save()
        self.assertEqual(self.cobrar([{"tipo": "promo", "id": self.promo.pk, "cantidad": 1}], "2000").status_code, 400)

    def test_la_pantalla_de_cobro_lista_las_promos_activas(self):
        self.assertContains(self.client.get(reverse("caja")), "Merienda")


class AnularVenta(Base):
    def setUp(self):
        super().setUp()
        self.cobrar([{"id": self.coca.pk, "cantidad": 2}], "3000")
        self.venta = Venta.objects.get()

    def test_cajero_anula_su_venta_y_vuelve_el_stock(self):
        self.anular(self.venta)
        self.venta.refresh_from_db(); self.coca.refresh_from_db()
        self.assertTrue(self.venta.anulada)
        self.assertEqual((self.venta.anulada_por, self.venta.motivo_anulacion), (self.cajero, "Se arrepintió"))
        self.assertEqual(self.coca.stock, 10)
        self.assertEqual(self.caja.efectivo_esperado, Decimal("5000"))  # ya no suma
        self.assertEqual(self.caja.cantidad_ventas, 0)

    def test_motivo_obligatorio(self):
        self.anular(self.venta, motivo="")
        self.venta.refresh_from_db()
        self.assertFalse(self.venta.anulada)

    def test_no_se_anula_dos_veces(self):
        self.anular(self.venta)
        self.anular(self.venta)
        self.coca.refresh_from_db()
        self.assertEqual(self.coca.stock, 10)  # no repone dos veces

    def test_otro_cajero_no_puede(self):
        self.client.force_login(self.otro_cajero)
        self.assertEqual(self.anular(self.venta).status_code, 403)

    def test_admin_puede(self):
        self.client.force_login(self.admin)
        self.anular(self.venta)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.anulada_por, self.admin)

    def test_con_la_caja_cerrada_no_se_puede(self):
        self.client.post(reverse("ventas:cerrar_caja"), {"efectivo_contado": "8000"})
        self.anular(self.venta)
        self.venta.refresh_from_db()
        self.assertFalse(self.venta.anulada)

    def test_anular_promo_repone_los_componentes(self):
        promo = Promocion.objects.create(nombre="P", precio=Decimal("2000"))
        PromocionItem.objects.create(promocion=promo, producto=self.alfajor, cantidad=2)
        self.cobrar([{"tipo": "promo", "id": promo.pk, "cantidad": 1}], "2000")
        venta = Venta.objects.filter(detalles__promocion=promo).get()
        self.anular(venta)
        self.alfajor.refresh_from_db()
        self.assertEqual(self.alfajor.stock, 10)

    def test_el_historial_marca_la_anulada_y_no_la_suma(self):
        self.anular(self.venta)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("ventas:historial"))
        self.assertContains(r, "Anulada")
        self.assertEqual(r.context["total"], 0)


class CierreDelDia(Base):
    def test_faltante_queda_registrado(self):
        self.cobrar([{"id": self.coca.pk, "cantidad": 2}], "3000")          # efectivo +3000
        self.cobrar([{"id": self.alfajor.pk, "cantidad": 1}], medio="tarjeta")  # tarjeta 1000
        r = self.client.post(reverse("ventas:cerrar_caja"), {"efectivo_contado": "7500"})
        self.caja.refresh_from_db()
        self.assertEqual(self.caja.efectivo_esperado, Decimal("8000"))
        self.assertEqual(self.caja.diferencia, Decimal("-500"))
        self.assertEqual((self.caja.total_ventas_efectivo, self.caja.total_ventas_tarjeta, self.caja.cantidad_ventas),
                         (Decimal("3000"), Decimal("1000"), 2))
        self.assertContains(r, "Faltante")

    def test_sin_contar_no_se_cierra(self):
        self.client.post(reverse("ventas:cerrar_caja"), {"efectivo_contado": ""})
        self.caja.refresh_from_db()
        self.assertIsNone(self.caja.cerrada_en)

    def test_el_admin_ve_la_diferencia(self):
        self.client.post(reverse("ventas:cerrar_caja"), {"efectivo_contado": "5200"})
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("ventas:cajas")), "Sobrante")


class MovimientosDelDia(Base):
    def test_descarga_excel_con_4_hojas(self):
        self.cobrar([{"id": self.coca.pk, "cantidad": 2}], "3000")
        self.cobrar([{"id": self.alfajor.pk, "cantidad": 1}], medio="tarjeta")
        self.anular(Venta.objects.filter(medio_pago="tarjeta").get())
        self.client.post(reverse("ventas:caja_chica"), {"tipo": "egreso", "monto": "500", "motivo": "Proveedor",
                                                       "productos": json.dumps([{"id": self.coca.pk, "cantidad": 6}])})
        self.client.force_login(self.admin)
        r = self.client.get(reverse("ventas:descargar_movimientos"), {"fecha": timezone.localdate().isoformat()})
        self.assertIn("attachment", r["Content-Disposition"])
        libro = load_workbook(BytesIO(r.content))
        self.assertEqual(libro.sheetnames, ["Resumen", "Cobros", "Productos vendidos", "Movimientos de caja"])
        cobros = [[c.value for c in f] for f in libro["Cobros"].iter_rows(min_row=2)]
        self.assertEqual(sorted(f[8] for f in cobros), ["Anulada", "Válida"])
        vendidos = [[c.value for c in f] for f in libro["Productos vendidos"].iter_rows(min_row=2)]
        self.assertEqual(vendidos, [["C", "Coca", 2, 3000]])  # la anulada no cuenta
        filas = [[c.value for c in f] for f in libro["Movimientos de caja"].iter_rows(min_row=2)]
        self.assertEqual([f[2] for f in filas], ["Apertura de caja", "Egreso"])
        self.assertIn("Coca x 6", filas[1][3])

    def test_solo_el_admin(self):
        self.assertEqual(self.client.get(reverse("ventas:descargar_movimientos")).status_code, 403)

    def test_clientes_solo_admin(self):
        self.assertEqual(self.client.get(reverse("ventas:clientes")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("ventas:clientes")).status_code, 200)


class CompraEnCajaChica(Base):
    """El egreso de caja chica es una compra: lleva productos y suma stock."""
    def egreso(self, productos, monto="12000"):
        return self.client.post(reverse("ventas:caja_chica"), {
            "tipo": "egreso", "monto": monto, "motivo": "Distribuidora", "productos": json.dumps(productos)})

    def test_egreso_suma_stock_y_resta_plata(self):
        self.egreso([{"id": self.coca.pk, "cantidad": 24}, {"id": self.alfajor.pk, "cantidad": 12}])
        self.coca.refresh_from_db(); self.alfajor.refresh_from_db()
        self.assertEqual((self.coca.stock, self.alfajor.stock), (34, 22))
        self.assertEqual(self.caja.efectivo_esperado, Decimal("-7000"))  # 5000 - 12000
        mov = self.caja.movimientos.get()
        self.assertEqual(mov.detalle_productos.count("x"), 2)

    def test_egreso_sin_productos_no_se_registra(self):
        r = self.egreso([])
        self.assertContains(r, "Agregá los productos")
        self.assertFalse(self.caja.movimientos.exists())

    def test_producto_inexistente_o_cantidad_mala(self):
        self.egreso([{"id": 99999, "cantidad": 1}])
        self.egreso([{"id": self.coca.pk, "cantidad": 0}])
        self.assertFalse(self.caja.movimientos.exists())
        self.coca.refresh_from_db()
        self.assertEqual(self.coca.stock, 10)

    def test_ingreso_no_toca_el_stock(self):
        self.client.post(reverse("ventas:caja_chica"), {"tipo": "ingreso", "monto": "300", "motivo": "Cambio",
                                                       "productos": json.dumps([{"id": self.coca.pk, "cantidad": 5}])})
        self.coca.refresh_from_db()
        self.assertEqual(self.coca.stock, 10)
        self.assertEqual(self.caja.movimientos.get().items.count(), 0)

    def test_si_se_borra_el_producto_la_compra_queda_registrada(self):
        nuevo = Producto.objects.create(codigo="N", nombre="Chicle", precio=Decimal("300"))
        self.egreso([{"id": nuevo.pk, "cantidad": 3}], monto="600")
        nuevo.delete()
        self.assertEqual(self.caja.movimientos.get().detalle_productos, "Chicle x 3")


class BusquedaMientrasSeEscribe(Base):
    def test_productos_primero_los_que_empiezan_asi(self):
        Producto.objects.create(codigo="X1", nombre="Galletitas con alfalfa", precio=Decimal("900"))
        Producto.objects.create(codigo="X2", nombre="Alfajor blanco", precio=Decimal("900"))
        r = self.client.get(reverse("ventas:buscar_producto"), {"q": "alf"})
        nombres = [p["nombre"] for p in r.json()["productos"]]
        self.assertEqual(nombres, ["Alfajor", "Alfajor blanco", "Galletitas con alfalfa"])

    def test_clientes_por_documento_que_empieza_con(self):
        Cliente.objects.create(documento="38111222", nombre="Ana")
        Cliente.objects.create(documento="38999000", nombre="Bruno")
        Cliente.objects.create(documento="20381112223", nombre="Carla SA")
        r = self.client.get(reverse("ventas:buscar_cliente"), {"q": "38"})
        self.assertEqual([c["nombre"] for c in r.json()["clientes"]], ["Ana", "Bruno"])
        r = self.client.get(reverse("ventas:buscar_cliente"), {"q": "carl"})
        self.assertEqual([c["nombre"] for c in r.json()["clientes"]], ["Carla SA"])
        r = self.client.get(reverse("ventas:buscar_cliente"), {"q": "3"})
        self.assertEqual(r.json()["clientes"], [])

    def test_las_promos_avisan_cuantas_hay(self):
        promo = Promocion.objects.create(nombre="Merienda", precio=Decimal("2000"))
        PromocionItem.objects.create(promocion=promo, producto=self.alfajor, cantidad=3)
        r = self.client.get(reverse("caja"))
        self.assertEqual(r.context["promociones"][0]["disponibles"], 3)  # 10 alfajores / 3

"""Tests de Cobro, Caja chica e Historial (Sprint 2). Correr con: python manage.py test"""
import json
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from productos.models import Producto

from .models import Caja, MovimientoCaja, Venta


def crear_usuario(nombre, grupo):
    u = User.objects.create_user(nombre, password="Clave12345!")
    u.groups.add(Group.objects.get(name=grupo))
    return u


class Base(TestCase):
    def setUp(self):
        User.objects.all().delete()
        self.admin = crear_usuario("admin_test", "Administrador")
        self.cajero = crear_usuario("cajero_test", "Cajero")
        self.coca = Producto.objects.create(codigo="7790001", nombre="Coca 500", precio=Decimal("1500"))
        self.alfajor = Producto.objects.create(codigo="7790002", nombre="Alfajor", precio=Decimal("800.50"))
        self.client.force_login(self.cajero)

    def abrir_caja(self, fondo="5000"):
        self.client.post(reverse("ventas:abrir_caja"), {"fondo_inicial": fondo})
        return Caja.objects.get(cajero=self.cajero, cerrada_en__isnull=True)

    def cobrar(self, items, monto):
        return self.client.post(reverse("ventas:confirmar_venta"),
                                json.dumps({"items": items, "monto_recibido": monto}),
                                content_type="application/json")


class CajaChica(Base):
    def test_sin_caja_abierta_pide_abrirla_y_no_deja_cobrar(self):
        r = self.client.get(reverse("caja"))
        self.assertTemplateUsed(r, "ventas/abrir_caja.html")
        r = self.cobrar([{"id": self.coca.pk, "cantidad": 1}], "1500")
        self.assertEqual(r.status_code, 400)

    def test_abrir_caja_muestra_pantalla_de_cobro(self):
        self.abrir_caja()
        self.assertTemplateUsed(self.client.get(reverse("caja")), "ventas/cobro.html")

    def test_no_se_abren_dos_cajas(self):
        self.abrir_caja()
        self.client.post(reverse("ventas:abrir_caja"), {"fondo_inicial": "100"})
        self.assertEqual(Caja.objects.filter(cajero=self.cajero, cerrada_en__isnull=True).count(), 1)

    def test_efectivo_esperado(self):
        caja = self.abrir_caja("5000")
        self.cobrar([{"id": self.coca.pk, "cantidad": 2}], "3000")                     # +3000
        self.client.post(reverse("ventas:caja_chica"), {"tipo": "egreso", "monto": "1000", "motivo": "Proveedor"})
        self.client.post(reverse("ventas:caja_chica"), {"tipo": "ingreso", "monto": "200", "motivo": "Cambio"})
        self.assertEqual(caja.efectivo_esperado, Decimal("7200"))  # 5000 + 3000 - 1000 + 200
        self.assertEqual(MovimientoCaja.objects.count(), 2)

    def test_cerrar_caja(self):
        caja = self.abrir_caja()
        self.client.post(reverse("ventas:cerrar_caja"))
        caja.refresh_from_db()
        self.assertIsNotNone(caja.cerrada_en)
        self.assertTemplateUsed(self.client.get(reverse("caja")), "ventas/abrir_caja.html")


class Cobro(Base):
    def setUp(self):
        super().setUp()
        self.abrir_caja()

    def test_buscar_por_codigo_y_por_nombre(self):
        r = self.client.get(reverse("ventas:buscar_producto"), {"codigo": "7790001"})
        self.assertEqual(r.json()["producto"]["nombre"], "Coca 500")
        self.assertEqual(self.client.get(reverse("ventas:buscar_producto"), {"codigo": "000"}).status_code, 404)
        r = self.client.get(reverse("ventas:buscar_producto"), {"q": "alfa"})
        self.assertEqual([p["nombre"] for p in r.json()["productos"]], ["Alfajor"])

    def test_cobro_con_vuelto(self):
        r = self.cobrar([{"id": self.coca.pk, "cantidad": 2}, {"id": self.alfajor.pk, "cantidad": 1}], "5000")
        self.assertEqual(r.status_code, 200)
        venta = Venta.objects.get()
        self.assertEqual(venta.total, Decimal("3800.50"))
        self.assertEqual(venta.vuelto, Decimal("1199.50"))
        self.assertEqual(venta.cajero, self.cajero)
        self.assertEqual(venta.detalles.count(), 2)

    def test_el_precio_lo_pone_el_servidor(self):
        # Aunque el navegador mande un precio trucho, se ignora
        self.cobrar([{"id": self.coca.pk, "cantidad": 1, "precio": "1"}], "1500")
        self.assertEqual(Venta.objects.get().total, Decimal("1500"))

    def test_monto_insuficiente(self):
        r = self.cobrar([{"id": self.coca.pk, "cantidad": 1}], "1000")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Venta.objects.exists())

    def test_datos_invalidos(self):
        for items in ([], [{"id": self.coca.pk, "cantidad": 0}], [{"id": 9999, "cantidad": 1}], "x"):
            self.assertEqual(self.cobrar(items, "5000").status_code, 400, items)

    def test_historial_no_cambia_si_se_modifica_o_borra_el_producto(self):
        self.cobrar([{"id": self.coca.pk, "cantidad": 1}], "1500")
        self.coca.precio = Decimal("2000")
        self.coca.save()
        self.coca.delete()
        detalle = Venta.objects.get().detalles.get()
        self.assertEqual((detalle.nombre_producto, detalle.precio_unitario), ("Coca 500", Decimal("1500")))

    def test_consultar_precio(self):
        r = self.client.get(reverse("ventas:consultar_precio"), {"q": "coca"})
        self.assertContains(r, "Coca 500")
        self.assertContains(r, "$ 1.500,00")


class Permisos(Base):
    def test_admin_no_cobra(self):
        self.client.force_login(self.admin)
        for nombre in ("caja", "ventas:consultar_precio", "ventas:caja_chica", "ventas:buscar_producto"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_cajero_no_ve_historial_ni_cajas(self):
        for nombre in ("ventas:historial", "ventas:cajas"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)


class Historial(Base):
    def test_admin_ve_cobros_con_cajero_y_horario(self):
        self.abrir_caja()
        self.cobrar([{"id": self.coca.pk, "cantidad": 1}], "2000")
        venta = Venta.objects.get()
        self.client.force_login(self.admin)
        r = self.client.get(reverse("ventas:historial"))
        self.assertContains(r, "cajero_test")
        self.assertContains(r, venta.fecha_hora.astimezone().strftime("%H:%M")[:2])
        r = self.client.get(reverse("ventas:detalle_venta", args=[venta.pk]))
        self.assertContains(r, "Coca 500")
        r = self.client.get(reverse("ventas:historial"), {"cajero": self.admin.pk})
        self.assertEqual(r.context["cantidad"], 0)

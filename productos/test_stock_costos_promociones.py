"""Tests del Sprint 3 (stock y costos) y de la sección Promociones (Sprint 4)."""
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from .models import Producto, Promocion, PromocionItem


def crear_usuario(nombre, grupo):
    u = User.objects.create_user(nombre, password="Clave12345!")
    u.groups.add(Group.objects.get(name=grupo))
    return u


def excel(filas, encabezado):
    libro = Workbook()
    hoja = libro.active
    hoja.append(encabezado)
    for f in filas:
        hoja.append(list(f))
    salida = BytesIO()
    libro.save(salida)
    return SimpleUploadedFile("p.xlsx", salida.getvalue())


class Base(TestCase):
    def setUp(self):
        User.objects.all().delete()
        self.admin = crear_usuario("admin_test", "Administrador")
        self.cajero = crear_usuario("cajero_test", "Cajero")
        self.client.force_login(self.admin)


class StockYCostos(Base):
    def test_alta_con_stock_y_costo(self):
        self.client.post(reverse("productos:nuevo"), {"codigo": "1", "nombre": "Coca", "precio": "1500",
                                                      "precio_costo": "1000", "stock": "24"})
        p = Producto.objects.get(codigo="1")
        self.assertEqual((p.stock, p.precio_costo, p.margen), (24, Decimal("1000"), Decimal("50.0")))

    def test_stock_vacio_vale_cero(self):
        self.client.post(reverse("productos:nuevo"), {"codigo": "2", "nombre": "Chicle", "precio": "300"})
        self.assertEqual(Producto.objects.get(codigo="2").stock, 0)

    def test_el_cajero_nunca_ve_el_costo(self):
        Producto.objects.create(codigo="3", nombre="Alfajor", precio=900, precio_costo=Decimal("612.34"))
        self.client.force_login(self.cajero)
        r = self.client.get(reverse("ventas:buscar_producto"), {"codigo": "3"})
        self.assertNotIn("costo", r.json()["producto"])
        r = self.client.get(reverse("ventas:consultar_precio"), {"q": "alfajor"})
        self.assertNotContains(r, "612")

    def test_importar_stock_y_costo_opcionales(self):
        Producto.objects.create(codigo="10", nombre="Viejo", precio=10, stock=7, precio_costo=5)
        archivo = excel([("10", "Viejo", 12, "", "", ""),       # vacíos: quedan como estaban
                         ("11", "Nuevo", 20, "", 30, "15,50"),
                         ("12", "Malo", 20, "", "dos", "")],
                        ["codigo", "nombre", "precio", "categoria", "stock", "costo"])
        r = self.client.post(reverse("productos:importar"), {"archivo": archivo})
        viejo, nuevo = Producto.objects.get(codigo="10"), Producto.objects.get(codigo="11")
        self.assertEqual((viejo.precio, viejo.stock, viejo.precio_costo), (Decimal("12"), 7, Decimal("5")))
        self.assertEqual((nuevo.stock, nuevo.precio_costo), (30, Decimal("15.50")))
        self.assertEqual([f for f, _ in r.context["resumen"]["errores"]], [4])


class Promociones(Base):
    def setUp(self):
        super().setUp()
        self.alfajor = Producto.objects.create(codigo="A", nombre="Alfajor", precio=1000)
        self.coca = Producto.objects.create(codigo="C", nombre="Coca", precio=1500)

    def datos(self, **extra):
        d = {"nombre": "Merienda", "precio": "2000", "activa": "on",
             "items-TOTAL_FORMS": "2", "items-INITIAL_FORMS": "0", "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
             "items-0-producto": self.alfajor.pk, "items-0-cantidad": "2",
             "items-1-producto": self.coca.pk, "items-1-cantidad": "1"}
        d.update(extra)
        return d

    def test_armar_promocion(self):
        self.client.post(reverse("productos:nueva_promocion"), self.datos())
        promo = Promocion.objects.get()
        self.assertEqual(promo.items.count(), 2)
        self.assertEqual((promo.precio_normal, promo.ahorro), (Decimal("3500"), Decimal("1500")))

    def test_necesita_al_menos_un_producto(self):
        self.client.post(reverse("productos:nueva_promocion"), self.datos(**{"items-0-producto": "", "items-1-producto": ""}))
        self.assertFalse(Promocion.objects.exists())

    def test_no_permite_producto_repetido(self):
        self.client.post(reverse("productos:nueva_promocion"), self.datos(**{"items-1-producto": self.alfajor.pk}))
        self.assertFalse(Promocion.objects.exists())

    def test_no_se_borra_un_producto_que_esta_en_una_promo(self):
        promo = Promocion.objects.create(nombre="P", precio=100)
        PromocionItem.objects.create(promocion=promo, producto=self.coca, cantidad=1)
        r = self.client.post(reverse("productos:eliminar", args=[self.coca.pk]), follow=True)
        self.assertTrue(Producto.objects.filter(pk=self.coca.pk).exists())
        self.assertContains(r, "está en la promoción")

    def test_el_cajero_no_entra(self):
        self.client.force_login(self.cajero)
        self.assertEqual(self.client.get(reverse("productos:promociones")).status_code, 403)

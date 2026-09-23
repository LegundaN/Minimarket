"""
Tests del Sprint 1. Cada test corresponde a un criterio de aceptación.
Correr con:  python manage.py test
"""
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse


class Base(TestCase):
    def setUp(self):
        call_command("crear_administrador", usuario="carlos", password="ClaveSegura123", stdout=StringIO())
        self.admin = User.objects.get(username="carlos")
        self.cajero = User.objects.create_user("juan", password="ClaveCajero123",
                                               first_name="Juan", last_name="Pérez")
        self.cajero.groups.add(Group.objects.get(name="Cajero"))


class HU01Login(Base):
    def test_login_correcto_cajero_va_a_caja(self):
        r = self.client.post(reverse("login"), {"username": "juan", "password": "ClaveCajero123"}, follow=True)
        self.assertRedirects(r, reverse("caja"))

    def test_login_correcto_admin_va_al_panel(self):
        r = self.client.post(reverse("login"), {"username": "carlos", "password": "ClaveSegura123"}, follow=True)
        self.assertRedirects(r, reverse("panel_admin"))

    def test_login_incorrecto_muestra_error(self):
        r = self.client.post(reverse("login"), {"username": "juan", "password": "mal"})
        self.assertContains(r, "Usuario o contraseña incorrectos")

    def test_sin_login_no_entra(self):
        r = self.client.get(reverse("caja"))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('caja')}")

    def test_usuario_desactivado_no_entra(self):
        self.cajero.is_active = False
        self.cajero.save()
        r = self.client.post(reverse("login"), {"username": "juan", "password": "ClaveCajero123"})
        self.assertContains(r, "Usuario o contraseña incorrectos")

    def test_logout(self):
        self.client.force_login(self.cajero)
        self.client.post(reverse("logout"))
        r = self.client.get(reverse("caja"))
        self.assertEqual(r.status_code, 302)  # vuelve a pedir login


class HU10Roles(Base):
    def test_existen_los_dos_roles(self):
        self.assertTrue(Group.objects.filter(name="Administrador").exists())
        self.assertTrue(Group.objects.filter(name="Cajero").exists())

    def test_solo_un_administrador(self):
        with self.assertRaises(CommandError):
            call_command("crear_administrador", usuario="otro", password="OtraClave123")

    def test_cajero_no_entra_a_pantallas_de_admin_ni_escribiendo_la_url(self):
        self.client.force_login(self.cajero)
        for nombre in ("panel_admin", "lista_cajeros", "alta_cajero"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)
        self.assertEqual(self.client.get(reverse("editar_cajero", args=[self.cajero.pk])).status_code, 403)

    def test_cajero_no_entra_al_admin_de_django(self):
        self.client.force_login(self.cajero)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 302)  # lo manda al login del admin


class HU02GestionUsuarios(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_alta_crea_siempre_un_cajero(self):
        self.client.post(reverse("alta_cajero"), {
            "first_name": "Ana", "last_name": "Gómez", "username": "ana",
            "password1": "ClaveNueva123", "password2": "ClaveNueva123"})
        ana = User.objects.get(username="ana")
        self.assertTrue(ana.groups.filter(name="Cajero").exists())
        self.assertFalse(ana.is_staff)

    def test_editar_cajero(self):
        self.client.post(reverse("editar_cajero", args=[self.cajero.pk]),
                         {"first_name": "Juan Carlos", "last_name": "Pérez", "username": "juan"})
        self.cajero.refresh_from_db()
        self.assertEqual(self.cajero.first_name, "Juan Carlos")

    def test_resetear_password(self):
        self.client.post(reverse("resetear_password", args=[self.cajero.pk]),
                         {"new_password1": "OtraClave456", "new_password2": "OtraClave456"})
        self.cajero.refresh_from_db()
        self.assertTrue(self.cajero.check_password("OtraClave456"))

    def test_desactivar_no_borra(self):
        self.client.post(reverse("cambiar_estado_cajero", args=[self.cajero.pk]))
        self.cajero.refresh_from_db()
        self.assertFalse(self.cajero.is_active)
        self.assertTrue(User.objects.filter(pk=self.cajero.pk).exists())

    def test_admin_no_puede_desactivarse_a_si_mismo(self):
        r = self.client.post(reverse("cambiar_estado_cajero", args=[self.admin.pk]))
        self.assertEqual(r.status_code, 404)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

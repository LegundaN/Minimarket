"""Tests de la recuperación de contraseña por mail (pedido de la revisión del Sprint 1)."""
import re

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse


class RecuperarPassword(TestCase):
    def setUp(self):
        User.objects.all().delete()
        self.cajero = User.objects.create_user("juan", "juan@ejemplo.com", "ClaveVieja123!")
        self.cajero.groups.add(Group.objects.get(name="Cajero"))

    def test_login_tiene_el_link(self):
        self.assertContains(self.client.get(reverse("login")), reverse("password_reset"))

    def test_usa_las_pantallas_del_minimarket(self):
        r = self.client.get(reverse("password_reset"))
        self.assertTemplateUsed(r, "usuarios/recuperar_form.html")
        self.assertContains(r, "Recuperar contraseña")
        self.assertNotContains(r, "Django")

    def test_flujo_completo(self):
        r = self.client.post(reverse("password_reset"), {"email": "JUAN@ejemplo.com"})
        self.assertRedirects(r, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("juan", mail.outbox[0].body)
        link = re.search(r"https?://[^/]+(/recuperar/\S+/)", mail.outbox[0].body).group(1)

        r = self.client.get(link, follow=True)  # Django redirige al link "seguro" sin el token
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "ClaveNueva456!", "new_password2": "ClaveNueva456!"})
        self.assertRedirects(r, reverse("password_reset_complete"))
        self.cajero.refresh_from_db()
        self.assertTrue(self.cajero.check_password("ClaveNueva456!"))

        # El link sirve una sola vez
        r = self.client.get(link, follow=True)
        self.assertFalse(r.context["validlink"])

    def test_mail_desconocido_no_revela_nada(self):
        r = self.client.post(reverse("password_reset"), {"email": "nadie@ejemplo.com"})
        self.assertRedirects(r, reverse("password_reset_done"))  # misma respuesta
        self.assertEqual(len(mail.outbox), 0)

    def test_usuario_desactivado_no_recibe_mail(self):
        self.cajero.is_active = False
        self.cajero.save()
        self.client.post(reverse("password_reset"), {"email": "juan@ejemplo.com"})
        self.assertEqual(len(mail.outbox), 0)


class MailDeUsuarios(TestCase):
    def setUp(self):
        User.objects.all().delete()
        self.admin = User.objects.create_superuser("carlos", password="ClaveSegura123")
        self.admin.groups.add(Group.objects.get(name="Administrador"))
        self.client.force_login(self.admin)

    def test_alta_de_cajero_pide_mail_y_no_se_repite(self):
        datos = {"first_name": "Ana", "last_name": "Gómez", "username": "ana", "email": "ana@ejemplo.com",
                 "password1": "ClaveNueva123", "password2": "ClaveNueva123"}
        self.client.post(reverse("alta_cajero"), {**datos, "email": ""})
        self.assertFalse(User.objects.filter(username="ana").exists())
        self.client.post(reverse("alta_cajero"), datos)
        self.assertTrue(User.objects.filter(username="ana").exists())
        self.client.post(reverse("alta_cajero"), {**datos, "username": "ana2", "email": "ANA@ejemplo.com"})
        self.assertFalse(User.objects.filter(username="ana2").exists())

    def test_admin_carga_su_mail(self):
        self.client.post(reverse("mi_mail"), {"email": "carlos@ejemplo.com"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, "carlos@ejemplo.com")

"""
Crea el ÚNICO administrador del sistema.

Uso:
    python manage.py crear_administrador

Si ya existe un administrador, no deja crear otro (regla del PO: solo un administrador).
"""
from getpass import getpass

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from usuarios.roles import ADMINISTRADOR


class Command(BaseCommand):
    help = "Crea el único usuario administrador del minimarket."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", help="Nombre de usuario")
        parser.add_argument("--password", help="Contraseña (si no se pasa, se pide por consola)")

    def handle(self, *args, **opciones):
        grupo, _ = Group.objects.get_or_create(name=ADMINISTRADOR)
        if grupo.user_set.exists():
            raise CommandError("Ya existe un administrador. El sistema admite solo uno.")

        usuario = opciones["usuario"] or input("Usuario del administrador: ").strip()
        if not usuario:
            raise CommandError("El usuario no puede estar vacío.")
        if User.objects.filter(username=usuario).exists():
            raise CommandError(f"Ya existe un usuario llamado '{usuario}'.")

        password = opciones["password"]
        if not password:
            password = getpass("Contraseña: ")
            if password != getpass("Repetir contraseña: "):
                raise CommandError("Las contraseñas no coinciden.")
        try:
            validate_password(password)
        except ValidationError as e:
            raise CommandError(" ".join(e.messages))

        # is_staff + is_superuser: también puede entrar al panel /admin de Django
        admin = User.objects.create_superuser(username=usuario, password=password)
        admin.groups.add(grupo)
        self.stdout.write(self.style.SUCCESS(f"Administrador '{usuario}' creado."))

"""
Usuarios iniciales: se crean solos al correr `python manage.py migrate`.

Las contraseñas están guardadas ENCRIPTADAS (hash): aunque el repo sea público,
no se pueden leer desde acá. La contraseña real la tiene el grupo por fuera del código.

- Si ya existe un administrador (por ejemplo, creado con `crear_administrador`),
  no se crea otro: el sistema admite uno solo.
- Si alguno de estos usuarios ya existe, se saltea.
"""
from django.db import migrations

ADMINISTRADOR = {
    "username": "carlos", "first_name": "Carlos", "last_name": "Dueño",
    "password": "pbkdf2_sha256$1000000$1NFACJppiGkXMh2P8fRAAh$BJ4BGdW7+gHb+wq9k9w6LH8+pQ0eYBqrfVxana7Bbxk=",
}

CAJERO = {
    "username": "juan", "first_name": "Juan", "last_name": "Pérez",
    "password": "pbkdf2_sha256$1000000$tppN8W6YEILHS7cUar4Nom$2J2UNYHZVSOMB+W9DGCXjy26Q0pLF/MnHLzxKzRZJA8=",
}


def crear_usuarios(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")
    grupo_admin = Group.objects.get(name="Administrador")
    grupo_cajero = Group.objects.get(name="Cajero")

    if not User.objects.filter(groups=grupo_admin).exists() and \
            not User.objects.filter(username=ADMINISTRADOR["username"]).exists():
        admin = User.objects.create(**ADMINISTRADOR, is_staff=True, is_superuser=True)
        admin.groups.add(grupo_admin)

    if not User.objects.filter(username=CAJERO["username"]).exists():
        cajero = User.objects.create(**CAJERO)
        cajero.groups.add(grupo_cajero)


def borrar_usuarios(apps, schema_editor):
    User = apps.get_model("auth", "User")
    User.objects.filter(username__in=[ADMINISTRADOR["username"], CAJERO["username"]]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0001_crear_roles"),
    ]

    operations = [
        migrations.RunPython(crear_usuarios, borrar_usuarios),
    ]

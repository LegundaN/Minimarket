"""HU02 - Formularios para gestionar cajeros."""
from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User


class CajeroAltaForm(UserCreationForm):
    """Alta de cajero: nombre, apellido, usuario y contraseña inicial.
    No se elige rol: todo usuario creado desde acá es cajero."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username")
        labels = {"first_name": "Nombre", "last_name": "Apellido", "username": "Usuario"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        # El admin ya elige la contraseña; la opción "sin contraseña" de Django no aplica
        self.fields.pop("usable_password", None)


class CajeroEdicionForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "username")
        labels = {"first_name": "Nombre", "last_name": "Apellido", "username": "Usuario"}


class ResetearPasswordForm(SetPasswordForm):
    """El administrador le pone una contraseña nueva al cajero (el cajero no puede cambiarla)."""

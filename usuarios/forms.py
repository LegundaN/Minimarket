"""HU02 - Formularios para gestionar cajeros."""
from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User

ETIQUETAS = {"first_name": "Nombre", "last_name": "Apellido", "username": "Usuario", "email": "Mail"}


def validar_mail_unico(email, excluir_pk=None):
    """El mail se usa para recuperar la contraseña, así que no puede repetirse."""
    email = (email or "").strip().lower()
    repetidos = User.objects.filter(email__iexact=email)
    if excluir_pk:
        repetidos = repetidos.exclude(pk=excluir_pk)
    if email and repetidos.exists():
        raise forms.ValidationError("Ya hay otro usuario con ese mail.")
    return email


class CajeroAltaForm(UserCreationForm):
    """Alta de cajero: nombre, apellido, usuario, mail y contraseña inicial.
    No se elige rol: todo usuario creado desde acá es cajero."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email")
        labels = ETIQUETAS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("first_name", "last_name", "email"):
            self.fields[campo].required = True
        self.fields["email"].help_text = "Se usa para recuperar la contraseña si se la olvida."
        # El admin ya elige la contraseña; la opción "sin contraseña" de Django no aplica
        self.fields.pop("usable_password", None)

    def clean_email(self):
        return validar_mail_unico(self.cleaned_data.get("email"))


class CajeroEdicionForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email")
        labels = ETIQUETAS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["email"].help_text = "Se usa para recuperar la contraseña si se la olvida."

    def clean_email(self):
        return validar_mail_unico(self.cleaned_data.get("email"), self.instance.pk)


class MiMailForm(forms.ModelForm):
    """El administrador carga su propio mail, para poder recuperar su contraseña."""

    class Meta:
        model = User
        fields = ("email",)
        labels = ETIQUETAS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

    def clean_email(self):
        return validar_mail_unico(self.cleaned_data.get("email"), self.instance.pk)


class ResetearPasswordForm(SetPasswordForm):
    """El administrador le pone una contraseña nueva al cajero."""

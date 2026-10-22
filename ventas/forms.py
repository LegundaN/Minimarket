from decimal import Decimal

from django import forms

from productos.forms import aplicar_bootstrap

from .models import MovimientoCaja


class AbrirCajaForm(forms.Form):
    fondo_inicial = forms.DecimalField(
        label="Fondo inicial (el cambio con el que arranca la caja)", min_value=Decimal("0"),
        max_digits=10, decimal_places=2, initial=0,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "autofocus": True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class MovimientoForm(forms.ModelForm):
    class Meta:
        model = MovimientoCaja
        fields = ("tipo", "monto", "motivo")
        widgets = {
            "monto": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "motivo": forms.TextInput(attrs={"placeholder": "Ej.: pago al proveedor de gaseosas"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

    def clean_monto(self):
        monto = self.cleaned_data["monto"]
        if monto <= 0:
            raise forms.ValidationError("El monto tiene que ser mayor a cero.")
        return monto

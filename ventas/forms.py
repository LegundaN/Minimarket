import json
from decimal import Decimal

from django import forms

from productos.forms import aplicar_bootstrap
from productos.models import Producto

from .models import Cliente, MovimientoCaja


class AbrirCajaForm(forms.Form):
    fondo_inicial = forms.DecimalField(
        label="Fondo inicial (el cambio con el que arranca la caja)", min_value=Decimal("0"),
        max_digits=10, decimal_places=2, initial=0,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "autofocus": True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class MovimientoForm(forms.ModelForm):
    """Ingreso: solo plata. Egreso: es una compra de mercadería, así que además del monto total
    (a mano, el del ticket) lleva los productos que entraron y sus cantidades, que suman stock.
    Los productos llegan desde la pantalla como JSON: [{"id": 3, "cantidad": 24}, ...]"""
    productos = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = MovimientoCaja
        fields = ("tipo", "monto", "motivo")
        labels = {"monto": "Monto total", "motivo": "Motivo / proveedor"}
        widgets = {
            "monto": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "motivo": forms.TextInput(attrs={"placeholder": "Ej.: proveedor de gaseosas"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)
        self.items = []  # [(producto, cantidad)] ya validados

    def clean_productos(self):
        texto = self.cleaned_data.get("productos") or "[]"
        try:
            lista = json.loads(texto)
            pedidos = {}
            for item in lista:
                pk, cantidad = int(item["id"]), int(item["cantidad"])
                if not 1 <= cantidad <= 100000:
                    raise forms.ValidationError("Las cantidades tienen que ser de 1 en adelante.")
                pedidos[pk] = pedidos.get(pk, 0) + cantidad
        except (ValueError, KeyError, TypeError):
            raise forms.ValidationError("La lista de productos no es válida.")
        productos = {p.pk: p for p in Producto.objects.filter(pk__in=pedidos)}
        if len(productos) != len(pedidos):
            raise forms.ValidationError("Algún producto ya no existe. Recargá la página.")
        self.items = [(productos[pk], cant) for pk, cant in pedidos.items()]
        return texto

    def clean(self):
        datos = super().clean()
        if datos.get("tipo") == MovimientoCaja.EGRESO and not self.items and "productos" not in self.errors:
            self.add_error("productos", "Agregá los productos que entraron con esta compra.")
        if datos.get("tipo") == MovimientoCaja.INGRESO:
            self.items = []  # un ingreso no toca el stock
        return datos

    def clean_monto(self):
        monto = self.cleaned_data["monto"]
        if monto <= 0:
            raise forms.ValidationError("El monto tiene que ser mayor a cero.")
        return monto


class CerrarCajaForm(forms.Form):
    """Sprint 4 - Cierre del día: el cajero cuenta la plata de la caja física."""
    efectivo_contado = forms.DecimalField(
        label="¿Cuánto efectivo contaste en la caja?", min_value=Decimal("0"), max_digits=12, decimal_places=2,
        help_text="Contá todos los billetes y monedas, incluido el fondo inicial.",
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class AnularVentaForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de la anulación", max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Ej.: el cliente se arrepintió / cobré de más", "autofocus": True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

    def clean_motivo(self):
        motivo = self.cleaned_data["motivo"].strip()
        if len(motivo) < 3:
            raise forms.ValidationError("Escribí un motivo.")
        return motivo


def limpiar_documento(valor):
    """Deja solo los números del CUIT o DNI (acepta 20-12345678-9, 12.345.678, etc.)."""
    return "".join(c for c in str(valor or "") if c.isdigit())


def validar_documento(documento):
    if len(documento) not in (7, 8, 11):
        raise forms.ValidationError("El DNI tiene 7 u 8 números y el CUIT 11.")
    return documento


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ("documento", "nombre", "telefono", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["documento"].help_text = "Solo números, sin guiones ni puntos."
        aplicar_bootstrap(self)

    def clean_documento(self):
        return validar_documento(limpiar_documento(self.cleaned_data["documento"]))

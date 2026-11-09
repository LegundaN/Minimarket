from django import forms

from django.forms import inlineformset_factory

from .models import Categoria, Producto, Promocion, PromocionItem


def aplicar_bootstrap(form):
    """Le pone las clases de Bootstrap a todos los campos del formulario."""
    for campo in form.fields.values():
        clase = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
        campo.widget.attrs["class"] = (campo.widget.attrs.get("class", "") + " " + clase).strip()


class ProductoForm(forms.ModelForm):
    nueva_categoria = forms.CharField(
        label="O crear una categoría nueva", max_length=60, required=False,
        help_text="Si escribís algo acá, se crea la categoría y se usa en vez de la elegida arriba.")

    class Meta:
        model = Producto
        fields = ("codigo", "nombre", "precio", "precio_costo", "stock", "categoria")
        help_texts = {
            "precio_costo": "Opcional. Solo lo ve el administrador.",
            "stock": "Unidades disponibles. Se descuenta solo con cada venta.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].empty_label = "Sin categoría"
        self.fields["precio"].widget.attrs.update({"step": "0.01", "min": "0.01"})
        self.fields["precio_costo"].widget.attrs.update({"step": "0.01", "min": "0"})
        self.fields["stock"].required = False
        aplicar_bootstrap(self)

    def clean_stock(self):
        return self.cleaned_data.get("stock") or 0

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip()

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()

    def save(self, commit=True):
        nueva = self.cleaned_data.get("nueva_categoria", "").strip()
        if nueva:
            categoria = Categoria.objects.filter(nombre__iexact=nueva).first()
            self.instance.categoria = categoria or Categoria.objects.create(nombre=nueva)
        return super().save(commit)


class ImportarExcelForm(forms.Form):
    archivo = forms.FileField(label="Planilla de Excel (.xlsx)",
                              widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("El archivo tiene que ser un Excel .xlsx.")
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("El archivo es demasiado grande (máximo 5 MB).")
        return archivo


class PromocionForm(forms.ModelForm):
    class Meta:
        model = Promocion
        fields = ("nombre", "precio", "activa")
        widgets = {"nombre": forms.TextInput(attrs={"placeholder": "Ej.: Alfajor + gaseosa"})}
        help_texts = {"activa": "Si está desactivada, no aparece en la pantalla de cobro."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["precio"].widget.attrs.update({"step": "0.01", "min": "0.01"})
        aplicar_bootstrap(self)
        self.fields["activa"].widget.attrs["class"] = "form-check-input"


class PromocionItemForm(forms.ModelForm):
    class Meta:
        model = PromocionItem
        fields = ("producto", "cantidad")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.order_by("nombre")
        self.fields["producto"].label_from_instance = lambda p: f"{p.nombre} · ${p.precio}"
        self.fields["cantidad"].widget.attrs.update({"min": "1"})
        aplicar_bootstrap(self)


ItemsPromocionFormSet = inlineformset_factory(
    Promocion, PromocionItem, form=PromocionItemForm,
    extra=0, min_num=1, validate_min=True, can_delete=True,
)

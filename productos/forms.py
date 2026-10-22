from django import forms

from .models import Categoria, Producto


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
        fields = ("codigo", "nombre", "precio", "categoria")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].empty_label = "Sin categoría"
        self.fields["precio"].widget.attrs.update({"step": "0.01", "min": "0.01"})
        aplicar_bootstrap(self)

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

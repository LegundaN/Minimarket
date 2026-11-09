from datetime import date

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from usuarios.roles import solo_administrador

from .excel import exportar_productos, importar_productos, planilla_modelo
from .forms import ImportarExcelForm, ItemsPromocionFormSet, ProductoForm, PromocionForm
from .models import Categoria, Producto, Promocion

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def filtrar_productos(request):
    """Aplica el buscador (nombre o código) y el filtro de categoría que vienen en la URL."""
    productos = Producto.objects.select_related("categoria")
    q = request.GET.get("q", "").strip()
    categoria = request.GET.get("categoria", "")
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q))
    if categoria == "sin":
        productos = productos.filter(categoria__isnull=True)
    elif categoria.isdigit():
        productos = productos.filter(categoria_id=categoria)
    return productos, q, categoria


@solo_administrador
def lista(request):
    productos, q, categoria = filtrar_productos(request)
    # Si lo pide el buscador en vivo, devolvemos solo la tabla
    plantilla = "productos/_tabla.html" if request.GET.get("parcial") else "productos/lista.html"
    return render(request, plantilla, {
        "productos": productos[:500],
        "total": productos.count(),
        "q": q,
        "categoria_elegida": categoria,
        "categorias": Categoria.objects.all(),
    })


@solo_administrador
def nuevo(request):
    form = ProductoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        producto = form.save()
        messages.success(request, f"Producto «{producto.nombre}» creado.")
        return redirect("productos:lista")
    return render(request, "productos/form.html", {"form": form, "titulo": "Nuevo producto"})


@solo_administrador
def editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, instance=producto)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Producto «{producto.nombre}» actualizado.")
        return redirect("productos:lista")
    return render(request, "productos/form.html", {"form": form, "titulo": f"Editar «{producto.nombre}»"})


@solo_administrador
def eliminar(request, pk):
    """Borrado manual. Las ventas viejas no se rompen: guardan su propia copia del nombre y el precio."""
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        nombre = producto.nombre
        try:
            producto.delete()
        except ProtectedError:
            promos = ", ".join(sorted({i.promocion.nombre for i in producto.en_promociones.all()}))
            messages.error(request, f"No se puede eliminar «{nombre}» porque está en la promoción: {promos}. "
                                    "Primero sacalo de la promoción.")
            return redirect("productos:lista")
        messages.success(request, f"Producto «{nombre}» eliminado.")
        return redirect("productos:lista")
    return render(request, "productos/eliminar.html", {"producto": producto})


@solo_administrador
def importar(request):
    form = ImportarExcelForm(request.POST or None, request.FILES or None)
    resumen = None
    if request.method == "POST" and form.is_valid():
        resumen = importar_productos(form.cleaned_data["archivo"])
    return render(request, "productos/importar.html", {"form": form, "resumen": resumen})


@solo_administrador
def exportar(request):
    productos, _, _ = filtrar_productos(request)
    respuesta = HttpResponse(exportar_productos(productos), content_type=TIPO_XLSX)
    respuesta["Content-Disposition"] = f'attachment; filename="productos_{date.today().isoformat()}.xlsx"'
    return respuesta


@solo_administrador
def descargar_modelo(request):
    respuesta = HttpResponse(planilla_modelo(), content_type=TIPO_XLSX)
    respuesta["Content-Disposition"] = 'attachment; filename="planilla_modelo_productos.xlsx"'
    return respuesta


# ---------- Sprint 4: Promociones ----------

@solo_administrador
def promociones(request):
    lista = Promocion.objects.prefetch_related("items__producto")
    return render(request, "productos/promociones.html", {"promociones": lista})


def _guardar_promocion(request, promocion=None):
    form = PromocionForm(request.POST or None, instance=promocion)
    formset = ItemsPromocionFormSet(request.POST or None, instance=promocion or Promocion(), prefix="items")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        productos = [f.cleaned_data["producto"] for f in formset.forms
                     if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        if len(productos) != len(set(productos)):
            messages.error(request, "Hay un producto repetido: dejalo una sola vez y cambiá la cantidad.")
        else:
            with transaction.atomic():
                promo = form.save()
                formset.instance = promo
                formset.save()
            messages.success(request, f"Promoción «{promo.nombre}» guardada.")
            return redirect("productos:promociones")
    titulo = f"Editar «{promocion.nombre}»" if promocion else "Nueva promoción"
    return render(request, "productos/form_promocion.html", {"form": form, "formset": formset, "titulo": titulo})


@solo_administrador
def nueva_promocion(request):
    return _guardar_promocion(request)


@solo_administrador
def editar_promocion(request, pk):
    return _guardar_promocion(request, get_object_or_404(Promocion, pk=pk))


@solo_administrador
def eliminar_promocion(request, pk):
    promo = get_object_or_404(Promocion, pk=pk)
    if request.method == "POST":
        nombre = promo.nombre
        promo.delete()  # las ventas viejas guardan su propia copia del nombre y el precio
        messages.success(request, f"Promoción «{nombre}» eliminada.")
        return redirect("productos:promociones")
    return render(request, "productos/eliminar_promocion.html", {"promo": promo})

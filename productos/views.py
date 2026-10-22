from datetime import date

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from usuarios.roles import solo_administrador

from .excel import exportar_productos, importar_productos, planilla_modelo
from .forms import ImportarExcelForm, ProductoForm
from .models import Categoria, Producto

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
        producto.delete()
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

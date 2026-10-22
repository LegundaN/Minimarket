from django.contrib import admin

from .models import Caja, DetalleVenta, MovimientoCaja, Venta


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha_hora", "cajero", "total", "monto_recibido", "vuelto")
    list_filter = ("cajero",)
    inlines = [DetalleVentaInline]


class MovimientoInline(admin.TabularInline):
    model = MovimientoCaja
    extra = 0


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ("id", "cajero", "abierta_en", "fondo_inicial", "cerrada_en")
    list_filter = ("cajero",)
    inlines = [MovimientoInline]

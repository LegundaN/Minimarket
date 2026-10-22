from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from productos.models import Producto

CERO = Decimal("0.00")


class Caja(models.Model):
    """HU05 - Caja chica: se abre al empezar el turno con un fondo inicial y se cierra al terminar."""
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cajas")
    abierta_en = models.DateTimeField("apertura", auto_now_add=True)
    fondo_inicial = models.DecimalField("fondo inicial", max_digits=10, decimal_places=2)
    cerrada_en = models.DateTimeField("cierre", null=True, blank=True)

    class Meta:
        ordering = ["-abierta_en"]

    def __str__(self):
        return f"Caja de {self.cajero} ({self.abierta_en:%d/%m/%Y %H:%M})"

    @property
    def esta_abierta(self):
        return self.cerrada_en is None

    def _suma(self, consulta, campo):
        return consulta.aggregate(t=Sum(campo))["t"] or CERO

    @property
    def total_ventas_efectivo(self):
        return self._suma(self.ventas.filter(medio_pago=Venta.EFECTIVO), "total")

    @property
    def cantidad_ventas(self):
        return self.ventas.count()

    @property
    def total_ingresos(self):
        return self._suma(self.movimientos.filter(tipo=MovimientoCaja.INGRESO), "monto")

    @property
    def total_egresos(self):
        return self._suma(self.movimientos.filter(tipo=MovimientoCaja.EGRESO), "monto")

    @property
    def efectivo_esperado(self):
        """Lo que tendría que haber en la caja: fondo + ventas en efectivo + ingresos - egresos."""
        return self.fondo_inicial + self.total_ventas_efectivo + self.total_ingresos - self.total_egresos


class MovimientoCaja(models.Model):
    """Ingresos o egresos de efectivo que no son ventas (ej.: pago a un proveedor)."""
    INGRESO = "ingreso"
    EGRESO = "egreso"
    TIPOS = [(INGRESO, "Ingreso"), (EGRESO, "Egreso")]

    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, related_name="movimientos")
    tipo = models.CharField(max_length=10, choices=TIPOS)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    motivo = models.CharField(max_length=200)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_hora"]


class Venta(models.Model):
    """HU03 - Cobro."""
    EFECTIVO = "efectivo"
    # Por ahora solo efectivo. Para sumar tarjeta más adelante: agregar ("tarjeta", "Tarjeta") acá.
    MEDIOS_PAGO = [(EFECTIVO, "Efectivo")]

    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name="ventas")
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    medio_pago = models.CharField(max_length=20, choices=MEDIOS_PAGO, default=EFECTIVO)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    monto_recibido = models.DecimalField(max_digits=12, decimal_places=2)
    vuelto = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"Venta #{self.pk}"


class DetalleVenta(models.Model):
    """Un renglón de la venta. Guarda una COPIA del nombre, código y precio del producto en el
    momento de la venta: así el historial no cambia si después se modifica o se borra el producto."""
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    codigo_producto = models.CharField(max_length=50)
    nombre_producto = models.CharField(max_length=150)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

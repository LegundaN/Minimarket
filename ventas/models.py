from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from productos.models import Producto, Promocion

CERO = Decimal("0.00")


class Cliente(models.Model):
    """Sprint 4 - Clientes que piden comprobante a su nombre (CUIT o DNI).
    Por defecto las ventas son a consumidor final: el cliente es opcional."""
    documento = models.CharField("CUIT / DNI", max_length=13, unique=True)  # solo números
    nombre = models.CharField("nombre o razón social", max_length=150)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    email = models.EmailField("mail", blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.documento})"

    @property
    def tipo_documento(self):
        return "CUIT" if len(self.documento) == 11 else "DNI"


class Caja(models.Model):
    """HU05 - Caja chica: se abre al empezar el turno con un fondo inicial y se cierra al terminar."""
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cajas")
    abierta_en = models.DateTimeField("apertura", auto_now_add=True)
    fondo_inicial = models.DecimalField("fondo inicial", max_digits=10, decimal_places=2)
    cerrada_en = models.DateTimeField("cierre", null=True, blank=True)
    # Sprint 4 - Cierre del día: lo que el cajero contó en la caja al cerrar
    efectivo_contado = models.DecimalField("efectivo contado", max_digits=12, decimal_places=2,
                                           null=True, blank=True)

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
    def ventas_validas(self):
        """Las ventas anuladas no cuentan para ningún total."""
        return self.ventas.filter(anulada=False)

    @property
    def total_ventas_efectivo(self):
        return self._suma(self.ventas_validas.filter(medio_pago=Venta.EFECTIVO), "total")

    @property
    def total_ventas_tarjeta(self):
        return self._suma(self.ventas_validas.filter(medio_pago=Venta.TARJETA), "total")

    @property
    def total_ventas(self):
        return self.total_ventas_efectivo + self.total_ventas_tarjeta

    @property
    def cantidad_ventas(self):
        return self.ventas_validas.count()

    @property
    def cantidad_anuladas(self):
        return self.ventas.filter(anulada=True).count()

    @property
    def total_ingresos(self):
        return self._suma(self.movimientos.filter(tipo=MovimientoCaja.INGRESO), "monto")

    @property
    def total_egresos(self):
        return self._suma(self.movimientos.filter(tipo=MovimientoCaja.EGRESO), "monto")

    @property
    def efectivo_esperado(self):
        """Lo que tendría que haber en la caja: fondo + ventas en efectivo + ingresos - egresos.
        Las ventas con tarjeta no suman: esa plata no entra a la caja."""
        return self.fondo_inicial + self.total_ventas_efectivo + self.total_ingresos - self.total_egresos

    @property
    def diferencia(self):
        """Contado - esperado. Negativo = faltante, positivo = sobrante. None si todavía no se contó."""
        if self.efectivo_contado is None:
            return None
        return self.efectivo_contado - self.efectivo_esperado

    @property
    def diferencia_absoluta(self):
        """La diferencia sin signo, para mostrar «Faltante $ 450» en vez de «$ -450»."""
        return abs(self.diferencia) if self.diferencia is not None else None


class MovimientoCaja(models.Model):
    """Ingresos o egresos de efectivo que no son ventas.
    Los egresos son compras de mercadería: llevan los productos que entraron y suman stock."""
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

    @property
    def detalle_productos(self):
        """Ej.: «Coca-Cola 500 ml x 24, Alfajor x 12»."""
        return ", ".join(f"{i.nombre_producto} x {i.cantidad}" for i in self.items.all())


class MovimientoItem(models.Model):
    """Productos que entraron con un egreso (compra de mercadería). Cada uno suma stock."""
    movimiento = models.ForeignKey(MovimientoCaja, on_delete=models.CASCADE, related_name="items")
    # SET_NULL + copia del nombre: si después se borra el producto, el registro de la compra queda
    producto = models.ForeignKey("productos.Producto", on_delete=models.SET_NULL, null=True,
                                 related_name="compras")
    codigo_producto = models.CharField(max_length=50)
    nombre_producto = models.CharField(max_length=150)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.nombre_producto} x {self.cantidad}"


class Venta(models.Model):
    """HU03 - Cobro."""
    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    MEDIOS_PAGO = [(EFECTIVO, "Efectivo"), (TARJETA, "Tarjeta")]

    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name="ventas")
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="ventas")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    medio_pago = models.CharField(max_length=20, choices=MEDIOS_PAGO, default=EFECTIVO)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    monto_recibido = models.DecimalField(max_digits=12, decimal_places=2)
    vuelto = models.DecimalField(max_digits=12, decimal_places=2)

    # Anulación: la venta nunca se borra, queda marcada con quién, cuándo y por qué
    anulada = models.BooleanField(default=False)
    anulada_en = models.DateTimeField(null=True, blank=True)
    anulada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="ventas_anuladas")
    motivo_anulacion = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-fecha_hora"]

    def __str__(self):
        return f"Venta #{self.pk}"


class DetalleVenta(models.Model):
    """Un renglón de la venta: un producto o una promoción. Guarda una COPIA del nombre, código y
    precio al momento de la venta: el historial no cambia si después se modifica o se borra algo."""
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    promocion = models.ForeignKey(Promocion, on_delete=models.SET_NULL, null=True, blank=True)
    codigo_producto = models.CharField(max_length=50)
    nombre_producto = models.CharField(max_length=150)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    # Para las promociones: qué productos (y cuántos) se descontaron del stock, por si se anula la venta
    componentes = models.JSONField(default=list, blank=True)

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    @property
    def es_promocion(self):
        return bool(self.componentes) or self.codigo_producto == "PROMO"

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

STOCK_BAJO = 5  # con esta cantidad o menos, el producto se marca como "stock bajo"


class Categoria(models.Model):
    """Bebidas, Cigarrillos, Golosinas, etc."""
    nombre = models.CharField("nombre", max_length=60, unique=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    # El código va como TEXTO (no número) para no perder ceros adelante, ej. "0012345"
    codigo = models.CharField("código", max_length=50, unique=True)
    nombre = models.CharField("nombre", max_length=150)
    # Decimal (no float) para que no haya errores de redondeo con la plata
    precio = models.DecimalField("precio de venta", max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    categoria = models.ForeignKey(Categoria, verbose_name="categoría", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="productos")
    # Sprint 3 - HU06 Stock: se descuenta con cada venta y sube con las compras (egresos de caja chica).
    # Nunca baja de 0: la caja no deja vender más unidades de las que hay.
    stock = models.PositiveIntegerField("stock", default=0)
    # Sprint 3 - HU07 Costos: solo lo ve el administrador
    precio_costo = models.DecimalField("precio de costo", max_digits=10, decimal_places=2,
                                       null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    @property
    def stock_bajo(self):
        return self.stock <= STOCK_BAJO

    @property
    def margen(self):
        """Ganancia en % sobre el costo. None si no se cargó el costo."""
        if not self.precio_costo:
            return None
        return ((self.precio - self.precio_costo) / self.precio_costo * 100).quantize(Decimal("0.1"))


class Promocion(models.Model):
    """Sprint 4 - Promociones: un grupo de productos con un precio especial (ej.: alfajor + café $2.000)."""
    nombre = models.CharField("nombre de la promoción", max_length=100)
    precio = models.DecimalField("precio de la promoción", max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    activa = models.BooleanField("activa", default=True)

    class Meta:
        ordering = ["-activa", "nombre"]
        verbose_name = "promoción"
        verbose_name_plural = "promociones"

    def __str__(self):
        return self.nombre

    @property
    def precio_normal(self):
        """Lo que costarían los productos por separado."""
        return sum((i.producto.precio * i.cantidad for i in self.items.all()), Decimal("0.00"))

    @property
    def ahorro(self):
        return self.precio_normal - self.precio

    @property
    def descripcion(self):
        return " + ".join(f"{i.cantidad} × {i.producto.nombre}" for i in self.items.all())


class PromocionItem(models.Model):
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="items")
    # PROTECT: no se puede borrar un producto que está en una promoción (primero hay que sacarlo de la promo)
    producto = models.ForeignKey(Producto, verbose_name="producto", on_delete=models.PROTECT,
                                 related_name="en_promociones")
    cantidad = models.PositiveIntegerField("cantidad", default=1, validators=[MinValueValidator(1)])

    class Meta:
        unique_together = [("promocion", "producto")]

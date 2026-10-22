from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


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
    precio = models.DecimalField("precio", max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("0.01"))])
    categoria = models.ForeignKey(Categoria, verbose_name="categoría", on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="productos")

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

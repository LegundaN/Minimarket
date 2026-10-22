"""Filtro para mostrar plata en formato argentino: {{ 1234.5|pesos }} -> $ 1.234,50"""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def pesos(valor):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return valor
    texto = f"{numero:,.2f}"                       # 1,234.50
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,50
    return f"$ {texto}"

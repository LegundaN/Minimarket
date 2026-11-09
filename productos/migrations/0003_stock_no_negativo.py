from django.db import migrations, models


def stock_negativo_a_cero(apps, schema_editor):
    """Antes el stock podía quedar negativo. Ahora el mínimo es 0: los negativos pasan a 0."""
    Producto = apps.get_model("productos", "Producto")
    Producto.objects.filter(stock__lt=0).update(stock=0)


class Migration(migrations.Migration):
    dependencies = [("productos", "0002_stock_costos_promociones")]

    operations = [
        migrations.RunPython(stock_negativo_a_cero, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="producto",
            name="stock",
            field=models.PositiveIntegerField(default=0, verbose_name="stock"),
        ),
    ]

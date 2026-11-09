# Minimarket — Sistema web (TP Metodologías Ágiles)

## Sprint 1 — Acceso y usuarios
- **HU01 Login**: ingreso con usuario y contraseña, cierre de sesión manual.
- **HU02 Gestión de usuarios**: el administrador da de alta, edita, resetea contraseñas y activa/desactiva cajeros (nunca se borran).
- **HU10 Roles y permisos**: un único Administrador y N Cajeros. El cajero no puede entrar a pantallas de administración ni escribiendo la URL.

## Sprint 2 — Productos, cobro y caja chica
- **Productos** (administrador): listado con buscador rápido y filtro por categoría, carga manual, edición, eliminación, **importar Excel** (`codigo | nombre | precio | categoria`) y **descargar Excel** con los datos actuales.
- **Cobro** (cajero): lector de código de barras o búsqueda por nombre (las sugerencias aparecen mientras se escribe), carrito, "¿Con cuánto pagó?" y vuelto, con botones de billetes (prueba, en `ventas/templates/ventas/_billetes.html`).
- **Caja chica** (cajero): apertura con fondo inicial, ingresos y egresos, efectivo esperado y cierre.
- **Consultar precio** (cajero, solo lectura).
- **Historial de cobros** y **Cajas** (administrador): cada cobro con fecha, hora y cajero.

## Sprint 3 — Stock y costos
- Cada producto tiene **stock** y **precio de costo** (opcionales). El listado muestra el **margen** y avisa stock bajo (≤ 5) o sin stock.
- Cada venta **descuenta stock** y el stock **nunca baja de 0**: la caja no deja vender más unidades de las que hay (tampoco promos sin stock).
- Los **egresos de caja chica son compras de mercadería**: se cargan los productos que entraron y sus cantidades (suman stock) y el monto total del ticket.
- El Excel de importación/exportación suma las columnas `stock` y `costo` (si se dejan vacías, no se pisa lo que había).
- El cajero **nunca ve el costo**.

## Sprint 4 — Clientes, anulaciones, promociones y cierre del día
- **Medio de pago**: efectivo o tarjeta. La tarjeta no entra a la caja chica.
- **Clientes con CUIT/DNI**: por defecto es consumidor final; botón "Cliente con CUIT/DNI": mientras se escribe aparecen los clientes cuyo documento empieza con esos números (o por nombre) y, si no existe, cargarlo en una ventanita. El administrador ve y edita los clientes en **Clientes**.
- **Anular venta** (motivo obligatorio): el cajero anula sus ventas mientras su caja está abierta; el administrador cualquier venta de una caja abierta. Repone el stock y deja de sumar en la caja. En el historial queda marcada como anulada.
- **Promociones** (administrador): se arma un combo eligiendo productos y cantidades y se le pone un precio. El cajero las agrega desde el botón "Promociones" en el cobro. Un producto que está en una promo no se puede borrar.
- **Cierre del día**: al cerrar, el cajero carga el efectivo contado. Se ve el total en efectivo, el total con tarjeta, la cantidad de operaciones y el **faltante o sobrante**, que queda registrado a nombre del cajero (pantalla **Cajas** del administrador).
- **Movimientos del día en Excel** (administrador, desde Historial de cobros): 4 hojas — Resumen por cajero, Cobros, Productos vendidos y Movimientos de caja.

## Pedidos de la revisión del Sprint 1
- **Recuperar contraseña por mail**: link "¿Olvidaste tu contraseña?" en el login. El administrador carga su mail en **Panel → Cargá tu mail** y el de cada cajero en **Cajeros → Editar**. Para que los mails salgan de verdad hay que configurar una cuenta (ver PUBLICAR_EN_PYTHONANYWHERE.md); sin configurar, el mail se imprime en la consola/log.
- **Diseño nuevo** con la paleta verde de Neosoft (`usuarios/static/css/minimarket.css`).

## Cómo levantarlo (Windows)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py crear_administrador
python manage.py runserver
```
Abrir http://127.0.0.1:8000 e ingresar con el administrador. Desde **Cajeros** se crean los usuarios de caja.

> En Mac/Linux, activar el entorno con `source venv/bin/activate`.

## Publicarlo en internet
Ver **PUBLICAR_EN_PYTHONANYWHERE.md**.

## Tests
```
python manage.py test
```

## Estructura
```
minimarket/        configuración del proyecto (settings, urls)
usuarios/
  roles.py         roles y decoradores @solo_administrador / @solo_cajero
  views.py         login → redirección por rol, gestión de cajeros
  forms.py         formularios de alta, edición y reseteo de contraseña
  migrations/      0001 crea los grupos Administrador y Cajero
  management/commands/crear_administrador.py   crea el único admin
  templates/       pantallas con Bootstrap (responsive)
  tests.py         un test por criterio de aceptación
productos/         productos, stock, costos, promociones, importar/exportar Excel
ventas/            cobro, clientes, caja chica, anulaciones, cierre, historial
  excel.py         Excel de movimientos del día
```

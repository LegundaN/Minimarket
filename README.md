# Minimarket — Sistema web (TP Metodologías Ágiles)

## Sprint 1 — Acceso y usuarios
- **HU01 Login**: ingreso con usuario y contraseña, cierre de sesión manual.
- **HU02 Gestión de usuarios**: el administrador da de alta, edita, resetea contraseñas y activa/desactiva cajeros (nunca se borran).
- **HU10 Roles y permisos**: un único Administrador y N Cajeros. El cajero no puede entrar a pantallas de administración ni escribiendo la URL.

## Sprint 2 — Productos, cobro y caja chica
- **Productos** (administrador): listado con buscador rápido y filtro por categoría, carga manual, edición, eliminación, **importar Excel** (`codigo | nombre | precio | categoria`) y **descargar Excel** con los datos actuales.
- **Cobro** (cajero): lector de código de barras o búsqueda por nombre, carrito, "¿Con cuánto pagó?" y vuelto, con botones de billetes (prueba, en `ventas/templates/ventas/_billetes.html`).
- **Caja chica** (cajero): apertura con fondo inicial, ingresos y egresos, efectivo esperado y cierre.
- **Consultar precio** (cajero, solo lectura).
- **Historial de cobros** y **Cajas** (administrador): cada cobro con fecha, hora y cajero.

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
```

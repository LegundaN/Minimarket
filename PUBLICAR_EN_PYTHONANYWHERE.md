# Cómo publicar el Minimarket en PythonAnywhere

Esto lo hace **una sola persona del grupo** (la "dueña" del servidor). Los demás siguen programando en sus compus y suben los cambios a GitHub.

En todos los pasos, reemplazá:
- `USUARIO` → tu nombre de usuario de PythonAnywhere (define la dirección: `USUARIO.pythonanywhere.com`)
- `USUARIO_GITHUB` → el usuario de GitHub donde está el repo

---

## Parte 1 — Subir el proyecto a GitHub (en tu compu)

1. En GitHub, creá un repositorio nuevo llamado **`minimarket`** (vacío, sin README).
2. En la terminal, dentro de la carpeta del proyecto:
   ```
   git init
   git add .
   git commit -m "Sprint 1: login, roles y gestión de cajeros"
   git branch -M main
   git remote add origin https://github.com/USUARIO_GITHUB/minimarket.git
   git push -u origin main
   ```
3. En GitHub → **Settings → Collaborators**, sumá a los otros 3 integrantes.

> Si el repo es **privado**, PythonAnywhere va a pedir usuario y un *token* de GitHub al clonar. Para el TP es más fácil dejarlo **público** (no hay contraseñas en el código: la clave secreta va en el servidor).

---

## Parte 2 — Crear la cuenta

1. Entrá a **pythonanywhere.com** → *Pricing & signup* → **Create a Beginner account** (gratis).
2. Elegí bien el nombre de usuario: va a ser la dirección del sistema.

---

## Parte 3 — Bajar el código al servidor

1. En PythonAnywhere: **Consoles → Bash** (se abre una terminal en el navegador).
2. Pegá, de a una:
   ```
   git clone https://github.com/USUARIO_GITHUB/minimarket.git
   cd minimarket
   python3.13 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   (Si `python3.13` no existe, probá con `python3.12`.)
3. Preparar la base de datos y los archivos estáticos:
   ```
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py crear_administrador
   ```
   El último te pide usuario y contraseña del administrador. **Usá una contraseña fuerte**: el sistema va a estar en internet.
4. Generá la clave secreta y **copiala** (la usás en la Parte 4):
   ```
   python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
   ```

---

## Parte 4 — Crear la web app

1. Pestaña **Web → Add a new web app → Next**.
2. Elegí **Manual configuration** (⚠️ NO la opción "Django", que crea un proyecto nuevo vacío).
3. Elegí la misma versión de Python que usaste en el paso anterior (3.13).
4. Ya en la configuración de la web app:

   **Virtualenv** → escribí:
   ```
   /home/USUARIO/minimarket/venv
   ```

   **Static files** → agregá una fila:
   | URL | Directory |
   |---|---|
   | `/static/` | `/home/USUARIO/minimarket/staticfiles` |

   **Security** → activá **Force HTTPS**.

5. En la sección **Code**, hacé clic en el link del **WSGI configuration file**. Borrá TODO lo que tiene y pegá esto (con tus datos):
   ```python
   import os
   import sys

   path = "/home/USUARIO/minimarket"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["DJANGO_SETTINGS_MODULE"] = "minimarket.settings"
   os.environ["DJANGO_DEBUG"] = "False"
   os.environ["DJANGO_SECRET_KEY"] = "PEGÁ-ACÁ-LA-CLAVE-DEL-PASO-3.4"
   os.environ["DJANGO_ALLOWED_HOSTS"] = "USUARIO.pythonanywhere.com"

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
   Guardá (**Save**).

6. Volvé a la pestaña **Web** y apretá el botón verde **Reload**.

7. Abrí **https://USUARIO.pythonanywhere.com** 🎉 — desde la PC, desde el trabajo o desde el celular.

---

## Parte 5 — Cuando hacen cambios

En la compu de quien programó:
```
git add .
git commit -m "descripción del cambio"
git push
```

En PythonAnywhere (Consoles → Bash):
```
cd minimarket
source venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```
Y después **Web → Reload**.

---

## Para no perderlo

- La cuenta gratis **da de baja la web app si no se renueva en un mes**. En la pestaña **Web** hay un botón para extenderla: pónganse un recordatorio mensual.
- La base de datos del servidor (`db.sqlite3`) es **distinta** de la de cada compu: los cajeros que creen en el servidor no aparecen en sus compus, y viceversa. Es normal.

## Si algo falla

- **Página de error "Something went wrong"** → en la pestaña **Web**, abrí el **Error log** y buscá la última línea con `Error`.
- **"Bad Request (400)"** → revisá que `DJANGO_ALLOWED_HOSTS` tenga exactamente `USUARIO.pythonanywhere.com`.
- **Se ve sin estilos el panel /admin** → revisá la fila de *Static files* y que hayas corrido `collectstatic`.
- **No toma los cambios** → te olvidaste el **Reload**.

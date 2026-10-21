# NEXO · Gestión de restaurantes

Proyecto local con backend Django/DRF, SQLite y frontend React con Vite.

## Iniciar en Windows (PowerShell)

Abre dos terminales desde la carpeta del proyecto. Las dependencias ya están instaladas.

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py runserver
```

Frontend:

```powershell
cd frontend
npm run dev
```

Abre http://localhost:5173. NEXO incluye un resumen de gestión, un plano de mesas interactivo, un tablero de cocina y una carta con búsqueda y filtros. El diseño usa tonos crema y dorado con navegación lateral oscura.

Los ocho productos y sus precios se consultan desde `GET /api/menu/` (datos en `backend/api/menu.json`). Las métricas, mesas y pedidos son de demostración. Los pedidos creados en el plano pasan al tablero de cocina y permiten avanzar su estado durante la sesión; no se guardan en el servidor. Las imágenes de platos son ilustrativas y se sirven desde Unsplash; las fuentes usan Google Fonts. `GET /api/health/` sigue disponible para comprobar el backend.

La pantalla `/login` (también `/login.html`) valida los campos y permite mostrar u ocultar la contraseña. Es una vista previa: autenticación, registro, recuperación de contraseña y reservas aún no están implementados. No envía credenciales.

Vite reenvía `/api` a `http://127.0.0.1:8000` mediante su proxy de desarrollo. Django también permite CORS desde localhost y 127.0.0.1 en el puerto 5173. Puedes copiar `frontend/.env.example` a `frontend/.env.local` y definir `VITE_API_URL` para consultar otra dirección; reinicia Vite tras cambiarla.

## Instalar desde cero

Requiere Python 3.12+ y Node.js 22.12+.

```powershell
python -m venv backend/.venv
python -m pip --python backend/.venv/Scripts/python.exe install -r backend/requirements.txt
backend/.venv/Scripts/python.exe backend/manage.py migrate
cd frontend
npm ci
```

Si la creación del entorno falla en `ensurepip`, pero existe `backend/.venv/Scripts/python.exe`, el comando de instalación con `python -m pip --python ...` permite instalar usando el pip global.

## Verificar

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py test api
```

Desde `frontend`, ejecuta `npm run build` y `npm run lint`.

El endpoint está en `backend/api/views.py`; la página está en `frontend/src/App.jsx`.

Configuración orientada a desarrollo local. Para producción, configura una clave secreta externa, `DEBUG=False`, hosts y orígenes permitidos, y un servidor que enrute `/api` al backend: el proxy de Vite no forma parte del build.

La clave de Django se lee de `DJANGO_SECRET_KEY`. Si no está definida, se genera una clave temporal por proceso para desarrollo. Define una clave estable en el entorno para conservar sesiones entre reinicios y para producción.

# Identidad y acceso — DN-19, DN-21, DN-17, DN-18

Implementa RF-003, RF-005, RF-001 y RF-002. Incluye asignación inicial de RF-007 para desbloquear autorización, y controles de RNF-004. Las decisiones multi-tenant y globales fueron aprobadas en el chat el 2026-10-22; no son nuevos RF inventados.

## Política aprobada y criterios

- Cada usuario operativo tiene una membresía en un restaurante. Roles: OWNER, ADMIN, CASHIER, WAITER, KITCHEN.
- OWNER y ADMIN crean/listan usuarios únicamente de su restaurante. El restaurante se obtiene de la identidad autenticada en servidor; un ID de otro restaurante en la solicitud nunca amplía acceso.
- El alta asigna un rol local válido, valida la contraseña con Django y almacena su hash. No permite convertir usuarios en administradores globales. Los demás roles no pueden crear/listar usuarios.
- Login con correo y contraseña: sesión de 3600 segundos desde emisión, sin renovación por actividad. Token opaco aleatorio; servidor guarda solo su hash. Logout revoca el token actual. Usuario, membresía y restaurante deben seguir activos en cada petición.
- El navegador guarda el token en sessionStorage. Cerrar una pestaña termina su almacenamiento; cerrar sesión lo revoca también en servidor. En despliegue, servir por HTTPS.
- El administrador global puede crear/activar/desactivar restaurantes, crear cuentas de futuros Dueños y asignarlos, sin acceso automático a empleados, ventas, caja ni otros datos operativos. GET de candidatos solo muestra cuentas activas sin membresía; los restaurantes muestran el correo de sus Dueños como metadato de administración. Las cuentas de administrador global se crean mediante comando local; ningún formulario concede ese privilegio.
- Asignar un Dueño agrega/promueve una membresía OWNER en ese restaurante. No traslada usuarios de otros restaurantes ni revoca a otros Dueños; un reemplazo exclusivo requiere definir el flujo correspondiente.
- RF-007, ampliación aprobada el 2026-10-27: al menos un Dueño activo por restaurante (cuenta y membresía activas). `Restaurant.initial_owner` conserva la identidad del primer Dueño aunque un administrador global cambie su rol. Los gestores locales no pueden retirarle OWNER. La excepción global solo cambia el rol de esa cuenta y exige otro Dueño activo del mismo restaurante; no lista empleados ni concede acceso operativo. El chequeo, cambio y auditoría se serializan por restaurante. Ante contención SQLite se devuelve 409 para reintentar, sin aplicar parcialmente el cambio.
- Caja incluye los módulos de Mesero. Los módulos operativos que aún no existen muestran únicamente su disponibilidad en el portal; su lógica llegará en los sprints planificados.
- Altas de usuarios y operaciones globales generan auditoría atómica, sin contraseñas ni tokens y sin endpoints para editarla o eliminarla.

## Migraciones para revisión

`backend/api/migrations/0003_restaurant_initial_owner.py` (RF-007): agrega una referencia protegida al usuario del primer Dueño. Para datos existentes usa la primera evidencia de `restaurant.created`/`restaurant.owner_assigned`, verifica su pertenencia y que exista al menos un Dueño activo; si falta evidencia o Dueño activo, aborta sin inventar asignaciones. La reversión a `0002_auditlog` retira únicamente la referencia; conserva usuarios, roles, restaurantes y auditorías. Aplicación y reversión verificadas en base de pruebas. **Revisada y autorizada por el usuario; aplicada a la base local el 2026-10-27**, con respaldo verificado `backend/nexo-before-0003-20261027-185122.sqlite3`. Verificados HTTP 200 de perfil, restaurantes y usuarios por el proxy local; diez pruebas de login/propiedad, check, lint y build correctos.

`backend/api/migrations/0001_initial.py`: crea Restaurant, Membership y AccessToken. Conserva el modelo de usuario de Django.

`backend/api/migrations/0002_auditlog.py`: crea AuditLog. No modifica tablas de negocio preexistentes. Ambas se aplicaron y revirtieron en una base en memoria; su aplicación a la base local se confirmó el 2026-10-27. El alta global desde interfaz no requiere migraciones adicionales.

Tras aprobar la revisión, desde `backend`:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_identity --email desarrollador@ejemplo.com --platform-admin
```

El comando inicial solicita la contraseña del administrador global de forma oculta. Después, desde `/app`, crear la cuenta del Dueño y seleccionarla por correo al crear un restaurante o vincularla a uno existente. No es necesario introducir IDs ni crear Dueños por consola. Un usuario operativo sin restaurante no puede iniciar sesión hasta recibir la membresía. Dueño y Administrador crean usuarios locales desde su propio panel.

La reversión de las tablas nuevas es `manage.py migrate api zero`: elimina datos de esas tablas, por lo que solo corresponde en una base de prueba o con respaldo y revisión previa. No ejecutarla para cerrar sesión ni deshacer una acción administrativa.

## Pantallas y API

- `/login`: autenticación real; `/app`: portal con roles, alta/listado de usuarios o administración global.
- `/example`: demostración pública con datos ficticios; `/api/menu/` sigue siendo el catálogo estático de la demo y no contiene datos privados de tenants.
- POST `/api/auth/login/`, POST `/api/auth/logout/`, GET `/api/auth/me/`.
- GET/POST `/api/users/`: requiere OWNER/ADMIN local.
- PATCH `/api/users/` (DN-23 / RF-007): `id` del usuario y `role` local obligatorio. Solo OWNER/ADMIN de su restaurante; IDs ajenos o inexistentes responden 404, roles inválidos o campos adicionales responden 400. No modifica identidad, contraseña, membresía de restaurante ni privilegios globales. El cambio genera `user.role_changed` con rol anterior/nuevo en la misma transacción; guardar el rol vigente no genera otro evento. Permite cambiar el propio rol, con retirada inmediata de permisos si corresponde.
- Ese PATCH rechaza quitar OWNER al primer Dueño (403) o al último Dueño activo (400). GET de usuarios incorpora `is_initial_owner` e `is_last_owner` para explicar el bloqueo en pantalla. Los demás Dueños pueden cambiar su propio rol si queda otro activo.
- PATCH `/api/platform/initial-owner-role/`: exclusivo del administrador global; recibe `restaurant` y `role` local. Resuelve el primer Dueño en servidor, no admite seleccionar otro empleado ni modificar su identidad/tenant. Rechaza quitar OWNER sin otro Dueño activo (400), roles inválidos y campos adicionales (400). GET de restaurantes incluye solo correo y rol del primer Dueño como metadatos de administración. Formulario integrado en cada restaurante del panel global.
- GET/POST `/api/platform/owners/`: solo administrador global; lista candidatos sin restaurante y crea cuentas sin membresía ni privilegios globales. POST: `email`, `password`.
- GET/POST/PATCH `/api/platform/restaurants/`: requiere administrador global. POST: `name`, `owner` (ID). PATCH: `id`, `is_active` y/o `owner`.
- Autenticación: `Authorization: Bearer <token>`.

## Validación

DN-23 / RF-007 (2026-10-27): 25 pruebas Django, `manage.py check`, lint y build correctos. Cinco pruebas nuevas cubren ambos roles gestores y los cinco roles destino, persistencia, aislamiento entre dos restaurantes, privilegios manipulados, acceso anónimo/global/operativo, sesión abierta, operaciones sin cambios y reversión si falla la auditoría. Flujo real comprobado en navegador sobre BD temporal con usuarios ficticios: cambio Mesero → Cocina, recarga, diseño móvil a 390 px y cambio propio Dueño → Cocina, retirando directorio y formularios. No hay script de typecheck en este frontend JavaScript.

20 pruebas Django (17 de identidad y 3 existentes), lint frontend y build. Se prueban accesos cruzados y payloads manipulados, roles, contraseñas, revocación, expiración fija, estados inactivos y límites de administración global. Incluye el flujo alta global → asignación de restaurante → login del Dueño → alta local, y el rechazo de candidatos globales a todos los roles locales. No hay script de typecheck: el frontend existente usa JavaScript.

Validación en navegador (2026-10-27) con una base QA temporal y cuentas ficticias: login global, alta de futuro Dueño, selección por correo y creación de restaurante, logout, login del Dueño, creación y consulta de un Mesero. Portal con navegación oscura, crema/dorado, estados vacíos, mensajes y formularios responsivos. No se cambió el estado de Jira ni se declara terminado todo el Sprint 01.

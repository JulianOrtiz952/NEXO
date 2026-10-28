# Zonas — DN-28 / RF-012

Plan y criterios aprobados en el chat el 2026-10-28. Se implementa únicamente DN-28; las mesas siguen pendientes de DN-29–DN-32.

## Criterios y comportamiento

- OWNER y ADMIN consultan, crean, editan, activan y desactivan zonas de su restaurante. CASHIER, WAITER, KITCHEN y administrador global carecen de acceso a esta gestión (RNF-004).
- El servidor obtiene el restaurante desde la membresía activa. IDs de otro restaurante responden 404; no se aceptan campos de pertenencia o privilegios en las mutaciones. Usuarios, membresías y restaurantes inactivos no obtienen acceso.
- Nombre obligatorio, máximo 100 caracteres, sin espacios exteriores. La clave de comparación usa `casefold`; no se repiten nombres dentro del restaurante, tampoco con zonas inactivas. Otro restaurante puede usar el mismo nombre. La restricción única en BD protege frente a altas concurrentes.
- Alta siempre activa. Desactivar no elimina información; reactivar conserva identidad e historial. No existe endpoint de borrado. La interfaz solicita confirmación antes de desactivar (RNF-032).
- Crear y editar se ejecutan con auditoría en la misma transacción. El evento conserva restaurante, actor, entidad y anterior/nuevo. Guardar sin cambios no genera eventos adicionales (RNF-007/019).
- La pantalla `/app#zones` usa el diseño NEXO y solo está disponible para gestores locales. Admite alta, edición, estados, errores y recarga de datos persistidos (RNF-029/031/033).

## API

- GET/POST `/api/zones/`: consulta local y alta con `name`.
- GET/PATCH `/api/zones/<uuid>/`: consulta local y edición de `name` y/o `is_active`.
- Errores: 400 validación/duplicado, 401 sin sesión, 403 sin permiso, 404 recurso ajeno/inexistente, 409 contención temporal de SQLite.

## Historial clasificado — RNF-007, RF-012

La ampliación del Historial fue solicitada por el usuario junto con esta implementación.
Cada evento muestra categoría y tipo de acción. El selector «Tipo de acción» combina ambos para distinguir, por ejemplo, «Usuarios · Edición» de «Zonas · Edición».
GET `/api/history/?action=zone.updated&page=1` aplica el filtro en servidor, después de restringir permisos/restaurante y antes de paginar. Devuelve tipos disponibles, total filtrado y 20 eventos por página. Cambiar o limpiar filtro vuelve a página 1; los resultados obsoletos se descartan. Valores de filtro desconocidos devuelven 400.

Registro explícito de tipos en `backend/api/history.py`: al incorporar otro módulo se deben registrar sus eventos, su clasificación y sus campos públicos seguros. El historial continúa siendo inmutable y no expone contraseñas ni tokens. La vista global conserva sus acciones administrativas; no recibe eventos de zonas ni acceso operativo.

## Migración para revisión

`backend/api/migrations/0004_zone.py` crea únicamente `Zone` y su restricción de nombre por restaurante. No altera usuarios, membresías, restaurantes ni auditorías existentes. No incorpora zonas de ejemplo ni dependencias nuevas.

Aplicación prevista, **solo tras revisión y autorización del usuario**, con respaldo previo de la base local:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate api 0004
```

Reversión técnica: `manage.py migrate api 0003`. Elimina la tabla de zonas y sus datos; requiere respaldo y revisión, y no debe ejecutarse como mecanismo para deshacer cambios de una zona. Conserva las identidades y auditorías previas.

Aplicación → reversión → reaplicación verificadas en BD QA temporal, conservando tres usuarios y membresías. **No aplicada a `backend/db.sqlite3`.**

## Validación del 2026-10-28

- 64 pruebas Django correctas; seis nuevas cubren ciclo completo, ambos roles gestores, permisos, aislamiento bidireccional, nombres/constraint, rollback de auditoría y filtrado/paginación sin datos ajenos o secretos.
- Ajustada la limpieza de la prueba histórica de migración 0003 para restaurar las migraciones vigentes al terminar.
- Django check, consistencia de migraciones, lint y build correctos. El frontend usa JavaScript y no tiene script `typecheck`.
- Navegador con BD temporal: alta → renombrar → confirmar desactivación → reactivar, rechazo de duplicado, persistencia tras recargar, clasificación/filtro y limpieza del Historial, restaurante B sin zonas ni historial de A, acceso directo de Mesero sin pantalla de gestión.
- Revisión móvil con viewport solicitado de 390 px; corregido ancho mínimo heredado para evitar desbordamiento del portal. Sin datos reales ni cambios de estado en Jira.
- Pendientes: revisión/aplicación autorizada de migración local y validación final del usuario. No declarar DN-28 cerrado en Jira.

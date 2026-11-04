# DN-39 / RF-023 — Categorías

Plan y criterios aprobados por el usuario en este chat antes de cambiar archivos o esquema, el 2026-10-28. Stack conservado: Django/DRF, React/Vite y SQLite. La preparación de la migración está autorizada; su aplicación a la base local requiere revisión del usuario.

## Alcance aprobado e implementado

- Categorías independientes por restaurante: UUID, nombre de hasta 100 caracteres, clave de comparación Unicode, estado y posición.
- OWNER/ADMIN pueden consultar, crear, renombrar, ordenar, activar y desactivar; no existe eliminación. Nombres únicos por restaurante ignorando espacios exteriores y mayúsculas, incluso si están inactivos. La misma categoría puede existir en restaurantes diferentes.
- Nuevas categorías activas al final; las inactivas conservan su posición y siguen disponibles en gestión.
- Pertenencia y autorización derivadas de la membresía activa en servidor; no se acepta restaurante ni posición en el formulario de alta/edición. Administrador global, CASHIER, WAITER y KITCHEN sin gestión (RNF-004).
- Cambios e historial anterior/nuevo en una transacción. Historial incluye categoría, responsable, nombre, estado y posición (RNF-007, RNF-019).
- Pantalla Categorías en `/app#categories`, estilos compartidos de NEXO, edición, botones Subir/Bajar accesibles, confirmación de desactivación y errores en español (RNF-029/031/033).

## API y concurrencia

- `GET/POST /api/categories/`: lista ordenada y alta.
- `GET/PATCH /api/categories/<uuid>/`: consulta y edición dentro del restaurante autorizado; IDs ajenos reciben 404.
- `POST /api/categories/reorder/`: `order` y `expected_order`, listas completas de UUID del restaurante sin duplicados, incluidas inactivas. Lotes con IDs ajenos, omitidos o malformados se rechazan íntegramente.
- Se serializan mutaciones mediante escritura sobre Restaurant dentro de la transacción antes de leer posiciones. Orden desactualizado o bloqueo concurrente: 409 con instrucción de actualizar y reintentar. Altas concurrentes no comparten posición; reordenamientos no sobrescriben un orden distinto al consultado (RNF-019/020).
- Se registra un evento `category.reordered` por cada categoría que cambia de posición. No se auditan solicitudes sin cambios. Un fallo de auditoría revierte la mutación completa.

## Migración para revisión

`backend/api/migrations/0008_category.py` depende de 0007 y crea únicamente `Category`, con FK protegida a Restaurant, restricción de nombre canónico único por restaurante y clave no vacía.

Aplicación prevista, solo tras revisión y autorización: `backend/.venv/Scripts/python.exe backend/manage.py migrate api 0008`. Debe realizarse respaldo verificado antes de aplicarla a la base local.

Reversión: `backend/.venv/Scripts/python.exe backend/manage.py migrate api 0007`. Elimina la tabla de categorías y sus datos; requiere respaldo previo si ya contiene registros. No elimina usuarios, restaurantes, membresías, zonas, mesas ni historial. Restaurar el respaldo permite recuperar categorías si se revierte después de su uso.

## Validación realizada

- Regresión completa de Django: 97 pruebas correctas. Después se añadió una prueba de reordenamientos concurrentes: las ocho pruebas dedicadas de categorías pasaron juntas.
- Incluye ciclo OWNER/ADMIN, nombres duplicados/Unicode, validación estricta, aislamiento bidireccional en listas/IDs/lotes/historial, revocación de acceso, anonimato, roles, posiciones, sesión desactualizada, fallos de auditoría y concurrencia de altas/reordenamientos.
- `manage.py check`, `makemigrations --check --dry-run`, lint y build correctos. Frontend JavaScript sin script de comprobación de tipos; no se declara typecheck ejecutado.
- Base temporal nueva: aplicar 0008 → revertir a 0007 → reaplicar 0008. Integridad SQLite correcta; se conservaron 3 usuarios, 2 restaurantes, 3 membresías, 1 zona, 1 mesa y 1 evento de auditoría de la fixture QA.
- Navegador con backend y base QA aislados: crear Bebidas/Entradas, ordenar, renombrar a Bebidas frías, desactivar con confirmación, recargar, reactivar y rechazar duplicado. Historial con anterior/nuevo y filtro por cambio de orden. Segundo restaurante sin categorías ajenas; Mesero sin gestión incluso manipulando hash. Vista móvil de 390 px, ancho de contenido igual al disponible, sin desbordamiento horizontal.
- QA se realizó con una base temporal y sin cuentas reales. El usuario autorizó la aplicación local de 0008 el 2026-11-03. Se verificó el respaldo `backend/nexo-before-0008-20261103-205108.sqlite3` y, tras migrar, se comprobó la integridad SQLite y se compararon los registros existentes de usuarios, restaurantes, membresías, zonas, mesas e historial con el respaldo.

## Pendientes para validar DN-39 completo

- Validación final del usuario.
- CA-02 de Jira, orden y activación reflejados en la carta de productos reales: pendiente de DN-40 / RF-024. La carta de demostración y su archivo JSON no se modificaron. Esta entrega no declara ese CA cumplido ni DN-39 cerrado.
- No se cambiaron estados ni se publicaron comentarios en Jira. DN-40–44, DN-36 y DN-37 no se iniciaron.

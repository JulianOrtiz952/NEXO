# DN-41 / RF-025 — Descripción de productos

Alcance y criterios aprobados por el usuario en el chat del 2026-11-04. Sprint 02; no incluye edición de nombre/categoría, cambio de precio, disponibilidad ni agrupación de la carta (DN-42/43/44/47).

## Comportamiento y autorización

- Descripción opcional de texto, vacía por defecto en productos anteriores. Se admite al registrar el producto y se devuelve en Productos y Carta autenticada.
- Dueño/Administrador pueden editar o vaciar únicamente la descripción desde Productos. Cancelar conserva el valor guardado; guardar actualiza la tarjeta sin recargar toda la página.
- `PATCH /api/products/<uuid>/description/` acepta exclusivamente `{"description": "texto"}`. No modifica nombre, precio, categoría, estado ni ID. No admite borrado ni reemplazo completo del producto.
- El restaurante se deriva de la membresía activa del usuario. IDs de otros restaurantes devuelven 404; campos extra se rechazan. Mesero, Caja, Cocina y administrador global no pueden escribir. Mesero/Caja consultan la descripción en su propia carta.
- Escritura y auditoría son atómicas (RNF-007/019), con revalidación de autorización bajo bloqueo del restaurante (RNF-004). `product.description_changed` conserva actor, restaurante, entidad y descripción anterior/nueva. Guardar el mismo valor no genera eventos adicionales. Los eventos anteriores permanecen intactos.
- Texto mostrado como texto React, con saltos de línea y ajuste de palabras; textarea con etiqueta, foco visible, colores NEXO y botones táctiles (RNF-029/031). Sin dependencias nuevas.

## Migración para revisión del usuario

`backend/api/migrations/0012_product_description.py`, posterior a `0011_operationreason`, añade `Product.description = TextField(blank=True, default='')`.

SQLite reconstruye internamente la tabla de productos, copia todos sus campos anteriores y asigna descripción vacía. Se conservan UUID, categoría, nombre, precio, estado, índice y restricción de precio no negativo. No se alteran restaurantes ni auditorías.

La prueba `ProductDescriptionMigrationTests` aplica → revierte a 0011 → reaplica, verificando los datos originales y el historial. **Revertir elimina las descripciones actuales de Product**; por eso se debe respaldar la base antes de aplicar o revertir. Los registros de auditoría permanecen. El usuario revisó/autorizó su aplicación el 2026-11-04. Aplicada a `backend/db.sqlite3` con respaldo verificado `backend/nexo-before-0012-20261104-092055.sqlite3`. Se compararon todos los campos originales de todas las tablas, excluyendo únicamente el registro de migraciones: datos anteriores intactos; integridad SQLite y claves foráneas correctas.

Comandos de referencia desde `backend`, una vez revisada y autorizada y con respaldo verificado:

```powershell
.\.venv\Scripts\python.exe manage.py migrate api 0012_product_description
# Reversión, si se autoriza perder la columna de descripción:
.\.venv\Scripts\python.exe manage.py migrate api 0011_operationreason
```

## Validación

Siete pruebas nuevas cubren alta opcional, persistencia, edición/vaciado sin cambios colaterales, auditoría, permisos y revocación, aislamiento bidireccional, IDs/campos manipulados, lectura de Mesero/Caja sin caché compartida, rollback ante fallo de auditoría y aplicación/reversión/reaplicación de la migración. Se ejecutan junto a las cinco pruebas existentes de productos y a la regresión general.

Resultados del 2026-11-04: **118 pruebas Django correctas**, 12 pruebas dedicadas correctas, `manage.py check`, `makemigrations --check --dry-run`, lint/build y dos pruebas de formato de Node correctos. `git diff --check` sin errores. Frontend JavaScript sin script de typecheck disponible. La base local solo recibió la migración autorizada; los datos de prueba se mantienen en una base QA separada. Jira sin cambios.

Validación en navegador completada el 2026-11-04 sobre `nexo-dn41-qa.sqlite3`, independiente de la base local. El bloqueo inicial de sockets se resolvió iniciando los servidores QA con permisos aprobados.

- Dueño: alta con descripción multilínea, edición independiente, precio exacto de $ 11,999.85 conservado, persistencia tras recargar, cancelación sin guardar y vaciado de descripción.
- Administrador: edición desde la misma interfaz con guardado correcto.
- Historial filtrado: responsable, producto/restaurante, fecha y descripción anterior/nueva; cancelar no añade un evento.
- Mesero y Caja: consulta real de descripción en Carta, sin botones de edición. Acceso directo a `#products` como Mesero conserva la vista autorizada de Carta.
- Restaurante B: carta propia sin productos ni descripciones de A. IDs y escrituras cruzadas, privilegios globales, revocación y fallo de auditoría cubiertos por las pruebas API.
- Escritorio (viewport configurado en 1280×900) y móvil (390×844): edición legible, foco visible y controles táctiles; medición DOM sin desbordamiento horizontal. El viewport se restauró y las sesiones QA se cerraron al terminar.

Evidencia guardada en la carpeta de visualizaciones del chat: `dn41-historial.png` y `dn41-carta-caja-movil.png`. DN-41 queda implementado y verificado; la validación final del usuario y el cierre en Jira siguen reservados al usuario. No se adelantan los siguientes DN.

## Incidencia del servidor local — RF-025

Tras la validación QA, el usuario reportó errores al crear y editar desde su frontend. El proceso de Django que atendía 8000 se había iniciado con `--noreload` y seguía usando el código previo: rechazaba `description` en el alta y no tenía la ruta de edición. La migración 0012 ya estaba aplicada.

Se reinició únicamente ese backend y se verificó por HTTP directo (8000) y por el frontend real (5176): consulta de productos con descripción 200, validador actualizado con rechazo controlado de un campo adicional y edición sin cambios 200. Se compararon productos y cantidad de auditorías antes/después: intactos. Token temporal eliminado. Las 12 pruebas de productos/descripciones y `manage.py check` pasan. Al ejecutar Django con `--noreload`, reiniciarlo después de los cambios y verificar el proxy real además de QA.

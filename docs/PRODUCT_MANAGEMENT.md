# Gestión de productos — Sprint 02

Bloque aprobado por el usuario el 2026-11-04: DN-42, DN-43, DN-44, DN-47 y verificaciones disponibles de DN-250/DN-20. Django/DRF + React/Vite + SQLite; sin dependencias ni migraciones nuevas.

## DN-42 / RF-026 — Edición

Dueño/Administrador editan nombre, descripción y categoría desde Productos. `GET/PATCH /api/products/<uuid>/` autoriza en servidor y restringe al restaurante de la membresía. Mantiene ID, precio y disponibilidad. Permite conservar la categoría actual inactiva, pero trasladar exige categoría activa propia. Campos ajenos a este editor se rechazan.

Edición y auditoría `product.updated` son atómicas bajo bloqueo del restaurante y revalidación de permisos (RNF-004/007/019). Guardar el mismo valor no genera eventos. Las auditorías anteriores conservan sus snapshots.

Verificación: 18 pruebas de productos/descripciones/edición correctas, lint/build correctos. Navegador QA: cambio de nombre, descripción y categoría, persistencia al recargar y precio de $ 18,000.25 intacto. Evidencia `dn42-edicion.png` en visualizaciones del chat.

El criterio de renombrado en **ventas históricas** queda pendiente hasta disponer del módulo de ventas; no se simula una venta con un evento de auditoría. El modelo actual no contiene ventas ni detalles de pedidos. No se modifican estados de Jira.

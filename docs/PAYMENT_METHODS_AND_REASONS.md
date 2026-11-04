# Configuración — DN-36 / RF-020 y DN-37 / RF-021

Implementación aprobada por el usuario en el chat. Django/DRF y React/Vite, sin dependencias nuevas.

## Validación manual

Ingresar como Dueño o Administrador en /app:

1. Métodos de pago: crear Efectivo, editar su nombre, desactivar con confirmación, recargar y reactivar. Historial permite filtrar creación, edición y cambio de estado.
2. Motivos: crear un nombre y seleccionar Cancelación, Modificación, Desperdicio, Devolución o Anulación. Filtrar por operación, editar el nombre o tipo y recargar. Historial conserva el nombre y tipo anterior/nuevo.
3. Ingresar a otro restaurante: los catálogos anteriores no aparecen. Mesero/Caja/Cocina y administrador global no administran estas configuraciones. Identificadores ajenos reciben 404 en consulta/edición; campos de restaurante manipulados reciben 400.
4. Formularios y API rechazan nombres vacíos y mayores de 100 caracteres. Los métodos nuevos se crean activos. No se imponen restricciones de nombre único no acordadas ni se añaden formularios de borrado.
5. Motivos no incluyen activación/desactivación en este alcance: RF-021 solicita configurar por tipo; no se inventa una política adicional para sus futuros flujos.

## API

- GET/POST /api/payment-methods/ y GET/PATCH /api/payment-methods/<uuid>/.
- GET/POST /api/operation-reasons/ y GET/PATCH /api/operation-reasons/<uuid>/.
- La consulta de motivos devuelve results y operation_types. El filtro opcional operation_type admite únicamente los cinco tipos del RF; no otorga permisos operativos.
- El restaurante deriva exclusivamente de la membresía activa. Bloqueo por restaurante, nueva comprobación de acceso y cambio/auditoría en una sola transacción (RNF-004/007/019). Sin cambios no se añade un evento. Caché no-store para ambos catálogos.

## Migraciones para revisión

0010_paymentmethod crea PaymentMethod; 0011_operationreason crea OperationReason y restringe sus tipos. Preparadas y verificadas en QA; no aplicadas a backend/db.sqlite3.

Aplicación tras revisión y autorización: respaldo verificado y migrate api 0011.
Reversión: migrate api 0009. Elimina exclusivamente las tablas nuevas y sus registros de configuración; el historial, identidades, categorías, productos y mesas se conservan. Si ya contienen configuraciones que se desean recuperar, respaldar antes de revertir. No usar la reversión como borrado habitual.

QA temporal: aplicar ambas → revertir a 0009 → reaplicar, comparando registros anteriores de usuarios, restaurantes, membresías, categorías, productos, zonas, mesas y auditoría. Integridad SQLite correcta. Regresión completa: 111 pruebas Django correctas. Ocho pruebas dedicadas cubren ciclo, validación, tipos, acceso cruzado por lectura/escritura, permisos/revocación y rollback ante fallo de auditoría. Lint/build, check y consistencia de migraciones correctos. No existe typecheck configurado en el frontend JavaScript.

## Criterios de integración pendientes

- DN-36, CA-02: desactivar un método no altera ventas históricas. No hay ventas implementadas; deberá verificarse cuando exista el Sprint 07, conservando los snapshots históricos pertinentes.
- DN-37, CA-02: cada flujo operativo presenta únicamente sus motivos correspondientes. La clasificación y consulta por tipo están probadas, pero la integración real depende de cancelaciones, modificaciones, desperdicios, devoluciones y anulaciones.
- El usuario valida y cierra Jira. No se hicieron transiciones ni comentarios en Jira.

# Gestión de productos — Sprint 02

Bloque aprobado por el usuario el 2026-11-04: DN-42, DN-43, DN-44, DN-47 y verificaciones disponibles de DN-250/DN-20. Django/DRF + React/Vite + SQLite; sin dependencias ni migraciones nuevas.

## DN-42 / RF-026 — Edición

Dueño/Administrador editan nombre, descripción y categoría desde Productos. `GET/PATCH /api/products/<uuid>/` autoriza en servidor y restringe al restaurante de la membresía. Mantiene ID, precio y disponibilidad. Permite conservar la categoría actual inactiva, pero trasladar exige categoría activa propia. Campos ajenos a este editor se rechazan.

Edición y auditoría `product.updated` son atómicas bajo bloqueo del restaurante y revalidación de permisos (RNF-004/007/019). Guardar el mismo valor no genera eventos. Las auditorías anteriores conservan sus snapshots.

Verificación: 18 pruebas de productos/descripciones/edición correctas, lint/build correctos. Navegador QA: cambio de nombre, descripción y categoría, persistencia al recargar y precio de $ 18,000.25 intacto. Evidencia `dn42-edicion.png` en visualizaciones del chat.

El criterio de renombrado en **ventas históricas** queda pendiente hasta disponer del módulo de ventas; no se simula una venta con un evento de auditoría. El modelo actual no contiene ventas ni detalles de pedidos. No se modifican estados de Jira.

## DN-43 / RF-027 — Precio

`PATCH /api/products/<uuid>/price/` acepta solo precio no negativo con hasta diez enteros y dos decimales, almacenado como Decimal. Dueño/Administrador del restaurante pueden modificarlo; la carta consulta el valor actualizado. El editor reutiliza el formato aprobado, precarga el valor actual y permite cancelar. Evento atómico `product.price_changed`, sin modificar información ni disponibilidad ni snapshots anteriores.

Cuatro pruebas nuevas: exactitud/límites/cero, campos inválidos, permisos/aislamiento bidireccional y reversión ante fallo de auditoría. Diez pruebas de edición/precio correctas, lint/build y dos pruebas de formato correctos. Navegador: $ 18,000.25 → $ 20,000.85, recarga y anterior/nuevo en Historial, evidencia `dn43-precio.png`. El CA de venta histórica de 18,000 tras cambiar a 20,000 y su aplicación a nuevas ventas se verificará cuando exista ventas; no se declara cumplido por probar únicamente el catálogo.

## DN-44 / RF-028 — Disponibilidad

`PATCH /api/products/<uuid>/status/` cambia exclusivamente `is_active`. Reutiliza autorización, bloqueo y auditoría atómica; envía un estado explícito, no un toggle en servidor. No elimina el producto ni sus eventos. Una categoría inactiva mantiene oculto el producto aunque se reactive. La consulta administrativa conserva ambos estados.

Interfaz con confirmación al activar/desactivar, Escape/Cancelar, retorno de foco y navegación de teclado contenida. Navegador QA: cancelar no cambia el estado; confirmar desactivación oculta el producto de Carta; reactivar lo restaura con el precio actualizado. Siete pruebas de disponibilidad cubren ciclo, categoría inactiva, permisos/IDs ajenos, validación/revocación, rollback, reautorización bajo bloqueo y desactivación concurrente idempotente con una sola auditoría.

El rechazo de un producto inactivo al crear **nuevos pedidos** y la conservación de **pedidos/ventas anteriores** quedan pendientes de esos módulos. El filtro de Carta no sustituye la futura validación en servidor al enviar pedidos. Sin borrado, migraciones ni cierre en Jira.

## DN-47 / RF-031 — Carta virtual

La carta autenticada agrupa visualmente por ID de categoría y conserva el orden recibido del servidor (posición de categoría y nombre de producto). Se muestran nombre, descripción y precio actual en tarjetas NEXO, con encabezados semánticos y adaptación móvil. No se añaden controles de pedidos ficticios ni datos de demostración. Solo aparecen productos activos en categorías activas del restaurante autorizado.

Cuatro pruebas API de aceptación: igualdad de catálogo para Mesero/Caja, orden/estados/vacío, aislamiento bidireccional ante parámetros manipulados y rechazo de roles/escrituras. Una prueba nativa de Node verifica agrupación por ID sin mezclar categorías homónimas ni cambiar orden/datos. Once pruebas de carta/disponibilidad, lint/build y tres pruebas de frontend correctos.

Navegador: Mesero y Caja ven secciones Entradas/Bebidas con los valores reales de QA, sin edición. Restaurante B solo ve sus propios productos. Escritorio y móvil; geometría DOM de tarjetas/encabezados dentro del viewport, sin desbordamiento horizontal. Evidencias `dn47-carta-escritorio.png` y `dn47-carta-movil.png`; las capturas de página completa del navegador integrado pueden presentar recorte de escala, por lo que el ancho se comprobó también con geometría DOM. Viewport restaurado al terminar.

## DN-250 / RF-234 — Persistencia de auditoría (ampliación verificada)

Tres pruebas nuevas ejecutan alta → edición → precio → desactivar/reactivar/desactivar, comparando todos los campos de los eventos anteriores (actor, entidad, restaurante, fecha y snapshots), y verifican que el historial sigue identificando el producto sin exposición a otro restaurante. La desactivación del actor conserva sus eventos e identificación. También se valida que desactivar una zona conserva su mesa y auditoría: **esto no equivale a desactivar individualmente la mesa**.

Siete pruebas de aceptación de auditoría correctas (tres nuevas y cuatro previas). Navegador: tras desactivar el producto, el evento de precio sigue disponible en Historial con actor y valores originales. Los flujos previos de empleados/restaurantes mantienen su cobertura.

**Pendiente para completar RF-234:** desactivación individual de mesas cuando exista ese flujo/estado; `Table` todavía no tiene `is_active`. No se añade ese comportamiento fuera del alcance aprobado ni se cierra DN-250 en Jira.

## DN-20 / RF-004 — Herencia de Caja (verificación disponible)

Cuatro pruebas nuevas verifican perfil autenticado, inclusión de los módulos de Mesero en Caja y consulta idéntica de la carta real, aislamiento bidireccional ante parámetros manipulados, rechazo de administración de productos/precios/estados/usuarios/categorías/zonas/mesas e historial para ambos roles y bloqueo tras revocar la membresía.

Navegador: Caja consulta la misma carta agrupada que Mesero; Mi acceso muestra Mesas/Carta/Caja y explica que los módulos operativos se incorporarán en sus sprints. Ruta directa `#products` conserva la vista autorizada de Carta sin edición/precio. Evidencia `bloque-carta-qa.png` en visualizaciones del chat.

**DN-20 permanece parcial:** los módulos declarados en el perfil no equivalen a flujos implementados. Faltan consulta operativa de mesas (los endpoints actuales son de configuración administrativa), borradores, envío de pedidos y cobro. No se habilita la configuración de mesas a Mesero/Caja como sustituto del flujo operativo. No se implementan esos módulos fuera de Sprint 02 ni se cierra el DN en Jira.

## Resultado final del bloque — 2026-11-04

- **146 pruebas Django correctas** (28 nuevas), `manage.py check` y consistencia de migraciones correctos. Sin cambios de esquema ni dependencias nuevas.
- Lint/build y tres pruebas nativas de Node correctos. Frontend JavaScript sin script `typecheck` configurado.
- QA en navegador con base independiente: edición/recarga, precio exacto e Historial, cancelación/confirmación/Escape y foco, desactivar/reactivar y Carta, agrupación Mesero/Caja, aislamiento visual B, ruta administrativa sin privilegios y escritorio/móvil. Auditorías previas consultables tras desactivar. Sesiones cerradas, viewport restaurado y servidores QA detenidos.
- Backend local de 8000 reiniciado con el código actual. HTTP directo y vía frontend real 5176: consulta de detalle/carta y edición de información/precio/estado con respuestas 200. Pruebas de guardado sin cambios, comparando todos los productos y cantidad de auditorías antes/después: intactos. Token temporal eliminado. El frontend real sirve la agrupación por categorías.
- Seis commits separados; estados de Jira intactos. Pendientes de otros módulos: históricos/nuevas operaciones de ventas y pedidos (DN-42/43/44), estado individual de mesas (DN-250) y mesas operativas/borradores/pedidos/cobro (DN-20). La ejecución de las verificaciones aprobadas no declara cumplidos esos criterios ausentes.

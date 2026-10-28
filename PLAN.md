# PLAN.md — NEXO · Backlog y seguimiento por Sprints

**Estado:** planificación propuesta; no equivale al estado real de Jira ni a funcionalidades implementadas. Los checkboxes permanecen sin marcar hasta verificar el código y las pruebas. **16 Sprints** (9 MVP, 6 V1, 1 V2), duración de referencia **2 semanas cada uno** (no fechas comprometidas).

## Reglas de ejecución
- Trabajar **una tarea a la vez**, con pruebas y un commit funcional al terminar; registrar RF, RNF, RN y criterios de aceptación (CA) en Jira.
- **Jira es la fuente de verdad del estado de los Sprints**. Este archivo documenta secuencia, alcance y dependencias; conciliar los cambios entre ambos.
- Antes de empezar, inspeccionar el repositorio y confirmar stack; **no migrar a Next.js/Prisma sin aprobación**.
- Desde Sprint 1, toda funcionalidad aplica aislamiento multi-restaurante. `Restaurant`, membresía, tenant activo y autorización en servidor no son una característica postergable a V2.
- `RNF-039 Multisede [V2]` es diferente a multi-restaurante (MVP). Diseñar para posible evolución, sin implementar sucursales por anticipado.
- Los **252 RF presentes** en el PDF están distribuidos una sola vez; no existe RF-242. Los RF-243–247 y RF-249–253 carecen de etiqueta de versión en el PDF y su ubicación es **provisional** (RF-248 sí es V2).
- Antes de construir flujos ambiguos, resolver y aprobar CA: cobro por mesero, modificación de receta/stock, costeo, inventario final, horas extra y pagos.
- No deducir que algo está terminado de la documentación. Ejecutar pruebas automáticas y manuales, lint/tipos y validación de aislamiento antes de marcar cada tarea.

## Sprint 00 — Preparación técnica transversal (no es un Sprint adicional en el cronograma oficial)
- [x] Auditar estructura y stack real existente; confirmar continuidad o aprobar migración. Django + DRF, React/Vite y SQLite; continuidad aprobada en este chat.
- [ ] Verificar Git, configuración, variables de entorno, calidad y pruebas.
- [ ] Definir esquema y política multi-tenant, roles locales, aislamiento, CA de seguridad.
- [ ] Preparar errores, moneda/decimales, idempotencia, transacciones y auditoría base.
- [ ] Confirmar Sprints y CA en Jira antes de implementar.

## Sprints oficiales

### Sprint 01 — Autenticación, usuarios y roles [MVP]
**RF:** RF-001–009; RF-223–224; RF-233–235.
**Resultado esperado:** Login, roles locales, membresía por restaurante, autorización y auditoría base.

**Transición al Sprint 02 (2026-10-28):** el usuario confirma el traslado de DN-20 / RF-004 y DN-250 / RF-234 pendientes al backlog y autoriza continuar con Sprint 02. Se conserva su alcance parcial y sus verificaciones futuras; no se declaran cumplidos esos RF. Las validaciones de auditoría quedaron registradas con 58 pruebas correctas y comprobación en navegador. La IA no modificó estados de Jira. Próximo paso: presentar plan y CA de DN-28 / RF-012 para aprobación antes de cambiar el esquema.

**Avance DN-19 / DN-21 / DN-17 / DN-18 (2026-10-22):**
- [x] DN-240 / RF-224 (2026-10-28): validada una edición real por API y navegador; auditoría persistida con actor, acción, fecha/hora con zona, ID de entidad, restaurante y anterior/nuevo. Historial identifica responsable y afectado, sin secretos. Prueba de aceptación dedicada en `backend/api/test_audit_acceptance.py`.
- [x] DN-249 / RF-233 (2026-10-28): ciclo completo alta → editar correo → cambiar Mesero a Cocina → desactivar → reactivar desde endpoints e interfaz NEXO; cinco eventos con actor, entidad, tenant y valores verificados. Desactivación y activación usan confirmación visual; el historial persiste al recargar.
- [x] DN-251 / RF-235 (2026-10-28): prueba de consulta OWNER/ADMIN, aislamiento bidireccional con dos restaurantes e IDs manipulados; CASHIER/WAITER/KITCHEN reciben 403 y anónimo 401. Administrador global sin eventos globales no recibe auditoría local. Validación visual del Dueño en Historial y evidencia previa DN-239 de rechazo para Mesero. Escritura/secretos/paginación cubiertos por regresión existente.
- [x] DN-250 / RF-234, validación parcial (2026-10-28): desactivar empleado conserva eventos anteriores y permite identificarlo en Historial; desactivar/reactivar restaurante no modifica registros previos y conserva el estado inactivo individual. Verificado por API y empleado desactivado en navegador, sobre base QA temporal.
- [ ] DN-250 / RF-234: validar productos y mesas cuando existan esos módulos. DN-20 / RF-004 sigue parcial hasta disponer de los flujos operativos de Mesero/Caja; no declarar terminado todo Sprint 01 ni cerrar Jira automáticamente.
- [x] Verificación de esta validación de auditoría (2026-10-28): 58 pruebas Django (cuatro nuevas de aceptación), check, consistencia de migraciones, lint, build y diff sin errores. Frontend JavaScript sin script typecheck. Dos archivos cambiados, sin modificaciones funcionales, dependencias ni esquema; pruebas sobre BD aisladas, sin modificar datos reales o Jira. Pendiente revisión final del usuario.
- [x] DN-239 / RF-223, RNF-007/019 (2026-10-28): revisión del registro de operaciones sensibles implementadas en Sprint 01. Cuatro pruebas nuevas verifican auditoría global, reversión de altas locales/globales y creación/asignación/estado de restaurantes cuando falla la auditoría, y rechazo de POST/PUT/PATCH/DELETE al historial sin alterar registros de ninguno de dos restaurantes. La batería existente cubre cambios de correo, rol y estado, permisos y aislamiento. Sin cambios funcionales, migraciones ni dependencias.
- [x] Validación automática DN-239: 54 pruebas Django, check, consistencia de migraciones, lint y build correctos. El frontend usa JavaScript y no dispone de script typecheck.
- [x] Validación visual DN-239 / RF-223 completada (2026-10-28): entorno QA con base temporal y frontend escuchando explícitamente en IPv4; alta real desde la interfaz → registro en Historial con actor, entidad, fecha y datos, persistencia tras recargar, consulta con dos Dueños de restaurantes distintos sin mezclar eventos y acceso directo a Historial sin exposición para Mesero. Revisada vista móvil. El rechazo de escrituras y los IDs manipulados quedan cubiertos por pruebas API. Sin modificar datos reales ni cerrar Jira; validación final y cierre reservados al usuario. No se adelantan otros DN.
- [x] RNF-007/RNF-029/RNF-031 (2026-10-28): Historial separado en `/app#history`, sin formularios de gestión en esa vista; navbar con estado activo y rutas independientes de Usuarios/Mi acceso o Dueños/Restaurantes según rol. Conserva selección al recargar y navegación por hash. Tres archivos modificados; lint/build y diez pruebas de estados/historial correctos, más validación real en escritorio/móvil.
- [x] DN-24 / RF-008, DN-25 / RF-009 e historial RNF-007 (2026-10-28): implementación de estados de cuentas locales, suspensión/reactivación global del primer Dueño y bloqueo de todo su restaurante, revocación de sesiones, preservación de históricos y estados individuales. Excepción de suspensión global aprobada por el usuario; cambios de rol y desactivaciones locales conservan protección de Dueños. Historial paginado de solo lectura con responsable, afectado y anterior/nuevo; aislamiento local y vista global limitada a acciones administrativas globales. Sin migraciones ni dependencias nuevas.
- [x] Validación automática y servidor local de esta ampliación: 50 pruebas Django, check, consistencia de migraciones, lint y build correctos. Incluye concurrencia entre desactivación/cambio de rol, bloqueo en cadena con segundo Dueño, tokens revocados, reactivación sin resucitar sesiones, aislamiento y lectura inmutable del historial sin secretos. Historial y estado global responden 200 por proxy 5173 con sesiones temporales; sin alterar cuentas reales.
- [x] Validación visual DN-24/DN-25 e historial completada en QA (2026-10-28): diálogo NEXO de activar/desactivar confirmado, historial anterior/nuevo en vista independiente, suspensión global con segundo Dueño activo, login de empleado rechazado durante la suspensión y correcto tras reactivar. Comprobadas navegación local/global, acceso directo y recarga de historial, vista móvil a 390 px y rechazo visual de Historial para Mesero. No se modificó Jira.
- [x] DN-22 / RF-006 (2026-10-27), alcance aprobado de edición de correo: OWNER/ADMIN actualizan usuarios de su restaurante desde el directorio NEXO; formato y disponibilidad validados, normalización de correo, identidad/contraseña/rol/históricos conservados y auditoría anterior/nuevo atómica. Cambios de rol y estado conservan sus flujos separados. Sin migraciones ni dependencias nuevas.
- [x] Verificación DN-22: 40 pruebas Django (seis nuevas para edición), check, consistencia de migraciones, lint y build correctos. Navegador con base QA temporal: edición, rechazo de duplicado, persistencia al recargar, vista móvil y login con correo nuevo. Backend local responde PATCH 200 vía proxy 5173 con petición sin cambios. Pendiente validación final del usuario; no modificar cierre en Jira.
- [x] RNF-033 / RF-007 (2026-10-27): el cliente muestra un error claro en español ante respuestas HTML del servidor y conserva el estado HTTP, en lugar de exponer `Unexpected token`. Siete comprobaciones con respuestas controladas, lint y build correctos. El 500 local por ausencia de `initial_owner_id` sigue pendiente de aplicar la migración 0003 revisada por el usuario.
- [x] Ampliación aprobada DN-23 / RF-007 (2026-10-27): proteger al primer Dueño frente a cambios locales y conservar al menos un Dueño con cuenta/membresía activas; excepción global limitada al primer Dueño, con auditoría atómica y serialización por restaurante. Interfaz NEXO con explicación de bloqueos y formulario global específico.
- [x] Validación de esta ampliación: 34 pruebas Django (incluye concurrencia, migración/reversión, permisos y aislamiento), check y consistencia de migraciones correctos; lint/build correctos, sin script de typecheck en JavaScript. Navegador sobre BD temporal: primer Dueño bloqueado localmente, excepción global con segundo Dueño activo, único Dueño bloqueado y vista móvil de 390 px. Migración/reversión comprobadas además sobre copia de la base local; primer Dueño existente identificado por auditoría.
- [x] Migración 0003 revisada y autorizada por el usuario, aplicada el 2026-10-27 con respaldo verificado `backend/nexo-before-0003-20261027-185122.sqlite3`. Perfil de sesión, restaurantes globales y usuarios locales devuelven HTTP 200/JSON por el proxy 5173; login sin credenciales devuelve 401 esperado. Diez pruebas de login/propiedad, check Django, lint y build correctos. Validación final del usuario pendiente; no cerrar Jira.
- [x] Corrección del entorno local DN-23 / RF-007 (2026-10-27): el backend de 8000 seguía ejecutando la versión anterior con `--noreload` y devolvía 405 al cambiar roles. Reiniciado con recarga automática. Verificado PATCH directo y vía proxy 5173: ambos llegan al validador de roles (400 esperado para rol inválido), sin modificar usuarios reales. Cinco pruebas RF-007, lint y build correctos. Validación final del usuario y cierre en Jira reservados al usuario.
- [x] DN-23 / RF-007 (2026-10-27): cambio de roles existentes desde Usuarios y roles, autorizado para OWNER/ADMIN dentro de su restaurante; rechazo de IDs ajenos, roles inválidos y campos de privilegios globales. Auditoría anterior/nuevo atómica y permisos vigentes en sesiones abiertas. Sin migraciones ni dependencias nuevas.
- [x] Validación DN-23: 25 pruebas Django, comprobación de Django, lint y build correctos; prueba específica repetida tras ajustar la aserción de persistencia. Navegador con BD temporal: Mesero → Cocina, persistencia tras recargar, vista móvil de 390 px y cambio del propio Dueño a Cocina con retirada inmediata del directorio y formularios de usuarios.
- [x] Corrección DN-18 / RF-002 (2026-10-27): actualizar perfil/permisos al comprobar sesión y recuperar foco; limpiar datos al perder acceso, e invalidar respuestas antiguas para que no restauren pantallas revocadas.
- [x] Validación de la corrección DN-18: cuatro comprobaciones del frontend con respuestas controladas (cambio de rol, respuesta obsoleta, revocación 403 y propagación de estado HTTP); lint y build sin advertencias. No sustituye la prueba manual en navegador.
- [x] DN-19 / RF-003: cinco roles locales, restaurante y membresía única por usuario operativo.
- [x] DN-21 / RF-005: alta por Dueño/Administrador, validación y hash de contraseña, asignación inicial de rol y registro de auditoría. Incluye la asignación inicial de DN-23 / RF-007, no una pantalla para cambiar roles existentes.
- [x] DN-17 / RF-001: login integrado, token opaco almacenado como hash, vencimiento fijo de una hora y logout con revocación.
- [x] DN-18 / RF-002: permisos en servidor para operaciones implementadas y módulos visibles según rol; Caja hereda Mesero. Los módulos operativos futuros siguen sus sprints.
- [x] CA aprobados en este chat: un restaurante por usuario operativo; rechazo de accesos cruzados, membresía/usuario/restaurante inactivos; rol local sin privilegios globales. Administrador global separado: crea/activa/desactiva restaurantes y asigna Dueños, sin acceso operativo automático.
- [x] Verificación automática: 16 pruebas Django, lint y build frontend; aplicación y reversión de migraciones en BD en memoria.
- [x] Aplicación de las migraciones 0001/0002 a la base local autorizada por el usuario (2026-10-27), con respaldo SQLite previo. RF-001, RF-003, RF-005, RNF-007: 16 pruebas Django, lint y build correctos; backend, frontend y proxy `/api/health/` responden HTTP 200 tras reiniciar los servidores.
- [x] Ampliación aprobada DN-21 / RF-005 (2026-10-27): administrador global crea futuros Dueños desde la interfaz y los selecciona por correo para vincular restaurantes nuevos o existentes; Dueño/Administrador conservan el alta local. Sin migraciones ni dependencias nuevas.
- [x] Interfaz del portal con diseño NEXO y flujo comprobado en navegador con BD QA aislada: alta global → selección por correo → restaurante → login del Dueño → alta y consulta de Mesero. 20 pruebas Django, lint y build correctos.
- [ ] Conciliación del estado en Jira. No se declara completado todo el Sprint 01.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 02 — Configuración del restaurante y carta [MVP]
**RF:** RF-012–018; RF-020–021; RF-023–028; RF-031; RF-034–035.
**Resultado esperado:** Zonas, mesas, carta, precio, exclusiones, observaciones; todo acotado al tenant.
- [x] DN-28 / RF-012 (2026-10-28), implementación y validación en QA: gestión de zonas por OWNER/ADMIN con nombre único por restaurante, creación activa, edición y activación/desactivación sin borrado; permisos en servidor, aislamiento, auditoría atómica e interfaz NEXO responsiva con confirmación. Plan y CA aprobados en el chat. Historial ampliado por solicitud del usuario con clasificación y filtro por tipo de acción en servidor, antes de paginar (RNF-007).
- [x] Verificación DN-28: 64 pruebas Django, check y consistencia de migraciones, lint/build; sin typecheck disponible en frontend JavaScript. Navegador con base temporal: ciclo completo, duplicados, recarga, historial filtrado, aislamiento entre dos restaurantes, Mesero sin gestión y revisión móvil. Migración 0004 aplicada/revertida/reaplicada en QA conservando identidades; detalles en `docs/ZONES.md`.
- [ ] DN-28: revisión del usuario y autorización para aplicar migración 0004 a la base local con respaldo. No aplicada a datos reales; no se modifica cierre de Jira ni se inicia DN-29.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 03 — Recetas, costos e inventario básico [MVP]
**RF:** RF-039–049; RF-054–062; RF-066–070; RF-229.
**Resultado esperado:** Recetas, costos, físico/reservado, reservas y consumo transaccional.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 04 — Mesas, cuentas y pedidos [MVP]
**RF:** RF-088–103; RF-237; RF-241.
**Resultado esperado:** Cuentas, borradores, nuevos pedidos por envío y visibilidad por restaurante.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 05 — Pantalla de cocina (KDS) [MVP]
**RF:** RF-113–117; RF-126–128; RF-140–143; RF-218; RF-222.
**Resultado esperado:** KDS con estados individuales, FIFO, alertas y notificaciones aisladas.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 06 — Modificaciones y cancelaciones [MVP]
**RF:** RF-063–065; RF-104–107; RF-118–124; RF-181–185; RF-219–220; RF-225–226; RF-238–239.
**Resultado esperado:** Aprobaciones, recálculo, liberaciones/mermas, auditoría.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 07 — Cobros e historial de ventas [MVP]
**RF:** RF-144–151; RF-153–154; RF-165–167.
**Resultado esperado:** Cobro único, propinas, ventas históricas y liberación de mesa.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 08 — Apertura y cierre de caja [MVP]
**RF:** RF-155–162; RF-164; RF-189–191; RF-232.
**Resultado esperado:** Sesiones, movimientos, egresos, conciliación y auditoría de caja.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 09 — Descuentos, reportes y dashboard [MVP]
**RF:** RF-173–176; RF-196–203; RF-205; RF-212–214; RF-230.
**Resultado esperado:** Descuentos, KPIs y reportes exclusivos del restaurante autorizado.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 10 — Carta avanzada y personalización [V1]
**RF:** RF-010–011; RF-019; RF-029–030; RF-032–033; RF-036–038; RF-050–052.
**Resultado esperado:** Contraseña, permisos V1, servicio sin mesa, variantes, adiciones, combos y subrecetas.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 11 — Inventario avanzado, compras y proveedores [V1]
**RF:** RF-071–077; RF-080–087; RF-188; RF-210–211; RF-221; RF-243–245.
**Resultado esperado:** Conteos, kardex, compras, proveedores y conteo final de cocina (versión de RF-243–245 por confirmar).
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 12 — Cocina avanzada y estaciones [V1]
**RF:** RF-022; RF-125; RF-129–139; RF-227–228; RF-240.
**Resultado esperado:** Estaciones, prioridades, reposiciones y tiempos de cocina.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 13 — Cuentas, promociones y finanzas avanzadas [V1]
**RF:** RF-108–112; RF-152; RF-163; RF-177–180; RF-186–187; RF-192–195; RF-231.
**Resultado esperado:** División/unión de cuentas, pagos mixtos, promociones, devoluciones y caja avanzada.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 14 — Turnos, horarios y remuneraciones [V1]
**RF:** RF-168–172; RF-246–247; RF-249–253.
**Resultado esperado:** Turnos, horarios, extras, anticipos y pagos (versiones RF nuevos por confirmar).
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 15 — Analítica avanzada y control administrativo [V1]
**RF:** RF-204; RF-206–209; RF-215–216; RF-236.
**Resultado esperado:** Rentabilidad/popularidad, desempeño, utilidad estimada, filtros de auditoría.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

### Sprint 16 — Históricos avanzados y mejoras de operación [V2]
**RF:** RF-053; RF-078–079; RF-217; RF-248.
**Resultado esperado:** Costos históricos, lotes, vencimientos, franjas de venta y reglas de fin de turno.
- [ ] Historias/tareas y CA acordados en Jira.
- [ ] Backend + frontend + persistencia integrada cuando corresponda.
- [ ] Pruebas funcionales, autorizaciones, aislamiento entre restaurantes y regresión.
- [ ] Revisión de entregable, actualización de Jira y commit(s).

## Puertas de calidad y dependencias
- **MVP entregable después del Sprint 09:** flujo integral mesas → borradores → cocina → cancelaciones → cobro → caja → reportes, con auditoría y datos separados por restaurante.
- **Sprint 03 precede a reservas del 04 y su consumo en el 05**; confirmar validación de stock al enviar, operación atómica y reintentos idempotentes.
- **Sprint 06:** requiere que estados de cocina y stock ya funcionen; cambios posteriores solo mediante solicitudes autorizadas.
- **Sprint 11:** RF-243–245 pendientes de definición de conteo final, confirmación y ajustes; no moverlos automáticamente al MVP solo porque PLAN previo los incluía en cocina.
- **Sprint 14:** aclarar conceptos de jornada programada, efectiva, extra, aprobación, anticipos y cálculos antes de programar.
- **Sprint 16:** implementar RF-248 únicamente según política aprobada; no confundirlo con RF-169.

## Definición de terminado para cada historia
- [ ] Vinculación explícita al RF y RN/RNF pertinentes.
- [ ] CA funcionales y casos negativos verificables, incluidos accesos cruzados prohibidos.
- [ ] Control de permisos **en backend**, no solo ocultamiento visual.
- [ ] Pruebas sobre datos de al menos dos restaurantes para operaciones que tocan información de negocio.
- [ ] Tratamiento de errores, consistencia, auditoría y transacciones según aplique.
- [ ] Código validado, pruebas ejecutadas, sin secretos y con documentación actualizada.

## Decisiones abiertas / bloqueos
- [x] Rol y facultades del administrador global de NEXO: crear/activar/desactivar restaurantes y asignar Dueño, sin acceso operativo automático.
- [x] Un usuario en uno o varios restaurantes: aprobado un restaurante por usuario operativo en este alcance.
- [x] Stack confirmado: Django + DRF, React/Vite, SQLite.
- [ ] Permiso del Mesero para finalizar/cobrar (RF-145).
- [ ] Costeo de inventario y snapshots de costos (RF-086, RN-099).
- [ ] Cambios de receta, exclusiones y modificaciones una vez enviado.
- [ ] Conciliación de inventario final (RF-243–245).
- [ ] Clasificación de RF nuevos sin etiqueta de versión y detalle de remuneraciones.

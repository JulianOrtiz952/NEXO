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

**Avance DN-19 / DN-21 / DN-17 / DN-18 (2026-10-22):**
- [x] RNF-033 / RF-007 (2026-10-27): el cliente muestra un error claro en español ante respuestas HTML del servidor y conserva el estado HTTP, en lugar de exponer `Unexpected token`. Siete comprobaciones con respuestas controladas, lint y build correctos. El 500 local por ausencia de `initial_owner_id` sigue pendiente de aplicar la migración 0003 revisada por el usuario.
- [x] Ampliación aprobada DN-23 / RF-007 (2026-10-27): proteger al primer Dueño frente a cambios locales y conservar al menos un Dueño con cuenta/membresía activas; excepción global limitada al primer Dueño, con auditoría atómica y serialización por restaurante. Interfaz NEXO con explicación de bloqueos y formulario global específico.
- [x] Validación de esta ampliación: 34 pruebas Django (incluye concurrencia, migración/reversión, permisos y aislamiento), check y consistencia de migraciones correctos; lint/build correctos, sin script de typecheck en JavaScript. Navegador sobre BD temporal: primer Dueño bloqueado localmente, excepción global con segundo Dueño activo, único Dueño bloqueado y vista móvil de 390 px. Migración/reversión comprobadas además sobre copia de la base local; primer Dueño existente identificado por auditoría.
- [ ] Revisar y aplicar migración 0003 a la base local con respaldo previo; verificar el servidor local después. Validación del usuario pendiente; no cerrar Jira.
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

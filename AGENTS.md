# AGENTS.md

## Qué es este proyecto
**NEXO** es una plataforma web multi-tenant para gestionar restaurantes independientes (DONDE NICO es un restaurante cliente, no el nombre del software): mesas, pedidos, cocina (KDS), inventario con recetas, caja, gastos, turnos, auditoría y analítica para el Dueño.
Los requerimientos completos están en `docs/requirements/` (RF, RNF, RN). **Cita siempre el ID** (ej. RF-058, RN-016) en commits, PRs y comentarios cuando implementes algo.

## Identidad y aislamiento entre restaurantes (MVP, decisión arquitectónica NEXO)
- Cada `Restaurant` constituye un tenant independiente. Cada usuario operativo actúa únicamente en el contexto de los restaurantes a los que tenga membresía activa.
- **Toda consulta y toda mutación de datos de negocio deben restringirse en el servidor al restaurante autorizado**, incluso ante IDs ajenos, cambios de URL, peticiones manipuladas, jobs y operaciones en lote. No confiar en filtros de interfaz o en `restaurant_id` aportado por el cliente.
- Mesas, zonas, carta, recetas, inventario, pedidos, cuentas, ventas, caja, turnos, auditoría y reportes deberán respetar el tenant. Toda relación entre entidades debe comprobar pertenencia al mismo restaurante.
- Los roles `OWNER`, `ADMIN`, `CASHIER`, `WAITER`, `KITCHEN` son **roles dentro de un restaurante**, no privilegios globales. Definir por separado las facultades de administración de la plataforma NEXO antes de implementarlas; no asumir que el OWNER de un restaurante puede consultar otros.
- Administrar múltiples **restaurantes independientes desde el MVP** no equivale a administrar varias **sedes de un mismo restaurante** (RNF-039, V2). No habilitar mezcla de información entre tenants mediante vistas «todos los restaurantes» para personal operativo.
- Probar aislamiento cruzado tanto por lectura como por escritura, enumeración de IDs, acceso a adjuntos/exportaciones, caché, búsquedas y notificaciones. Un recurso ajeno nunca debe exponerse.
- Esta arquitectura multi-tenant es una **decisión de proyecto incorporada posteriormente** a los RF originales: formalizar sus RF/RNF/CA antes de darla por cerrada.

## Stack (POR CONFIRMAR, ajusta antes de empezar)
- **Antes de programar:** inspeccionar el repositorio real y confirmar si el stack existente es Django + Django REST Framework + React/Vite + PostgreSQL u otro. No migrar ni reemplazar código por asumir este stack propuesto.
- Propuesta no confirmada (solo si se aprueba expresamente): TypeScript (strict)
- Framework: Next.js (App Router) + React
- Base de datos: PostgreSQL + Prisma
- Tiempo real (KDS, notificaciones): SSE o WebSockets
- Validación: Zod · Tests: Vitest + Playwright · UI: Tailwind
- Auth: sesiones/JWT con expiración, contraseñas con argon2 o bcrypt

## Comandos de referencia (solo si se confirma el stack Next.js/Prisma; actualizar según el repositorio)
- Instalar: `pnpm install`
- Desarrollo: `pnpm dev`
- Tests: `pnpm test`
- Lint + tipos: `pnpm lint && pnpm typecheck`
- Migraciones: `pnpm prisma migrate dev`
- Build: `pnpm build`

## Estructura propuesta (solo para stack Next.js/Prisma; adaptar al código existente, RNF-040)
```
src/modules/
  tenants/  memberships/  users/  restaurant-config/  menu/  recipes/  inventory/
  purchases/  orders/  kitchen/  cashier/  sales/
  expenses/  shifts/  discounts/  reports/  audit/  notifications/
src/lib/        utilidades compartidas (dinero, fechas, errores)
prisma/         esquema y migraciones
docs/           PRD, reglas de dominio, modelo de datos, requisitos
```
Si se confirma esta arquitectura, cada módulo: `service` (lógica), `repository` (BD), `schema` (Zod), `routes/actions`, `tests`. La lógica de negocio NUNCA va en componentes de UI.

## Invariantes de dominio (no negociables; detalle en `docs/DOMAIN_RULES.md`)
0. **Aislamiento de tenant:** toda autorización, consulta, transacción, auditoría y evento queda en el contexto de `Restaurant`; denegar acceso cruzado por defecto.
1. **Cuenta ≠ Pedido ≠ Borrador.** Cuenta → N pedidos → N detalles. Cada "Enviar a cocina" crea un pedido nuevo. El borrador es libre y no reserva inventario.
2. **Nada enviado desaparece.** Se cancela/devuelve/repone/cortesía, pero nunca se borra (RN-113). Usar borrado lógico en todo.
3. **Históricos inmutables.** Ventas y detalles guardan copia (snapshot) de precio, nombre, costo y descuentos al momento de la venta (RN-016, RN-072, RN-106).
4. **Inventario:** `disponible = físico − reservado`. Enviar a cocina RESERVA; pasar a Preparando CONSUME (baja el físico); cancelar antes de preparar LIBERA; cancelar después NO devuelve (se registra merma).
5. **Dinero:** nunca `float`. Usar entero o `Decimal`. Propina separada de la venta. Descuento NO cambia el consumo de inventario.
6. **Transaccionalidad:** crear pedido + reservar inventario + auditar = una sola transacción (RNF-019).
7. **Idempotencia y concurrencia:** evitar doble procesamiento (RNF-020), cierre único de cuenta (RNF-026), reserva concurrente de stock (RNF-027) con bloqueo/versionado.
8. **Permisos en servidor, siempre.** No basta ocultar botones (RNF-004).
9. **Auditoría** en toda operación sensible, con valor anterior y nuevo. Los registros no se editan ni borran (RNF-007).
10. **Nada hardcodeado** que cambie entre restaurantes: mesas, zonas, métodos de pago, motivos, umbrales (RNF-042).

## Reglas de comportamiento para la IA
- No marcar tareas de Jira como completadas ni moverlas a «Listo», «Hecho», «Done» o equivalentes. El usuario valida el resultado y realiza el cierre en Jira; las pruebas y los commits no autorizan a la IA a cerrar una tarea.
- Antes de cambiar más de 3 archivos o tocar el esquema de BD, muéstrame un plan y espera mi OK.
- Trabaja UN paso del Sprint vigente de `PLAN.md` a la vez; Jira registra el estado real. No adelantes funciones de V1/V2 mientras hacemos MVP.
- No inventes funcionalidades ni reglas. Si algo es ambiguo o contradice los requisitos, registra el bloqueo y pide decisión antes de codificar ese comportamiento.
- Antes de implementar RF que dependan del multi-tenant o de asignación global de privilegios, exige CA aprobados de aislamiento, pertenencia y autorización.
- Respeta los Sprints 01–16 del plan como mapa de alcance; no interpretes subtareas técnicas como autorización para adelantarte a V1/V2.
- No instales dependencias nuevas sin preguntarme.
- No borres ni reescribas archivos ajenos a la tarea.
- Toda migración de BD debe ser reversible y revisada por mí.
- Nunca pongas claves o secretos en el código. Usa `.env` (ignorado por git) y mantén `.env.example`.
- Escribe tests para reglas de negocio críticas (inventario, cuentas, caja, permisos).
- Corre lint, tipos y tests antes de decir que terminaste.
- Al terminar, marca el paso en `PLAN.md`, y explica qué cambiaste en pocas líneas.
- Un DN con interacción de usuario solo está completo cuando incluye una interfaz funcional conectada al backend y con el diseño visual de NEXO (crema/dorado, navegación y componentes coherentes, responsiva y accesible). No darlo por terminado con API, formularios sin diseño o datos de demostración; validar el flujo en navegador y sus permisos.
- El administrador global debe poder crear desde su interfaz las cuentas operativas de futuros Dueños y vincularlas a restaurantes; no exigir consola ni IDs introducidos manualmente para ese flujo. Dueño y Administrador deben poder crear usuarios de su propio restaurante desde su interfaz. Esto no concede acceso global a datos operativos ni permite crear administradores globales desde formularios.
- Si repites un error que ya te corregí, avísame para agregar una regla aquí.

## Convenciones
- Código e identificadores en **inglés**; textos de UI y documentación en **español**.
- Glosario: Cuenta=`Tab`, Pedido=`Order`, Detalle=`OrderItem`, Mesa=`Table`, Insumo=`Ingredient`, Receta=`Recipe`, Merma=`Waste`.
- Roles locales por restaurante: `OWNER`, `ADMIN`, `CASHIER`, `WAITER`, `KITCHEN`. Caja hereda las funciones operativas de Mesero. Administrador global aprobado: crea/activa/desactiva restaurantes, crea futuros Dueños y los vincula; no obtiene acceso automático a empleados, ventas, caja ni otros datos operativos. Los formularios no conceden privilegios globales.
- Errores al usuario: claros, en español, indicando qué pasó y cómo resolverlo (RNF-033).
- UI táctil, responsiva, y nunca depender solo del color para un estado (RNF-029, RNF-031).
- Confirmación antes de acciones críticas: cerrar caja/cuenta, anular, ajustar inventario (RNF-032).
- Commits: `tipo(modulo): descripción [RF-xxx]`. Un commit por cosa que funcione.

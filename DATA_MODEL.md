# Modelo de datos propuesto (borrador, revisar antes de migrar)

## Alcance y estado
- **Borrador conceptual, no esquema aprobado ni migración ejecutada.** Confirmar stack, modelo de autenticación y relaciones antes de generar migraciones.
- NEXO opera **restaurantes independientes (tenants)** desde el MVP. `Branch` (múltiples sedes del mismo restaurante) sería una capacidad distinta y posterior (RNF-039, V2).
- Las entidades aquí descritas son propuestas de diseño derivadas de RF/RNF/RN y de la decisión multi-tenant, no requisitos aprobados automáticamente.

## Principios
- PK `uuid`. Todas las tablas: `created_at`, `updated_at`; entidades de negocio: `is_active` / `deleted_at` (borrado lógico, RN-107).
- Dinero en entero o `NUMERIC`, nunca float. Cantidades de inventario en `NUMERIC(14,4)`.
- `version` (int) en entidades con edición concurrente (cuentas, stock) para control optimista.
- `idempotency_key` único **por restaurante + tipo de operación** en operaciones críticas (enviar a cocina, cobrar); definir alcance y caducidad antes de migrar.
- Snapshots en detalles de pedido/venta: nombre, precio, costo, descuento.

## Tenant y autorización (MVP; incorporar en el esquema antes de implementar)
- `Restaurant`: tenant independiente (`id`, nombre, estado, configuración, fechas), sin mezclar operaciones con otros restaurantes.
- `RestaurantMembership`: vínculo `user_id + restaurant_id` con estado activo y rol(es) locales; único según la política de membresía aprobada. Un usuario podría pertenecer a más de un restaurante **solo si se autoriza explícitamente**; cada sesión/operación usa un restaurante activo validado en servidor.
- `Role` / `Permission` / asignaciones deben tener un ámbito explícito (`restaurant` o `platform`) y no conceder permisos globales a un `OWNER` local. El rol de administración global queda pendiente de definición.
- Todas las entidades de negocio con propietario tenant usan `restaurant_id` (o una relación obligatoria que garantice el mismo tenant); filtrar y autorizar en el servidor. Para vínculos críticos, priorizar integridad reforzada (p. ej. restricciones compuestas `restaurant_id + id`) frente a confiar exclusivamente en validación de aplicación.
- Índices y unicidades son **scoped** cuando corresponda: mesa única por `(restaurant_id, zone_id, identifier)`; números de pedido, referencias de caja y claves de idempotencia según alcance definido por restaurante.
- Nunca permitir relaciones cruzadas: la cuenta, mesa, pedido, detalles, recetas, reservas, pagos y transacciones deben pertenecer al mismo restaurante. Auditoría y notificaciones identifican también el tenant.
- La visibilidad de una vista «Todos los restaurantes» requeriría un rol global explícito, no habilitado por defecto.

## Entidades por módulo
**Usuarios:** `User`, `Restaurant`, `RestaurantMembership`, `Role`, `Permission`, `RolePermission`, `UserPermissionOverride` (V1).
**Configuración:** `Zone`, `Table` (único dentro de restaurante y zona: `restaurant_id + zone_id + identifier`), `ServiceType` (V1), `PaymentMethod`, `Reason` (tipo: cancelación, modificación, desperdicio, devolución, anulación), `KitchenStation` (V1).
**Carta:** `Category`, `Product`, `ProductVariant` (V1), `Addition` (V1), `Combo` / `ComboItem` (V1).
**Insumos/recetas:** `Ingredient`, `Unit`, `UnitConversion`, `Recipe`, `RecipeItem`, `SubRecipe` (V1), `CostHistory` (V2).
**Inventario:** `StockItem` (físico, reservado), `StockMovement` (tipo: ENTRY, RESERVE, RELEASE, CONSUME, WASTE, ADJUSTMENT, PURCHASE, REPLACEMENT; usuario, motivo, referencia), `StockCount` / `StockCountItem` (V1), `Lot` (V2).
**Compras (V1):** `Supplier`, `Purchase`, `PurchaseItem`.
**Ventas:** `Tab` (cuenta: mesa, mesero, estado, totales, version), `Order` (pedido: tab, número, estado derivado, prioridad), `OrderItem` (producto, cantidad, estado cocina, snapshots, estación), `OrderItemModifier` (exclusiones, observaciones, adiciones), `ChangeRequest` (modificación/cancelación: solicitante, estado, resolución por cocina), `Sale`, `Payment` (uno por medio), `Tip`.
**Caja:** `CashRegisterSession` (apertura, fondo, cierre, efectivo real/esperado, diferencia), `CashMovement`.
**Finanzas:** `ExpenseCategory`, `Expense`, `CashWithdrawal` (V1), `ExtraIncome` (V1).
**Descuentos:** `Discount` (usuario, motivo, valor, tipo), `Promotion` (V1), `Complimentary` (V1).
**Cocina (V1):** `Replacement` (vínculo a item original + motivo), `PriorityChange`, `Waste`, `Return`.
**Cocina (V1 provisional según Sprint 11; RF sin etiqueta):** `FinalInventoryCount` (inventario final del cocinero: registro, confirmación o rechazo con notas; RF-243 a RF-245).
**Turnos:** `Shift`, `Schedule`, `ZoneAssignment`, `OvertimeApproval`, `PayrollCalculation`.
**Auditoría:** `AuditLog` (append-only: user, action, module, entity, entity_id, before, after, timestamp). Sin UPDATE/DELETE desde la app.
**Notificaciones:** `Notification`.

## Notas
- El estado de `Order` se deriva de sus `OrderItem`; no es fuente de verdad.
- `StockItem.reserved` y `physical` solo cambian mediante `StockMovement` dentro de una transacción.


## Integridad, transacciones y seguridad de datos
- La solicitud autenticada resuelve en servidor `user_id`, `restaurant_id` activo y permisos locales. El cliente nunca elige libremente un tenant ajeno.
- Enviar un pedido implica validar el tenant de cuenta, productos y recetas; reservar stock; crear el pedido; y auditar **en una sola transacción** (RNF-019).
- La actualización de `StockItem.physical/reserved` y `StockMovement` es atómica; usar bloqueo o control optimista con reintento seguro (RNF-027). Definir controles ante saldos negativos.
- Cobrar o cerrar una cuenta debe ser idempotente y resistente a doble clic y concurrencia (RNF-020, RNF-026).
- Auditar tenant, actor, entidad, acción, antes/después y marca temporal. Preservar históricos y referencias incluso después de desactivar usuarios o restaurantes.
- Conservar snapshots comerciales de pedidos/ventas; **por decidir** el momento exacto de fijación del costo y la metodología de valoración (RF-086, RN-099).
- El acceso a exportaciones, búsquedas, cachés y notificaciones debe aplicar el mismo aislamiento de tenant que la BD.

## Preguntas de modelado pendientes de decisión
1. Relación exacta entre usuario, uno o varios restaurantes y el selector de contexto.
2. Ciclo de vida de restaurantes y privilegios del administrador global de NEXO.
3. Momento de captura de snapshots, política de costeo y cambios de receta tras el envío a cocina.
4. Política para modificaciones, exclusiones y consumo adicional de ingredientes en pedidos ya enviados.
5. ¿Qué constituye un ajuste confirmado del conteo final de cocina (RF-243–245)?
6. Estructura de remuneraciones, adelantos, horarios y horas extra (RF-246–253).
7. Diseño futuro de `Branch` por restaurante sin confundirlo con multi-tenancy desde MVP.

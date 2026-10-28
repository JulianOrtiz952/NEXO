# Reglas de dominio críticas (resumen operativo)
Fuente completa: `docs/requirements/`. Este archivo condensa lo que más se rompe si la IA decide por su cuenta.
**Alcance:** NEXO es una plataforma multi-tenant. Las reglas de separación por restaurante que siguen son una decisión arquitectónica posterior al PDF de RF, pendiente de formalización en requisitos y CA.

## 1. Jerarquía
```
Mesa → Cuenta (abierta/cerrada) → Pedido (uno por "Enviar a cocina") → Detalle (un producto)
Borrador: pedido previo al envío; libre, sin cocina, sin inventario.
```

## 2. Estados
**Detalle (cocina):** `NEW → PREPARING → READY → DELIVERED`  (+ `CANCELLED` desde estados permitidos).
**Pedido:** estado derivado de los estados de sus detalles (RN-050). Nunca se guarda a mano.
**Mesa:** `AVAILABLE` / `OCCUPIED` (y desactivada). Ocupada mientras tenga cuenta abierta.
**Cuenta:** `OPEN → CLOSED` (no se cierra dos veces).

## 3. Inventario (flujo central)
| Evento | Efecto |
|---|---|
| Enviar a cocina | Valida `disponible` y RESERVA ingredientes de la receta. Falla → advertir (RF-060) |
| Cocina pasa a Preparando | Reservado → Consumido; baja stock físico |
| Cancelar en estado Nuevo | LIBERA reserva |
| Cancelar en Preparando/Listo | NO devuelve; registrar merma con motivo |
| Cortesía | Consume inventario normal |
| Descuento | No altera consumo |
| Reposición | Nuevo consumo + vínculo al original + motivo + prioridad alta |
| Compra confirmada | Entrada de inventario; compra anulada exige movimiento compensatorio |
| Ajuste manual | Exige usuario, fecha, cantidad y motivo |
`disponible = físico − reservado`. Todo movimiento: usuario + fecha/hora, nunca se elimina.

## 4. Cambios después de enviar
- Mesero NO edita lo enviado; solo **solicita** modificación o cancelación.
- Cocina acepta o rechaza; Mesero es notificado.
- Nuevo → puede aceptarse sin consumo del original. Preparando → decisión explícita de cocina. Listo → no se modifica; se gestiona con cancelación/devolución/cortesía/reposición.
- Toda cancelación posterior al envío: motivo obligatorio, solicitante, autorizador (si la política lo exige), y estado en que estaba.

## 5. Dinero
- Precio y costo al momento de la venta quedan copiados en el detalle (snapshot).
- Cambiar precio/receta/nombre hoy no altera ventas pasadas.
- Propina separada de venta. Pago mixto: suma de medios = total pagado.
- Efectivo esperado = fondo inicial + ventas en efectivo + entradas − egresos desde caja − retiros. Transferencias no suman efectivo. Retiro ≠ gasto.
- Clasificar todo movimiento: venta, gasto, retiro, propina, ajuste, ingreso extraordinario.

## 6. Fórmulas de reportes
- Utilidad bruta = ingreso − costo estimado
- Margen % = utilidad / ingreso × 100
- Food Cost % = costo / precio × 100
- "Más vendido" = unidades; "mayores ingresos" = dinero; "mayor utilidad" = ingreso − costo. Son tres rankings distintos.

## 7. Prioridades en cocina
FIFO por hora de llegada; la antigüedad aumenta relevancia visual; prioridad manual exige permiso, responsable y motivo; reposición tiene prioridad superior; la hora original nunca se pierde.

## 8. Permisos y auditoría
Sensibles: descuentos, anulaciones, ajustes de inventario, cambios de precio, movimientos de caja, gestión de usuarios, reposiciones, edición de recetas. Auditoría guarda usuario, acción, fecha/hora, entidad, valor anterior y nuevo. Nunca editable ni borrable.

## 9. Concurrencia
Dos usuarios cerrando la misma cuenta → solo uno gana. Dos pedidos simultáneos sobre el mismo stock → no sobre-reservar. Doble clic/reintento → una sola operación (idempotency key).


## 10. Aislamiento multi-restaurante (MVP, decisión NEXO)
- Un `Restaurant` es un tenant; **cada consulta, escritura, cálculo, informe, notificación y movimiento financiero o de inventario está acotado a su restaurante**.
- Un usuario debe contar con una membresía activa y un rol autorizado para operar en el restaurante correspondiente. Un `OWNER` o `ADMIN` no obtiene acceso a otros restaurantes por su nombre de rol.
- RF-007, decisión aprobada el 2026-10-27: cada restaurante conserva al menos un Dueño con cuenta y membresía activas. No se puede retirar el rol al último Dueño activo. El primer Dueño se identifica permanentemente; ningún gestor local, incluido él mismo, puede quitarle el rol OWNER. Solo el administrador global puede hacerlo desde una operación específica, conservando otro Dueño activo del mismo restaurante, con auditoría y decisión transaccional. No concede acceso global a empleados ni a datos operativos. Las futuras operaciones de desactivación deben conservar esta misma invariante.
- RF-008/RF-009, excepción aprobada el 2026-10-27: el administrador global puede suspender al primer Dueño aun siendo el único activo. Esto suspende el acceso de **todos** los usuarios de ese restaurante, incluso otros Dueños, sin desactivar individualmente a sus empleados ni cambiar el estado administrativo del restaurante. Revoca las sesiones locales; reactivar al primer Dueño no restaura esas sesiones ni activa empleados desactivados individualmente. La cadena depende de la identidad permanente del primer Dueño, aunque su rol haya cambiado. Los gestores locales no pueden cambiar su estado ni desactivar al último Dueño activo. Cambios de rol siguen requiriendo otro Dueño activo. La excepción no concede acceso global a empleados ni a datos operativos.
- RNF-007, historial aprobado en este alcance: OWNER/ADMIN consultan las acciones de acceso de su propio restaurante; el administrador global consulta únicamente acciones de administración de plataforma realizadas por identidades globales. Historial de solo lectura con responsable, fecha, registro afectado y valores anterior/nuevo; no expone contraseñas ni tokens. Filtros y analítica avanzada de auditoría permanecen fuera de este alcance.
- Validar en servidor la pertenencia conjunta de `Zone`, `Table`, `Tab`, `Order`, `OrderItem`, `Ingredient`, `StockItem`, `CashRegisterSession`, `Sale` y entidades relacionadas antes de asociarlas. Las claves foráneas y las restricciones deben prevenir mezclas entre tenants.
- Rechazar lectura/modificación por ID de otro restaurante, inclusive solicitudes directas a API, exportaciones, búsquedas, notificaciones y acciones masivas. No aceptar el restaurante del payload como prueba de autorización.
- Reservas, cancelaciones, pagos y cierres se procesan dentro de una transacción y del tenant correcto. Los eventos de auditoría identifican el restaurante de la acción.
- El administrador **global** de NEXO, su acceso a datos y la gestión de altas/bajas de restaurantes requieren una política explícita y aprobación previa; no se infieren de los roles locales.
- Multi-restaurante independiente en MVP no implica múltiples sedes por restaurante: esto último permanece como evolución posible (RNF-039, V2).

## 11. Modificaciones e inventario: pendiente de cerrar criterios
- Para cambios aceptados en estado `NEW`, recalcular reservas conforme a los ingredientes finalmente autorizados, de forma atómica y auditable. **Pendiente de confirmar**: política exacta para inclusiones, exclusiones y diferencia de costos.
- Para cambios aceptados en `PREPARING`, no devolver automáticamente ingredientes ya consumidos; decidir explícitamente el consumo adicional, merma y efecto económico antes de implementarlo.
- En `READY`, usar el procedimiento autorizado de cancelación/devolución/cortesía/reposición, no editar silenciosamente el detalle.
- En RF-243–245, definir alcance del conteo final, registro teórico de comparación, autorización de ajustes y resolución de diferencias antes de construir flujo definitivo.

## 12. Decisiones abiertas (no sustituir con supuestos de la IA)
- ¿Puede `WAITER` cobrar/finalizar cuenta (RF-145) y bajo cuáles permisos?
- Metodología de costeo en compras/recetas: promedio ponderado, último costo, PEPS u otra (RF-086, RN-099).
- Instante exacto de snapshots de costo y precio para reportes; evitar que cambios actuales reescriban la historia (RN-016, RN-106).
- Tratamiento de descuentos en la base de cálculo de `Food Cost` y reportes (RN-098 a RN-102).
- Política de cierre de cuenta con productos aún no entregados o en preparación (RF-145).
- Flujo y autorizaciones de turnos, extras, anticipos y nómina (RF-246–253), además de etiquetas de versión faltantes.
- No marcar estas reglas como implementadas hasta definir CA verificables.

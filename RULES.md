# RULES.md — acceso rápido a las reglas de NEXO

El archivo canónico con las reglas de dominio es **[`DOMAIN_RULES.md`](DOMAIN_RULES.md)**. Esta ruta se incluye por compatibilidad con la denominación solicitada; no mantener reglas duplicadas en dos sitios.

Para instrucciones de desarrollo, revisar también [`AGENTS.md`](AGENTS.md). Para la planificación, [`PLAN.md`](PLAN.md).

## Presentación y entrada de cantidades — RF-024, RNF-029/031/033

Regla transversal aprobada por el usuario: precios y cantidades deben usar el mismo formato durante la escritura y al mostrarse en Productos, Carta, Historial, contadores y futuras pantallas.

- Miles con coma: `1,000`, `11,999`, `999,999`.
- Bloques de millones con apóstrofo recto: `1'000,000`, `12'345,678`, `1,234'567,890`. Agrupar cada bloque de seis dígitos con coma interna.
- Decimales con punto, separados de la agrupación: `11,999.85`, `1'000,000.50`. Conservar los centavos; no redondear importes persistidos al mostrarlos.
- Los campos de importe deben usar texto con `inputMode="decimal"`, sin controles que incrementen/decrementen con rueda o flechas. Las futuras cantidades enteras deben usar teclado numérico sin incrementos accidentales.
- Permitir escribir, pegar, seleccionar, reemplazar y borrar conservando una posición de cursor coherente al agregar separadores. No convertir un pegado inválido en otro importe silenciosamente.
- Para RF-024, validar un máximo de diez dígitos enteros y dos decimales, precio no negativo y campos obligatorios. El cero sigue permitido.
- Enviar al servidor cadenas decimales canónicas sin coma ni apóstrofo; almacenar dinero con Decimal/entero. El formato es presentación y no cambia reglas de cálculo, límites ni autorización.
- Usar el formateador compartido en `frontend/src/numberFormat.js`. No aplicar separadores a IDs, nombres de mesas, fechas, horas, teléfonos, correos o códigos.

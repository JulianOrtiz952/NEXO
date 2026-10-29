# Mesas por zona — DN-29 / RF-013

Plan y CA de DN-29 aprobados por el usuario en el chat el 2026-10-28: alta y consulta de mesas asociadas a zonas. DN-30 / RF-014, DN-31 / RF-015 y DN-32 / RF-016 se incorporan con los alcances aprobados más abajo. Los estados operativos siguen pendientes; no se dan por implementados.

## Criterios aprobados

- OWNER y ADMIN configuran mesas. El administrador global y CASHIER/WAITER/KITCHEN no reciben acceso a esta configuración (RNF-004).
- Crear exige una zona existente y activa del restaurante autenticado. Una zona inactiva conserva las mesas existentes y permite consultarlas, pero rechaza altas nuevas.
- El servidor obtiene el restaurante desde la membresía activa, nunca de campos del cliente. IDs ajenos e inexistentes responden 404. Membresía, usuario o restaurante inactivos impiden acceso.
- La mesa aparece solo en la zona donde fue creada. Su UUID interno es estable. La relación protegida `Table.zone` determina su restaurante sin duplicar una referencia que pueda contradecirlo.
- Crear mesa y registrar auditoría constituyen una transacción, con nueva comprobación de autorización tras adquirir el bloqueo de restaurante. Fallar la auditoría revierte el alta (RNF-007/019).
- No existen endpoints para borrar, editar, trasladar ni cambiar estados de mesas en este DN. No se eliminan mesas al desactivar zonas.

## Interfaz NEXO

`/app#tables`: selector de zona, alta de una mesa por acción, listado de registros con nombre, zona y fecha de creación, carga, errores y estados vacíos. DN-31 sustituye «Mesa registrada» por el nombre configurable y añade edición por tarjeta; no exige escribir IDs. Zonas inactivas se identifican con texto y no permiten altas. Ante ausencia de zonas ofrece enlace a Zonas.

Se preservan navegación, diseño crema/dorado, controles táctiles y adaptación móvil (RNF-029/031/033). Cambiar la zona invalida los resultados previos; respuestas antiguas no restauran mesas de otra selección. El botón se bloquea durante el envío y hay una guarda contra doble envío simultáneo desde el componente.

## API e Historial

- GET `/api/zones/<uuid>/tables/`: lista únicamente mesas de esa zona autorizada.
- POST en la misma ruta: DN-31 requiere `name`; crea una mesa en esa zona. No acepta IDs, restaurante ni otros campos.
- GET/PATCH `/api/tables/<uuid>/`: consulta individual y edición de nombre, restringidas por `zone__restaurant`.
- 400: zona inactiva o campos no admitidos; 401: sin sesión; 403: sin permiso; 404: zona/mesa ajena o inexistente; 409: contención temporal SQLite.
- Evento `table.created`, clasificado en el Historial como **Mesas · Creación**. Persiste actor, restaurante, ID de entidad y snapshot de ID/nombre de zona; muestra el nombre de zona al crear, aunque posteriormente cambie. El filtro en servidor y la paginación existentes mantienen aislamiento. La vista global no incorpora eventos de mesas.

## Migración 0005 para revisión

`backend/api/migrations/0005_table.py` crea únicamente `Table` con UUID, fecha de alta y FK protegida a `Zone`. No modifica datos existentes ni crea mesas de muestra. Sin dependencias nuevas.

Aplicación prevista **tras revisión y autorización del usuario**, con respaldo de la base local:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate api 0005
```

Reversión técnica: `manage.py migrate api 0004`. Elimina la tabla de mesas y sus datos; debe revisarse y respaldarse antes de usarla, y no sustituye una operación de negocio. Conserva identidades, zonas y registros de auditoría.

Aplicación/reversión/reaplicación verificadas en una base QA temporal con una mesa: identidades, seis zonas y auditoría conservadas; al reaplicar la tabla de mesas vuelve vacía. **Revisada y autorizada por el usuario; aplicada a `backend/db.sqlite3` el 2026-10-28**, con respaldo verificado `backend/nexo-before-0005-20261028-170312.sqlite3`. Integridad SQLite correcta; se conservaron cinco usuarios, un restaurante, cuatro membresías, dos zonas y diecinueve auditorías. Nueve pruebas de mesas/migraciones, check, consistencia de migraciones, lint y build correctos. Endpoints de mesas e historial responden HTTP 200/JSON en backend y proxy 5173 con una sesión temporal eliminada al terminar; sin altas de mesas reales durante esta verificación.

## Verificación del 2026-10-28

- 72 pruebas Django correctas, incluidas ocho nuevas: alta por ambos gestores, pertenencia, aislamiento bidireccional de listas/detalles/mutaciones, roles prohibidos, accesos inactivos, zonas inactivas, campos manipulados, métodos no permitidos, relación protegida, rollback y snapshot/clasificación de auditoría.
- Django check, consistencia de migraciones, lint y build correctos. Frontend JavaScript sin script `typecheck`.
- Navegador en QA aislado (`5174`/`8001`): alta real, consulta por zona, zona inactiva bloqueada, persistencia al recargar, filtro Mesas · Creación, restaurante B sin las mesas de A y acceso directo de Mesero sin gestión. Diseño revisado en escritorio y viewport móvil de 390 px, sin desbordamiento horizontal.
- La validación funcional inicial se realizó sin modificar datos reales ni estados de Jira. Migración local aplicada posteriormente con autorización. Pendiente: validación final del usuario; no cerrar Jira automáticamente.

## Cantidad por zona — DN-30 / RF-014

Plan y alcance aprobados por el usuario el 2026-10-28: mantener altas individuales y permitir entre 0 y 100 mesas por zona. No se incorpora un formulario para reducir el total ni se decide automáticamente qué mesas retirar. No se añaden estados ni desactivación individual de mesas; todas las mesas actualmente registradas cuentan para el límite. Si posteriormente se incorpora desactivación individual, su interacción con la cantidad de mesas activas deberá definirse y probarse en ese alcance.

- La zona vacía es válida. Se permite el alta número 100; la siguiente devuelve 400 con explicación en español, sin cambiar mesas ni generar auditorías de altas fallidas.
- `MAX_TABLES_PER_ZONE = 100` expresa el límite fijo de RF-014, común a todos los restaurantes; no constituye un umbral configurable por tenant.
- El servidor cuenta únicamente mesas de la zona autorizada dentro de la misma transacción y bloqueo de restaurante usados para crear/auditar. Las altas simultáneas no pueden ocupar dos veces el último cupo. La contención temporal SQLite devuelve 409 para reintentar, incluyendo contención durante la consulta inicial de autorización dentro de la vista.
- El tope se aplica por zona. Tener 100 mesas en Salón no bloquea crear en Terraza ni afecta otro restaurante. Las consultas y mutaciones con IDs ajenos mantienen el rechazo 404.
- La interfaz muestra `cantidad / 100 mesas`, deshabilita el alta al alcanzar el límite y explica cómo continuar en otra zona. Ante rechazo 400 recarga zonas y mesas para actualizar la capacidad si otra sesión ocupó el último cupo. El bloqueo visual complementa la validación independiente en servidor.
- No requiere migraciones, dependencias ni cambios en datos existentes. Si hubiera zonas preexistentes por encima del límite, se conservan y se impiden nuevas altas; no hay recorte automático de registros.

Verificación de DN-30: 75 pruebas Django correctas (tres nuevas para límites, independencia/aislamiento y concurrencia real con dos conexiones), Django check y consistencia de migraciones, lint/build correctos; frontend JavaScript sin typecheck disponible. Navegador QA aislado con 99 registros: creación número 100, bloqueo/explicación, rechazo y actualización desde una segunda sesión desactualizada, zona diferente con `0 / 100` y alta habilitada. Vista móvil de 390 px sin desbordamiento horizontal. Datos QA ficticios; no se crearon mesas reales ni se modificó el estado de Jira. Validación final del usuario pendiente.

## Nombres editables — DN-31 / RF-015

Plan aprobado y autorización explícita del usuario el 2026-10-28 para añadir nombre editable y preparar una migración que asigne «Mesa 1», «Mesa 2»… por zona, conservando IDs e historial. La autorización de preparación no incluye aplicar 0006 a la base local.

- `Table.name`: texto obligatorio, hasta 100 caracteres, admite números como texto. El servidor retira espacios exteriores y rechaza nombres vacíos, nulos, demasiado largos o campos adicionales. Restricción de BD contra cadena vacía.
- POST de alta y PATCH de edición reciben exclusivamente `name`. Solo OWNER/ADMIN locales; no se trasladan mesas ni se modifican UUID, restaurante, zona o fecha de alta. Las mesas en zonas inactivas conservan edición de nombre; la restricción de nuevas altas permanece.
- El cambio de nombre y la auditoría son atómicos bajo bloqueo de restaurante y autorización revisada en servidor. Un fallo de auditoría revierte el nombre. Guardar el mismo valor no agrega eventos.
- Evento `table.name_changed`: snapshot anterior/nuevo con nombre y zona, actor, entidad y restaurante. Se clasifica como «Mesas · Cambio de nombre». Los eventos de alta nuevos incluyen nombre; los anteriores permanecen intactos y su presentación sigue usando la zona histórica si carecen de nombre.
- Formularios NEXO de alta y edición muestran el nombre en cada tarjeta y conservan los borradores ante errores/actualización periódica. Los mensajes de validación son españoles y no desaparecen por la recarga de zonas. Nombres como `OWNER` o `toString` se muestran como texto, sin traducirlos como roles en el Historial.
- La pantalla actual es de configuración. La vista operativa de Mesero/Caja corresponde al flujo de visualización DN-104 / RF-088 del Sprint 04; no se amplían permisos operativos ni se afirma validado ese flujo futuro. Los nombres quedarán disponibles en las respuestas de los endpoints autorizados para las vistas que se implementen.
- DN-31 no incorporó la restricción de duplicados; se añade en DN-32 / RF-016, descrito más abajo.

### Migración 0006 para revisión

`backend/api/migrations/0006_table_name.py`: añade `name` temporalmente nullable, recorre mesas ordenadas por zona/fecha/UUID asignando `Mesa 1…N` dentro de cada zona y convierte el campo a obligatorio con comprobación de cadena no vacía. No modifica UUID, zona, fecha de alta, usuarios, membresías ni auditorías. No crea eventos retroactivos ni mesas ficticias.

Aplicación prevista **solo tras revisión y autorización del usuario**, con respaldo previo:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate api 0006
```

Reversión técnica: `manage.py migrate api 0005`. Retira la columna de nombres y su comprobación; conserva las mesas con sus IDs, fechas y zonas y todos los eventos de auditoría. Los nombres actuales se pierden al retirar la columna; reaplicar vuelve a asignar los nombres iniciales, por lo que se requiere respaldo y revisión antes de revertir.

Probada aplicación/reversión/reaplicación en BD de pruebas con varias zonas y dos restaurantes, verificando IDs, fechas, zonas y eventos idénticos. **Revisada y autorizada por el usuario; aplicada a `backend/db.sqlite3` el 2026-10-28**, con respaldo verificado `backend/nexo-before-0006-20261028-173618.sqlite3`. Cuatro mesas recibieron nombres iniciales por zona; IDs, zonas y fechas se compararon exactamente con el respaldo usando SQLite. Las 23 auditorías, dos zonas, cinco usuarios, un restaurante y cuatro membresías permanecieron intactos. Dieciocho pruebas de mesas/migraciones, check, consistencia de migraciones, lint y build correctos después de aplicarla. Sin dependencias nuevas.

Verificación DN-31: 82 pruebas Django correctas (siete nuevas de nombres/migración), regresión específica de 18 pruebas tras ajustar mensajes, check, consistencia de migraciones y lint/build correctos. Frontend JavaScript sin script typecheck. Pruebas existentes de alta/capacidad adaptadas al nombre obligatorio. Navegador QA: nombres iniciales, edición «Mesa 1» → «Ventana», alta «12», error de blancos persistente, recarga, historial anterior/nuevo filtrado, restaurante B con sus propios nombres, Mesero sin gestión y edición móvil «Ventana principal» a 390 px sin desbordamiento.

Pendientes: validación final del usuario y posterior comprobación del nombre en la futura vista operativa. Migración local 0006 aplicada con autorización; Jira no se cierra automáticamente.

## Identificador único — DN-32 / RF-016

Plan y CA aprobados explícitamente por el usuario el 2026-10-28 antes de tocar el esquema. Crear o renombrar una mesa debe rechazar un identificador ocupado en su zona, ignorando mayúsculas y espacios exteriores. El mismo identificador se permite en otras zonas y restaurantes. No se quitan acentos, ceros iniciales ni espacios interiores.

- `Table.name_key = name.strip().casefold()` conserva la presentación en `name` y compara con clave Unicode. Capacidad de 300 caracteres para admitir expansiones de `casefold` de nombres válidos de 100 caracteres, sin reducir el máximo aprobado de RF-015.
- Restricción única BD `(zone, name_key)` y comprobación de clave no vacía. `save()` sincroniza la clave, también al actualizar solo `name`; las operaciones de carga masiva que omiten `save()` deben proporcionar explícitamente la clave canónica. No hay endpoints de importación ni de traslado en este alcance.
- Alta y edición comprueban duplicados dentro de la zona autorizada y del bloqueo/transacción existentes. La edición excluye la propia mesa: mantener el nombre no crea un evento; cambiar solo mayúsculas está permitido y se audita como edición de presentación.
- El duplicado devuelve 400 con explicación en español, sin modificar mesa, ID, fecha o auditoría. Se traduce la violación de la restricción única conocida; otras excepciones de integridad no se disfrazan como duplicados. La contención temporal SQLite sigue respondiendo 409 para reintentar.
- La interfaz explica la regla y conserva el nombre escrito ante el rechazo. Se reutilizan formularios NEXO y alertas accesibles de DN-31; el servidor es quien decide la unicidad, incluso con solicitudes manipuladas o simultáneas.
- Se mantiene aislamiento por la relación zona→restaurante y los permisos OWNER/ADMIN. No se consulta la existencia de nombres en zonas ajenas para responder a una mutación local.

### Migración 0007 para revisión

`backend/api/migrations/0007_table_unique_name.py` añade la clave temporalmente nullable, valida todos los nombres existentes antes de rellenarla y aplica la obligatoriedad/restricción única. Si encuentra nombres duplicados según la comparación aprobada o vacíos al recortar, aborta con explicación y revierte la migración completa. No renombra ni elimina mesas, ni modifica eventos anteriores.

Aplicación prevista **solo tras revisión y autorización del usuario**, con respaldo previo y nueva comprobación de colisiones:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate api 0007
```

Reversión técnica: `manage.py migrate api 0006`. Retira únicamente la clave auxiliar y sus dos restricciones; conserva nombres visibles, UUID, fechas, zonas y auditorías. Requiere revisión y respaldo. Pruebas verifican fallo ante colisiones sin cambiar registros, posterior aplicación tras corregir explícitamente el dato de prueba, reversión y reaplicación.

**Revisada y autorizada por el usuario; aplicada a `backend/db.sqlite3` el 2026-10-28**, con respaldo verificado `backend/nexo-before-0007-20261028-232519.sqlite3`. La comprobación previa y la migración no encontraron colisiones entre las diez mesas. Se verificaron sus claves canónicas y la conservación exacta de nombres, UUID, fechas y zonas; también de 35 auditorías, tres zonas, seis usuarios, dos restaurantes y cinco membresías. Veintiséis pruebas de mesas/migraciones, check, consistencia de migraciones y lint/build correctos tras aplicarla; sin migraciones pendientes. Backend y proxy 5173 responden 200/JSON en endpoints de mesas e historial con una sesión temporal eliminada al terminar, sin crear ni renombrar mesas reales. No se modificaron estados de Jira ni dependencias.

Verificación DN-32: 90 pruebas Django correctas, incluidas ocho nuevas para duplicados de alta/edición, mayúsculas/espacios/Unicode, exclusión de la propia mesa, identidad/históricos intactos, coincidencia permitida entre zonas/tenants, restricción BD, sincronización de clave, migración y carreras reales de alta y edición. Regresión anterior adaptada para usar nombres válidos y únicos en los datos de prueba. Django check, consistencia de migraciones, lint y build correctos; frontend JavaScript sin script typecheck.

Navegador QA aislado: rechazos de alta ` mESA 1 ` y renombrado de Mesa 2 a `MESA 1` en Salón, nombres originales conservados, alta `Mesa 1` permitida en Terraza y ausencia de auditorías de cambios de nombre por intentos rechazados. Revisado mensaje y formulario en móvil de 390 px sin desbordamiento horizontal y escritorio. Pendiente: validación final del usuario; 0007 aplicada localmente con autorización y Jira sin cierre automático.

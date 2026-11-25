# Manual de usuario: gestión de biblioteca

## 1. Para qué sirve

La aplicación permite gestionar libros y socios, registrar préstamos y devoluciones, importar datos desde CSV y exportar el histórico. Trabaja con una base de datos MySQL existente: **los cambios que haga en la aplicación se guardan en esa base**.

La ventana tiene cinco pestañas: **Libros**, **Socios**, **Préstamos y devoluciones**, **Reservas** e **Importar / Exportar**.

## 2. Antes de empezar

Necesita Windows con Python 3.14 y las dependencias instaladas, acceso a MySQL 8 y una base `biblioteca` ya preparada, incluida la migración de reservas y prórrogas. Si no administra el servidor, solicite a la persona responsable los datos de conexión y los permisos necesarios.

1. Compruebe que el servidor MySQL está iniciado.
2. En la carpeta de la aplicación, abra `.env` y configure host, puerto, usuario, contraseña y nombre de la base. No comparta ese archivo.
3. En PowerShell, desde esa carpeta, ejecute:

   ```powershell
   python app.py
   ```

Si utiliza el entorno virtual del proyecto, ejecute `.\.venv\Scripts\python app.py` en lugar de `python app.py`. Consulte [instalación y configuración](../README.md) si aún no ha preparado las dependencias.

Cuando termine, cierre la ventana con el botón **X**. Si aparece un error de conexión, consulte la sección [Problemas frecuentes](#9-problemas-frecuentes).

## 3. Libros

Abra **Libros** para consultar y mantener el catálogo.

### Añadir un libro

1. Pulse **Limpiar** para empezar con el formulario vacío.
2. Escriba **ISBN**, **Título**, **Autor**, **Año de publicación** y **Ejemplares disponibles**.
3. Pulse **Crear** y compruebe el mensaje de confirmación.

El ISBN, el título y el autor son obligatorios. El año debe ser un número entero positivo; los ejemplares deben ser un entero igual o superior a cero. **Ejemplares disponibles** es el stock que se puede prestar ahora, no el total histórico de ejemplares.

### Buscar y recorrer el catálogo

Escriba parte del título, autor o ISBN en **Buscar**. La tabla se actualiza al escribir. Borre el texto para volver al listado completo. Se muestran hasta **15 registros por página**; use **Anterior** y **Siguiente** para recorrerlos. La tabla tiene barras de desplazamiento.

### Editar o eliminar

1. Seleccione una fila de la tabla: sus datos aparecerán en el formulario.
2. Para cambiarla, modifique los campos y pulse **Editar**.
3. Para eliminarla, pulse **Eliminar** y confirme cuando se le pregunte.

**Limpiar** vacía el formulario y quita la selección; no elimina el libro. La base de datos puede impedir eliminar un libro asociado a préstamos. Si ocurre, consulte a la persona administradora antes de modificar el histórico.

## 4. Socios

Abra **Socios** para consultar y mantener los datos de las personas socias.

### Añadir un socio

1. Pulse **Limpiar**.
2. Introduzca **Nombre**, **Apellidos** y un **Email** válido. El teléfono puede quedar vacío.
3. Compruebe la **Fecha de alta**: se propone la fecha de hoy y puede modificarla con el formato `AAAA-MM-DD`, por ejemplo `2026-11-25`.
4. Pulse **Crear** y compruebe la confirmación.

### Buscar, editar o eliminar

- Busque escribiendo parte del **nombre**, los **apellidos** o el **email**. El resultado cambia al escribir y se muestra en páginas de hasta 15 registros.
- Seleccione una fila, cambie sus datos y pulse **Editar**.
- Para eliminarla, seleccione la fila, pulse **Eliminar** y confirme.
- **Limpiar** vacía el formulario, quita la selección y vuelve a proponer la fecha de hoy.

La base de datos puede impedir eliminar un socio asociado a préstamos.

## 5. Préstamos y devoluciones

### Registrar un préstamo

1. Abra **Préstamos y devoluciones**.
2. Seleccione un **Socio** y un **Libro disponible**. El selector solo muestra libros con stock positivo e indica su cantidad disponible.
3. Pulse **Registrar préstamo**.
4. Compruebe la confirmación y localice el préstamo en la tabla. El stock disponible se reduce en uno.

**Límite:** cada socio puede tener como máximo **dos préstamos activos** a la vez. Si ya tiene dos, aparecerá un error y no se registrará otro. Para el cómputo, un préstamo se considera activo si su estado es `Activo` **o** si su fecha de devolución real está vacía.

**Plazo:** la aplicación registra como fecha de préstamo la fecha actual del equipo y calcula automáticamente la devolución prevista **20 días naturales después**. Por ejemplo, un préstamo del 20 de diciembre de 2026 vence el 9 de enero de 2027. La fecha prevista aparece en la tabla.

Si el libro se agota antes de confirmar la operación, la aplicación mostrará un error y no registrará el préstamo.

### Consultar préstamos

En **Mostrar** elija:

- **Todos:** muestra el histórico completo.
- **Solo Activos:** muestra los préstamos con estado `Activo` o sin fecha de devolución real.
- **Devueltos:** muestra los que tienen fecha real y estado distinto de `Activo`.

Los préstamos se ordenan por ID ascendente. Pulse **Actualizar** para volver a consultar los datos. Esta tabla no está paginada.

### Registrar una devolución

1. Elija **Solo Activos** para localizar el préstamo.
2. Seleccione su fila y pulse **Registrar devolución**.
3. Compruebe la confirmación. La fecha real se establece a hoy, el estado cambia a `Devuelto` y el stock del libro aumenta en uno.

No se puede registrar de nuevo una devolución con fecha real ya informada. Si un registro aparece activo pero ya tiene fecha real, hay una inconsistencia que debe revisar la persona administradora.

**Importante:** la aplicación no bloquea automáticamente nuevos préstamos por retraso ni cambia el estado automáticamente al vencer.

### Prorrogar un préstamo

1. En **Préstamos y devoluciones**, seleccione el préstamo que quiere prorrogar.
2. Pulse **Prorrogar préstamo**.
3. La aplicación comprueba que no tenga fecha real de devolución, que no se haya prorrogado antes, que no haya vencido y que ningún otro socio tenga una reserva para el libro.
4. Si se permite, se suman **20 días naturales a la fecha de devolución prevista**. El mensaje y la tabla muestran la nueva fecha.

Solo se permite **una prórroga por préstamo**, hasta el día de devolución prevista inclusive; a partir del día siguiente se rechaza por retraso. Se usa la fecha local del ordenador donde se ejecuta la aplicación. Una reserva del mismo socio no la impide; una reserva de cualquier otro socio sí, incluso si existen otros ejemplares disponibles. Prorrogar no cambia el stock ni la fecha de préstamo.

Si el préstamo ya se ha devuelto, aparece este aviso:

> Este préstamo ya tiene registrada la devolución y no se puede prorrogar. Para volver a prestar el libro, registre un nuevo préstamo si se cumplen las condiciones.

Para hacerlo, cierre el aviso, seleccione el socio y el libro en **Préstamos y devoluciones** y pulse **Registrar préstamo**. El libro debe tener stock y el socio debe tener menos de dos préstamos activos. El nuevo préstamo se registra por separado; el devuelto permanece en el histórico.

### Registrar y cancelar reservas

1. Abra la pestaña **Reservas**.
2. Seleccione un socio y un libro; el selector incluye libros sin stock.
3. Pulse **Registrar reserva**. La tabla muestra las reservas vigentes.
4. Para cancelar una reserva, seleccione su fila, pulse **Cancelar reserva** y confirme.

Un socio no puede tener dos reservas vigentes del mismo libro. Registrar o cancelar una reserva no cambia el stock. Las reservas no caducan ni se cancelan automáticamente cuando se presta un libro; deben cancelarse manualmente cuando ya no sean necesarias. Esta versión no aplica prioridades de reserva al registrar préstamos.

## 6. Importar datos

Abra **Importar / Exportar**. Los diálogos proponen la carpeta `imports`, aunque puede seleccionar un archivo de otra carpeta. Los archivos deben estar codificados en **UTF-8**, usar comas como separador y tener las cabeceras exactas y en el orden mostrado. Utilice los ejemplos de `imports` como plantilla.

### Importar libros

La primera línea debe ser:

```csv
isbn,titulo,autor,anio_publicacion,ejemplares
```

1. Pulse **Importar libros** y seleccione el CSV.
2. Si el ISBN no existe, se crea el libro con los ejemplares indicados.
3. Si ya existe un único libro con ese ISBN, se suman los ejemplares al stock disponible.
4. Revise el resumen de libros nuevos, libros existentes actualizados y errores.

Por ejemplo, si un libro existente tiene 3 ejemplares disponibles y el archivo indica 2 para su ISBN, pasará a tener 5. **No importe de nuevo el mismo archivo sin comprobarlo:** volverá a sumar su stock. Si hay varios libros con el mismo ISBN, esa fila se informa como error.

### Importar socios

La primera línea debe ser:

```csv
nombre,apellidos,email,telefono
```

1. Pulse **Importar socios** y seleccione el CSV.
2. Los emails ya existentes se omiten; los socios nuevos se insertan con la fecha actual del servidor MySQL.
3. Revise el resumen de socios insertados, duplicados, errores y el total actual de socios en la base.

### Importar reservas y prórrogas

Ambos archivos tienen la cabecera `isbn,email`. El ISBN identifica el libro y el email, el socio.

1. Pulse **Importar reservas** o **Importar prórrogas** y seleccione el archivo correspondiente.
2. Para una reserva deben existir un único libro y un único socio con esas referencias. Una reserva ya existente se informa como error.
3. Para una prórroga debe existir exactamente un préstamo de esa pareja sin devolución registrada. Se aplican las mismas reglas que al prorrogar desde la pestaña de préstamos: plazo no vencido, una sola prórroga y ninguna reserva de otro socio. Si hay varios préstamos coincidentes, prorrogue el deseado manualmente.
4. Revise el resumen de reservas registradas o préstamos prorrogados y los errores por línea.

En todos los tipos de importación las filas válidas se guardan **una por una**. Si hay errores, las filas anteriores ya guardadas no se deshacen; revise el detalle antes de corregir y volver a importar. Cancelar la selección de archivo no importa nada. Repetir reservas o prórrogas ya registradas produce errores, no nuevas operaciones.

Los archivos [prueba_libros.csv](../imports/prueba_libros.csv) y [prueba_socios.csv](../imports/prueba_socios.csv) contienen datos ficticios. Impórtelos preferiblemente en una base de pruebas, ya que crean datos reales en la base configurada.

Para probar [prueba_reservas.csv](../imports/prueba_reservas.csv) y [prueba_prorrogas.csv](../imports/prueba_prorrogas.csv), con cinco filas cada uno:

1. Configure una **base de pruebas** con el esquema y la migración de reservas y prórrogas aplicados.
2. Importe los libros y socios de prueba si aún no existen. Reimportar libros suma de nuevo sus ejemplares.
3. En **Préstamos y devoluciones**, cree un préstamo para cada pareja ISBN/email de `prueba_prorrogas.csv`: compruebe el libro y el socio seleccionados. Cada socio debe tener menos de dos préstamos activos y el libro debe tener stock. Cada pareja debe tener exactamente un préstamo sin devolución, dentro de plazo, sin prórroga previa ni reservas de otros socios.
4. Importe las reservas y después las prórrogas con sus botones. Los archivos de ejemplo reservan libros distintos de los que se prorrogan. Compruebe los resultados en las pestañas **Reservas** y **Préstamos y devoluciones**.

## 7. Exportar el histórico

1. En **Importar / Exportar**, pulse **Exportar CSV** o **Exportar JSON**.
2. El diálogo propone la carpeta `exports` y un nombre con la fecha y hora locales, por ejemplo `prestamos_2026-11-25_20-01-02.csv`. Puede cambiar la carpeta o el nombre.
3. Confirme dónde guardar el archivo. La aplicación indicará cuántos préstamos se exportaron.

La exportación contiene **todo el histórico**, aunque en la pestaña de préstamos esté seleccionado un filtro. Incluye ID, ISBN, título, nombre completo y email del socio, fechas de préstamo y devolución y estado. CSV se guarda en UTF-8 con BOM; JSON en UTF-8.

Los archivos contienen datos personales de los socios: guárdelos y compártalos únicamente con personas autorizadas. Si cancela el diálogo no se crea la exportación.

## 8. Ejemplo completo de uso

En una base de pruebas:

1. Cree un socio y tres libros con al menos un ejemplar disponible.
2. Preste dos de esos libros al socio. Compruebe que sus fechas previstas son 20 días posteriores.
3. Intente prestar el tercero: la aplicación debe mostrar el aviso de límite.
4. Devuelva uno de los dos préstamos y vuelva a intentar el tercero.
5. Exporte el histórico si necesita conservar un informe.

Este ejercicio modifica la base y deja los préstamos en el histórico. Hay más comprobaciones en el [documento de pruebas](pruebas.md).

## 9. Problemas frecuentes

| Situación | Qué revisar |
|---|---|
| Error de conexión o acceso denegado | Compruebe que MySQL está iniciado y que host, puerto, usuario, contraseña, base y permisos de `.env` son correctos. Las variables de entorno existentes tienen prioridad sobre `.env`. |
| No aparece un libro en el selector | Compruebe en Libros que tenga ejemplares disponibles mayores que cero y pulse **Actualizar** en Préstamos. |
| Se alcanza el máximo de 2 libros | Revise los préstamos activos del socio y registre una devolución cuando corresponda. |
| No se puede prorrogar | Compruebe que el plazo no haya vencido, que no tenga devolución registrada ni una prórroga previa y que ningún otro socio tenga el libro reservado. Revise también la fecha local del ordenador. |
| Préstamo ya devuelto | No se puede prorrogar. Para prestar otra vez el libro, registre un nuevo préstamo si hay stock y el socio cumple el límite. |
| No se puede registrar una reserva | Compruebe las selecciones y que el socio no tenga ya una reserva del mismo libro. |
| No se puede eliminar un libro o socio | Puede tener préstamos relacionados protegidos por claves foráneas; consulte a la persona administradora. |
| Cabecera CSV incorrecta | Compare nombres, orden y separadores con las cabeceras de la sección 6. |
| Importación con errores | Lea el resumen y las líneas indicadas. Las filas válidas anteriores pueden haberse guardado; no repita el archivo completo sin revisarlo. |
| No se puede preparar `imports` o `exports` | Tras el aviso, elija otra carpeta en el diálogo y compruebe sus permisos. |
| Ventana temporalmente sin respuesta | Las consultas e importaciones se ejecutan en el hilo de la interfaz; un servidor lento o un archivo grande puede hacer que tarde en responder. |

Para detalles técnicos, consulte el [manual de desarrollador](manual_desarrollador.md).

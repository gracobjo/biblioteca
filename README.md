# Gestión de biblioteca

Aplicación Tkinter para Python 3.14 y una base MySQL 8 **existente**. Requiere las tablas originales y las tablas `reservas` y `prorrogas` añadidas por la migración. Deben usar InnoDB y claves foráneas; la aplicación no las crea automáticamente. Se recomiendan índices únicos en `libros.isbn` y `socios.email` para impedir duplicados incluso con importaciones concurrentes o con otros clientes.

## Ejecutar en Windows

1. Inicie MySQL y compruebe que existe la base `biblioteca` con las tablas indicadas. En una instalación nueva, aplique una vez la [migración de reservas y prórrogas](doc/manual_desarrollador.md#migración-de-reservas-y-prórrogas).
2. Abra PowerShell en la carpeta de la aplicación. Si acaba de clonar este repositorio, entre con:

```powershell
cd biblioteca
```

   Si usa la copia incluida en el repositorio CE_Python, desde su raíz ejecute `cd tareas\biblioteca`.

3. En la carpeta de la aplicación, edite `.env` y establezca su contraseña y demás datos de conexión. Si no existe, copie `.env.example` a `.env`. El archivo `.env` está excluido de Git; no comparta su contraseña. Para contraseñas con caracteres especiales, utilice comillas simples en el archivo, por ejemplo `BIBLIOTECA_DB_PASSWORD='su contraseña'`.
4. Si ya instaló las dependencias en el Python que utiliza, arranque la aplicación:

```powershell
python app.py
```

### Instalación opcional en un entorno virtual

Si todavía no ha instalado las dependencias, puede crear un entorno aislado desde la carpeta de la aplicación:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

En adelante, use `.\.venv\Scripts\python app.py` para arrancar con ese entorno.

Los valores predeterminados son `localhost`, `3306`, `root`, contraseña vacía y base `biblioteca`; `BIBLIOTECA_DB_NAME` permite elegir otra base con el mismo esquema. Las variables de entorno existentes tienen prioridad sobre `.env`. El usuario MySQL necesita permisos de lectura, inserción, actualización y eliminación en las tablas. La conexión tiene un límite de 10 segundos y las operaciones de lectura y escritura de 30 segundos. Las consultas y las importaciones se ejecutan en el hilo de la interfaz, por lo que archivos grandes o un servidor lento pueden congelarla temporalmente.

## Uso y datos

En Libros y Socios, seleccione una fila para editarla o eliminarla. La fecha de alta usa `AAAA-MM-DD`; al crear un socio se propone la fecha de hoy. Las claves foráneas pueden impedir eliminar registros con préstamos asociados. El campo de ejemplares del formulario representa el stock **disponible**, no el total.

En Préstamos, el selector muestra los libros con stock y la tabla ordena los préstamos por ID ascendente. El máximo de dos préstamos se comprueba por `estado = 'Activo' OR fecha_devolucion_real IS NULL`, bloqueando la fila del socio durante la operación. Las operaciones de préstamo y devolución actualizan stock y préstamo en una misma transacción. Un registro con fecha real ya informada y estado `Activo` se muestra como activo por la regla indicada, pero no puede devolverse de nuevo: hay que corregir la inconsistencia en la base de datos.

Un préstamo sin devolución registrada puede prorrogarse una sola vez por 20 días desde su fecha prevista, siempre que no esté vencido ni haya una reserva de otro socio para ese libro. Se admite la prórroga hasta el mismo día de vencimiento, inclusive, según la fecha local del ordenador. Las reservas se registran y cancelan en la pestaña **Reservas**; no descuentan stock, no caducan ni se cancelan automáticamente al prestar el libro.

Si el préstamo ya tiene registrada la devolución, la aplicación explica que no se puede prorrogar. Para volver a prestar el libro, registre un préstamo nuevo, sujeto a las condiciones habituales de stock y límite por socio.

Los ejemplos en `imports` muestran las cabeceras exactas. El diálogo de importación abre inicialmente esa carpeta, pero permite elegir un CSV de otra ubicación. Los CSV deben ser UTF-8 (con o sin BOM), separados por comas. Cada fila válida se confirma individualmente: los errores no deshacen filas ya importadas y se detallan al finalizar. Los libros existentes se identifican por ISBN y suman stock; los socios existentes por email se omiten. El resumen distingue los libros nuevos de los libros ya existentes cuyo stock se ha actualizado; no muestra el total de ejemplares. El resumen de socios muestra también el total actual de socios en la base de datos. Una interrupción o error de lectura puede dejar importadas las filas anteriores. Para exportar se incluyen todos los préstamos con sus datos relacionados; CSV usa UTF-8 con BOM y JSON UTF-8.

Para probar la importación y la paginación, [prueba_libros.csv](imports/prueba_libros.csv) y [prueba_socios.csv](imports/prueba_socios.csv) contienen 20 registros ficticios cada uno. Importe cada archivo con su botón correspondiente. Al importar los libros más de una vez se vuelve a sumar el stock; los socios repetidos se omiten.

[prueba_reservas.csv](imports/prueba_reservas.csv) y [prueba_prorrogas.csv](imports/prueba_prorrogas.csv) contienen cinco operaciones ficticias cada uno, con cabecera `isbn,email`. Importe con sus botones en una base de pruebas y prepare primero los cinco préstamos necesarios, como se explica en el [manual de usuario](doc/manual_usuario.md#importar-reservas-y-prórrogas). Las filas se confirman individualmente y los errores no deshacen las anteriores.

Al exportar, se crea la carpeta `exports` junto a la aplicación y se propone como ubicación inicial, junto con un nombre como `prestamos_2026-11-25_20-01-02.csv` (o `.json`), con la fecha y hora locales al abrir el diálogo. Puede cambiar el nombre o la ubicación antes de guardar. Si no se puede crear la carpeta predeterminada de importación o exportación, aparece un aviso y puede elegir otra ubicación. `exports` está excluida de Git.

## Estructura de carpetas

- `imports/`: CSV de ejemplo y archivos de entrada.
- `exports/`: destino predeterminado de los CSV y JSON exportados; excluido de Git.
- `doc/`: documentación, requisitos, casos de uso y pruebas.
- `tests/`: pruebas automáticas.
- `migrations/`: migración SQL para reservas y prórrogas.
- En la raíz de la aplicación: módulos Python, configuración y dependencias.

Para ejecutar las pruebas desde la carpeta de la aplicación, usando el mismo Python en el que instaló las dependencias:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas usan una base de datos simulada; no comprueban la conexión real a MySQL. Si utiliza el entorno virtual anterior, sustituya `python` por `.\.venv\Scripts\python`.

### Comprobar el límite y la duración de préstamos

Para ejecutar solo las pruebas de estas reglas:

```powershell
python -m unittest discover -s tests -p test_biblioteca.py -k ReglasPrestamosTest -v
```

La prueba crea datos aislados en SQLite en memoria: permite dos préstamos, rechaza un tercero sin descontar stock, permite otro tras una devolución y comprueba el vencimiento a los 20 días incluso al cambiar de año y en año bisiesto. También comprueba que cuentan como activos los préstamos con `estado = 'Activo'` **o** fecha real vacía. SQLite no reproduce los bloqueos concurrentes de MySQL, por lo que estas pruebas no verifican la concurrencia en InnoDB.

Para comprobarlo manualmente en la aplicación, use un socio de prueba sin préstamos activos y tres libros con stock: registre dos préstamos y verifique en la tabla que sus fechas previstas son 20 días posteriores; intente registrar el tercero y compruebe el aviso de límite. Después, devuelva uno de los dos y compruebe que puede registrar el tercero. Esta comprobación modifica la base de datos configurada y deja un histórico; hágala preferiblemente en una base de pruebas.

## Documentación

- [Manual de usuario](doc/manual_usuario.md).
- [Manual de desarrollador](doc/manual_desarrollador.md).
- [Especificación de requisitos](doc/especificacion_requisitos.md).
- [Casos de uso y diagramas UML](doc/casos_de_uso_y_diagramas_uml.md).
- [Pruebas automáticas y manuales](doc/pruebas.md).

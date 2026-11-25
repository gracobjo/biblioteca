# Manual de desarrollador

## 1. Alcance y referencias

Aplicación de escritorio con Python 3.14, Tkinter/ttk y MySQL 8. La aplicación usa una base existente y no crea ni migra tablas al arrancar; la migración SQL se aplica aparte. Véanse la [especificación](especificacion_requisitos.md), los [casos de uso y diagramas](casos_de_uso_y_diagramas_uml.md), las [pruebas](pruebas.md) y el [manual de usuario](manual_usuario.md).

## 2. Estructura

Rutas relativas a la carpeta de la aplicación:

| Ruta | Responsabilidad |
|---|---|
| `app.py` | Ventana, pestañas, formularios, tablas, diálogos, mensajes y coordinación de operaciones. |
| `config.py` | Valores predeterminados y lectura de `.env` y variables de entorno. |
| `database.py` | Conexiones, consultas, repositorio, reglas de préstamo/devolución y transacciones. |
| `services.py` | Validaciones, lectura de CSV y escritura de CSV/JSON. |
| `requirements.txt` | Dependencias `mysql-connector-python` y `python-dotenv`. |
| `.env.example` | Plantilla sin credenciales para crear `.env`. |
| `imports/` | CSV de ejemplo y ubicación inicial del diálogo de importación. |
| `exports/` | Ubicación inicial de exportaciones; excluida de Git. |
| `tests/` | Pruebas automáticas con `unittest`. |
| `migrations/` | Migración aditiva para reservas y registro de prórrogas. |
| `doc/` | Manuales, requisitos, casos de uso y documentación de pruebas. |

`.env`, `exports/`, `__pycache__/` y `*.pyc` están excluidos por el `.gitignore` de la aplicación. Los archivos que el usuario guarde fuera de `exports` no quedan protegidos por esa regla.

## 3. Preparación en Windows

Desde PowerShell, en la carpeta de la aplicación:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

El último comando crea `.env` a partir de la plantilla; **no lo ejecute si ya tiene un `.env` configurado**, para no sobrescribirlo. Edite el archivo con sus datos y ejecute:

```powershell
.\.venv\Scripts\python app.py
```

La base `biblioteca` y sus tablas deben existir antes de abrir la aplicación. El usuario MySQL necesita permisos de lectura, inserción, actualización y eliminación en ellas. Para pruebas que escriben datos, utilice una base aislada con el mismo esquema y una cuenta adecuada.

### Migración de reservas y prórrogas

En una base que solo tenga las tres tablas originales, haga una copia de seguridad y ejecute una vez [001_reservas_prorrogas.sql](../migrations/001_reservas_prorrogas.sql) con una cuenta autorizada, por ejemplo abriéndolo y ejecutándolo en MySQL Workbench después de seleccionar la base correspondiente. La migración crea `reservas` y `prorrogas`; no modifica las tablas originales.

El SQL está preparado para el esquema inspeccionado, cuyas claves `id_libro`, `id_socio` e `id_prestamo` son `INT UNSIGNED`. En otro esquema, verifique y adapte los tipos de las claves foráneas antes de aplicarlo. No vuelva a ejecutarlo si las tablas ya existen: MySQL confirma los cambios DDL de forma implícita. Si falla parcialmente, inspeccione qué tabla se creó antes de continuar; no elimine tablas ni vuelva a ejecutar la migración a ciegas.

El registro de prórrogas comienza con esta funcionalidad. Los préstamos existentes sin fila en `prorrogas` se consideran no prorrogados; si había prórrogas anteriores fuera del sistema, la persona administradora debe revisar y registrar ese histórico antes de habilitar nuevas prórrogas.

### Configuración

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `BIBLIOTECA_DB_HOST` | `localhost` | Servidor MySQL. |
| `BIBLIOTECA_DB_PORT` | `3306` | Puerto, convertido a entero. |
| `BIBLIOTECA_DB_USER` | `root` | Usuario. |
| `BIBLIOTECA_DB_PASSWORD` | Vacío | Contraseña. |
| `BIBLIOTECA_DB_NAME` | `biblioteca` | Base de datos con el esquema esperado. |

`configuracion()` busca `.env` junto a `config.py`, no en el directorio de trabajo. Los valores del entorno tienen prioridad sobre los de `.env`; los valores ausentes usan los predeterminados. La lectura no interpola variables. El conector utiliza `utf8mb4`, un límite de conexión de 10 segundos y límites de lectura y escritura de 30 segundos.

No incluya contraseñas en código, documentación ni archivos versionados. Las exportaciones pueden contener nombres y emails: controle sus permisos y distribución.

## 4. Esquema y dependencias de datos

Se usan exactamente estas tablas y columnas:

| Tabla | Columnas |
|---|---|
| `libros` | `id_libro` (PK autoincremental), `isbn`, `titulo`, `autor`, `anio_publicacion`, `ejemplares_disponibles` |
| `socios` | `id_socio` (PK autoincremental), `nombre`, `apellidos`, `email`, `telefono`, `fecha_alta` |
| `prestamos` | `id_prestamo` (PK autoincremental), `id_libro`, `id_socio`, `fecha_prestamo`, `fecha_devolucion_prevista`, `fecha_devolucion_real` nullable, `estado` |
| `reservas` | `id_reserva` (PK autoincremental), `id_libro`, `id_socio`, `fecha_reserva` |
| `prorrogas` | `id_prestamo` (PK y FK), `fecha_anterior`, `fecha_nueva`, `fecha_prorroga` |

`prestamos.id_libro` referencia `libros.id_libro`; `prestamos.id_socio` referencia `socios.id_socio`. Las reservas referencian libro y socio y tienen una restricción única por pareja; cada fila de `prorrogas` referencia un préstamo y su clave primaria limita a una prórroga. Las tablas deben usar **InnoDB** para las transacciones y bloqueos. Las claves foráneas pueden impedir eliminar libros o socios con préstamos o reservas relacionados.

Se recomiendan índices únicos en `libros.isbn` y `socios.email` para proteger también frente a accesos concurrentes o externos. La aplicación no crea esos índices; antes de añadirlos, revise los duplicados y acuerde cualquier cambio de esquema con la persona administradora.

## 5. Arquitectura y flujo de ejecución

1. `app.py` crea `Biblioteca`, una subclase de `tk.Tk`, un `Repositorio` y un `Servicio` que comparte dicho repositorio.
2. La interfaz invoca directamente el repositorio para CRUD, consultas, préstamos y devoluciones. Para importar y exportar invoca `Servicio`; los formularios también usan las funciones de validación de `services.py`.
3. `Repositorio.sesion()` abre una conexión y un cursor de diccionario, confirma al terminar y solicita `rollback` si se produce una excepción; cierra cursor y conexión.
4. `configuracion()` proporciona los parámetros para cada conexión nueva.

### El repositorio en los diagramas

En los [diagramas UML](casos_de_uso_y_diagramas_uml.md), **Repositorio** no significa la aplicación completa ni un repositorio de Git o GitHub. Representa la capa de acceso a datos, implementada por la clase `Repositorio` de [`database.py`](../database.py). Este componente sigue el patrón Repository: ofrece operaciones a la interfaz y a los servicios, y las aísla de los detalles de conexión y consultas SQL. En esta aplicación también contiene reglas de negocio y gestiona las transacciones.

En el diagrama de secuencia de registrar una devolución, los participantes corresponden a:

| Participante | Componente | Responsabilidad en la devolución |
|---|---|---|
| Bibliotecario | Usuario humano | Selecciona un préstamo y pulsa el botón de registrar devolución. |
| Biblioteca (Tkinter) | Clase `Biblioteca` de [`app.py`](../app.py) | Captura el evento, llama a `Repositorio.devolver(id_prestamo)`, muestra el resultado y actualiza las vistas. |
| Repositorio | Clase `Repositorio` de [`database.py`](../database.py) | Comprueba el préstamo mediante `SELECT ... FOR UPDATE`, actualiza la devolución y el stock con `UPDATE` y gestiona `commit` o `rollback`. |
| MySQL | Servidor de base de datos | Ejecuta las sentencias y almacena los cambios confirmados. |

[`services.py`](../services.py) proporciona validaciones y servicios de importación y exportación que también usan el repositorio, pero no interviene en la devolución desde el botón. El diagrama resume la respuesta como «Operación completada» o «Error»: `devolver()` no devuelve esos textos, sino que termina sin valor en caso de éxito o propaga una excepción; la interfaz muestra el mensaje correspondiente. Así, `app.py` es la cara visible y `database.py` el componente que habla SQL con MySQL, sin que la interfaz escriba esas consultas.

Las búsquedas usan `LIKE` con parámetros y las listas de libros y socios usan `LIMIT`/`OFFSET`, 15 filas por página y una consulta adicional para detectar la página siguiente. El listado de préstamos no está paginado y se ordena por ID ascendente.

Los valores SQL se pasan mediante `%s`; el fragmento de condición del filtro de préstamos se selecciona de un diccionario fijo, no de texto arbitrario del usuario. Mantenga esta separación al añadir consultas.

## 6. Reglas de negocio y transacciones

### Préstamo

`Repositorio.prestar()` bloquea la fila del socio con `FOR UPDATE`, cuenta sus préstamos con `estado = 'Activo' OR fecha_devolucion_real IS NULL` y rechaza el intento si hay dos o más. Bloquea la fila del libro, comprueba el stock, inserta el préstamo y resta un ejemplar en la misma transacción.

La fecha de préstamo se obtiene con `date.today()` en el equipo de la aplicación; la fecha prevista se calcula sumando `timedelta(days=20)`. El estado inicial es `Activo` y la fecha real es `NULL`.

### Devolución

`Repositorio.devolver()` bloquea el préstamo, rechaza una fecha real ya informada y actualiza fecha real y estado a `Devuelto`. Incrementa el stock en la misma transacción. Si el libro no se actualiza, lanza un error para revertir la operación.

El filtro de activos usa la condición OR anterior. El filtro de devueltos requiere estado distinto de `Activo` y fecha real informada. Un registro con `Activo` y fecha real ya informada aparece en activos, pero no puede devolverse otra vez. No hay estado automático de vencido ni bloqueo de nuevos préstamos por retraso; sí se bloquea la prórroga de un préstamo vencido.

### Reservas y prórrogas

`reservar()` bloquea la fila del libro, comprueba el socio y evita reservas repetidas para la misma pareja libro/socio; la restricción única refuerza esta regla. `cancelar_reserva()` bloquea el libro y elimina la reserva. Se admiten reservas con cualquier stock; no hay caducidad, asignación preferente ni cancelación automática al prestar.

`prorrogar()` bloquea el préstamo, rechaza los que tienen fecha real informada o una fila en `prorrogas`, bloquea el libro y comprueba mediante lectura de bloqueo que no haya una reserva de otro socio. También rechaza fechas previstas anteriores a `date.today()`, la fecha local del ordenador de la aplicación; el día de vencimiento sigue siendo válido. Inserta el registro de prórroga y actualiza la fecha prevista a su valor anterior más 20 días en la misma transacción; no modifica el stock. Una reserva del mismo socio no impide la prórroga.

Si la fecha real está informada, `_prorrogar()` lanza `ReglaNegocio` antes de escribir cambios. El gestor de sesión solicita `rollback` y el decorador `proteger` muestra el mensaje de error: explica que el préstamo ya está devuelto y que debe registrarse un nuevo préstamo para volver a prestar el libro. No crea ese préstamo automáticamente; `prestar()` comprueba el stock y el límite de préstamos activos cuando el usuario lo solicita.

Registrar o cancelar reservas y prorrogar toman el bloqueo del mismo libro antes de modificar o comprobar reservas. Otros clientes que escriban reservas deben seguir el mismo protocolo para conservar la garantía ante concurrencia. Una fecha real informada se rechaza incluso si el estado inconsistente es `Activo`.

Las garantías de bloqueo dependen de InnoDB y de que otros clientes respeten las mismas reglas. Las pruebas actuales no verifican condiciones de carrera reales en MySQL.

## 7. Importación y exportación

### Importación

`Servicio.importar()` admite `libros`, `socios`, `reservas` y `prorrogas`. `csv.DictReader` requiere las cabeceras exactas y en orden:

```text
isbn,titulo,autor,anio_publicacion,ejemplares
nombre,apellidos,email,telefono
isbn,email
```

Los archivos se leen como UTF-8 con o sin BOM. En libros, `ejemplares` se transforma a `ejemplares_disponibles`: por ISBN existente se suma stock; si no existe, se inserta; si hay más de una coincidencia, se informa un error. En socios, se omite un email existente y se usa `CURDATE()` de MySQL para la fecha de alta del nuevo.

Reservas y prórrogas usan `isbn,email`. La resolución de referencias y la operación comparten transacción y lecturas con bloqueo; las operaciones reutilizan las mismas reglas que los botones individuales. Reservas requiere una pareja única de libro y socio; prórrogas, un único préstamo de la pareja sin devolución. Se rechazan las referencias ausentes o ambiguas y las operaciones que incumplen las reglas. Las reservas se cuentan como insertadas y las prórrogas como actualizaciones. Los CSV de prueba requieren preparar previamente los préstamos indicados en el [manual de usuario](manual_usuario.md#importar-reservas-y-prórrogas).

Cada fila válida se confirma en su propia sesión/transacción. Los errores de validación y de MySQL por fila se acumulan; un error de lectura detiene el procesamiento. Las filas ya confirmadas no se deshacen. El resumen de socios consulta después el total actual, y si falla muestra un aviso sin ocultar el resultado de la importación.

Los diálogos proponen `imports/` y `exports/` relativos a `app.py`, independientemente del directorio de trabajo. Si no se puede preparar una carpeta, se avisa y se permite elegir otra ubicación.

### Exportación

`Repositorio.historico()` realiza un `JOIN` con libros y socios y devuelve todos los préstamos, no solo los del filtro visible. `Servicio.exportar()` serializa fechas con `isoformat()` y escribe las columnas de `CAMPOS_HISTORICO`. CSV usa UTF-8 con BOM; JSON usa UTF-8, sin escape obligatorio de Unicode y con sangría de 2 espacios.

El diálogo propone `prestamos_AAAA-MM-DD_HH-MM-SS.csv` o `.json`, con la hora local al abrir el diálogo. El usuario puede cambiar nombre y destino; por tanto, el nombre final no garantiza mantener la marca de tiempo.

## 8. Validaciones y gestión de errores

- `validar_libro`: ISBN, título y autor no vacíos; año entero positivo; ejemplares enteros no negativos.
- `validar_socio`: nombre, apellidos y email no vacíos; formato básico de email; teléfono opcional; fecha de alta ISO si se solicita.
- `ReglaNegocio` hereda de `ValueError`. El decorador `proteger` muestra mensajes para errores de MySQL, archivos, Unicode, CSV y validación en los métodos decorados.
- Los datos ya confirmados de una importación parcial no se revocan al fallar una fila posterior.
- Las consultas y la importación/exportación se ejecutan en el hilo de Tkinter. Archivos grandes o un servidor lento pueden bloquear temporalmente la interfaz.

Al modificar el código, mantenga las operaciones de stock y préstamo dentro de la misma transacción, preserve la condición OR de préstamo activo y pruebe tanto la operación correcta como sus fallos. No sustituya las consultas parametrizadas por interpolación de valores.

## 9. Pruebas y diagnóstico

Desde la carpeta de la aplicación, con las dependencias instaladas:

```powershell
python -m unittest discover -s tests -v
```

Para aislar las reglas de préstamos:

```powershell
python -m unittest discover -s tests -p test_biblioteca.py -k ReglasPrestamosTest -v
```

En un entorno virtual, sustituya `python` por `.\.venv\Scripts\python`. Las pruebas usan simulaciones y SQLite en memoria; no requieren MySQL ni verifican la concurrencia de InnoDB. El [documento de pruebas](pruebas.md) detalla cada caso, la comprobación manual y las limitaciones.

Ante un error de conexión, revise servidor, configuración efectiva, permisos y versión del conector sin registrar ni compartir contraseñas. Ante errores de importación, revise las líneas reportadas y el estado ya confirmado antes de reintentar. Para investigar transacciones concurrentes, utilice una base MySQL aislada y clientes independientes; no ejecute pruebas destructivas sobre datos reales.

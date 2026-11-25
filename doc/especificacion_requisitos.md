# Documento de Especificación de Requisitos (SRS)

## 1.1. Propósito y Alcance
Aplicación de escritorio en **Python 3.14** con interfaz gráfica basada en **`tkinter`** (`ttk`) para gestionar libros, socios, préstamos, reservas, importaciones y exportaciones de una biblioteca conectada a **MySQL 8** (`biblioteca`). El servidor puede ser local o remoto. La aplicación no migra el esquema automáticamente; las tablas adicionales se crean mediante una migración explícita.

## 1.2. Arquitectura de Datos (Esquema Existente)
La aplicación operará sobre la base de datos relacional `biblioteca` ya desplegada en MySQL, respetando estrictamente sus tablas, columnas y claves foráneas:

| Tabla | Columnas | Descripción y Restricciones |
| :--- | :--- | :--- |
| **`libros`** | `id_libro` (PK), `isbn`, `titulo`, `autor`, `anio_publicacion`, `ejemplares_disponibles` | Catálogo bibliográfico y control de stock disponible en tiempo real. |
| **`socios`** | `id_socio` (PK), `nombre`, `apellidos`, `email`, `telefono`, `fecha_alta` | Registro de usuarios habilitados para solicitar préstamos. |
| **`prestamos`** | `id_prestamo` (PK), `id_libro` (FK), `id_socio` (FK), `fecha_prestamo`, `fecha_devolucion_prevista`, `fecha_devolucion_real` (nullable), `estado` | Registro transaccional de préstamos; la aplicación establece `Activo` o `Devuelto`. |
| **`reservas`** | `id_reserva` (PK), `id_libro` (FK), `id_socio` (FK), `fecha_reserva` | Reservas vigentes; la pareja libro/socio es única. |
| **`prorrogas`** | `id_prestamo` (PK y FK), `fecha_anterior`, `fecha_nueva`, `fecha_prorroga` | Registro persistente de la única prórroga permitida por préstamo. |

Las tres tablas originales conservan su estructura. La [migración](../migrations/001_reservas_prorrogas.sql) añade las dos tablas restantes; sus claves foráneas deben ser compatibles con los tipos de la base existente.

## 1.3. Requisitos Funcionales (RF)
* **RF-01. Gestión CRUD de Libros:** Permitir crear, consultar (con buscador dinámico por título, autor o ISBN), actualizar y eliminar registros de `libros`. La eliminación de libros asociados a préstamos queda sujeta a las restricciones de claves foráneas configuradas en la base de datos.
* **RF-02. Gestión CRUD de Socios:** Permitir crear, consultar (búsqueda por nombre, apellidos o email), actualizar y eliminar socios en `socios`. La eliminación de socios asociados a préstamos queda sujeta a las restricciones de claves foráneas configuradas en la base de datos.
* **RF-03. Gestión de Préstamos y Devoluciones:**
  * Registrar nuevos préstamos seleccionando socio y libro.
  * Calcular automáticamente `fecha_devolucion_prevista` sumando **20 días naturales** a `fecha_prestamo`.
  * Registrar devoluciones actualizando `fecha_devolucion_real` con la fecha actual, cambiando `estado` a devuelto (ej. `'Devuelto'`) e incrementando en `+1` `ejemplares_disponibles` en `libros`.
* **RF-04. Visualización Tabular:** Mostrar **Libros**, **Socios** y **Préstamos** en componentes `ttk.Treeview` con barras de desplazamiento. Libros y socios disponen de búsqueda y paginación de 15 registros (`LIMIT`/`OFFSET`); préstamos se muestra sin paginación, ordenado por ID ascendente y con filtros «Todos», «Solo Activos» y «Devueltos».
* **RF-05. Importación Masiva desde CSV:**
  * Permitir seleccionar archivos `.csv` mediante cuadro de diálogo (`filedialog`) para importar libros, socios, reservas y prórrogas. Proponer la carpeta `imports`, permitiendo elegir otra ubicación; si no se puede crear, avisar y permitir seleccionar otro archivo.
  * **Lógica de Upsert / Stock en Libros:** Si el `isbn` importado ya existe en la tabla `libros`, se incrementará `ejemplares_disponibles` sumando los nuevos ejemplares importados; si no existe, se insertará como libro nuevo.
  * **Lógica en Socios:** Omitir emails ya existentes e insertar socios nuevos con `fecha_alta = CURDATE()`.
  * **Reservas y prórrogas:** aceptar la cabecera exacta `isbn,email` y aplicar las reglas RF-07 y RF-08. La reserva requiere un libro y socio identificados de forma única; la prórroga requiere un único préstamo de esa pareja sin devolución. Rechazar referencias inexistentes o ambiguas.
  * Confirmar cada fila válida individualmente y mostrar insertados, libros existentes actualizados, socios duplicados o préstamos prorrogados, además de los errores. El resumen de socios muestra también el total actual de socios en la base de datos. Un error posterior no revierte filas ya confirmadas.
* **RF-06. Exportación de Histórico de Préstamos:**
  * Exportar el histórico completo, independientemente del filtro de la pantalla, mediante `JOIN` con libros y socios a **CSV** (UTF-8 con BOM) o **JSON** (UTF-8 con sangría de 2 espacios). Incluir `id_prestamo`, `isbn`, `titulo`, `socio_nombre_completo`, `email`, `fecha_prestamo`, `fecha_devolucion_prevista`, `fecha_devolucion_real` y `estado`.
  * Proponer en el diálogo la carpeta `exports` y un nombre editable con fecha y hora locales, `prestamos_AAAA-MM-DD_HH-MM-SS.csv` o `.json`, tomadas al abrir el diálogo. El usuario puede elegir otro destino; si no se puede crear `exports`, se avisa y se permite seleccionar otra ubicación.
* **RF-07. Reservas:** Permitir consultar, registrar y cancelar reservas de libro y socio, incluyendo libros sin stock. Una reserva no altera el stock ni se cancela automáticamente.
* **RF-08. Prórrogas:** Permitir prorrogar un préstamo sin devolución registrada una sola vez, si el plazo no ha vencido y el libro no está reservado por otro socio. La fecha prevista puede ser la fecha local actual o posterior. Sumar 20 días naturales a la fecha prevista y registrar la prórroga y la nueva fecha en una transacción.
  * Si el préstamo tiene fecha de devolución real, rechazar la prórroga y explicar que, para volver a prestar el libro, debe registrarse un nuevo préstamo sujeto a las condiciones habituales. La prórroga rechazada no modifica el préstamo, su historial de prórrogas ni el stock.

## 1.4. Reglas de Negocio (RN)
* **RN-01. Límite de Préstamos Simultáneos:** Un socio solo puede tener un máximo de **2 préstamos activos** simultáneamente (`fecha_devolucion_real IS NULL` o `estado = 'Activo'`). Si ya tiene 2, la aplicación bloqueará el nuevo préstamo mostrando una alerta clara.
* **RN-02. Duración Estándar:** Todo préstamo tiene una duración fija de **20 días** (`fecha_devolucion_prevista = fecha_prestamo + 20 días`).
* **RN-03. Control de Stock e Integridad Transaccional:** No se puede prestar un libro si `ejemplares_disponibles <= 0`. Cada préstamo o devolución se confirma o revierte junto con su actualización de stock. Se bloquean las filas correspondientes durante la operación; las tablas deben usar InnoDB. Una devolución con fecha real ya informada se rechaza para evitar incrementar el stock dos veces.
* **RN-04. Validación:** ISBN, título, autor, nombre, apellidos y email son obligatorios; el año debe ser un entero positivo y los ejemplares un entero no negativo. El email debe tener formato válido y la fecha de alta debe usar `AAAA-MM-DD`; el teléfono puede estar vacío.
* **RN-05. Retrasos:** Un préstamo cuya fecha prevista sea anterior a la fecha local actual no se puede prorrogar. El día del vencimiento todavía se puede prorrogar. No se bloquean nuevos préstamos por retraso ni hay un estado automático de vencimiento.
* **RN-06. Reserva y prórroga:** Una reserva de otro socio bloquea la prórroga aunque haya otros ejemplares disponibles; la reserva del propio socio no la bloquea. Una pareja libro/socio solo puede tener una reserva vigente. Las reservas no caducan ni tienen prioridad automática al prestar.
* **RN-07. Histórico de prórrogas:** Solo se permite una prórroga registrada por préstamo. Los préstamos existentes sin registro de prórroga se consideran no prorrogados; las prórrogas previas externas deben revisarse y registrarse antes de habilitar la función.

## 1.5. Requisitos No Funcionales (RNF)
* **RNF-01. Stack Tecnológico:** Python 3.14, `tkinter` (`ttk`), `mysql-connector-python`, `python-dotenv` y los módulos estándar `csv`, `json` y `datetime`.
* **RNF-02. Seguridad:** Parámetros SQL mediante `%s`; configuración mediante `.env` y variables de entorno, que tienen prioridad. `.env` está excluido de Git.
* **RNF-03. Arquitectura Modular:** `config.py` configura la conexión; `database.py` accede a MySQL y gestiona las transacciones; `services.py` valida e importa/exporta; `app.py` implementa la interfaz.
* **RNF-04. Operación:** Los errores de validación, MySQL y archivos se notifican en la interfaz. La conexión tiene un límite de 10 segundos y las lecturas/escrituras de 30 segundos. Las operaciones se ejecutan en el hilo de la interfaz y pueden bloquearla temporalmente.
* **RNF-05. Integridad:** Se recomiendan índices únicos en `libros.isbn` y `socios.email` para proteger las importaciones concurrentes y otros accesos externos; la aplicación no crea dichos índices.

## 1.6. Documentación relacionada

- [Casos de uso y diagramas UML](casos_de_uso_y_diagramas_uml.md).
- [Instalación, ejecución y datos de prueba](../README.md).
- [Pruebas, trazabilidad y límites de verificación](pruebas.md). Los casos P-01 a P-08 verifican aspectos de préstamos y devoluciones mediante SQLite o simulaciones; no prueban concurrencia en MySQL/InnoDB.


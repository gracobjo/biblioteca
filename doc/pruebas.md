# Pruebas de la aplicación de biblioteca

Este documento describe las pruebas existentes, cómo ejecutarlas y qué queda pendiente de comprobar en un entorno real. Las reglas funcionales están en la [especificación](especificacion_requisitos.md) y los flujos de usuario en los [casos de uso](casos_de_uso_y_diagramas_uml.md).

## 1. Preparación y ejecución

Se necesita Python 3.14 con las dependencias de `requirements.txt`. Desde PowerShell, situado en la carpeta de la aplicación:

```powershell
python -m unittest discover -s tests -v
```

Si se usa el entorno virtual indicado en el [README](../README.md), sustituya `python` por `.\.venv\Scripts\python`. Un resultado `OK` significa que todas las pruebas ejecutadas han pasado; un `FAIL` o `ERROR` identifica la prueba y su detalle.

Para ejecutar únicamente las reglas de préstamos:

```powershell
python -m unittest discover -s tests -p test_biblioteca.py -k ReglasPrestamosTest -v
```

Las pruebas automáticas no requieren conexión a MySQL ni modifican la base de datos configurada en `.env`. Usan objetos simulados, bases SQLite en memoria y directorios temporales. Las pruebas de interfaz simulan diálogos y mensajes, sin abrir ventanas.

## 2. Casos automáticos de préstamos y devoluciones

Los siguientes casos están en [tests/test_biblioteca.py](../tests/test_biblioteca.py).

| ID | Prueba | Preparación y resultado esperado | Requisitos |
|---|---|---|---|
| P-01 | `test_dos_prestamos_tercero_rechazado_y_devolucion_habilita_otro` | Con un socio y tres libros con stock, se registran dos préstamos, se rechaza el tercero sin descontar su stock y, después de devolver uno, se permite otro. Se verifican las fechas `2026-12-20 → 2027-01-09` y `2028-02-20 → 2028-03-11`: 20 días en cambio de año y año bisiesto. | RF-03, RN-01, RN-02, RN-03 |
| P-02 | `test_limite_cuenta_estado_activo_o_fecha_real_vacia` | Dos registros inconsistentes, uno con estado `Activo` y fecha real informada y otro con estado `Devuelto` y fecha real vacía, cuentan como activos por la condición OR; se rechaza un tercer préstamo. | RN-01 |
| P-03 | `test_prestamo_fecha_y_transaccion` | Con una conexión simulada, se comprueban los datos enviados al insertar, el vencimiento a 20 días, el bloqueo del socio, la condición de activo, el `commit` y el cierre. | RF-03, RN-01, RN-02, RN-03 |
| P-04 | `test_limite_y_stock_agotado_no_insertan` | Con dos préstamos activos o stock cero, se rechaza el préstamo, no se ejecuta la inserción y se solicita `rollback`. | RN-01, RN-03 |
| P-05 | `test_fallo_stock_revierte_insercion` | Se simula un error al descontar stock después de insertar; se solicita `rollback`, sin `commit`. | RN-03 |
| P-06 | `test_devolucion_y_proteccion_contra_doble_devolucion` | Se comprueban la fecha y estado de devolución, el incremento de stock y el `commit`; una fecha real ya informada se rechaza sin actualizar. | RF-03, RN-03 |
| P-07 | `test_error_al_incrementar_stock_revierte_devolucion` | Un error simulado al incrementar stock provoca `rollback`, sin `commit`. | RN-03 |
| P-08 | `test_prestamos_ascendentes_en_todos_los_filtros` | En SQLite en memoria, los filtros Todos, Solo Activos y Devueltos devuelven sus resultados ordenados por ID ascendente. | RF-04 |

P-01 y P-02 ejecutan las consultas del repositorio adaptadas a SQLite. El adaptador cambia los marcadores de parámetros y elimina `FOR UPDATE`; por tanto, estas pruebas **no verifican los bloqueos ni la concurrencia de MySQL/InnoDB**. P-03 a P-07 utilizan conexiones y cursores simulados: comprueban llamadas y errores, no el funcionamiento real del motor MySQL.

## 3. Casos automáticos de validación, archivos y configuración

| ID | Archivo y prueba | Resultado esperado | Requisitos |
|---|---|---|---|
| P-09 | `test_biblioteca.py::test_validacion` | Se rechazan un stock negativo y un email incorrecto. | RN-04 |
| P-10 | `test_biblioteca.py::test_importar_resumen_y_formato` | Un ISBN nuevo se inserta, uno repetido suma stock, una cantidad negativa se informa como error y una cabecera incorrecta se rechaza. Usa un repositorio simulado. | RF-05 |
| P-11 | `test_biblioteca.py::test_importar_socios_duplicados_y_error_csv` | Se cuentan un socio nuevo, un email duplicado y un error de CSV mal formado. Usa un repositorio simulado. | RF-05 |
| P-12 | `test_biblioteca.py::test_exportar_formatos_y_fechas` | Los archivos temporales CSV y JSON contienen los campos, fechas y valores nulos comprobados por la prueba. El histórico procede de un repositorio simulado. | RF-06 |
| P-13 | `test_app.py::test_libros_nuevos_no_se_describen_como_stock_actualizado` | El resumen distingue libros nuevos de libros existentes actualizados. | RF-05 |
| P-14 | `test_app.py::test_socios_muestra_total_consultado` | El resumen incluye insertados, duplicados y el total de socios proporcionado por el repositorio simulado. | RF-05 |
| P-15 | `test_app.py::test_error_al_contar_conserva_resumen_de_la_importacion` | Un fallo al consultar el total muestra un aviso y conserva el resumen de socios insertados. | RF-05, RNF-04 |
| P-16 | `test_app.py::test_nombre_propuesto_y_destino_elegido` | En CSV y JSON se propone `exports` y un nombre con fecha y hora; se respeta el destino elegido. El diálogo y la exportación están simulados. | RF-06 |
| P-17 | `test_app.py::test_cancelar_no_exporta` | Cancelar el diálogo no llama al servicio de exportación. | RF-06 |
| P-18 | `test_app.py::test_error_de_carpeta_permite_elegir_otro_destino` | Si no se puede preparar `exports`, se avisa y se permite elegir otro destino. | RF-06, RNF-04 |
| P-19 | `test_config.py::test_archivo_y_prioridad_del_entorno` | Se leen los valores de un `.env` temporal y las variables de entorno tienen prioridad. | RNF-02 |
| P-20 | `test_config.py::test_sin_archivo_usa_valores_predeterminados` | Sin archivo ni variables de entorno se utilizan los valores predeterminados comprobados. | RNF-02 |
| P-21 | `test_app.py::test_importar_propone_directorio_y_respeta_archivo_elegido` | El diálogo propone `imports` y se utiliza el archivo elegido, aunque esté en otra ubicación. | RF-05 |
| P-22 | `test_app.py::test_directorio_inaccesible_avisa_y_permite_otra_ubicacion` | Si no se puede preparar `imports`, se muestra un aviso y el diálogo permite elegir otro destino. | RF-05, RNF-04 |
| P-23 | `test_biblioteca.py::test_prorroga_una_vez_desde_fecha_prevista_sin_cambiar_stock` | Una prórroga suma 20 días, registra las fechas, no modifica stock y rechaza una segunda. | RF-08, RN-07 |
| P-24 | `test_biblioteca.py::test_reserva_ajena_bloquea_hasta_cancelarla_y_reserva_propia_no_bloquea` | Una reserva ajena bloquea la prórroga; al cancelarla se permite, incluso con una reserva propia. Se rechazan reservas duplicadas. | RF-07, RF-08, RN-06 |
| P-25 | `test_biblioteca.py::test_prestamo_devuelto_o_inexistente_no_se_prorroga` | Se rechazan un préstamo con fecha real y otro inexistente. Con SQLite en memoria y diálogos simulados se comprueba que el aviso indica la devolución y propone un nuevo préstamo, sin mostrar éxito ni actualizar la vista. | RF-08 |
| P-26 | `test_biblioteca.py::test_fallo_actualizacion_revierte_registro_prorroga` | Un fallo al actualizar la fecha solicita `rollback` sin `commit`. | RF-08 |
| P-27 | `test_app.py::test_prorrogar_muestra_fecha_y_actualiza` | El botón envía el préstamo seleccionado y muestra la fecha devuelta. | RF-08 |
| P-28 | `test_app.py::test_reservar_usa_selectores_independientes` | El botón envía los identificadores de los selectores de reserva. | RF-07 |
| P-29 | `test_app.py::test_cancelar_reserva_respeta_confirmacion` | Cancelar la confirmación conserva la reserva; confirmarla llama al repositorio. | RF-07 |
| P-30 | `test_biblioteca.py::test_importar_por_referencias_aplica_reglas_reales` | Una reserva duplicada se rechaza; una reserva ajena bloquea la prórroga y solo se permite una tras cancelarla. | RF-05, RF-07, RF-08 |
| P-31 | `test_biblioteca.py::test_referencias_desconocidas_o_prestamos_ambiguos_se_rechazan` | Se rechazan referencias ausentes y préstamos ambiguos sin generar prórrogas. | RF-05 |
| P-32 | `test_biblioteca.py::test_reserva_rechaza_isbn_ambiguo` | Un ISBN duplicado no genera una reserva. | RF-05 |
| P-33 | `test_biblioteca.py::test_importar_reservas_y_prorrogas_informa_errores_por_fila` | Se cuentan éxitos y errores por fila para ambos tipos con repositorio simulado. | RF-05 |
| P-34 | `test_biblioteca.py::test_importacion_referencias_rechaza_cabecera_y_filas_invalidas` | Se rechazan cabeceras incorrectas, ISBN vacío y columnas adicionales. | RF-05 |
| P-35 | `test_biblioteca.py::test_csv_ficticios_referencian_ejemplos_existentes` | Ambos CSV contienen cinco filas válidas que referencian los ejemplos de libros y socios. | RF-05 |
| P-36 | `test_app.py::test_resumen_reservas_y_prorrogas` | Los resúmenes muestran los contadores correspondientes con diálogos simulados. | RF-05 |
| P-37 | `test_biblioteca.py::test_plazo_de_prorroga_incluye_vencimiento_y_rechaza_retraso` | Con reloj simulado, un préstamo vencido ayer se rechaza sin modificar fecha, stock ni historial; el día de vencimiento se permite una prórroga y se rechaza la segunda. | RF-08, RN-05, RN-07 |
| P-38 | `test_biblioteca.py::test_importacion_rechaza_prorroga_vencida_y_continua` | Con reloj simulado, la importación informa la fila vencida y procesa otra dentro de plazo, conservando la fecha del préstamo rechazado. | RF-05, RF-08, RN-05 |
| P-39 | `test_app.py::test_prorroga_vencida_muestra_error_sin_confirmacion` | El diálogo presenta el error y no muestra una confirmación de éxito. | RF-08, RN-05 |

## 4. Comprobación manual de las reglas de préstamo

**Precaución:** este procedimiento escribe en la base de datos configurada y deja un histórico. Utilice preferiblemente una base de pruebas con el mismo esquema, InnoDB y claves foráneas. Configure su conexión en `.env` y no publique las credenciales.

**Preparación:** disponga de un socio de prueba sin préstamos activos y tres libros distintos con stock positivo. Anote el stock disponible de cada libro. Inicie la aplicación.

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | En Préstamos y devoluciones, registre el primer préstamo para el socio y el primer libro. | Aparece un préstamo `Activo`, con fecha de devolución real vacía; el stock del libro disminuye en uno. |
| 2 | Compare sus fechas de préstamo y devolución prevista. | La fecha prevista es exactamente 20 días naturales posterior a la fecha de préstamo. |
| 3 | Registre el segundo préstamo con el mismo socio y otro libro. | Se registra; su devolución prevista también está a 20 días y su stock disminuye en uno. |
| 4 | Intente prestar el tercer libro al mismo socio. | Aparece el error de máximo de 2 libros; no se crea un tercer préstamo y el stock de ese libro no cambia. |
| 5 | Seleccione uno de los préstamos activos y pulse Registrar devolución. | Se establece la fecha real a hoy, el estado pasa a `Devuelto` y el stock del libro aumenta en uno. |
| 6 | Registre el préstamo del tercer libro. | Se permite, ya que el socio vuelve a tener menos de dos préstamos activos antes de la operación. |

Puede buscar los libros en la pestaña Libros y usar el botón Actualizar en la pestaña de préstamos para revisar los datos. Los préstamos devueltos permanecen en el histórico; la prueba manual no deja la base en su estado inicial.

Para comprobar las prórrogas manualmente en una base de pruebas: con un préstamo sin devolución y dentro de plazo, registre una reserva del libro por otro socio y confirme que la prórroga se rechaza; cancele esa reserva, prorrogue y compruebe que la fecha prevista avanza 20 días y el stock no cambia; intente prorrogar otra vez y compruebe que se rechaza. Con otro préstamo vencido y sin prórroga, compruebe que se rechaza y que su fecha, stock e historial no cambian. Esto deja un registro permanente de prórroga en la base de pruebas.

Para comprobar el aviso de un préstamo devuelto, selecciónelo en el filtro **Devueltos** y pulse **Prorrogar préstamo**. Debe indicarse que ya tiene devolución registrada y que para volver a prestar el libro hay que registrar un nuevo préstamo; no debe aparecer confirmación de prórroga ni cambiar el stock. Después, si hay ejemplares disponibles y el socio cumple el límite, registre un nuevo préstamo y compruebe que el anterior sigue en el histórico.

Para comprobar la importación de los cinco ejemplos de reservas y prórrogas, siga la preparación y los pasos del [manual de usuario](manual_usuario.md#importar-reservas-y-prórrogas). Compruebe cinco reservas registradas y cinco fechas previstas incrementadas en 20 días; una segunda importación debe informar los duplicados y prórrogas ya realizadas.

## 5. Alcance y límites

- Las pruebas automáticas no comprueban la conexión real, el esquema ni los permisos de MySQL. Tampoco prueban las condiciones de carrera, los bloqueos de InnoDB o el comportamiento de varios clientes concurrentes.
- No existe una prueba automatizada completa de interacción gráfica con Tkinter, CRUD de libros o socios, paginación, ni de la importación/exportación integrada contra MySQL. Los casos P-10 a P-12 utilizan datos simulados.
- Una verificación de concurrencia requiere una base MySQL de pruebas y clientes independientes: se debe comprobar que dos solicitudes simultáneas para un socio con un préstamo activo no produzcan más de dos activos, y que dos solicitudes para el último ejemplar no produzcan stock negativo. Esta verificación no está automatizada en la suite actual.
- P-23 a P-26 usan SQLite en memoria o conexiones simuladas; no verifican `FOR UPDATE` ni la concurrencia entre una reserva y una prórroga en MySQL. Debe comprobarse con clientes independientes y una base MySQL aislada.
- P-30 a P-32 usan SQLite en memoria, que tampoco reproduce los bloqueos de MySQL. P-33 a P-36 emplean repositorios o diálogos simulados.
- P-37 y P-38 usan SQLite en memoria y un reloj simulado; P-39 simula la respuesta del repositorio y los diálogos.

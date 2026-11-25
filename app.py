"""Aplicación de escritorio para la biblioteca."""

import csv
import tkinter as tk
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mysql.connector import Error

from database import Repositorio
from services import Servicio, validar_libro, validar_socio


DIRECTORIO_IMPORTACIONES = Path(__file__).resolve().parent / "imports"
DIRECTORIO_EXPORTACIONES = Path(__file__).resolve().parent / "exports"


def opciones_directorio(parent, directorio):
    try:
        directorio.mkdir(exist_ok=True)
    except OSError as error:
        messagebox.showwarning(
            "Carpeta de datos", f"No se pudo preparar la carpeta predeterminada: {error}\n"
            "Seleccione otra ubicación.", parent=parent
        )
        return {}
    return {"initialdir": str(directorio)}


def proteger(funcion):
    @wraps(funcion)
    def llamada(self, *args, **kwargs):
        try:
            return funcion(self, *args, **kwargs)
        except (Error, OSError, UnicodeError, csv.Error, ValueError) as error:
            messagebox.showerror("No se pudo completar la operación", str(error), parent=self)
    return llamada


class Biblioteca(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestión de biblioteca")
        self.geometry("1150x720")
        self.minsize(850, 550)
        estilo = ttk.Style(self)
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("TButton", padding=5)
        estilo.configure("Treeview", rowheight=25)
        self.repo = Repositorio()
        self.servicio = Servicio(self.repo)
        self.paginas = {"libros": 0, "socios": 0}
        self.hay_siguiente = {"libros": False, "socios": False}
        self.seleccion = {"libros": None, "socios": None}
        self.campos = {}
        self.tablas = {}
        self.busquedas = {}
        self.etiquetas_pagina = {}
        self.botones_siguiente = {}

        notebook = ttk.Notebook(self, padding=8)
        notebook.pack(fill="both", expand=True)
        libros = ttk.Frame(notebook, padding=10)
        socios = ttk.Frame(notebook, padding=10)
        prestamos = ttk.Frame(notebook, padding=10)
        reservas = ttk.Frame(notebook, padding=10)
        datos = ttk.Frame(notebook, padding=10)
        for marco, titulo in ((libros, "Libros"), (socios, "Socios"),
                              (prestamos, "Préstamos y devoluciones"), (reservas, "Reservas"),
                              (datos, "Importar / Exportar")):
            notebook.add(marco, text=titulo)
        self.crear_crud(libros, "libros", (
            ("isbn", "ISBN"), ("titulo", "Título"), ("autor", "Autor"),
            ("anio_publicacion", "Año de publicación"), ("ejemplares_disponibles", "Ejemplares disponibles"),
        ))
        self.crear_crud(socios, "socios", (
            ("nombre", "Nombre"), ("apellidos", "Apellidos"), ("email", "Email"),
            ("telefono", "Teléfono"), ("fecha_alta", "Fecha de alta (AAAA-MM-DD)"),
        ))
        self.crear_prestamos(prestamos)
        self.crear_reservas(reservas)
        self.crear_datos(datos)
        self.limpiar("socios")
        self.actualizar()

    def tabla(self, padre, columnas):
        marco = ttk.Frame(padre)
        marco.pack(fill="both", expand=True, pady=8)
        tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", selectmode="browse")
        vertical = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        horizontal = ttk.Scrollbar(marco, orient="horizontal", command=tabla.xview)
        tabla.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tabla.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        marco.columnconfigure(0, weight=1)
        marco.rowconfigure(0, weight=1)
        for campo, titulo in columnas:
            tabla.heading(campo, text=titulo)
            tabla.column(campo, width=145, minwidth=80, stretch=True)
        return tabla

    def crear_crud(self, padre, tipo, campos):
        formulario = ttk.LabelFrame(padre, text="Datos", padding=10)
        formulario.pack(fill="x")
        self.campos[tipo] = {}
        for indice, (nombre, etiqueta) in enumerate(campos):
            fila, columna = divmod(indice, 3)
            celda = ttk.Frame(formulario, padding=4)
            celda.grid(row=fila, column=columna, sticky="ew")
            formulario.columnconfigure(columna, weight=1)
            ttk.Label(celda, text=etiqueta).pack(anchor="w")
            variable = tk.StringVar()
            ttk.Entry(celda, textvariable=variable).pack(fill="x")
            self.campos[tipo][nombre] = variable
        botones = ttk.Frame(padre)
        botones.pack(fill="x", pady=6)
        for nombre, accion in (
            ("Crear", lambda: self.guardar(tipo, False)),
            ("Editar", lambda: self.guardar(tipo, True)),
            ("Eliminar", lambda: self.eliminar(tipo)),
            ("Limpiar", lambda: self.limpiar(tipo)),
        ):
            ttk.Button(botones, text=nombre, command=accion).pack(side="left", padx=(0, 6))
        buscador = ttk.Frame(padre)
        buscador.pack(fill="x")
        ttk.Label(buscador, text="Buscar:").pack(side="left")
        variable = tk.StringVar()
        self.busquedas[tipo] = variable
        ttk.Entry(buscador, textvariable=variable).pack(side="left", fill="x", expand=True, padx=8)
        variable.trace_add("write", lambda *_: self.buscar(tipo))
        columnas = (("id_" + ("libro" if tipo == "libros" else "socio"), "ID"),) + campos
        tabla = self.tabla(padre, columnas)
        self.tablas[tipo] = tabla
        tabla.bind("<<TreeviewSelect>>", lambda _: self.seleccionar(tipo))
        paginacion = ttk.Frame(padre)
        paginacion.pack()
        ttk.Button(paginacion, text="Anterior", command=lambda: self.paginar(tipo, -1)).pack(side="left")
        etiqueta = ttk.Label(paginacion, text="Página 1", padding=8)
        etiqueta.pack(side="left")
        self.etiquetas_pagina[tipo] = etiqueta
        siguiente = ttk.Button(paginacion, text="Siguiente", command=lambda: self.paginar(tipo, 1))
        siguiente.pack(side="left")
        self.botones_siguiente[tipo] = siguiente

    def limpiar(self, tipo):
        self.seleccion[tipo] = None
        for variable in self.campos[tipo].values():
            variable.set("")
        if tipo == "socios":
            self.campos[tipo]["fecha_alta"].set(date.today().isoformat())
        tabla = self.tablas[tipo]
        tabla.selection_remove(tabla.selection())

    def seleccionar(self, tipo):
        tabla = self.tablas[tipo]
        if not tabla.selection():
            return
        valores = tabla.item(tabla.selection()[0], "values")
        self.seleccion[tipo] = int(valores[0])
        for variable, valor in zip(self.campos[tipo].values(), valores[1:]):
            variable.set(valor)

    @proteger
    def guardar(self, tipo, editar):
        identificador = self.seleccion[tipo] if editar else None
        if editar and identificador is None:
            raise ValueError("Seleccione un registro para editar.")
        datos = {clave: valor.get() for clave, valor in self.campos[tipo].items()}
        if tipo == "libros":
            self.repo.guardar_libro(validar_libro(datos), identificador)
        else:
            self.repo.guardar_socio(validar_socio(datos), identificador)
        self.limpiar(tipo)
        messagebox.showinfo("Guardado", "Registro guardado correctamente.", parent=self)
        self.actualizar()

    @proteger
    def eliminar(self, tipo):
        identificador = self.seleccion[tipo]
        if identificador is None:
            raise ValueError("Seleccione un registro para eliminar.")
        if not messagebox.askyesno("Confirmar", "¿Desea eliminar el registro seleccionado?", parent=self):
            return
        if tipo == "libros":
            self.repo.eliminar_libro(identificador)
        else:
            self.repo.eliminar_socio(identificador)
        self.limpiar(tipo)
        messagebox.showinfo("Eliminado", "Registro eliminado correctamente.", parent=self)
        self.actualizar()

    @proteger
    def buscar(self, tipo):
        self.paginas[tipo] = 0
        self.refrescar_crud(tipo)

    @proteger
    def paginar(self, tipo, cambio):
        if cambio > 0 and not self.hay_siguiente[tipo]:
            return
        self.paginas[tipo] = max(0, self.paginas[tipo] + cambio)
        self.refrescar_crud(tipo)

    def refrescar_crud(self, tipo):
        pagina = self.paginas[tipo]
        consulta = self.repo.libros if tipo == "libros" else self.repo.socios
        busqueda = self.busquedas[tipo].get().strip()
        filas = consulta(busqueda, 15, pagina * 15)
        if not filas and pagina:
            self.paginas[tipo] -= 1
            return self.refrescar_crud(tipo)
        hay_siguiente = len(filas) == 15 and bool(consulta(busqueda, 1, (pagina + 1) * 15))
        self.hay_siguiente[tipo] = hay_siguiente
        self.botones_siguiente[tipo].configure(state="normal" if hay_siguiente else "disabled")
        self.etiquetas_pagina[tipo].configure(text=f"Página {self.paginas[tipo] + 1}")
        self.limpiar(tipo)
        tabla = self.tablas[tipo]
        tabla.delete(*tabla.get_children())
        for fila in filas:
            tabla.insert("", "end", values=tuple(fila.values()))

    def crear_prestamos(self, padre):
        controles = ttk.LabelFrame(padre, text="Nuevo préstamo", padding=10)
        controles.pack(fill="x")
        ttk.Label(controles, text="Socio").grid(row=0, column=0, sticky="w")
        ttk.Label(controles, text="Libro disponible").grid(row=0, column=1, sticky="w")
        self.selector_socio = ttk.Combobox(controles, state="readonly")
        self.selector_libro = ttk.Combobox(controles, state="readonly")
        self.selector_socio.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.selector_libro.grid(row=1, column=1, sticky="ew", padx=(0, 8))
        controles.columnconfigure(0, weight=1)
        controles.columnconfigure(1, weight=1)
        ttk.Button(controles, text="Registrar préstamo", command=self.prestar).grid(row=1, column=2)
        barra = ttk.Frame(padre)
        barra.pack(fill="x", pady=8)
        ttk.Label(barra, text="Mostrar:").pack(side="left")
        self.filtro = ttk.Combobox(barra, state="readonly", values=("Todos", "Solo Activos", "Devueltos"), width=16)
        self.filtro.set("Todos")
        self.filtro.pack(side="left", padx=8)
        self.filtro.bind("<<ComboboxSelected>>", lambda _: self.actualizar_prestamos())
        ttk.Button(barra, text="Registrar devolución", command=self.devolver).pack(side="left", padx=5)
        ttk.Button(barra, text="Prorrogar préstamo", command=self.prorrogar).pack(side="left", padx=5)
        ttk.Button(barra, text="Actualizar", command=self.actualizar).pack(side="left")
        self.tabla_prestamos = self.tabla(padre, (
            ("id_prestamo", "ID"), ("titulo", "Libro"), ("socio", "Socio"),
            ("fecha_prestamo", "Fecha préstamo"), ("fecha_devolucion_prevista", "Devolución prevista"),
            ("fecha_devolucion_real", "Devolución real"), ("estado", "Estado"),
        ))

    def crear_reservas(self, padre):
        controles = ttk.LabelFrame(padre, text="Nueva reserva", padding=10)
        controles.pack(fill="x")
        ttk.Label(controles, text="Socio").grid(row=0, column=0, sticky="w")
        ttk.Label(controles, text="Libro").grid(row=0, column=1, sticky="w")
        self.selector_socio_reserva = ttk.Combobox(controles, state="readonly")
        self.selector_libro_reserva = ttk.Combobox(controles, state="readonly")
        self.selector_socio_reserva.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.selector_libro_reserva.grid(row=1, column=1, sticky="ew", padx=(0, 8))
        controles.columnconfigure(0, weight=1)
        controles.columnconfigure(1, weight=1)
        ttk.Button(controles, text="Registrar reserva", command=self.reservar).grid(row=1, column=2)
        barra = ttk.Frame(padre)
        barra.pack(fill="x", pady=8)
        ttk.Button(barra, text="Cancelar reserva", command=self.cancelar_reserva).pack(side="left", padx=(0, 5))
        ttk.Button(barra, text="Actualizar", command=self.actualizar).pack(side="left")
        self.tabla_reservas = self.tabla(padre, (
            ("id_reserva", "ID"), ("titulo", "Libro"), ("socio", "Socio"), ("fecha_reserva", "Fecha reserva"),
        ))

    def refrescar_prestamos(self):
        socios = self.repo.opciones_socios()
        libros = self.repo.opciones_libros()
        filas = self.repo.prestamos(self.filtro.get())
        self.ids_socios = [fila["id_socio"] for fila in socios]
        self.ids_libros = [fila["id_libro"] for fila in libros]
        self.selector_socio["values"] = [
            f'{fila["id_socio"]} - {fila["nombre"]} {fila["apellidos"]} ({fila["email"]})' for fila in socios
        ]
        self.selector_libro["values"] = [
            f'{fila["id_libro"]} - {fila["titulo"]} ({fila["isbn"]}; stock: {fila["ejemplares_disponibles"]})'
            for fila in libros
        ]
        self.selector_socio.set("")
        self.selector_libro.set("")
        self.tabla_prestamos.delete(*self.tabla_prestamos.get_children())
        for fila in filas:
            self.tabla_prestamos.insert("", "end", values=tuple("" if v is None else v for v in fila.values()))

    def refrescar_reservas(self):
        socios = self.repo.opciones_socios()
        libros = self.repo.opciones_libros_reserva()
        filas = self.repo.reservas()
        self.ids_socios_reserva = [fila["id_socio"] for fila in socios]
        self.ids_libros_reserva = [fila["id_libro"] for fila in libros]
        self.selector_socio_reserva["values"] = [
            f'{fila["id_socio"]} - {fila["nombre"]} {fila["apellidos"]} ({fila["email"]})' for fila in socios
        ]
        self.selector_libro_reserva["values"] = [
            f'{fila["id_libro"]} - {fila["titulo"]} ({fila["isbn"]}; stock: {fila["ejemplares_disponibles"]})'
            for fila in libros
        ]
        self.selector_socio_reserva.set("")
        self.selector_libro_reserva.set("")
        self.tabla_reservas.delete(*self.tabla_reservas.get_children())
        for fila in filas:
            self.tabla_reservas.insert("", "end", values=tuple(fila.values()))

    def actualizar_todo(self):
        self.refrescar_crud("libros")
        self.refrescar_crud("socios")
        self.refrescar_prestamos()
        self.refrescar_reservas()

    @proteger
    def actualizar(self):
        self.actualizar_todo()

    @proteger
    def actualizar_prestamos(self):
        self.refrescar_prestamos()

    @proteger
    def prestar(self):
        socio, libro = self.selector_socio.current(), self.selector_libro.current()
        if socio < 0 or libro < 0:
            raise ValueError("Seleccione un socio y un libro disponible.")
        self.repo.prestar(self.ids_socios[socio], self.ids_libros[libro])
        messagebox.showinfo("Préstamo", "Préstamo registrado. Devolución prevista en 20 días.", parent=self)
        self.actualizar()

    @proteger
    def devolver(self):
        seleccion = self.tabla_prestamos.selection()
        if not seleccion:
            raise ValueError("Seleccione un préstamo para registrar la devolución.")
        identificador = int(self.tabla_prestamos.item(seleccion[0], "values")[0])
        self.repo.devolver(identificador)
        messagebox.showinfo("Devolución", "Devolución registrada correctamente.", parent=self)
        self.actualizar()

    @proteger
    def prorrogar(self):
        seleccion = self.tabla_prestamos.selection()
        if not seleccion:
            raise ValueError("Seleccione un préstamo para prorrogar.")
        identificador = int(self.tabla_prestamos.item(seleccion[0], "values")[0])
        fecha = self.repo.prorrogar(identificador)
        messagebox.showinfo("Prórroga", f"Préstamo prorrogado hasta {fecha.isoformat()}.", parent=self)
        self.actualizar()

    @proteger
    def reservar(self):
        socio, libro = self.selector_socio_reserva.current(), self.selector_libro_reserva.current()
        if socio < 0 or libro < 0:
            raise ValueError("Seleccione un socio y un libro para la reserva.")
        self.repo.reservar(self.ids_socios_reserva[socio], self.ids_libros_reserva[libro])
        messagebox.showinfo("Reserva", "Reserva registrada correctamente.", parent=self)
        self.actualizar()

    @proteger
    def cancelar_reserva(self):
        seleccion = self.tabla_reservas.selection()
        if not seleccion:
            raise ValueError("Seleccione una reserva para cancelarla.")
        if not messagebox.askyesno("Confirmar", "¿Desea cancelar la reserva seleccionada?", parent=self):
            return
        identificador = int(self.tabla_reservas.item(seleccion[0], "values")[0])
        self.repo.cancelar_reserva(identificador)
        messagebox.showinfo("Reserva", "Reserva cancelada correctamente.", parent=self)
        self.actualizar()

    def crear_datos(self, padre):
        importar = ttk.LabelFrame(padre, text="Importar desde CSV", padding=15)
        importar.pack(fill="x", pady=(0, 12))
        ttk.Label(importar, text="Los archivos deben usar UTF-8 y las cabeceras de los ejemplos.").pack(anchor="w")
        ttk.Button(importar, text="Importar libros", command=lambda: self.importar("libros")).pack(anchor="w", pady=5)
        ttk.Button(importar, text="Importar socios", command=lambda: self.importar("socios")).pack(anchor="w", pady=5)
        ttk.Button(importar, text="Importar reservas", command=lambda: self.importar("reservas")).pack(anchor="w", pady=5)
        ttk.Button(importar, text="Importar prórrogas", command=lambda: self.importar("prorrogas")).pack(anchor="w")
        exportar = ttk.LabelFrame(padre, text="Exportar histórico de préstamos", padding=15)
        exportar.pack(fill="x")
        ttk.Button(exportar, text="Exportar CSV", command=lambda: self.exportar("csv")).pack(anchor="w", pady=5)
        ttk.Button(exportar, text="Exportar JSON", command=lambda: self.exportar("json")).pack(anchor="w")

    @proteger
    def importar(self, tipo):
        ruta = filedialog.askopenfilename(
            parent=self, filetypes=[("Archivos CSV", "*.csv")],
            **opciones_directorio(self, DIRECTORIO_IMPORTACIONES)
        )
        if not ruta:
            return
        resultado = self.servicio.importar(ruta, tipo)
        error_total = None
        if tipo == "libros":
            resumen = (f'Libros nuevos insertados: {resultado["insertados"]}\n'
                       f'Libros existentes con stock actualizado: {resultado["actualizados"]}')
        elif tipo == "socios":
            resumen = (f'Socios nuevos insertados: {resultado["insertados"]}\n'
                       f'Socios duplicados omitidos: {resultado["duplicados"]}')
            try:
                total = self.repo.contar_socios()
                resumen += f'\nTotal de socios en la base de datos: {total}'
            except (Error, ValueError) as error:
                error_total = str(error)
                resumen += f'\nNo se pudo consultar el total de socios: {error_total}'
        elif tipo == "reservas":
            resumen = f'Reservas registradas: {resultado["insertados"]}'
        else:
            resumen = f'Préstamos prorrogados: {resultado["actualizados"]}'
        resumen += f'\nErrores: {len(resultado["errores"])}'
        if resultado["errores"] or error_total is not None:
            if resultado["errores"]:
                resumen += "\n\n" + "\n".join(resultado["errores"])
            messagebox.showwarning("Importación completada con avisos", resumen, parent=self)
        else:
            messagebox.showinfo("Importación completada", resumen, parent=self)
        self.actualizar()

    @proteger
    def exportar(self, formato):
        fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ruta = filedialog.asksaveasfilename(
            parent=self, initialfile=f"prestamos_{fecha_hora}.{formato}",
            defaultextension="." + formato, filetypes=[(formato.upper(), "*." + formato)],
            **opciones_directorio(self, DIRECTORIO_EXPORTACIONES)
        )
        if not ruta:
            return
        cantidad = self.servicio.exportar(ruta, formato)
        messagebox.showinfo("Exportación", f"Se han exportado {cantidad} préstamos.", parent=self)


if __name__ == "__main__":
    Biblioteca().mainloop()

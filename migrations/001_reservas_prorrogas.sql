CREATE TABLE reservas (
    id_reserva INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_libro INT UNSIGNED NOT NULL,
    id_socio INT UNSIGNED NOT NULL,
    fecha_reserva TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_reserva),
    UNIQUE KEY uq_reserva_libro_socio (id_libro, id_socio),
    CONSTRAINT fk_reserva_libro FOREIGN KEY (id_libro) REFERENCES libros (id_libro),
    CONSTRAINT fk_reserva_socio FOREIGN KEY (id_socio) REFERENCES socios (id_socio)
) ENGINE=InnoDB;

CREATE TABLE prorrogas (
    id_prestamo INT UNSIGNED NOT NULL,
    fecha_anterior DATE NOT NULL,
    fecha_nueva DATE NOT NULL,
    fecha_prorroga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_prestamo),
    CONSTRAINT fk_prorroga_prestamo FOREIGN KEY (id_prestamo) REFERENCES prestamos (id_prestamo)
) ENGINE=InnoDB;

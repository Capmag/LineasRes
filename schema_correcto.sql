-- =========================================
-- SCHEMA CORRECTO SEGÚN ERS
-- Sistema de Control de Líneas Telefónicas
-- =========================================

CREATE TABLE IF NOT EXISTS directores (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    apellido VARCHAR(120),
    UNIQUE KEY uk_director_nombre (nombre, apellido)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS centros_costo (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE,
    director_id VARCHAR(40),
    nombre_completo_dir_anterior VARCHAR(240),
    FOREIGN KEY (director_id) REFERENCES directores(id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS areas (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE,
    centro_costo_id VARCHAR(40) NOT NULL,
    FOREIGN KEY (centro_costo_id) REFERENCES centros_costo(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS empleados (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    apellido VARCHAR(120),
    correo VARCHAR(255),
    area_id VARCHAR(40) NOT NULL,
    estatus ENUM('Activo', 'Inactivo') NOT NULL DEFAULT 'Activo',
    FOREIGN KEY (area_id) REFERENCES areas(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cuentas_padre (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    codigo VARCHAR(120) NOT NULL UNIQUE,
    operador VARCHAR(120) NOT NULL,
    descripcion VARCHAR(255),
    estatus ENUM('Activo', 'Inactivo') NOT NULL DEFAULT 'Activo'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS lineas (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    cuenta_padre_id VARCHAR(40) NOT NULL,
    lada INT NOT NULL,
    numero BIGINT NOT NULL,
    iccid VARCHAR(20),
    plan VARCHAR(120) NOT NULL,
    estatus ENUM('Disponible', 'Asignado', 'Externo', 'Baja') NOT NULL DEFAULT 'Disponible',
    UNIQUE KEY uk_linea_lada_numero (lada, numero),
    UNIQUE KEY uk_linea_iccid (iccid),
    FOREIGN KEY (cuenta_padre_id) REFERENCES cuentas_padre(id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS equipos (
    imei VARCHAR(15) NOT NULL PRIMARY KEY,
    marca VARCHAR(120),
    modelo VARCHAR(120),
    serial VARCHAR(120),
    estatus ENUM('Disponible', 'Asignado', 'En Taller', 'Robado', 'Baja') NOT NULL DEFAULT 'Disponible',
    motivo_no_disponible VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS asignaciones (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    empleado_id VARCHAR(40) NOT NULL,
    linea_id VARCHAR(40) NOT NULL,
    imei VARCHAR(15) NOT NULL,
    fecha_inicio DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_fin DATETIME,
    estatus ENUM('Vigente', 'Cerrada') NOT NULL DEFAULT 'Vigente',
    observaciones VARCHAR(255),
    UNIQUE KEY uk_empleado_linea_vigente (empleado_id, linea_id, fecha_fin),
    UNIQUE KEY uk_imei_vigente (imei, fecha_fin),
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (linea_id) REFERENCES lineas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (imei) REFERENCES equipos(imei) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS usuarios (
    id VARCHAR(40) NOT NULL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(120),
    activo TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS historial_asignaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asignacion_id VARCHAR(40),
    empleado_id VARCHAR(40) NOT NULL,
    linea_id VARCHAR(40) NOT NULL,
    imei VARCHAR(15) NOT NULL,
    fecha_inicio DATETIME NOT NULL,
    fecha_fin DATETIME,
    tipo_movimiento ENUM('Alta', 'Reasignacion', 'Cambio Equipo', 'Cambio Linea', 'Baja', 'Incidencia') NOT NULL,
    motivo VARCHAR(255),
    usuario_registro VARCHAR(120),
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asignacion_id) REFERENCES asignaciones(id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (linea_id) REFERENCES lineas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (imei) REFERENCES equipos(imei) ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_empleado (empleado_id),
    INDEX idx_linea (linea_id),
    INDEX idx_imei (imei),
    INDEX idx_fecha (fecha_registro)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

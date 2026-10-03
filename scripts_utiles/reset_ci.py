# -*- coding: utf-8 -*-
"""
Script de reinicio total de la base de datos.
Borra la base antigua y crea una nueva con CI como identificador principal.
EJECUTAR UNA SOLA VEZ.
"""

import os
import sqlite3

DB_FILE = 'colegio_vaca_diez.db'

print("=" * 60)
print("REINICIO TOTAL DE BASE DE DATOS")
print("Cambio de RUDE a C.I. como identificador principal")
print("=" * 60)

# Paso 1: Borrar la base de datos antigua si existe
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print(f"\n✅ Base de datos antigua '{DB_FILE}' eliminada.")
else:
    print(f"\nℹ️  No se encontró '{DB_FILE}'. Se creará una nueva.")

# Paso 2: Crear la base de datos nueva vacía
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Crear tablas principales con CI como identificador
cursor.execute("""
    CREATE TABLE IF NOT EXISTS estudiantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ci VARCHAR(20) UNIQUE NOT NULL,
        rude VARCHAR(20),
        apellidos VARCHAR(100) NOT NULL,
        nombres VARCHAR(100) NOT NULL,
        fecha_nacimiento DATE,
        curso VARCHAR(50) NOT NULL,
        estado VARCHAR(20) DEFAULT 'Activo',
        pension FLOAT,
        direccion VARCHAR(200),
        zona VARCHAR(100),
        ciudad VARCHAR(100),
        foto_path VARCHAR(255) DEFAULT 'default.png',
        tipo_sangre VARCHAR(10),
        alergias TEXT,
        enfermedades_cronicas TEXT,
        medicamentos_actuales VARCHAR(255),
        medico_nombre VARCHAR(150),
        medico_telefono VARCHAR(20),
        clinica_habitual VARCHAR(150),
        seguro_medico VARCHAR(150),
        observaciones_salud TEXT,
        fecha_actualizacion_salud DATE
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS padres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estudiante_id INTEGER NOT NULL,
        ci VARCHAR(20) UNIQUE NOT NULL,
        ci_estudiante VARCHAR(20),
        rude_estudiante VARCHAR(20),
        parentesco VARCHAR(50) NOT NULL,
        nombres VARCHAR(150) NOT NULL,
        telefono1 VARCHAR(20),
        telefono2 VARCHAR(20),
        telefono3 VARCHAR(20),
        telefono4 VARCHAR(20),
        email VARCHAR(100),
        ocupacion VARCHAR(100),
        foto_path VARCHAR(255) DEFAULT 'default.png',
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS profesores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ci VARCHAR(20) UNIQUE NOT NULL,
        apellidos VARCHAR(100) NOT NULL,
        nombres VARCHAR(100) NOT NULL,
        especialidad VARCHAR(100),
        salario_base FLOAT,
        estado VARCHAR(20) DEFAULT 'Activo',
        foto_path VARCHAR(255) DEFAULT 'default.png',
        usuario VARCHAR(50) UNIQUE,
        contrasena_hash VARCHAR(255),
        adelanto FLOAT DEFAULT 0.0,
        salario_neto FLOAT DEFAULT 0.0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS personal_administrativo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ci VARCHAR(20) UNIQUE NOT NULL,
        apellidos VARCHAR(100) NOT NULL,
        nombres VARCHAR(100) NOT NULL,
        cargo VARCHAR(100) NOT NULL,
        area VARCHAR(100),
        salario_base FLOAT,
        estado VARCHAR(20) DEFAULT 'Activo',
        foto_path VARCHAR(255) DEFAULT 'default.png',
        usuario VARCHAR(50) UNIQUE,
        contrasena_hash VARCHAR(255),
        adelanto FLOAT DEFAULT 0.0,
        salario_neto FLOAT DEFAULT 0.0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS materias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre VARCHAR(100) NOT NULL,
        curso_id VARCHAR(50) NOT NULL,
        profesor_id INTEGER,
        FOREIGN KEY (profesor_id) REFERENCES profesores(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS calificaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estudiante_id INTEGER NOT NULL,
        ci_estudiante VARCHAR(20) NOT NULL,
        rude_estudiante VARCHAR(20),
        materia_id INTEGER NOT NULL,
        tipo VARCHAR(50) NOT NULL,
        tipo_evaluacion_id INTEGER,
        fecha DATE NOT NULL,
        nota FLOAT NOT NULL,
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id),
        FOREIGN KEY (materia_id) REFERENCES materias(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estudiante_id INTEGER NOT NULL,
        ci_estudiante VARCHAR(20) NOT NULL,
        rude_estudiante VARCHAR(20),
        mes VARCHAR(20) NOT NULL,
        anio INTEGER NOT NULL,
        monto_total FLOAT NOT NULL,
        descuento FLOAT,
        monto_pagado FLOAT NOT NULL,
        fecha_pago DATETIME,
        estado VARCHAR(20) DEFAULT 'Pendiente',
        metodo_pago VARCHAR(20) DEFAULT 'Efectivo',
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS faltas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_sujeto VARCHAR(20) NOT NULL,
        sujeto_id INTEGER NOT NULL,
        ci_sujeto VARCHAR(20),
        rude_estudiante VARCHAR(20),
        fecha DATE NOT NULL,
        tipo_falta VARCHAR(50) NOT NULL,
        observaciones TEXT,
        estado VARCHAR(20) DEFAULT 'Pendiente',
        archivo_adjunto VARCHAR(255),
        fecha_registro DATETIME
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria VARCHAR(50) NOT NULL,
        descripcion VARCHAR(255) NOT NULL,
        monto FLOAT NOT NULL,
        fecha DATE NOT NULL,
        proveedor VARCHAR(100),
        responsable VARCHAR(100),
        metodo_pago VARCHAR(20) DEFAULT 'Efectivo'
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS mensajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        destinatario VARCHAR(100) NOT NULL,
        estudiante_id INTEGER,
        telefono VARCHAR(20) NOT NULL,
        tipo_mensaje VARCHAR(50) NOT NULL,
        contenido TEXT,
        fecha_envio DATETIME,
        remitente VARCHAR(20) DEFAULT 'Colegio',
        leido BOOLEAN DEFAULT 0,
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS egresados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estudiante_id_original INTEGER UNIQUE NOT NULL,
        ci VARCHAR(20) UNIQUE NOT NULL,
        rude VARCHAR(20),
        apellidos VARCHAR(100) NOT NULL,
        nombres VARCHAR(100) NOT NULL,
        fecha_nacimiento DATE,
        curso_final VARCHAR(50) NOT NULL,
        anio_egreso INTEGER NOT NULL,
        estado_egreso VARCHAR(20) NOT NULL,
        nombre_tutor VARCHAR(150),
        telefono_tutor VARCHAR(20),
        fecha_archivo DATETIME
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS historial_calificaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        egresado_id INTEGER NOT NULL,
        ci_egresado VARCHAR(20) NOT NULL,
        rude_egresado VARCHAR(20),
        gestion INTEGER NOT NULL,
        materia VARCHAR(100) NOT NULL,
        tipo VARCHAR(50) NOT NULL,
        periodo VARCHAR(20),
        nota FLOAT NOT NULL,
        FOREIGN KEY (egresado_id) REFERENCES egresados(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS pago_personal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo VARCHAR(20) NOT NULL,
        persona_id INTEGER NOT NULL,
        ci_persona VARCHAR(20),
        nombre_persona VARCHAR(150) NOT NULL,
        mes VARCHAR(20) NOT NULL,
        anio INTEGER NOT NULL,
        monto_base FLOAT NOT NULL,
        monto_adelanto FLOAT DEFAULT 0.0,
        monto_neto_pagado FLOAT NOT NULL,
        fecha_pago DATE NOT NULL,
        metodo_pago VARCHAR(20) DEFAULT 'Efectivo'
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        materia_id INTEGER NOT NULL,
        titulo VARCHAR(150) NOT NULL,
        descripcion TEXT,
        fecha_asignacion DATETIME,
        fecha_entrega DATE NOT NULL,
        archivo_adjunto VARCHAR(255),
        FOREIGN KEY (materia_id) REFERENCES materias(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS asistencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estudiante_id INTEGER NOT NULL,
        materia_id INTEGER NOT NULL,
        ci_estudiante VARCHAR(20) NOT NULL,
        rude_estudiante VARCHAR(20),
        fecha DATE NOT NULL,
        estado VARCHAR(20) DEFAULT 'Presente',
        observacion TEXT,
        fecha_registro DATETIME,
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id),
        FOREIGN KEY (materia_id) REFERENCES materias(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS reportes_pedagogicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estudiante_id INTEGER NOT NULL,
        profesor_id INTEGER,
        materia_id INTEGER,
        asunto VARCHAR(150) NOT NULL,
        mensaje TEXT NOT NULL,
        fecha DATETIME,
        leido BOOLEAN DEFAULT 0,
        FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id),
        FOREIGN KEY (profesor_id) REFERENCES profesores(id),
        FOREIGN KEY (materia_id) REFERENCES materias(id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS informes_economicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_informe VARCHAR(20) NOT NULL,
        fecha_generacion DATETIME,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        ingresos_efectivo FLOAT DEFAULT 0.0,
        ingresos_bancario FLOAT DEFAULT 0.0,
        total_ingresos FLOAT DEFAULT 0.0,
        gastos_efectivo FLOAT DEFAULT 0.0,
        gastos_bancario FLOAT DEFAULT 0.0,
        total_gastos FLOAT DEFAULT 0.0,
        saldo_efectivo FLOAT DEFAULT 0.0,
        saldo_bancario FLOAT DEFAULT 0.0,
        saldo_total FLOAT DEFAULT 0.0,
        detalle_json TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuracion_superadmin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clave VARCHAR(50) UNIQUE NOT NULL,
        valor VARCHAR(255) NOT NULL,
        descripcion VARCHAR(255)
    )
""")

# Crear índices
cursor.execute("CREATE INDEX IF NOT EXISTS idx_estudiantes_ci ON estudiantes(ci)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_estudiantes_rude ON estudiantes(rude)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_padres_ci ON padres(ci)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_profesores_ci ON profesores(ci)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_personal_ci ON personal_administrativo(ci)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_calificaciones_ci ON calificaciones(ci_estudiante)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_pagos_ci ON pagos(ci_estudiante)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_faltas_ci ON faltas(ci_sujeto)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_asistencias_ci ON asistencias(ci_estudiante)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_pago_personal_ci ON pago_personal(ci_persona)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_historial_ci ON historial_calificaciones(ci_egresado)")

conn.commit()
conn.close()

print("\n" + "=" * 60)
print("✅ BASE DE DATOS NUEVA CREADA EXITOSAMENTE")
print("=" * 60)
print("✅ El C.I. es ahora el identificador principal")
print("✅ El RUDE queda como dato informativo")
print("✅ Todas las tablas incluyen campos CI")
print("✅ Índices creados para búsquedas rápidas por CI")
print("=" * 60)
print("\nAhora ejecuta: python app.py")
print("El sistema creará automáticamente las tablas restantes.")
print("=" * 60)
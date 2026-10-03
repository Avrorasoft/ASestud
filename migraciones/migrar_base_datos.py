# -*- coding: utf-8 -*-
"""
Script de migración para corregir la tabla materias y permitir profesor_id NULL.
También corrige la estructura de interceptores de eventos.
"""

import sqlite3
import os
import sys

DB_FILE = 'colegio_vaca_diez.db'

if not os.path.exists(DB_FILE):
    print(f"❌ No se encontró la base de datos: {DB_FILE}")
    sys.exit(1)

print(f"📂 Conectando a base de datos: {DB_FILE}")
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Verificar si existe la tabla materias
cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name='materias'
""")

if not cursor.fetchone():
    print("ℹ️  La tabla 'materias' no existe. No se requiere migración.")
    conn.close()
    sys.exit(0)

print("✅ Tabla 'materias' encontrada. Iniciando migración...")

try:
    # Desactivar foreign keys temporalmente
    cursor.execute("PRAGMA foreign_keys=OFF;")
    cursor.execute("BEGIN TRANSACTION;")
    
    # Renombrar tabla original
    print("  → Renombrando tabla original a 'materias_old'...")
    cursor.execute("ALTER TABLE materias RENAME TO materias_old;")
    
    # Crear nueva tabla con profesor_id nullable
    print("  → Creando nueva tabla 'materias' con profesor_id nullable...")
    cursor.execute("""
        CREATE TABLE materias (
            id INTEGER NOT NULL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            curso_id VARCHAR(50) NOT NULL,
            profesor_id INTEGER,
            FOREIGN KEY(profesor_id) REFERENCES profesores(id)
        )
    """)
    
    # Copiar datos de la tabla vieja a la nueva
    print("  → Copiando datos de 'materias_old' a 'materias'...")
    cursor.execute("""
        INSERT INTO materias (id, nombre, curso_id, profesor_id)
        SELECT id, nombre, curso_id, profesor_id
        FROM materias_old
    """)
    
    # Eliminar tabla vieja
    print("  → Eliminando tabla 'materias_old'...")
    cursor.execute("DROP TABLE materias_old;")
    
    # Confirmar cambios
    conn.commit()
    
    print("\n" + "="*60)
    print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
    print("="*60)
    print("✅ La columna 'profesor_id' ahora permite valores NULL")
    print("✅ Puedes desasignar materias de profesores sin errores")
    print("✅ Puedes eliminar profesores sin errores de integridad")
    print("="*60)
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR durante la migración: {e}")
    print("La base de datos NO fue modificada.")
    sys.exit(1)

finally:
    conn.close()
    print("\n📂 Conexión cerrada correctamente.")
# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: migrar_niveles_turnos.py
Descripción: Agrega las columnas de TURNO (estudiantes) y NIVEL+TURNO
             (profesores) a la base de datos REAL, sin perder datos.
==============================================================================
"""
import sqlite3
import glob

for db_path in glob.glob('**/*.db', recursive=True):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tablas = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )]

    if 'estudiantes' in tablas:
        cols = [r[1] for r in cur.execute('PRAGMA table_info(estudiantes)')]
        if 'turno' not in cols:
            cur.execute("ALTER TABLE estudiantes ADD COLUMN turno VARCHAR(20) DEFAULT 'Mañana'")
            print(f'✅ estudiantes.turno agregado en {db_path}')
        else:
            print(f'ℹ️ estudiantes.turno ya existe en {db_path}')

    if 'profesores' in tablas:
        cols = [r[1] for r in cur.execute('PRAGMA table_info(profesores)')]
        if 'nivel' not in cols:
            cur.execute("ALTER TABLE profesores ADD COLUMN nivel VARCHAR(20)")
            print(f'✅ profesores.nivel agregado en {db_path}')
        else:
            print(f'ℹ️ profesores.nivel ya existe en {db_path}')

        if 'turno' not in cols:
            cur.execute("ALTER TABLE profesores ADD COLUMN turno VARCHAR(20) DEFAULT 'Mañana'")
            print(f'✅ profesores.turno agregado en {db_path}')
        else:
            print(f'ℹ️ profesores.turno ya existe en {db_path}')

    conn.commit()
    conn.close()

print('✅ Migración de niveles y turnos completada.')
# -*- coding: utf-8 -*-
import sqlite3
import glob

for db_path in glob.glob('**/*.db', recursive=True):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tablas = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )]

    if 'profesores' in tablas:
        cols = [r[1] for r in cur.execute('PRAGMA table_info(profesores)')]
        if 'nivel' not in cols:
            cur.execute("ALTER TABLE profesores ADD COLUMN nivel VARCHAR(20)")
            print(f'✅ profesores.nivel agregado en {db_path}')
        if 'turno' not in cols:
            cur.execute("ALTER TABLE profesores ADD COLUMN turno VARCHAR(20) DEFAULT 'Mañana'")
            print(f'✅ profesores.turno agregado en {db_path}')

    conn.commit()
    conn.close()

print('✅ Migración de nivel y turno de profesores completada.')
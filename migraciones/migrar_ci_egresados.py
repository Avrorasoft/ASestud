# -*- coding: utf-8 -*-
"""
Migración segura: agrega la columna 'ci' a la tabla egresados
de la base de datos REAL (la busca automáticamente).
"""
import sqlite3
import glob

print("Buscando bases de datos .db en el proyecto...")
archivos_db = glob.glob('**/*.db', recursive=True)
print("Archivos encontrados:", archivos_db)
print("")

migrada = False

for db_path in archivos_db:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tablas = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )]

    if 'egresados' in tablas:
        cols = [row[1] for row in cur.execute('PRAGMA table_info(egresados)')]

        if 'ci' not in cols:
            cur.execute('ALTER TABLE egresados ADD COLUMN ci VARCHAR(20)')
            conn.commit()
            print(f'✅ Columna ci agregada en: {db_path}')
        else:
            print(f'ℹ️ La columna ci ya existe en: {db_path}')

        migrada = True
    else:
        print(f'-> {db_path} no tiene tabla egresados (se omite)')

    conn.close()

print("")
if not migrada:
    print('❌ No se encontró ninguna base con la tabla egresados.')
    print('Revisa arriba qué archivos .db existen en el proyecto.')
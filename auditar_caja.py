# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: auditar_caja.py
Proyecto: Sistema de Gestión Escolar
Descripción: Script de auditoría y rastreo profundo para determinar de dónde
             proviene el valor '3333' (código quemado, plantilla HTML o BD).
==============================================================================
"""

import os
import re
import sqlite3

BASE_DIR = r"C:\ASestud"

print("=" * 70)
print("🔍 INICIANDO AUDITORÍA INTEGRAL DE CAJA Y TESORERÍA")
print("=" * 70)

# -----------------------------------------------------------------------------
# FASE 1: BUSCAR CÓDIGO QUEMADO EN PYTHON, HTML Y JS
# -----------------------------------------------------------------------------
print("\n[FASE 1] Buscando '3333' quemado en archivos de código (.py, .html, .js)...")
archivos_encontrados_codigo = []

extensiones_evaluar = ('.py', '.html', '.js', '.jinja', '.json')

for raiz, dirs, archivos in os.walk(BASE_DIR):
    if 'venv' in raiz or '.git' in raiz or '__pycache__' in raiz:
        continue
    for archivo in archivos:
        if archivo.endswith(extensiones_evaluar):
            ruta_completa = os.path.join(raiz, archivo)
            try:
                with open(ruta_completa, 'r', encoding='utf-8', errors='ignore') as f:
                    lineas = f.readlines()
                    for num_linea, linea in enumerate(lineas, 1):
                        if '3333' in linea:
                            archivos_encontrados_codigo.append((ruta_completa, num_linea, linea.strip()))
            except Exception:
                pass

if archivos_encontrados_codigo:
    print("⚠️ ¡ATENCIÓN! Se encontró '3333' escrito directamente en el código:")
    for ruta, num, contenido in archivos_encontrados_codigo:
        rel = os.path.relpath(ruta, BASE_DIR)
        print(f"  --> Archivo: {rel} (Línea {num}):")
        print(f"      {contenido}")
else:
    print("✔ No hay ningún '3333' escrito en duro (hardcoded) en archivos de código.")


# -----------------------------------------------------------------------------
# FASE 2: RASTREAR LA RUTA Y VARIABLES EN routes/caja.py Y templates/caja/index.html
# -----------------------------------------------------------------------------
print("\n[FASE 2] Analizando qué variables alimentan 'Flujo Semanal' y 'Flujo Mensual'...")

html_caja = os.path.join(BASE_DIR, 'templates', 'caja', 'index.html')
if os.path.exists(html_caja):
    with open(html_caja, 'r', encoding='utf-8', errors='ignore') as f:
        contenido_html = f.read()
    
    # Buscar variables Jinja alrededor de Flujo Semanal / Flujo Mensual
    print(f"✔ Plantilla analizada: {os.path.relpath(html_caja, BASE_DIR)}")
    patrones = [
        r'(Flujo\s*Semanal[\s\S]{0,300})',
        r'(Flujo\s*Mensual[\s\S]{0,300})'
    ]
    for p in patrones:
        coincidencias = re.findall(p, contenido_html, re.IGNORECASE)
        for c in coincidencias:
            limpio = " ".join(c.split())
            print(f"    Fragmento HTML detectado: {limpio[:150]}...")
else:
    print("❌ No se encontró la plantilla templates/caja/index.html.")


# -----------------------------------------------------------------------------
# FASE 3: ESCANEAR TODAS LAS BASES DE DATOS ACTIVAS
# -----------------------------------------------------------------------------
print("\n[FASE 3] Escaneando bases de datos SQLite en busca de '3333'...")

bases_datos = []
for raiz, dirs, archivos in os.walk(BASE_DIR):
    if 'venv' in raiz or '.git' in raiz or 'instance\\backups' in raiz:
        continue
    for archivo in archivos:
        if archivo.endswith('.db'):
            bases_datos.append(os.path.join(raiz, archivo))

hallazgos_bd = []

for db_path in bases_datos:
    rel_db = os.path.relpath(db_path, BASE_DIR)
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tablas = [t[0] for t in cur.fetchall()]

        for tabla in tablas:
            try:
                cur.execute(f"PRAGMA table_info([{tabla}]);")
                cols = [c[1] for c in cur.fetchall()]
                
                cur.execute(f"SELECT rowid, * FROM [{tabla}];")
                filas = cur.fetchall()
                for fila in filas:
                    row_id = fila[0]
                    valores = fila[1:]
                    for idx_col, val in enumerate(valores):
                        val_str = str(val) if val is not None else ""
                        if '3333' in val_str:
                            nombre_col = cols[idx_col] if idx_col < len(cols) else f"col_{idx_col}"
                            hallazgos_bd.append({
                                'bd': rel_db,
                                'tabla': tabla,
                                'columna': nombre_col,
                                'rowid': row_id,
                                'valor': val,
                                'fila_completa': dict(zip(['rowid'] + cols, fila))
                            })
            except Exception:
                pass
        conn.close()
    except Exception as e:
        print(f"  Error al leer {rel_db}: {e}")

if hallazgos_bd:
    print(f"⚠️ ¡ENCONTRADO EN BASE DE DATOS! Se hallaron {len(hallazgos_bd)} registro(s) con '3333':")
    for h in hallazgos_bd:
        print(f"\n  • Archivo BD : {h['bd']}")
        print(f"    Tabla      : {h['tabla']}")
        print(f"    Columna    : {h['columna']} = {h['valor']}")
        print(f"    Registro ID: {h['rowid']}")
        print(f"    Detalle    : {h['fila_completa']}")
else:
    print("✔ No se encontró '3333' en ninguna base de datos activa (fuera de backups).")


# -----------------------------------------------------------------------------
# FASE 4: SIMULACIÓN DE CÁLCULO DE CAJA EN VIVO
# -----------------------------------------------------------------------------
print("\n[FASE 4] Simulando el cálculo que realiza routes/caja.py...")

try:
    from app import create_app
    from models import db, Pago, IngresoCaja, Gasto
    from datetime import datetime, timedelta

    app = create_app()
    with app.app_context():
        print(f"✔ SQLAlchemy conectado a: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        
        pagos_count = Pago.query.count()
        ingresos_count = IngresoCaja.query.count()
        gastos_count = Gasto.query.count()
        
        print(f"  - Total registros en Pago        : {pagos_count}")
        print(f"  - Total registros en IngresoCaja : {ingresos_count}")
        print(f"  - Total registros en Gasto       : {gastos_count}")
        
        if pagos_count > 0:
            suma_p = db.session.query(db.func.sum(Pago.monto_pagado)).scalar() or 0.0
            print(f"  - Suma acumulada de Pagos        : Bs. {suma_p:.2f}")
            for p in Pago.query.all():
                print(f"      ID {p.id}: Monto={p.monto_pagado}, Fecha={p.fecha_pago}, Estado={p.estado}")

        if ingresos_count > 0:
            suma_i = db.session.query(db.func.sum(IngresoCaja.monto)).scalar() or 0.0
            print(f"  - Suma acumulada de IngresoCaja  : Bs. {suma_i:.2f}")
            for i in IngresoCaja.query.all():
                print(f"      ID {i.id}: Monto={i.monto}, Fecha={i.fecha}, Estado={i.estado}")

except Exception as e:
    print(f"  No se pudo completar la simulación ORM: {e}")

print("\n" + "=" * 70)
print("AUDITORÍA FINALIZADA")
print("=" * 70)
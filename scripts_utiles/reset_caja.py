# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: scripts_utiles/reset_caja.py
Proyecto: Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Script maestro con contexto de aplicación Flask para purgar
             todos los movimientos de Caja, Pagos, Ingresos Directos y Egresos,
             dejando el balance y arqueo semanal/mensual en Bs. 0.00 absoluto.
==============================================================================
"""

import os
import sys

# Asegurar que el directorio raíz del proyecto esté en el path de Python
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db

app = create_app()

with app.app_context():
    print("=" * 60)
    print("INICIANDO PURGA ESPECIALIZADA DE CAJA Y TESORERÍA")
    print(f"Base de datos activa: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    print("=" * 60)

    try:
        from models import Pago, IngresoCaja, Gasto, TurnoCaja
    except ImportError:
        Pago = getattr(sys.modules.get('models'), 'Pago', None)
        IngresoCaja = getattr(sys.modules.get('models'), 'IngresoCaja', None)
        Gasto = getattr(sys.modules.get('models'), 'Gasto', None)
        TurnoCaja = getattr(sys.modules.get('models'), 'TurnoCaja', None)

    # 1. Purga explícita a través del ORM de SQLAlchemy
    if Pago:
        num = db.session.query(Pago).delete()
        print(f"✔ Pagos escolares eliminados: {num}")

    if IngresoCaja:
        num = db.session.query(IngresoCaja).delete()
        print(f"✔ Ingresos directos de caja eliminados: {num}")

    if Gasto:
        num = db.session.query(Gasto).delete()
        print(f"✔ Gastos y egresos eliminados: {num}")

    if TurnoCaja:
        num = db.session.query(TurnoCaja).delete()
        print(f"✔ Turnos y arqueos de caja eliminados: {num}")

    # Verificar si existe modelo PagoPersonal
    try:
        from models import PagoPersonal
        num = db.session.query(PagoPersonal).delete()
        print(f"✔ Pagos a personal eliminados: {num}")
    except Exception:
        pass

    # 2. Purga directa por SQL crudo sobre las tablas y secuencias
    tablas_financieras = [
        'pagos', 'pago',
        'ingresos_caja', 'ingreso_caja',
        'gastos', 'gasto',
        'turnos_caja', 'turno_caja',
        'pagos_personal', 'pago_personal'
    ]

    for t in tablas_financieras:
        try:
            db.session.execute(db.text(f"DELETE FROM {t};"))
        except Exception:
            pass

    try:
        secuencias = "','".join(tablas_financieras)
        db.session.execute(db.text(f"DELETE FROM sqlite_sequence WHERE name IN ('{secuencias}');"))
    except Exception:
        pass

    # 3. Confirmar cambios y expirar caché de entidades
    db.session.commit()
    db.session.expire_all()
    db.session.remove()

    print("=" * 60)
    print("✅ PURGA EXITOSA: Caja y Tesorería restablecidas a Bs. 0.00.")
    print("=" * 60)
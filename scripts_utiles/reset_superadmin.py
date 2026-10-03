# -*- coding: utf-8 -*-
"""
Script para resetear la contraseña del Superadmin a ADMIN2026.
Ejecutar: python reset_superadmin.py
"""
import sys
import os

# Agregar la ruta del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, ConfiguracionSuperadmin

def reset_password():
    app = create_app()
    
    with app.app_context():
        # Buscar la entrada de superadmin_password
        cfg = ConfiguracionSuperadmin.query.filter_by(clave='superadmin_password').first()
        
        if cfg:
            # Actualizar a ADMIN2026
            cfg.valor = 'ADMIN2026'
            print(f"✅ Contraseña actualizada de '{cfg.valor}' a 'ADMIN2026'")
        else:
            # Crear nueva entrada
            cfg = ConfiguracionSuperadmin(
                clave='superadmin_password',
                valor='ADMIN2026',
                descripcion='Contraseña maestra del Superadmin'
            )
            db.session.add(cfg)
            print("✅ Contraseña creada: ADMIN2026")
        
        db.session.commit()
        print("=" * 60)
        print("🔐 CONTRASEÑA SUPERADMIN RESETADA")
        print("   Nueva contraseña: ADMIN2026")
        print("=" * 60)

if __name__ == '__main__':
    reset_password()
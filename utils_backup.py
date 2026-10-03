# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: utils_backup.py
Proyecto: Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Utilidad para la creación automática de respaldos de la base de datos.
==============================================================================
"""

import os
import shutil
from datetime import datetime

def realizar_respaldo_db(app=None):
    """Crea una copia de respaldo de la base de datos SQLite de forma segura."""
    try:
        # Detectar la ruta de la base de datos activa
        db_path = "instance/colegio.db"
        if not os.path.exists(db_path):
            db_path = "colegio.db"
        
        if os.path.exists(db_path):
            backup_dir = os.path.join("instance", "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"colegio_respaldo_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            shutil.copy2(db_path, backup_path)
            print(f"✅ Respaldo automático de base de datos generado: {backup_path}")
            return True
    except Exception as e:
        print(f"⚠️ Aviso: No se pudo completar el respaldo automático: {e}")
    return False
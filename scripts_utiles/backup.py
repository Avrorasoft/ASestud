# -*- coding: utf-8 -*-
# ==============================================================================
# Archivo: backup.py
# Descripción: Script de respaldo optimizado (Incluye Base de Datos y Datos, ignora caché/código innecesario)
# ==============================================================================

import os
import zipfile
from datetime import datetime

def crear_backup_datos():
    print("Iniciando la recolección de datos y base de datos...")
    
    # Generar nombre del archivo con fecha y hora
    fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_zip = f"backup_esencial_colegio_{fecha_str}.zip"
    
    base_dir = r"C:\ASestud"
    base_upload = r"C:\ASestud\uploads"
    
    # Archivos específicos y carpetas irremplazables a respaldar en el disco C
    elementos_esenciales = [
        os.path.join(base_dir, 'colegio_vaca_diez.db'),  # <--- ¡LA BASE DE DATOS CRÍTICA ESTÁ AQUÍ!
        os.path.join(base_upload, 'estudiantes'),
        os.path.join(base_upload, 'chat'),
        os.path.join(base_upload, 'justificaciones'),
        os.path.join(base_upload, 'gastos'),
        os.path.join(base_upload, 'monitor_album'),
        os.path.join(base_upload, 'boletines'),
        os.path.join(base_upload, 'recibos'),
        os.path.join(base_upload, 'recibos_personal'),
        os.path.join(base_upload, 'backups'),
        os.path.join(base_dir, '.env')                   # Variables de entorno si las usas
    ]

    # Extensiones de código fuente que podemos omitir si solo quieres datos
    extensiones_prohibidas = ('.pyc', '.pyo', '.log')
    
    archivos_procesados = 0

    with zipfile.ZipFile(nombre_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for raiz, _, archivos in os.walk(base_dir):
            # Evitar entrar en carpetas de entorno virtual o caché para ahorrar espacio
            if '__pycache__' in raiz or 'venv' in raiz or '.git' in raiz:
                continue
                
            for archivo in archivos:
                ruta_completa = os.path.join(raiz, archivo)
                
                # 1. Ignorar temporales y caché
                if archivo.endswith(extensiones_prohibidas):
                    continue
                    
                # 2. Verificar si pertenece a los elementos esenciales
                es_valido = False
                for elemento in elementos_esenciales:
                    if os.path.abspath(ruta_completa).startswith(os.path.abspath(elemento)) or os.path.abspath(ruta_completa) == os.path.abspath(elemento):
                        es_valido = True
                        break
                        
                # 3. Empaquetar si pasa la validación
                if es_valido:
                    arcname = os.path.relpath(ruta_completa, base_dir)
                    zipf.write(ruta_completa, arcname)
                    archivos_procesados += 1
                    
    print(f"\n✅ Backup finalizado con éxito.")
    print(f"📦 Archivo generado: {nombre_zip}")
    print(f"📄 Total de archivos respaldados: {archivos_procesados}")
    print("Este respaldo incluye tu base de datos SQLite de forma segura.")

if __name__ == '__main__':
    crear_backup_datos()
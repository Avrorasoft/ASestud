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
    
    # Archivos específicos y carpetas irremplazables a respaldar
    elementos_esenciales = [
        'colegio_vaca_diez.db',  # <--- ¡LA BASE DE DATOS CRÍTICA ESTÁ AQUÍ!
        os.path.join('static', 'uploads'),
        os.path.join('static', 'recibos'),
        os.path.join('static', 'boletines'),
        os.path.join('static', 'recibos_personal'),
        'backups',
        '.env'                   # Variables de entorno si las usas
    ]

    # Extensiones de código fuente que podemos omitir si solo quieres datos, 
    # OJO: Si también quieres respaldar tu código por seguridad, elimina '.py' de aquí.
    extensiones_prohibidas = ('.pyc', '.pyo', '.log')
    
    archivos_procesados = 0

    with zipfile.ZipFile(nombre_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for raiz, _, archivos in os.walk('.'):
            # Evitar entrar en carpetas de entorno virtual o caché para ahorrar espacio
            if '__pycache__' in raiz or 'venv' in raiz or '.git' in raiz:
                continue
                
            for archivo in archivos:
                ruta_completa = os.path.join(raiz, archivo)
                ruta_normalizada = ruta_completa.replace('./', '').replace('.\\', '')
                
                # 1. Ignorar temporales y caché
                if archivo.endswith(extensiones_prohibidas):
                    continue
                    
                # 2. Verificar si es la base de datos en la raíz o pertenece a las carpetas válidas
                es_valido = False
                if ruta_normalizada == 'colegio_vaca_diez.db' or ruta_normalizada == '.env':
                    es_valido = True
                else:
                    for elemento in elementos_esenciales:
                        if ruta_normalizada.startswith(elemento):
                            es_valido = True
                            break
                        
                # 3. Empaquetar si pasa la validación
                if es_valido:
                    arcname = os.path.relpath(ruta_completa, '.')
                    zipf.write(ruta_completa, arcname)
                    archivos_procesados += 1
                    
    print(f"\n✅ Backup finalizado con éxito.")
    print(f"📦 Archivo generado: {nombre_zip}")
    print(f"📄 Total de archivos respaldados: {archivos_procesados}")
    print("Este respaldo incluye tu base de datos SQLite de forma segura.")

if __name__ == '__main__':
    crear_backup_datos()
# -*- coding: utf-8 -*-
import os
import zipfile
from datetime import datetime

def crear_respaldo_esencial():
    directorio_actual = os.path.abspath(os.path.dirname(__file__))
    carpeta_backups = os.path.join(directorio_actual, 'backups')
    
    if not os.path.exists(carpeta_backups):
        os.makedirs(carpeta_backups)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_zip = os.path.join(carpeta_backups, f"respaldo_esencial_{timestamp}.zip")
    
    exclusiones_directorios = {'__pycache__', 'venv', 'env', '.venv', 'backups', '.git'}
    exclusiones_extensiones = ('.pyc', '.pyo', '.log')
    
    print("📦 Iniciando compresión de archivos esenciales...")
    archivos_respaldados = 0
    
    with zipfile.ZipFile(nombre_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for raiz, directorios, archivos in os.walk(directorio_actual):
            directorios[:] = [d for d in directorios if d not in exclusiones_directorios]
            
            for archivo in archivos:
                if archivo.endswith(exclusiones_extensiones):
                    continue
                
                ruta_completa = os.path.join(raiz, archivo)
                ruta_relativa = os.path.relpath(ruta_completa, directorio_actual)
                
                try:
                    zipf.write(ruta_completa, ruta_relativa)
                    archivos_respaldados += 1
                    print(f"[{archivos_respaldados}] Agregando: {ruta_relativa}")
                except Exception as e:
                    print(f"⚠️ Omitido por bloqueo/error en {ruta_relativa}: {e}")
                
    print(f"\n✅ ¡Respaldo completado con éxito! Se archivaron {archivos_respaldados} archivos.")

if __name__ == '__main__':
    crear_respaldo_esencial()
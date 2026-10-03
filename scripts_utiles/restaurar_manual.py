import os
import sys
import shutil
import zipfile
from datetime import datetime

print("=" * 70)
print("RESTAURADOR MANUAL DE ARCHIVO .avr")
print("=" * 70)

# Detectar el directorio actual (donde se ejecuta el script)
proyecto_dir = os.getcwd()
print(f"\nDirectorio del proyecto: {proyecto_dir}")

# Buscar la carpeta de backups
backups_dir = os.path.join(proyecto_dir, "static", "backups")
print(f"Buscando backups en: {backups_dir}")

# Si no existe en static/backups, buscar en otras ubicaciones comunes
if not os.path.exists(backups_dir):
    print(f"  [!] No existe {backups_dir}")
    print(f"  [..] Buscando en otras ubicaciones...")
    
    # Verificar subdirectorios
    for root, dirs, files in os.walk(proyecto_dir):
        if 'backups' in dirs:
            backups_dir = os.path.join(root, 'backups')
            print(f"  [OK] Encontrado en: {backups_dir}")
            break
    
    if not os.path.exists(backups_dir):
        print("  [ERROR] No se encontro ninguna carpeta 'backups'")
        print("\nEstructura actual del proyecto:")
        for item in os.listdir(proyecto_dir):
            print(f"  {item}")
        sys.exit(1)

# Listar archivos .avr disponibles
archivos_avr = [f for f in os.listdir(backups_dir) if f.endswith('.avr')]
if not archivos_avr:
    print(f"  [ERROR] No hay archivos .avr en {backups_dir}")
    print(f"  Contenido de la carpeta:")
    for item in os.listdir(backups_dir):
        print(f"    {item}")
    sys.exit(1)

print(f"\nArchivos .avr disponibles ({len(archivos_avr)}):")
for i, f in enumerate(archivos_avr, 1):
    ruta = os.path.join(backups_dir, f)
    tamano = os.path.getsize(ruta) / (1024 * 1024)
    print(f"  [{i}] {f} ({tamano:.2f} MB)")

# Seleccionar archivo
try:
    opcion = int(input(f"\nSeleccione el numero del archivo a restaurar (1-{len(archivos_avr)}): "))
    if opcion < 1 or opcion > len(archivos_avr):
        print("Opcion invalida")
        sys.exit(1)
except:
    print("Entrada invalida")
    sys.exit(1)

archivo_seleccionado = os.path.join(backups_dir, archivos_avr[opcion - 1])
print(f"\nRestaurando: {archivos_avr[opcion - 1]}")

# Ruta de la base de datos
db_destino = os.path.join(proyecto_dir, "colegio_vaca_diez.db")
print(f"BD destino: {db_destino}")

# Paso 1: Respaldo de seguridad de la BD actual
if os.path.exists(db_destino):
    backup_seguridad = db_destino + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(db_destino, backup_seguridad)
        print(f"  [OK] Respaldo de seguridad creado: {os.path.basename(backup_seguridad)}")
    except Exception as e:
        print(f"  [!] Aviso: no se pudo crear respaldo de seguridad: {e}")

# Paso 2: Extraer el .avr a carpeta temporal
temp_dir = os.path.join(proyecto_dir, "_temp_restauracion")
if os.path.exists(temp_dir):
    shutil.rmtree(temp_dir)
os.makedirs(temp_dir, exist_ok=True)

print(f"  [..] Extrayendo .avr...")
try:
    with zipfile.ZipFile(archivo_seleccionado, 'r') as zipf:
        lista_archivos = zipf.namelist()
        print(f"       Archivos en el .avr: {len(lista_archivos)}")
        # Mostrar primeros 10 archivos
        for f in lista_archivos[:10]:
            print(f"       - {f}")
        if len(lista_archivos) > 10:
            print(f"       ... y {len(lista_archivos) - 10} mas")
        zipf.extractall(temp_dir)
    print(f"  [OK] Extraido exitosamente")
except Exception as e:
    print(f"  [ERROR] No se pudo extraer el .avr: {e}")
    sys.exit(1)

# Paso 3: Buscar el archivo .db extraido
db_extraido = None
for root, dirs, files in os.walk(temp_dir):
    for f in files:
        if f.endswith('.db'):
            db_extraido = os.path.join(root, f)
            break
    if db_extraido:
        break

if not db_extraido:
    print("  [ERROR] No se encontro archivo .db en el .avr")
    print("  Contenido extraido:")
    for root, dirs, files in os.walk(temp_dir):
        for f in files[:20]:
            print(f"    {os.path.join(root, f)}")
    shutil.rmtree(temp_dir)
    sys.exit(1)

tam_origen = os.path.getsize(db_extraido)
print(f"  [OK] BD encontrada: {os.path.basename(db_extraido)} ({tam_origen/1024:.1f} KB)")

# Paso 4: TECNICA INFALIBLE - Renombrar + Copiar
print(f"  [..] Reemplazando base de datos...")

db_viejo = db_destino + ".old"
if os.path.exists(db_viejo):
    try:
        os.remove(db_viejo)
    except:
        pass

# Renombrar el actual (Windows permite esto aunque este bloqueado)
if os.path.exists(db_destino):
    try:
        os.rename(db_destino, db_viejo)
        print(f"       BD actual renombrada a .old")
    except Exception as e:
        print(f"  [ERROR] No se pudo renombrar BD actual: {e}")
        shutil.rmtree(temp_dir)
        sys.exit(1)

# Copiar la nueva
try:
    shutil.copy2(db_extraido, db_destino)
    tam_nuevo = os.path.getsize(db_destino)
    print(f"  [OK] BD restaurada: {tam_nuevo/1024:.1f} KB")
except Exception as e:
    print(f"  [ERROR] No se pudo copiar la nueva BD: {e}")
    # Revertir
    if os.path.exists(db_viejo):
        os.rename(db_viejo, db_destino)
    shutil.rmtree(temp_dir)
    sys.exit(1)

# Eliminar el .old si todo salio bien
if os.path.exists(db_viejo):
    try:
        os.remove(db_viejo)
        print(f"  [OK] BD antigua eliminada")
    except:
        pass

# Paso 5: Restaurar archivos adicionales (static/uploads, etc.)
print(f"  [..] Restaurando archivos adicionales...")
archivos_restaurados = 0
for item in os.listdir(temp_dir):
    if item.endswith('.db') or item == 'base_de_datos.sql':
        continue
    origen = os.path.join(temp_dir, item)
    destino = os.path.join(proyecto_dir, item)
    try:
        if os.path.isdir(origen):
            if os.path.exists(destino):
                shutil.rmtree(destino)
            shutil.copytree(origen, destino)
        else:
            shutil.copy2(origen, destino)
        archivos_restaurados += 1
    except Exception as e:
        print(f"       Aviso: no se pudo restaurar {item}: {e}")

print(f"  [OK] {archivos_restaurados} elementos adicionales restaurados")

# Limpieza
shutil.rmtree(temp_dir)

print()
print("=" * 70)
print("RESTAURACION COMPLETADA EXITOSAMENTE")
print("=" * 70)
print()
print("Ahora inicie el servidor con: python app.py")
print()

import os
import glob

# Buscar el archivo base.html
base_files = glob.glob(r"D:\colegio_vaca_diez\templates\base.html", recursive=True)
base_files += glob.glob(r"D:\colegio_vaca_diez\templates\**\base.html", recursive=True)

if not base_files:
    print("ERROR: No se encontró base.html")
else:
    ruta_base = base_files[0]
    print(f"Archivo base encontrado: {ruta_base}")
    
    with open(ruta_base, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    # Verificar si ya existe el enlace
    if "configuracion_anio_escolar" in contenido:
        print("NOTA: El enlace ya existe en base.html")
    else:
        # Buscar un lugar típico para agregar el enlace (cerca de superadmin o boveda)
        # Buscamos patrones comunes en el navbar
        patrones_busqueda = [
            "superadmin",
            "boveda",
            "Bóveda",
            "nav-item",
            "</nav>"
        ]
        
        encontrado = False
        for patron in patrones_busqueda:
            if patron in contenido:
                print(f"Patrón encontrado: {patron}")
                encontrado = True
                break
        
        if not encontrado:
            print("ADVERTENCIA: No se encontraron patrones típicos de menú")
        
        print(f"Tamaño del archivo: {len(contenido)} caracteres")
        print(f"Primeras 500 líneas contienen {len(contenido.split(chr(10))[:500])} líneas revisadas")

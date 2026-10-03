import os
import glob

# Buscar la plantilla de boveda
boveda_files = glob.glob(r"D:\colegio_vaca_diez\templates\superadmin\*.html")
print(f"Archivos en templates/superadmin/: {len(boveda_files)}")
for f in boveda_files:
    print(f"  - {os.path.basename(f)}")

# Buscar el archivo de boveda específico
boveda_file = None
for f in boveda_files:
    if 'boveda' in os.path.basename(f).lower() or 'vault' in os.path.basename(f).lower():
        boveda_file = f
        break

if not boveda_file:
    print("\nERROR: No se encontró boveda.html en templates/superadmin/")
    print("Usando base.html para agregar el enlace al menú principal")
    
    # Agregar enlace en base.html
    base_path = r"D:\colegio_vaca_diez\templates\base.html"
    with open(base_path, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    if "configuracion_anio_escolar" in contenido:
        print("NOTA: El enlace ya existe en base.html")
    else:
        # Buscar el lugar donde está el menú de superadmin
        busca = "{% if session.get('superadmin_boveda') or session.get('superadmin_informes') %}"
        if busca in contenido:
            # Insertar después de la apertura del if
            idx = contenido.find(busca) + len(busca)
            nuevo_enlace = """
                <!-- Enlace a configuración del año escolar -->
                <li class="nav-item">
                    <a class="nav-link" href="{{ url_for('superadmin.configuracion_anio_escolar') }}">
                        <i class="bi bi-calendar3"></i> Configuración Año Escolar
                    </a>
                </li>"""
            contenido = contenido[:idx] + nuevo_enlace + contenido[idx:]
            with open(base_path, "w", encoding="utf-8") as f:
                f.write(contenido)
            print("OK: Enlace agregado a base.html")
        else:
            print("ERROR: No se encontró el if de superadmin en base.html")
else:
    print(f"\nArchivo de boveda encontrado: {boveda_file}")
    
    with open(boveda_file, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    if "configuracion_anio_escolar" in contenido:
        print("NOTA: El enlace ya existe en boveda.html")
    else:
        # Buscar el lugar donde insertar (al inicio del contenido)
        busca = '{% block content %}'
        if busca in contenido:
            idx = contenido.find(busca) + len(busca)
            nuevo_enlace = """
    <!-- ACCESO A CONFIGURACIÓN DEL AÑO ESCOLAR -->
    <div class="alert alert-warning mt-3">
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <i class="bi bi-calendar3"></i>
                <strong>Configuración del Año Escolar:</strong> Define fechas, mora, trimestres y parámetros del sistema.
            </div>
            <a href="{{ url_for('superadmin.configuracion_anio_escolar') }}" class="btn btn-warning">
                <i class="bi bi-gear-fill"></i> Configurar Año Escolar
            </a>
        </div>
    </div>
    """
            contenido = contenido[:idx] + nuevo_enlace + contenido[idx:]
            with open(boveda_file, "w", encoding="utf-8") as f:
                f.write(contenido)
            print(f"OK: Enlace agregado a {os.path.basename(boveda_file)}")
        else:
            print("ERROR: No se encontró {% block content %}")

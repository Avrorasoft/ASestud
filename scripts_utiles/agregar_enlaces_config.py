import os

# ========================================================================
# 1. AGREGAR ENLACE EN EL MENU PRINCIPAL (base.html)
# ========================================================================
base_path = r"D:\colegio_vaca_diez\templates\base.html"
with open(base_path, "r", encoding="utf-8") as f:
    contenido = f.read()

if "configuracion_anio_escolar" in contenido:
    print("NOTA: El enlace ya existe en base.html")
else:
    # Buscar el bloque de informess y agregar después
    busca = """                {% if session.get('superadmin_boveda') or session.get('superadmin_informes') %}
                <a class="nav-link" href="/superadmin/informes">
                    <i class="bi bi-graph-up-arrow"></i>
                    Informes
                </a>
                {% endif %}"""
    
    reemplazo = """                {% if session.get('superadmin_boveda') or session.get('superadmin_informes') %}
                <a class="nav-link" href="/superadmin/informes">
                    <i class="bi bi-graph-up-arrow"></i>
                    Informes
                </a>
                
                <a class="nav-link" href="/superadmin/configuracion_anio_escolar">
                    <i class="bi bi-calendar3"></i>
                    Configuración Año Escolar
                </a>
                {% endif %}"""
    
    if busca in contenido:
        contenido = contenido.replace(busca, reemplazo)
        with open(base_path, "w", encoding="utf-8") as f:
            f.write(contenido)
        print("OK: Enlace agregado al menu principal (base.html)")
    else:
        print("ERROR: No se encontro el bloque de informes en base.html")
        print("Intentando variante 2...")
        # Buscar solo la parte del if para agregar despues de informes
        busca2 = """                <a class="nav-link" href="/superadmin/informes">
                    <i class="bi bi-graph-up-arrow"></i>
                    Informes
                </a>
                {% endif %}"""
        reemplazo2 = """                <a class="nav-link" href="/superadmin/informes">
                    <i class="bi bi-graph-up-arrow"></i>
                    Informes
                </a>
                
                <a class="nav-link" href="/superadmin/configuracion_anio_escolar">
                    <i class="bi bi-calendar3"></i>
                    Configuración Año Escolar
                </a>
                {% endif %}"""
        
        if busca2 in contenido:
            contenido = contenido.replace(busca2, reemplazo2)
            with open(base_path, "w", encoding="utf-8") as f:
                f.write(contenido)
            print("OK: Enlace agregado al menu principal (variante 2)")
        else:
            print("ERROR: No se pudo agregar el enlace")

# ========================================================================
# 2. AGREGAR TARJETA EN EL PANEL DE BOVEDA (panel.html)
# ========================================================================
panel_path = r"D:\colegio_vaca_diez\templates\superadmin\panel.html"
if os.path.exists(panel_path):
    with open(panel_path, "r", encoding="utf-8") as f:
        contenido_panel = f.read()
    
    if "configuracion_anio_escolar" in contenido_panel:
        print("NOTA: El enlace ya existe en panel.html")
    else:
        # Buscar el lugar donde insertar (después del título o al inicio del contenido)
        if "{% block content %}" in contenido_panel:
            idx = contenido_panel.find("{% block content %}") + len("{% block content %}")
            nueva_tarjeta = """

    <!-- TARJETA DE CONFIGURACION DEL ANO ESCOLAR -->
    <div class="row mb-4 mt-3">
        <div class="col-12">
            <div class="card border-warning shadow-sm">
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="card-title mb-1">
                            <i class="bi bi-calendar3 text-warning"></i> 
                            Configuración del Año Escolar
                        </h5>
                        <p class="card-text mb-0 text-muted small">
                            Define la fecha de inicio, días de vencimiento, mora, trimestres y todos los parámetros del año escolar.
                        </p>
                    </div>
                    <a href="{{ url_for('superadmin.configuracion_anio_escolar') }}" 
                       class="btn btn-warning btn-lg">
                        <i class="bi bi-gear-fill"></i> Configurar
                    </a>
                </div>
            </div>
        </div>
    </div>
    """
            contenido_panel = contenido_panel[:idx] + nueva_tarjeta + contenido_panel[idx:]
            with open(panel_path, "w", encoding="utf-8") as f:
                f.write(contenido_panel)
            print("OK: Tarjeta de configuracion agregada a panel.html")
        else:
            print("ERROR: No se encontro {% block content %} en panel.html")
else:
    print("NOTA: No existe panel.html")

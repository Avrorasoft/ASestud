base_path = r"D:\colegio_vaca_diez\templates\base.html"
with open(base_path, "r", encoding="utf-8") as f:
    contenido = f.read()

if "configuracion_institucion" in contenido:
    print("NOTA: El enlace ya existe")
else:
    busca = """                <a class="nav-link" href="/superadmin/configuracion_anio_escolar">
                    <i class="bi bi-calendar3"></i>
                    Configuración Año Escolar
                </a>
                {% endif %}"""
    
    reemplazo = """                <a class="nav-link" href="/superadmin/configuracion_anio_escolar">
                    <i class="bi bi-calendar3"></i>
                    Configuración Año Escolar
                </a>
                
                <a class="nav-link" href="/superadmin/configuracion_institucion">
                    <i class="bi bi-building"></i>
                    Configuración Institucional
                </a>
                {% endif %}"""
    
    if busca in contenido:
        contenido = contenido.replace(busca, reemplazo)
        with open(base_path, "w", encoding="utf-8") as f:
            f.write(contenido)
        print("OK: Enlace de Configuracion Institucional agregado al menu")
    else:
        print("ERROR: No se encontro el bloque de Configuracion Anio Escolar")
        print("Intentando agregar directamente despues de informes...")
        
        # Buscar el bloque de informes como alternativa
        busca_alt = """                <a class="nav-link" href="/superadmin/informes">
                    <i class="bi bi-graph-up-arrow"></i>
                    Informes
                </a>
                {% endif %}"""
        
        reemplazo_alt = """                <a class="nav-link" href="/superadmin/informes">
                    <i class="bi bi-graph-up-arrow"></i>
                    Informes
                </a>
                
                <a class="nav-link" href="/superadmin/configuracion_institucion">
                    <i class="bi bi-building"></i>
                    Configuración Institucional
                </a>
                
                <a class="nav-link" href="/superadmin/configuracion_anio_escolar">
                    <i class="bi bi-calendar3"></i>
                    Configuración Año Escolar
                </a>
                {% endif %}"""
        
        if busca_alt in contenido:
            contenido = contenido.replace(busca_alt, reemplazo_alt)
            with open(base_path, "w", encoding="utf-8") as f:
                f.write(contenido)
            print("OK: Enlaces agregados (variante alternativa)")
        else:
            print("ERROR: No se pudo agregar el enlace")

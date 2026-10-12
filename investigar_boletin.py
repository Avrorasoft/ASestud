import os
import re

print("=" * 70)
print("🔍 AUDITORÍA DE ARCHIVOS: BOLETÍN Y KÁRDEX EN ASESTUD")
print("=" * 70)

# 1. Buscar todas las plantillas HTML vinculadas
print("\n[1] Archivos HTML existentes en 'templates':")
if os.path.exists("templates"):
    for root, dirs, files in os.walk("templates"):
        for f in files:
            if f.endswith(".html") and any(k in f.lower() for k in ["boletin", "kardex", "reporte", "calificacion", "libro", "nota"]):
                ruta_rel = os.path.relpath(os.path.join(root, f), "templates")
                print(f"  📄 templates/{ruta_rel}")
else:
    print("  ❌ Carpeta 'templates' no encontrada.")

# 2. Rastrear en las rutas qué plantillas se están renderizando para el boletín y kárdex
print("\n[2] Rutas registradas en 'routes' que renderizan estas vistas:")
if os.path.exists("routes"):
    for root, dirs, files in os.walk("routes"):
        for f in files:
            if f.endswith(".py"):
                path_py = os.path.join(root, f)
                with open(path_py, "r", encoding="utf-8", errors="ignore") as arch:
                    contenido = arch.read()
                    coincidencias = re.findall(r"render_template\s*\(\s*['\"]([^'\"]+)['\"]", contenido)
                    rutas_vistas = re.findall(r"@[\w_]+\.route\s*\(\s*['\"]([^'\"]+)['\"]", contenido)
                    
                    for template_name in coincidencias:
                        if any(k in template_name.lower() for k in ["boletin", "kardex", "reporte"]):
                            print(f"  🔗 En {f}: render_template('{template_name}')")
else:
    print("  ❌ Carpeta 'routes' no encontrada.")

# 3. Detectar generador de PDF
print("\n[3] Generadores de boletines en PDF:")
if os.path.exists("utils"):
    for f in os.listdir("utils"):
        if f.endswith(".py") and any(k in f.lower() for k in ["boletin", "pdf"]):
            print(f"  ⚙️ utils/{f}")

print("\n" + "=" * 70)

import os
import re

print("=" * 70)
print("🔍 BÚSQUEDA DEL CÁRDEX DE ESTUDIANTE")
print("=" * 70)

if os.path.exists("routes"):
    for root, dirs, files in os.walk("routes"):
        for f in files:
            if "estudiante" in f.lower():
                path_py = os.path.join(root, f)
                with open(path_py, "r", encoding="utf-8", errors="ignore") as arch:
                    contenido = arch.read()
                    matches = re.findall(r"def (ver_estudiante|kardex|detalle_estudiante)[\s\S]*?render_template\s*\(\s*['\"]([^'\"]+)['\"]", contenido)
                    for func, tpl in matches:
                        print(f"📌 En routes/{f} -> función '{func}' renderiza: 'templates/{tpl}'")

print("=" * 70)

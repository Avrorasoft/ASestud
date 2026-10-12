import os

def mostrar_archivo(ruta):
    print("=" * 70)
    print(f"📄 CONTENIDO DE: {ruta}")
    print("=" * 70)
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
            print(f.read())
    else:
        print("❌ Archivo no encontrado.")

mostrar_archivo("utils/boletin_generator.py")
mostrar_archivo("templates/estudiantes/ver_boletin.html")

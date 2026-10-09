# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.abspath('.'))
from app import app
from models import db, ConfiguracionSuperadmin

with app.app_context():
    print("=" * 60)
    print(" [ DIAGNÓSTICO FORENSE: CONFIGURACIÓN DE MESES ACTIVOS ]")
    print("=" * 60)
    
    configs = ConfiguracionSuperadmin.query.all()
    print(f"Total de registros en ConfiguracionSuperadmin: {len(configs)}")
    
    encontrado = False
    for cfg in configs:
        if 'mes' in cfg.clave.lower():
            print(f" -> Clave encontrada en BD: [{cfg.clave}] = '{cfg.valor}'")
            encontrado = True
            
    if not encontrado:
        print("❌ [ALERTA CRÍTICA]: No existe ninguna clave relacionada con 'meses' en la base de datos.")
        print("   Esto significa que la función siempre cae al valor por defecto.")

    try:
        from routes.pagos import obtener_meses_activos
        meses = obtener_meses_activos()
        print(f"\n Resultado actual de obtener_meses_activos():")
        print(f"   {meses} (Total: {len(meses)} meses)")
    except Exception as e:
        print(f"❌ Error al importar o ejecutar obtener_meses_activos(): {e}")

    print("\n" + "-" * 60)
    print(" [ REVISIÓN DE PLANTILLAS HTML ]")
    print("-" * 60)
    
    ruta_plantilla = os.path.join('templates', 'estudiantes', 'pagar.html')
    if os.path.exists(ruta_plantilla):
        with open(ruta_plantilla, 'r', encoding='utf-8') as f:
            contenido_html = f.read()
            if 'Enero' in contenido_html and 'Diciembre' in contenido_html:
                print(f"⚠️ [AVISO]: La plantilla '{ruta_plantilla}' menciona nombres de meses explícitos.")
                if 'obtener_meses_activos' not in contenido_html and 'estado_meses' not in contenido_html:
                    print(f"❌ [CAUSA RAIZ]: La plantilla '{ruta_plantilla}' NO está iterando dinámicamente sobre los meses.")
                else:
                    print(f"✅ La plantilla tiene referencias dinámicas.")
            else:
                print("✅ La plantilla no contiene listas fijas aparentes.")
    else:
        print(f"⚠️ No se encontró la plantilla en {ruta_plantilla}")

    print("=" * 60)

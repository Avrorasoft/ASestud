# -*- coding: utf-8 -*-
r"""
==============================================================================
Archivo: run.py
Proyecto: ASestud
Descripción:
    Punto de entrada para ejecución en producción local con IP fija/dinámica de red.
    Configurado para operar de manera absoluta desde C:\ASestud, utilizando
    Waitress como servidor WSGI y abriendo automáticamente el navegador en Modo App.
==============================================================================
"""

import os
import sys
import time
import threading
import subprocess
import webbrowser
import ctypes
import socket

# Forzar el directorio base absoluto en la raíz del disco C:\ si se ejecuta de forma independiente
BASE_SYSTEM_DIR = r"C:\ASestud"
if os.path.exists(BASE_SYSTEM_DIR):
    if BASE_SYSTEM_DIR not in sys.path:
        sys.path.insert(0, BASE_SYSTEM_DIR)
    os.chdir(BASE_SYSTEM_DIR)

from app import create_app
from models import db


def configurar_id_barra_tareas():
    """Asigna un AppUserModelID único para que Windows muestre el ícono propio en la barra de tareas."""
    try:
        appid = 'AvroraSoft.ASestud.GestorEscolar.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    except Exception:
        pass


def get_port():
    try:
        return int(os.environ.get('PORT', '5000'))
    except Exception:
        return 5000


def obtener_ip_local():
    """Detecta automáticamente la IP real de la PC en la red local de forma dinámica."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def abrir_navegador(url):
    """
    Abre el navegador en 'Modo App' para forzar una ventana limpia (sin pestañas ni menús)
    y asegurar que la barra de tareas de Windows muestre el ícono del sistema ASestud.
    """
    time.sleep(1.5)
    
    # Rutas comunes de instalación de navegadores Chromium en Windows
    rutas_navegadores = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ]

    navegador_encontrado = False

    for ruta in rutas_navegadores:
        if os.path.exists(ruta):
            try:
                # Ejecutar el navegador forzando el modo aplicación
                subprocess.Popen([ruta, f"--app={url}"])
                navegador_encontrado = True
                break
            except Exception:
                continue
    
    # Respaldo: Si no existe Chrome ni Edge en la computadora, usar el comportamiento estándar
    if not navegador_encontrado:
        try:
            webbrowser.open(url)
        except Exception:
            pass


def main():
    configurar_id_barra_tareas()
    port = get_port()
    
    # Detectar dinámicamente la IP local de la red
    ip_local = obtener_ip_local()
    url = f'http://{ip_local}:{port}/'

    app = create_app()

    # Crear tablas si no existen en la base de datos de C:\ASestud
    with app.app_context():
        db.create_all()

    print("=" * 70)
    print("ASestud - Gestión Escolar (Servidor Central)")
    print(f"Directorio de Operación: {BASE_SYSTEM_DIR}")
    print("=" * 70)
    print(f"Servidor iniciado y accesible en: {url}")
    print(f"Puerto activo: {port}")
    print("Presione Ctrl+C para detener el servidor.")
    print("=" * 70)

    # Abrir navegador automáticamente usando la IP real de red
    threading.Thread(
        target=abrir_navegador,
        args=(url,),
        daemon=True
    ).start()

    try:
        from waitress import serve
        serve(
            app,
            host='0.0.0.0',
            port=port,
            threads=10
        )
    except KeyboardInterrupt:
        print("\n✅ Sistema detenido correctamente.")
    except ImportError:
        print("⚠️ Waitress no instalado. Ejecutando con servidor Flask simple.")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False
        )


if __name__ == '__main__':
    main()
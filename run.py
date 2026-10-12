# -*- coding: utf-8 -*-
r"""
==============================================================================
Archivo: run.py
Proyecto: ASestud
Descripción:
    Punto de entrada para ejecución en producción local con IP fija/dinámica de red.
    Configurado para operar de manera absoluta desde C:\ASestud, utilizando
    Waitress como servidor WSGI y maximizando la ventana al 100% mediante
    la API Win32 (ShowWindow SW_MAXIMIZE) sin carteles de contraseñas.
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


def forzar_ventana_maximizada():
    """
    Busca la ventana abierta por el sistema y le aplica la instrucción
    SW_MAXIMIZE (3) a nivel de sistema operativo Windows para forzar el 100%.
    """
    user32 = ctypes.windll.user32
    SW_MAXIMIZE = 3

    # Reintenta durante 6 segundos hasta que la ventana esté creada en pantalla
    for _ in range(12):
        time.sleep(0.5)
        def enum_windows_callback(hwnd, extra):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                titulo = buff.value.lower()
                # Coincide si el título contiene ASestud, el nombre del sistema o la IP/puerto
                if any(k in titulo for k in ['asestud', 'colegio', '5000', 'gestión', 'gestion', 'cardex', 'unidad']):
                    user32.ShowWindow(hwnd, SW_MAXIMIZE)
                    user32.SetForegroundWindow(hwnd)
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        cb = WNDENUMPROC(enum_windows_callback)
        user32.EnumWindows(cb, 0)


def abrir_navegador(url):
    """
    Lanza el navegador y ejecuta el forzado de ventana al 100% en Windows.
    """
    time.sleep(1.2)

    # Banderas específicas para neutralizar captura de contraseñas
    flags_navegador = [
        f"--app={url}",
        "--start-maximized",
        "--disable-save-password-bubble",
        "--disable-features=PasswordManager,AutofillServerCommunication,PasswordGeneration",
        "--password-store=basic",
        "--no-first-run",
        "--no-default-browser-check"
    ]

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
                subprocess.Popen([ruta] + flags_navegador)
                navegador_encontrado = True
                break
            except Exception:
                continue

    if not navegador_encontrado:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    # Disparar el forzado a 100% de Windows en segundo plano
    threading.Thread(target=forzar_ventana_maximizada, daemon=True).start()


def main():
    configurar_id_barra_tareas()
    port = get_port()

    ip_local = obtener_ip_local()
    url = f'http://{ip_local}:{port}/'

    app = create_app()

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
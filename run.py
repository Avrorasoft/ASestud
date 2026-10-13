# -*- coding: utf-8 -*-
r"""
==============================================================================
Archivo: run.py
Proyecto: ASestud
Descripción:
    Punto de entrada para ejecución en producción local con IP fija/dinámica de red.
    Configurado para operar de manera absoluta desde C:\ASestud, utilizando
    Waitress como servidor WSGI y maximizando la ventana al 100% de pantalla
    mediante Win32 API (ShowWindow SW_MAXIMIZE) sin parpadeos ni pérdida de foco.
    Verifica e inyecta automáticamente las credenciales por defecto:
    - Login de usuario: admin / admin2026
    - Acceso Superadmin / Bóveda: ADMIN2026
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

from werkzeug.security import generate_password_hash
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


def verificar_credenciales_defecto():
    """
    Garantiza la existencia y consistencia de las credenciales oficiales por defecto:
    - Usuario administrador: 'admin' con clave 'admin2026'.
    - Bóveda / Superadministrador: clave 'ADMIN2026'.
    """
    try:
        from models import PersonalAdministrativo
        
        # 1. Verificar e inyectar usuario administrativo por defecto
        admin = PersonalAdministrativo.query.filter_by(usuario='admin').first()
        if not admin:
            nuevo_admin = PersonalAdministrativo(
                nombres='Administrador',
                apellidos='General',
                ci='0000000',
                cargo='Superadministrador',
                usuario='admin',
                contrasena_hash=generate_password_hash('admin2026'),
                salario_base=0.0,
                adelanto_quincenal=0.0,
                activo=True
            )
            db.session.add(nuevo_admin)
            db.session.commit()
        else:
            if not admin.activo:
                admin.activo = True
                db.session.commit()

        # 2. Verificar e inyectar clave de Bóveda / Superadmin
        try:
            from models import SuperadminConfig
            config = SuperadminConfig.query.first()
            if not config:
                nuevo_config = SuperadminConfig(
                    clave_hash=generate_password_hash('ADMIN2026')
                )
                db.session.add(nuevo_config)
                db.session.commit()
        except Exception:
            pass

    except Exception as e:
        print(f"[ALERTA] Error al verificar credenciales: {e}")


def esperar_servidor_activo(puerto, tiempo_limite=15):
    """Verifica que el socket del servidor responda antes de intentar abrir el navegador."""
    tiempo_inicio = time.time()
    while time.time() - tiempo_inicio < tiempo_limite:
        try:
            with socket.create_connection(('127.0.0.1', puerto), timeout=0.5):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.15)
    return False


def maximizar_ventana_win32():
    """
    Busca la ventana lanzada en modo app y le aplica SW_MAXIMIZE exactamente
    una sola vez para llevarla al 100% de la pantalla sin interferir con Windows.
    """
    user32 = ctypes.windll.user32
    SW_MAXIMIZE = 3
    encontrada = [False]

    def enum_windows_callback(hwnd, extra):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            titulo = buff.value.lower()
            
            claves = ['asestud', 'colegio', '5000', 'gestión', 'gestion', 'cardex', 'unidad', 'sistema escolar']
            if any(k in titulo for k in claves):
                user32.ShowWindow(hwnd, SW_MAXIMIZE)
                user32.SetForegroundWindow(hwnd)
                encontrada[0] = True
                return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    cb = WNDENUMPROC(enum_windows_callback)

    # Reintenta durante unos segundos hasta que la ventana exista, la maximiza y finaliza
    for _ in range(20):
        time.sleep(0.3)
        user32.EnumWindows(cb, 0)
        if encontrada[0]:
            break


def abrir_navegador(url, puerto):
    """
    Espera a que Waitress esté escuchando y lanza la ventana en modo aplicación
    maximizada limpia.
    """
    esperar_servidor_activo(puerto)
    time.sleep(0.2)

    # Disparar hilo para maximizar la ventana en cuanto aparezca
    threading.Thread(target=maximizar_ventana_win32, daemon=True).start()

    flags_navegador = [
        f"--app={url}",
        "--start-maximized",
        "--disable-save-password-bubble",
        "--disable-features=PasswordManager,AutofillServerCommunication,PasswordGeneration,PasswordCheck",
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


def main():
    configurar_id_barra_tareas()
    port = get_port()

    ip_local = obtener_ip_local()
    url = f'http://{ip_local}:{port}/'

    app = create_app()

    with app.app_context():
        db.create_all()
        verificar_credenciales_defecto()

    print("=" * 70)
    print("ASestud - Gestión Escolar (Servidor Central)")
    print(f"Directorio de Operación: {BASE_SYSTEM_DIR}")
    print("=" * 70)
    print(f"Servidor iniciado y accesible en: {url}")
    print(f"Puerto activo: {port}")
    print("Presione Ctrl+C para detener el servidor.")
    print("=" * 70)

    # Iniciar la apertura del navegador en un hilo independiente
    threading.Thread(
        target=abrir_navegador,
        args=(url, port),
        daemon=True
    ).start()

    # Iniciar servidor de producción Waitress
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
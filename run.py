# -*- coding: utf-8 -*-
r"""
==============================================================================
Archivo: D:\colegio_vaca_diez\run.py
Proyecto: ASestud-Konetz
Descripción:
    Punto de entrada para ejecución en producción local.
    Usa Waitress como servidor WSGI y abre automáticamente el navegador.
==============================================================================
"""

import os
import sys
import time
import threading
import webbrowser

from app import create_app
from models import db


def get_port():
    try:
        return int(os.environ.get('PORT', '5000'))
    except Exception:
        return 5000


def abrir_navegador(url):
    """
    Abre el navegador después de unos segundos para dar tiempo
    a que el servidor inicie.
    """
    time.sleep(1.5)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    port = get_port()
    url = f'http://127.0.0.1:{port}/'

    app = create_app()

    # Crear tablas si no existen
    with app.app_context():
        db.create_all()

    print("=" * 70)
    print("ASestud-Konetz - Sistema de Gestión Escolar")
    print("=" * 70)
    print(f"Servidor iniciado en: {url}")
    print("Presione Ctrl+C para detener el servidor.")
    print("=" * 70)

    # Abrir navegador automáticamente
    threading.Thread(
        target=abrir_navegador,
        args=(url,),
        daemon=True
    ).start()

    try:
        from waitress import serve
        serve(
            app,
            host='127.0.0.1',
            port=port,
            threads=10
        )
    except KeyboardInterrupt:
        print("\n✅ Sistema detenido correctamente.")
    except ImportError:
        print("⚠️ Waitress no instalado. Ejecutando con servidor Flask simple.")
        app.run(
            host='127.0.0.1',
            port=port,
            debug=False
        )


if __name__ == '__main__':
    main()
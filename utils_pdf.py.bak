# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: utils_pdf.py
Proyecto: Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Utilidades para la generación de reportes y membretes en PDF.
==============================================================================
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Flowable


def obtener_datos_institucion():
    """Obtiene el nombre, subtítulo y logo configurados en la base de datos."""
    nombre = "SISTEMA DE GESTIÓN ESCOLAR"
    subtitulo = "MÓDULO ACADÉMICO INSTITUCIONAL"
    logo_filename = "logo_institucion.png"

    try:
        from models import ConfiguracionInstitucion
        cfg = ConfiguracionInstitucion.query.first()
        if cfg:
            if cfg.institucion_linea1 and cfg.institucion_linea1.strip():
                nombre = cfg.institucion_linea1.strip().upper()
            if cfg.institucion_linea2 and cfg.institucion_linea2.strip():
                subtitulo = cfg.institucion_linea2.strip().upper()
            if cfg.institucion_logo and cfg.institucion_logo.strip():
                logo_filename = cfg.institucion_logo.strip()
    except Exception:
        pass

    return nombre, subtitulo, logo_filename


class _InstitucionStr(str):
    """
    Objeto dinámico compatible con cadenas: cuando se evalúa o se llama
    como función, consulta el nombre real de la institución en la BD.
    """
    def __call__(self):
        nombre, _, _ = obtener_datos_institucion()
        return nombre

    def __str__(self):
        nombre, _, _ = obtener_datos_institucion()
        return nombre

    def __repr__(self):
        return self.__str__()


nombre_institucion = _InstitucionStr("SISTEMA DE GESTIÓN ESCOLAR")


def ruta_logo():
    """Retorna la ruta física del logotipo institucional si existe en disco."""
    _, _, logo_filename = obtener_datos_institucion()

    posibles_rutas = [
        os.path.join("uploads", logo_filename),
        os.path.join("static", "uploads", logo_filename),
        os.path.join("static", "images", logo_filename),
        os.path.join("static", "images", "logo.png"),
        os.path.join("static", "img", "logo.png")
    ]

    for p in posibles_rutas:
        if os.path.exists(p):
            return p
    return None


class CabeceraFlowable(Flowable):
    """
    Clase adaptadora para que ReportLab (Platypus) pueda procesar la cabecera
    cuando se inserta directamente en una lista de elementos (Story).
    """
    def __init__(self):
        Flowable.__init__(self)
        self.width = 0
        self.height = 30

    def draw(self):
        nombre, subtitulo, _ = obtener_datos_institucion()
        self.canv.saveState()
        self.canv.setFont("Helvetica-Bold", 10)
        self.canv.drawString(54, 750, nombre)
        self.canv.setFont("Helvetica", 8)
        self.canv.drawString(54, 738, subtitulo)
        self.canv.setStrokeColorRGB(0.2, 0.4, 0.6)
        self.canv.setLineWidth(1)
        self.canv.line(54, 730, 558, 730)
        self.canv.restoreState()


def cabecera_logo(canvas_obj=None, doc=None, *args, **kwargs):
    """
    Dibuja una cabecera institucional estándar para los reportes PDF.
    Retorna un Flowable si se llama sin argumentos (para Platypus).
    """
    if canvas_obj is None:
        return CabeceraFlowable()

    nombre, subtitulo, _ = obtener_datos_institucion()
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawString(54, 750, nombre)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(54, 738, subtitulo)
    canvas_obj.setStrokeColorRGB(0.2, 0.4, 0.6)
    canvas_obj.setLineWidth(1)
    canvas_obj.line(54, 730, 558, 730)
    canvas_obj.restoreState()

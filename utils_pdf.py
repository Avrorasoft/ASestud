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

class _InstitucionStr(str):
    def __call__(self):
        return "COLEGIO DR. ANTONIO VACA DÍEZ"

# Al heredar de str, la inicializamos con el texto real para que no imprima un vacío
nombre_institucion = _InstitucionStr("COLEGIO DR. ANTONIO VACA DÍEZ")

def ruta_logo():
    """Retorna la ruta del logotipo institucional si existe."""
    logo_path = os.path.join("static", "images", "logo.png")
    if os.path.exists(logo_path):
        return logo_path
    return None

class CabeceraFlowable(Flowable):
    """
    Clase adaptadora para que ReportLab (Platypus) pueda procesar la cabecera
    cuando se inserta directamente en una lista de elementos (Story).
    """
    def __init__(self):
        Flowable.__init__(self)
        self.width = 0
        self.height = 30  # Espacio que ocupa la cabecera en el flujo normal

    def draw(self):
        # self.canv es el lienzo que Platypus inyecta automáticamente al momento de dibujar
        self.canv.saveState()
        self.canv.setFont("Helvetica-Bold", 10)
        self.canv.drawString(54, 750, str(nombre_institucion))
        self.canv.setFont("Helvetica", 8)
        self.canv.drawString(54, 738, "UNIDAD EDUCATIVA")
        self.canv.setStrokeColorRGB(0.2, 0.4, 0.6)
        self.canv.setLineWidth(1)
        self.canv.line(54, 730, 558, 730)
        self.canv.restoreState()

def cabecera_logo(canvas_obj=None, doc=None, *args, **kwargs):
    """
    Dibuja una cabecera institucional estándar para los reportes PDF.
    Retorna un Flowable si se llama sin argumentos (para Platypus).
    """
    # Si se invoca sin el lienzo (como ocurre en la lista elements del recibo), 
    # devolvemos el objeto Flowable para que ReportLab no colapse.
    if canvas_obj is None:
        return CabeceraFlowable()

    # Comportamiento clásico por si se llama directamente pasando el canvas
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawString(54, 750, str(nombre_institucion))
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(54, 738, "UNIDAD EDUCATIVA")
    canvas_obj.setStrokeColorRGB(0.2, 0.4, 0.6)
    canvas_obj.setLineWidth(1)
    canvas_obj.line(54, 730, 558, 730)
    canvas_obj.restoreState()
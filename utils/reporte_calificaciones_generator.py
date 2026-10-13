# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: utils/reporte_calificaciones_generator.py
Proyecto: Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Generador oficial del reporte/boletín individual por materia:
             - Formato vertical compacto (Letter Portrait, 1 página).
             - Estructura horizontal: 3 filas continuas (1er, 2do y 3er Trimestre).
             - Promedio dinámico: división estricta entre trimestres calificados (1, 2 o 3).
             - Nombre institucional 100% dinámico y genérico (sin nombres quemados).
             - 100% Autónomo: funciones institucionales integradas sin dependencias externas.
             - Código QR y pie de firmas institucional.
==============================================================================
"""

import os
import io
import tempfile
from datetime import datetime, timezone, timedelta
from flask import current_app
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import qrcode
from utils_pdf import ruta_logo, obtener_datos_institucion

BOLIVIA_TZ = timezone(timedelta(hours=-4))

def nombre_institucion():
    nom, _, _ = obtener_datos_institucion()
    return nom

def linea_secundaria_institucion():
    _, sub, _ = obtener_datos_institucion()
    return sub

# =============================================================================
# GENERADOR PRINCIPAL DEL REPORTE
# =============================================================================

def generar_detalle_calificaciones_pdf(estudiante, calificaciones, materias=None, cloudinary_url=None):
    """
    Genera el PDF del reporte individual por materia o detalle de calificaciones
    en formato vertical (Letter Portrait) con 3 filas horizontales por trimestre.
    """
    buffer = io.BytesIO()
    c_canvas = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Datos básicos del estudiante
    if isinstance(estudiante, dict):
        nombre_est = estudiante.get('nombre_completo') or f"{estudiante.get('nombres', '')} {estudiante.get('apellidos', '')}".strip() or "Estudiante"
        curso_est = estudiante.get('curso', 'Secundaria')
        rude_est = estudiante.get('rude', '-')
        turno_est = estudiante.get('turno', 'Regular')
        ci_est = estudiante.get('ci', '-')
    else:
        nombre_est = getattr(estudiante, 'nombre_completo', None) or f"{getattr(estudiante, 'nombres', '')} {getattr(estudiante, 'apellidos', '')}".strip() or "Estudiante"
        curso_est = getattr(estudiante, 'curso', getattr(estudiante, 'nivel', 'Secundaria'))
        rude_est = getattr(estudiante, 'rude', '-')
        turno_est = getattr(estudiante, 'turno', 'Regular')
        ci_est = getattr(estudiante, 'ci', '-')

    # Fondo blanco base
    c_canvas.setFillColor(colors.white)
    c_canvas.rect(0, 0, width, height, fill=1, stroke=0)

    # Logo institucional opcional
    logo_path = ruta_logo()
    if logo_path and os.path.exists(logo_path):
        try:
            c_canvas.drawImage(logo_path, 24, height - 56, width=44, height=44, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Encabezado institucional dinámico (sin textos quemados)
    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.setFont("Helvetica-Bold", 12.5)
    c_canvas.drawString(74, height - 26, nombre_institucion().upper())

    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#4A5568'))
    c_canvas.drawString(74, height - 37, linea_secundaria_institucion().upper())

    c_canvas.setFont("Helvetica-Bold", 10.5)
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.drawRightString(width - 24, height - 26, "REPORTE INDIVIDUAL DE MATERIA")

    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    ahora = datetime.now(BOLIVIA_TZ)
    fecha_txt = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#718096'))
    c_canvas.drawRightString(width - 24, height - 37, f"Gestión {ahora.year} • Emisión: {fecha_txt}")

    # Ficha del estudiante compacta
    c_canvas.setFillColor(colors.HexColor('#F8FAFC'))
    c_canvas.setStrokeColor(colors.HexColor('#CBD5E1'))
    c_canvas.roundRect(24, height - 88, width - 48, 27, 3, fill=1, stroke=1)

    c_canvas.setFont("Helvetica-Bold", 8)
    c_canvas.setFillColor(colors.HexColor('#1E293B'))
    c_canvas.drawString(32, height - 73, f"Estudiante: {nombre_est.upper()}")
    c_canvas.drawString(250, height - 73, f"Curso: {curso_est}")
    c_canvas.drawString(430, height - 73, f"C.I.: {ci_est}")

    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#475569'))
    c_canvas.drawString(32, height - 84, f"Código RUDE: {rude_est}")
    c_canvas.drawString(250, height - 84, f"Turno: {turno_est}")

    # Agrupar calificaciones por materia y trimestre
    materias_dict = {}

    for cal in calificaciones:
        m_nom = None
        if hasattr(cal, 'materia') and cal.materia:
            m_nom = cal.materia.nombre.strip()
        elif materias:
            m_obj = next((m for m in materias if str(m.id) == str(getattr(cal, 'materia_id', ''))), None)
            if m_obj:
                m_nom = m_obj.nombre.strip()

        if not m_nom:
            m_nom = "Materia General"

        if m_nom not in materias_dict:
            materias_dict[m_nom] = {1: [], 2: [], 3: []}

        periodo_txt = str(getattr(cal, 'periodo', '') or '').lower().strip()
        raw_tri = getattr(cal, 'trimestre', None)

        tri = None
        if raw_tri in [1, '1'] or '1' in periodo_txt or 'primer' in periodo_txt or '1er' in periodo_txt:
            tri = 1
        elif raw_tri in [2, '2'] or '2' in periodo_txt or 'segundo' in periodo_txt or '2do' in periodo_txt:
            tri = 2
        elif raw_tri in [3, '3'] or '3' in periodo_txt or 'tercer' in periodo_txt or '3er' in periodo_txt:
            tri = 3

        if tri in [1, 2, 3]:
            materias_dict[m_nom][tri].append(cal)

    # Estilos tipográficos
    styles = getSampleStyleSheet()
    th_style = ParagraphStyle('THDet', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.white, alignment=1)
    td_mat = ParagraphStyle('TDMatDet', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'), alignment=0)
    td_tri = ParagraphStyle('TDTriDet', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.HexColor('#1E4E79'), alignment=0)
    td_eval = ParagraphStyle('TDEvalDet', fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#334155'))
    td_nota = ParagraphStyle('TDNotaDet', fontName='Helvetica-Bold', fontSize=9, leading=10.5, alignment=1)
    td_prom = ParagraphStyle('TDPromDet', fontName='Helvetica-Bold', fontSize=9.5, leading=11, alignment=1)

    # Encabezado con salto de línea explícito en PROMEDIO ACUMULADO
    filas_tabla = [[
        Paragraph("MATERIA", th_style),
        Paragraph("TRIMESTRE", th_style),
        Paragraph("EVALUACIONES Y CRITERIOS", th_style),
        Paragraph("NOTA FINAL", th_style),
        Paragraph("PROMEDIO<br/>ACUMULADO", th_style)
    ]]

    suma_anuales = 0.0
    total_materias_prom = 0
    lineas_estilo_tabla = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E4E79')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]

    fila_idx = 1
    nombres_trim = {1: "1° Trimestre", 2: "2° Trimestre", 3: "3° Trimestre"}

    for mat_nom in sorted(materias_dict.keys()):
        tri_data = materias_dict[mat_nom]
        notas_trimestres_calificados = []
        filas_materia = []

        for tri in [1, 2, 3]:
            lista_cals = tri_data[tri]
            nota_final_tri = None
            evals_txt = []

            for c in lista_cals:
                tipo_c = str(getattr(c, 'tipo', '') or '').strip()
                val_c = getattr(c, 'nota', None)
                if val_c is not None:
                    try:
                        val_num = float(val_c)
                        if any(k in tipo_c.lower() for k in ['final', 'promedio']):
                            nota_final_tri = val_num
                        else:
                            evals_txt.append(f"{tipo_c}: <font size='9.5' color='#0F2942'><b>{val_num:.0f}</b></font>")
                    except (ValueError, TypeError):
                        pass

            if nota_final_tri is None and evals_txt:
                notas_numericas = []
                for c in lista_cals:
                    try:
                        if c.nota is not None:
                            notas_numericas.append(float(c.nota))
                    except (ValueError, TypeError):
                        pass
                if notas_numericas:
                    s = sum(notas_numericas)
                    nota_final_tri = s if (len(notas_numericas) > 1 and s <= 100) else (s / len(notas_numericas))

            # Solo registrar si realmente existe nota válida
            if nota_final_tri is not None and nota_final_tri > 0:
                notas_trimestres_calificados.append(nota_final_tri)
                c_hex_nota = "#166534" if nota_final_tri >= 51 else "#991B1B"
                p_nota = Paragraph(f"<font color='{c_hex_nota}'><b>{nota_final_tri:.1f}</b></font>", td_nota)
            elif nota_final_tri == 0 and len(evals_txt) > 0:
                notas_trimestres_calificados.append(0.0)
                p_nota = Paragraph("<font color='#991B1B'><b>0.0</b></font>", td_nota)
            else:
                p_nota = Paragraph("-", td_nota)

            texto_evaluaciones = " &nbsp;&bull;&nbsp; ".join(evals_txt) if evals_txt else "Sin evaluaciones"
            p_eval = Paragraph(texto_evaluaciones, td_eval)
            p_tri = Paragraph(nombres_trim[tri], td_tri)

            filas_materia.append((p_tri, p_eval, p_nota))

        # CÁLCULO DINÁMICO: Dividir únicamente entre los trimestres con nota
        cant_calificados = len(notas_trimestres_calificados)
        if cant_calificados > 0:
            prom_materia = sum(notas_trimestres_calificados) / cant_calificados
            suma_anuales += prom_materia
            total_materias_prom += 1
            c_hex_prom = "#166534" if prom_materia >= 51 else "#991B1B"
            txt_prom = f"<font color='{c_hex_prom}'><b>{prom_materia:.1f}</b></font><br/><font size='5.5' color='#64748B'>({cant_calificados} trim. eval.)</font>"
            p_prom = Paragraph(txt_prom, td_prom)
        else:
            p_prom = Paragraph("-", td_prom)

        # 3 filas horizontales por materia
        for i, (p_tri, p_eval, p_nota) in enumerate(filas_materia):
            if i == 0:
                filas_tabla.append([
                    Paragraph(mat_nom, td_mat),
                    p_tri,
                    p_eval,
                    p_nota,
                    p_prom
                ])
            else:
                filas_tabla.append([
                    "",
                    p_tri,
                    p_eval,
                    p_nota,
                    ""
                ])

        # Fusión vertical para la materia y su promedio
        lineas_estilo_tabla.append(('SPAN', (0, fila_idx), (0, fila_idx + 2)))
        lineas_estilo_tabla.append(('SPAN', (4, fila_idx), (4, fila_idx + 2)))
        lineas_estilo_tabla.append(('BACKGROUND', (0, fila_idx), (0, fila_idx + 2), colors.HexColor('#F8FAFC')))
        lineas_estilo_tabla.append(('BACKGROUND', (4, fila_idx), (4, fila_idx + 2), colors.HexColor('#F8FAFC')))
        lineas_estilo_tabla.append(('LINEBELOW', (0, fila_idx + 2), (-1, fila_idx + 2), 0.8, colors.HexColor('#0F2942')))

        fila_idx += 3

    # Anchos equilibrados para Letter Portrait vertical
    col_w = [118, 68, 240, 62, 76]
    t = Table(filas_tabla, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(lineas_estilo_tabla))

    w_tab, h_tab = t.wrap(width - 48, height)
    pos_y = max(64, height - 98 - h_tab)
    t.drawOn(c_canvas, 24, pos_y)

    # Pie y código QR
    inst_nombre = nombre_institucion().upper()
    qr_text = cloudinary_url if cloudinary_url else f"{inst_nombre} | EST: {nombre_est} | RUDE: {rude_est} | CURSO: {curso_est}"
    qr = qrcode.QRCode(version=1, box_size=2, border=1)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_qr:
        img_qr.save(tmp_qr.name)
        tmp_qr_path = tmp_qr.name

    try:
        c_canvas.drawImage(tmp_qr_path, width - 68, 12, width=44, height=44)
    except Exception:
        pass
    finally:
        if os.path.exists(tmp_qr_path):
            os.unlink(tmp_qr_path)

    # Líneas de firmas
    c_canvas.setStrokeColor(colors.HexColor('#94A3B8'))
    c_canvas.setLineWidth(0.6)
    
    c_canvas.line(36, 36, 170, 36)
    c_canvas.setFont("Helvetica", 6.5)
    c_canvas.setFillColor(colors.HexColor('#334155'))
    c_canvas.drawCentredString(103, 27, "Dirección Académica")

    c_canvas.line(210, 36, 344, 36)
    c_canvas.drawCentredString(277, 27, "Profesor(a) de Asignatura")

    c_canvas.line(384, 36, 498, 36)
    c_canvas.drawCentredString(441, 27, "Firma Padre / Tutor")

    c_canvas.setFont("Helvetica", 6)
    c_canvas.setFillColor(colors.HexColor('#64748B'))
    c_canvas.drawString(24, 12, f"Documento oficial emitido por el Sistema Académico - {inst_nombre} • Verificable mediante código QR.")

    c_canvas.save()
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
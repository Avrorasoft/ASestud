# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: utils/boletin_generator.py
Proyecto: Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Generador oficial de Boletines en PDF:
             - Formato vertical compacto (Letter Portrait, 1 página garantizada).
             - Estructura horizontal: 3 filas por materia (1er, 2do y 3er Trimestre).
             - Encabezado corregido: 'PROMEDIO<br/>ACUMULADO' completo sin particiones.
             - Números de evaluaciones/criterios destacados.
             - Promedio dinámico: división estricta entre trimestres calificados (1, 2 o 3).
             - 100% Autónomo: funciones institucionales dinámicas integradas.
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

BOLIVIA_TZ = timezone(timedelta(hours=-4))

# =============================================================================
# FUNCIONES DINÁMICAS INSTITUCIONALES (INTEGRADAS DIRECTAMENTE)
# =============================================================================

def ruta_logo():
    """Busca y devuelve la ruta del logo institucional si existe físicamente."""
    try:
        base_dir = current_app.root_path if current_app else os.getcwd()
        posibles = [
            os.path.join(base_dir, 'static', 'img', 'logo.png'),
            os.path.join(base_dir, 'static', 'uploads', 'logo.png'),
            os.path.join(base_dir, 'uploads', 'logo.png'),
            os.path.join(base_dir, 'static', 'logo.png')
        ]
        for p in posibles:
            if os.path.exists(p):
                return p
    except Exception:
        pass
    return None

def nombre_institucion():
    """
    Obtiene el nombre de la institución dinámicamente de variables o base de datos.
    Si no existe ninguna configuración, utiliza un nombre genérico.
    """
    try:
        if current_app:
            nom_cfg = current_app.config.get('NOMBRE_INSTITUCION') or current_app.config.get('INSTITUCION_NOMBRE')
            if nom_cfg and str(nom_cfg).strip():
                return str(nom_cfg).strip()

        from models import db
        try:
            from models import Configuracion
            cfg = Configuracion.query.filter_by(clave='nombre_institucion').first()
            if cfg and cfg.valor and cfg.valor.strip():
                return cfg.valor.strip()
        except Exception:
            pass

        try:
            from models import Institucion
            inst = Institucion.query.first()
            if inst:
                nom = getattr(inst, 'nombre', None) or getattr(inst, 'institucion_linea1', None)
                if nom and str(nom).strip():
                    return str(nom).strip()
        except Exception:
            pass
    except Exception:
        pass

    return "UNIDAD EDUCATIVA"

def linea_secundaria_institucion():
    """Subtítulo genérico institucional."""
    try:
        if current_app:
            sub = current_app.config.get('INSTITUCION_SUBTITULO')
            if sub and str(sub).strip():
                return str(sub).strip()
    except Exception:
        pass
    return "SEGUIMIENTO ACADÉMICO INTEGRAL"

def guardar_boletin_localmente(pdf_bytes, est_id, anio_actual, est_rude):
    """Guarda físicamente el PDF generado reemplazando cualquier copia previa."""
    try:
        filename = f"boletin_{est_id}_{anio_actual}_{est_rude}.pdf"
        boletines_dir = os.path.join(os.getcwd(), 'static', 'boletines')
        os.makedirs(boletines_dir, exist_ok=True)
        filepath = os.path.join(boletines_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)
        return filename
    except Exception as e:
        print(f"Error al guardar boletin localmente: {e}")
        return None

# =============================================================================
# RENDERIZADOR: NIVEL INICIAL / CUALITATIVO
# =============================================================================

def _render_nidito(c_canvas, width, height, estudiante, calificaciones, materias, cloudinary_url):
    if isinstance(estudiante, dict):
        nombre_est = estudiante.get('nombre_completo') or f"{estudiante.get('nombres', '')} {estudiante.get('apellidos', '')}".strip() or "Estudiante"
        curso_est = estudiante.get('curso', 'Nidito')
        rude_est = estudiante.get('rude', '-')
        turno_est = estudiante.get('turno', 'Regular')
        ci_est = estudiante.get('ci', '-')
    else:
        nombre_est = getattr(estudiante, 'nombre_completo', None) or f"{getattr(estudiante, 'nombres', '')} {getattr(estudiante, 'apellidos', '')}".strip() or "Estudiante"
        curso_est = getattr(estudiante, 'curso', getattr(estudiante, 'nivel', 'Nidito'))
        rude_est = getattr(estudiante, 'rude', '-')
        turno_est = getattr(estudiante, 'turno', 'Regular')
        ci_est = getattr(estudiante, 'ci', '-')

    c_canvas.setFillColor(colors.white)
    c_canvas.rect(0, 0, width, height, fill=1, stroke=0)

    logo_path = ruta_logo()
    if logo_path and os.path.exists(logo_path):
        try:
            c_canvas.drawImage(logo_path, 24, height - 60, width=46, height=46, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.setFont("Helvetica-Bold", 13)
    c_canvas.drawString(76, height - 28, nombre_institucion().upper())

    c_canvas.setFont("Helvetica", 8)
    c_canvas.setFillColor(colors.HexColor('#4A5568'))
    c_canvas.drawString(76, height - 40, "EDUCACIÓN INICIAL EN FAMILIA COMUNITARIA - SEGUIMIENTO INTEGRAL")

    c_canvas.setFont("Helvetica-Bold", 10.5)
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.drawRightString(width - 24, height - 28, "INFORME CUALITATIVO DE APRENDIZAJE")

    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    ahora = datetime.now(BOLIVIA_TZ)
    fecha_txt = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#718096'))
    c_canvas.drawRightString(width - 24, height - 40, f"Gestión {ahora.year} • Emisión: {fecha_txt}")

    c_canvas.setFillColor(colors.HexColor('#F8FAFC'))
    c_canvas.setStrokeColor(colors.HexColor('#CBD5E1'))
    c_canvas.roundRect(24, height - 92, width - 48, 26, 3, fill=1, stroke=1)

    c_canvas.setFont("Helvetica-Bold", 8)
    c_canvas.setFillColor(colors.HexColor('#1E293B'))
    c_canvas.drawString(32, height - 76, f"Estudiante: {nombre_est.upper()}")
    c_canvas.drawString(280, height - 76, f"Nivel / Sala: {curso_est}")
    c_canvas.drawString(460, height - 76, f"C.I.: {ci_est}")

    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#475569'))
    c_canvas.drawString(32, height - 87, f"Código RUDE: {rude_est}")
    c_canvas.drawString(280, height - 87, f"Turno: {turno_est}")

    areas_registradas = {}
    informe_general = []

    AREAS_BASE = [
        "Desarrollo Psicomotriz",
        "Lenguaje y Comunicación",
        "Autonomía y Convivencia"
    ]

    for cal in calificaciones:
        nom = (getattr(cal, 'campo', None) or getattr(cal, 'area', None) or getattr(cal, 'materia_nombre', None) or "").strip()
        if not nom and hasattr(cal, 'materia') and cal.materia:
            nom = cal.materia.nombre.strip()
        elif not nom and materias:
            m_obj = next((m for m in materias if str(m.id) == str(getattr(cal, 'materia_id', ''))), None)
            if m_obj:
                nom = m_obj.nombre.strip()

        obs = getattr(cal, 'informe_descriptivo', None) or getattr(cal, 'observacion', None) or getattr(cal, 'informe', None)
        if obs and obs.strip() and obs.strip() not in informe_general:
            informe_general.append(obs.strip())

        val = (getattr(cal, 'valoracion_cualitativa', None) or getattr(cal, 'valoracion', None) or "").strip()

        for a_oficial in AREAS_BASE:
            palabras = [p.lower() for p in a_oficial.split() if len(p) > 3]
            if any(k in nom.lower() for k in palabras):
                areas_registradas[a_oficial] = val or "En Proceso"
                break
        else:
            if nom and not any(k in nom.lower() for k in ['nidito', 'inicial 1', 'kinder 1']):
                areas_registradas[nom] = val or "En Proceso"

    valores_defecto = {
        "Desarrollo Psicomotriz": "En Proceso",
        "Lenguaje y Comunicación": "Logrado",
        "Autonomía y Convivencia": "En Proceso"
    }
    for a, v in valores_defecto.items():
        if a not in areas_registradas:
            areas_registradas[a] = v

    styles = getSampleStyleSheet()
    th_style = ParagraphStyle('THN', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=1)
    td_area = ParagraphStyle('TDAN', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'))
    td_val = ParagraphStyle('TDVN', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=1)

    filas_tabla = [[
        Paragraph("ÁREA DE EVALUACIÓN Y DESARROLLO", th_style),
        Paragraph("VALORACIÓN CUALITATIVA", th_style)
    ]]

    for area, val in areas_registradas.items():
        val_clean = val.strip().title()
        if "Logrado" in val_clean:
            c_hex = "#166534"
        elif "Proceso" in val_clean:
            c_hex = "#1E40AF"
        else:
            c_hex = "#B45309"
        td_val_c = ParagraphStyle('TDVC', parent=td_val, textColor=colors.HexColor(c_hex))
        filas_tabla.append([
            Paragraph(area, td_area),
            Paragraph(f"<b>{val_clean}</b>", td_val_c)
        ])

    col_w = [364, 200]
    t = Table(filas_tabla, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E4E79')),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    w_tab, h_tab = t.wrap(width - 48, height)
    pos_y_tab = height - 104 - h_tab
    t.drawOn(c_canvas, 24, pos_y_tab)

    pos_y_inf = pos_y_tab - 14
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.setFont("Helvetica-Bold", 8.5)
    c_canvas.drawString(24, pos_y_inf, "INFORME PEDAGÓGICO Y RECOMENDACIONES:")

    cuadro_alto = 55
    pos_y_box = pos_y_inf - 8 - cuadro_alto
    c_canvas.setFillColor(colors.HexColor('#F8FAFC'))
    c_canvas.setStrokeColor(colors.HexColor('#CBD5E1'))
    c_canvas.roundRect(24, pos_y_box, width - 48, cuadro_alto, 3, fill=1, stroke=1)

    txt_inf = " ".join(informe_general) if informe_general else "Se desarrolla favorablemente."
    p_inf_style = ParagraphStyle('PINF', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#1E293B'))
    p_inf = Paragraph(f"• {txt_inf}", p_inf_style)
    w_i, h_i = p_inf.wrap(width - 64, cuadro_alto - 12)
    p_inf.drawOn(c_canvas, 32, pos_y_box + cuadro_alto - 8 - h_i)

    _dibujar_qr_y_pie(c_canvas, width, nombre_est, rude_est, curso_est, cloudinary_url, cualitativo=True)

# =============================================================================
# RENDERIZADOR: REGULAR / 1 PÁGINA VERTICAL COMPACTA
# =============================================================================

def _render_regular(c_canvas, width, height, estudiante, calificaciones, materias, cloudinary_url):
    """Renderiza el boletín oficial en formato vertical con números destacados."""
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

    c_canvas.setFillColor(colors.white)
    c_canvas.rect(0, 0, width, height, fill=1, stroke=0)

    # Logo opcional
    logo_path = ruta_logo()
    if logo_path and os.path.exists(logo_path):
        try:
            c_canvas.drawImage(logo_path, 24, height - 56, width=44, height=44, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Encabezado institucional dinámico
    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.setFont("Helvetica-Bold", 12.5)
    c_canvas.drawString(74, height - 26, nombre_institucion().upper())

    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#4A5568'))
    c_canvas.drawString(74, height - 37, linea_secundaria_institucion().upper())

    c_canvas.setFont("Helvetica-Bold", 10.5)
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.drawRightString(width - 24, height - 26, "BOLETÍN DE CALIFICACIONES")

    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    ahora = datetime.now(BOLIVIA_TZ)
    fecha_txt = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#718096'))
    c_canvas.drawRightString(width - 24, height - 37, f"Gestión {ahora.year} • Emisión: {fecha_txt}")

    # Datos del estudiante compactos
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

    # Estructura horizontal: agrupación por materia y trimestre
    materias_dict = {}

    for cal in calificaciones:
        m_nom = None
        if hasattr(cal, 'materia') and cal.materia:
            m_nom = cal.materia.nombre.strip()
        elif materias:
            m_obj = next((m for m in materias if str(m.id) == str(getattr(cal, 'materia_id', ''))), None)
            if m_obj:
                m_nom = m_obj.nombre.strip()

        if not m_nom or any(term in m_nom.lower() for term in ['nidito', 'inicial', 'kinder']):
            continue

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

    styles = getSampleStyleSheet()
    th_style = ParagraphStyle('THV', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.white, alignment=1)
    
    td_mat = ParagraphStyle('TDMatV', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'), alignment=0)
    td_tri = ParagraphStyle('TDTriV', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.HexColor('#1E4E79'), alignment=0)
    td_eval = ParagraphStyle('TDEvalV', fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#334155'))
    td_nota = ParagraphStyle('TDNotaV', fontName='Helvetica-Bold', fontSize=9, leading=10.5, alignment=1)
    td_prom = ParagraphStyle('TDPromV', fontName='Helvetica-Bold', fontSize=9.5, leading=11, alignment=1)

    # ENCABEZADO CON SALTO LIMPIO ENTRE PROMEDIO Y ACUMULADO
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

        # DIVISIÓN ESTRICTA: suma dividida solo entre trimestres calificados
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

        lineas_estilo_tabla.append(('SPAN', (0, fila_idx), (0, fila_idx + 2)))
        lineas_estilo_tabla.append(('SPAN', (4, fila_idx), (4, fila_idx + 2)))
        lineas_estilo_tabla.append(('BACKGROUND', (0, fila_idx), (0, fila_idx + 2), colors.HexColor('#F8FAFC')))
        lineas_estilo_tabla.append(('BACKGROUND', (4, fila_idx), (4, fila_idx + 2), colors.HexColor('#F8FAFC')))
        lineas_estilo_tabla.append(('LINEBELOW', (0, fila_idx + 2), (-1, fila_idx + 2), 0.8, colors.HexColor('#0F2942')))

        fila_idx += 3

    prom_inst = (suma_anuales / total_materias_prom) if total_materias_prom > 0 else 0.0
    c_canvas.setFont("Helvetica-Bold", 8)
    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.drawString(430, height - 84, f"Prom. General: {prom_inst:.1f}")

    # Columnas recalculadas: ancho suficiente (76 pt) para 'PROMEDIO' y 'ACUMULADO' completos
    col_w = [118, 68, 240, 62, 76]
    t = Table(filas_tabla, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle(lineas_estilo_tabla))

    w_tab, h_tab = t.wrap(width - 48, height)
    pos_y = max(64, height - 98 - h_tab)
    t.drawOn(c_canvas, 24, pos_y)

    _dibujar_qr_y_pie(c_canvas, width, nombre_est, rude_est, curso_est, cloudinary_url, cualitativo=False)

def _dibujar_qr_y_pie(c_canvas, width, nombre_est, rude_est, curso_est, cloudinary_url, cualitativo=False):
    """Pie institucional genérico y código QR."""
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
    c_canvas.drawCentredString(277, 27, "Profesor(a) / Asesor(a)")

    c_canvas.line(384, 36, 498, 36)
    c_canvas.drawCentredString(441, 27, "Firma Padre / Tutor")

    # Pie informativo genérico
    c_canvas.setFont("Helvetica", 6)
    c_canvas.setFillColor(colors.HexColor('#64748B'))
    if cualitativo:
        c_canvas.drawString(24, 12, f"Documento oficial de valoración pedagógica - {inst_nombre}")
    else:
        c_canvas.drawString(24, 12, f"Documento oficial emitido por el Sistema Académico - {inst_nombre} • Verificable mediante código QR.")

def generar_boletin_pdf(estudiante, calificaciones, materias, cloudinary_url=None):
    """Punto de entrada: genera el PDF en formato vertical (Letter Portrait)."""
    curso_str = ""
    if estudiante:
        if isinstance(estudiante, dict):
            curso_str = str(estudiante.get('curso', '') or estudiante.get('nivel', '')).lower().strip()
        else:
            curso_str = str(getattr(estudiante, 'curso', '') or getattr(estudiante, 'nivel', '')).lower().strip()

    es_nidito = any(k in curso_str for k in ['nidito', 'inicial', 'kinder', 'pre-kinder', 'prekinder', 'parvulario'])

    if es_nidito:
        try:
            from utils.boletin_nidito_generator import generar_boletin_nidito_pdf
        except ImportError:
            from boletin_nidito_generator import generar_boletin_nidito_pdf
        return generar_boletin_nidito_pdf(estudiante, calificaciones, materias, cloudinary_url)

    buffer = io.BytesIO()
    c_canvas = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    _render_regular(c_canvas, width, height, estudiante, calificaciones, materias, cloudinary_url)

    c_canvas.save()
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
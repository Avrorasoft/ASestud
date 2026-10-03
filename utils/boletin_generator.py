# -*- coding: utf-8 -*-
import os
import io
import tempfile
from datetime import datetime, timezone, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import qrcode
from utils_pdf import ruta_logo, nombre_institucion

BOLIVIA_TZ = timezone(timedelta(hours=-4))

def guardar_boletin_localmente(pdf_bytes, est_id, anio_actual, est_rude):
    try:
        # Ahora utiliza el RUDE y el orden exacto que envía chat.py
        filename = f"boletin_{est_id}_{anio_actual}_{est_rude}.pdf"
        boletines_dir = os.path.join(os.getcwd(), 'static', 'boletines')
        os.makedirs(boletines_dir, exist_ok=True)
        filepath = os.path.join(boletines_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)
        return filename
    except Exception as e:
        print(f"Error al guardar boletin: {e}")
        return None

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
            c_canvas.drawImage(logo_path, 36, height - 76, width=62, height=62, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.setFont("Helvetica-Bold", 16)
    c_canvas.drawString(108, height - 36, nombre_institucion().upper())

    c_canvas.setFont("Helvetica", 9)
    c_canvas.setFillColor(colors.HexColor('#4A5568'))
    c_canvas.drawString(108, height - 50, "EDUCACIÓN INICIAL EN FAMILIA COMUNITARIA - SEGUIMIENTO INTEGRAL")

    c_canvas.setFont("Helvetica-Bold", 13)
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.drawRightString(width - 36, height - 36, "INFORME CUALITATIVO DE APRENDIZAJE")

    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    ahora = datetime.now(BOLIVIA_TZ)
    fecha_txt = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
    c_canvas.setFont("Helvetica", 9)
    c_canvas.setFillColor(colors.HexColor('#718096'))
    c_canvas.drawRightString(width - 36, height - 50, f"Gestión {ahora.year} • Emisión: {fecha_txt}")

    c_canvas.setFillColor(colors.HexColor('#F8FAFC'))
    c_canvas.setStrokeColor(colors.HexColor('#CBD5E1'))
    c_canvas.roundRect(36, height - 118, width - 72, 36, 4, fill=1, stroke=1)

    c_canvas.setFont("Helvetica-Bold", 9)
    c_canvas.setFillColor(colors.HexColor('#1E293B'))
    c_canvas.drawString(48, height - 96, f"Estudiante: {nombre_est.upper()}")
    c_canvas.drawString(340, height - 96, f"Nivel / Sala: {curso_est}")
    c_canvas.drawString(570, height - 96, f"C.I.: {ci_est}")

    c_canvas.setFont("Helvetica", 9)
    c_canvas.setFillColor(colors.HexColor('#475569'))
    c_canvas.drawString(48, height - 110, f"Código RUDE: {rude_est}")
    c_canvas.drawString(340, height - 110, f"Turno: {turno_est}")

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
    th_style = ParagraphStyle('THN', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white, alignment=1)
    td_area = ParagraphStyle('TDAN', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#0F172A'))
    td_val = ParagraphStyle('TDVN', fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=1)

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

    col_w = [470, 250]
    t = Table(filas_tabla, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E4E79')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    w_tab, h_tab = t.wrap(width - 72, height)
    pos_y_tab = height - 132 - h_tab
    t.drawOn(c_canvas, 36, pos_y_tab)

    pos_y_inf = pos_y_tab - 18
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.setFont("Helvetica-Bold", 10)
    c_canvas.drawString(36, pos_y_inf, "INFORME PEDAGÓGICO Y RECOMENDACIONES:")

    cuadro_alto = 70
    pos_y_box = pos_y_inf - 10 - cuadro_alto
    c_canvas.setFillColor(colors.HexColor('#F8FAFC'))
    c_canvas.setStrokeColor(colors.HexColor('#CBD5E1'))
    c_canvas.roundRect(36, pos_y_box, width - 72, cuadro_alto, 4, fill=1, stroke=1)

    txt_inf = " ".join(informe_general) if informe_general else "Se desarrolla muy bien."
    p_inf_style = ParagraphStyle('PINF', fontName='Helvetica', fontSize=9.5, leading=14, textColor=colors.HexColor('#1E293B'))
    p_inf = Paragraph(f"• {txt_inf}", p_inf_style)
    w_i, h_i = p_inf.wrap(width - 96, cuadro_alto - 16)
    p_inf.drawOn(c_canvas, 48, pos_y_box + cuadro_alto - 12 - h_i)

    _dibujar_qr_y_pie(c_canvas, width, nombre_est, rude_est, curso_est, cloudinary_url, cualitativo=True)

def _render_regular(c_canvas, width, height, estudiante, calificaciones, materias, cloudinary_url):
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

    logo_path = ruta_logo()
    if logo_path and os.path.exists(logo_path):
        try:
            c_canvas.drawImage(logo_path, 36, height - 76, width=62, height=62, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.setFont("Helvetica-Bold", 16)
    c_canvas.drawString(108, height - 36, nombre_institucion().upper())

    c_canvas.setFont("Helvetica", 9)
    c_canvas.setFillColor(colors.HexColor('#4A5568'))
    c_canvas.drawString(108, height - 50, "COLEGIO PARTICULAR - EXCELENCIA ACADÉMICA Y FORMACIÓN INTEGRAL")

    c_canvas.setFont("Helvetica-Bold", 13)
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.drawRightString(width - 36, height - 36, "BOLETÍN OFICIAL DE CALIFICACIONES")

    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    ahora = datetime.now(BOLIVIA_TZ)
    fecha_txt = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
    c_canvas.setFont("Helvetica", 9)
    c_canvas.setFillColor(colors.HexColor('#718096'))
    c_canvas.drawRightString(width - 36, height - 50, f"Gestión {ahora.year} • Emisión: {fecha_txt}")

    c_canvas.setFillColor(colors.HexColor('#F8FAFC'))
    c_canvas.setStrokeColor(colors.HexColor('#CBD5E1'))
    c_canvas.roundRect(36, height - 118, width - 72, 36, 4, fill=1, stroke=1)

    c_canvas.setFont("Helvetica-Bold", 9)
    c_canvas.setFillColor(colors.HexColor('#1E293B'))
    c_canvas.drawString(48, height - 96, f"Estudiante: {nombre_est.upper()}")
    c_canvas.drawString(320, height - 96, f"Curso: {curso_est}")
    c_canvas.drawString(560, height - 96, f"C.I.: {ci_est}")

    c_canvas.setFont("Helvetica", 9)
    c_canvas.setFillColor(colors.HexColor('#475569'))
    c_canvas.drawString(48, height - 110, f"Código RUDE: {rude_est}")
    c_canvas.drawString(320, height - 110, f"Turno: {turno_est}")

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
        tipo_txt = str(getattr(cal, 'tipo', '') or '').lower().strip()
        raw_tri = getattr(cal, 'trimestre', None)

        tri = None
        if raw_tri in [1, '1'] or '1' in periodo_txt or 'primer' in periodo_txt or '1er' in periodo_txt:
            tri = 1
        elif raw_tri in [2, '2'] or '2' in periodo_txt or 'segundo' in periodo_txt or '2do' in periodo_txt:
            tri = 2
        elif raw_tri in [3, '3'] or '3' in periodo_txt or 'tercer' in periodo_txt or '3er' in periodo_txt:
            tri = 3

        if tri in [1, 2, 3] and getattr(cal, 'nota', None) is not None:
            try:
                materias_dict[m_nom][tri].append({
                    'nota': float(cal.nota),
                    'tipo': tipo_txt
                })
            except (ValueError, TypeError):
                pass

    materias_finales = {}

    for m_nom, trimestres in materias_dict.items():
        materias_finales[m_nom] = {1: None, 2: None, 3: None}
        for tri in [1, 2, 3]:
            lista = trimestres[tri]
            if not lista:
                continue

            # Prioridad 1: Nota Final
            nota_oficial = next((item['nota'] for item in lista if any(k in item['tipo'] for k in ['final', 'promedio'])), None)
            if nota_oficial is not None:
                materias_finales[m_nom][tri] = nota_oficial
            else:
                notas_v = [item['nota'] for item in lista if item['nota'] > 0]
                if notas_v:
                    s = sum(notas_v)
                    materias_finales[m_nom][tri] = s if (len(notas_v) > 1 and s <= 100) else (s / len(notas_v))

    styles = getSampleStyleSheet()
    th_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white, alignment=1)
    td_mat = ParagraphStyle('TDMat', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#0F172A'))
    td_val = ParagraphStyle('TDVal', fontName='Helvetica', fontSize=9, leading=12, alignment=1, textColor=colors.HexColor('#334155'))
    td_prom = ParagraphStyle('TDProm', fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=1, textColor=colors.HexColor('#0F2942'))

    filas_tabla = [[
        Paragraph("ÁREA / MATERIA", th_style),
        Paragraph("1° TRIMESTRE", th_style),
        Paragraph("2° TRIMESTRE", th_style),
        Paragraph("3° TRIMESTRE", th_style),
        Paragraph("PROMEDIO FINAL", th_style)
    ]]

    suma_anuales = 0
    total_materias_prom = 0

    for mat_nom in sorted(materias_finales.keys()):
        t_dict = materias_finales[mat_nom]
        fila = [Paragraph(mat_nom, td_mat)]
        notas_existentes = []

        for tri in [1, 2, 3]:
            nota_tri = t_dict.get(tri)
            if nota_tri is not None:
                fila.append(Paragraph(f"{nota_tri:.1f}", td_val))
                notas_existentes.append(nota_tri)
            else:
                fila.append(Paragraph("-", td_val))

        if notas_existentes:
            prom_materia = sum(notas_existentes) / len(notas_existentes)
            fila.append(Paragraph(f"<b>{prom_materia:.1f}</b>", td_prom))
            suma_anuales += prom_materia
            total_materias_prom += 1
        else:
            fila.append(Paragraph("-", td_val))

        filas_tabla.append(fila)

    prom_inst = (suma_anuales / total_materias_prom) if total_materias_prom > 0 else 0
    c_canvas.setFont("Helvetica-Bold", 9)
    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.drawString(560, height - 110, f"Prom. General: {prom_inst:.1f}")

    col_w = [300, 105, 105, 105, 105]
    t = Table(filas_tabla, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E4E79')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    w_tab, h_tab = t.wrap(width - 72, height)
    pos_y = max(68, height - 130 - h_tab)
    t.drawOn(c_canvas, 36, pos_y)

    _dibujar_qr_y_pie(c_canvas, width, nombre_est, rude_est, curso_est, cloudinary_url, cualitativo=False)

def _dibujar_qr_y_pie(c_canvas, width, nombre_est, rude_est, curso_est, cloudinary_url, cualitativo=False):
    qr_text = cloudinary_url if cloudinary_url else f"COLEGIO VACA DIEZ | EST: {nombre_est} | RUDE: {rude_est} | CURSO: {curso_est}"
    qr = qrcode.QRCode(version=1, box_size=2, border=1)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_qr:
        img_qr.save(tmp_qr.name)
        tmp_qr_path = tmp_qr.name

    try:
        c_canvas.drawImage(tmp_qr_path, width - 86, 16, width=48, height=48)
    except Exception:
        pass
    finally:
        if os.path.exists(tmp_qr_path):
            os.unlink(tmp_qr_path)

    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#64748B'))
    if cualitativo:
        c_canvas.drawString(36, 32, f"Documento oficial de valoración pedagógica - {nombre_institucion()}")
        c_canvas.drawString(36, 22, "Válido institucionalmente para el nivel de Educación Inicial en Familia Comunitaria.")
    else:
        c_canvas.drawString(36, 32, f"Documento oficial generado digitalmente por el Sistema Académico - {nombre_institucion()}")
        c_canvas.drawString(36, 22, "Válido institucionalmente con registro en base de datos. Verificación mediante código QR.")

def generar_boletin_pdf(estudiante, calificaciones, materias, cloudinary_url=None):
    curso_str = ""
    if estudiante:
        if isinstance(estudiante, dict):
            curso_str = str(estudiante.get('curso', '') or estudiante.get('nivel', '')).lower().strip()
        else:
            curso_str = str(getattr(estudiante, 'curso', '') or getattr(estudiante, 'nivel', '')).lower().strip()

    es_nidito = any(k in curso_str for k in ['nidito', 'inicial', 'kinder', 'pre-kinder', 'prekinder', 'parvulario'])

    if es_nidito:
        from boletin_nidito_generator import generar_boletin_nidito_pdf
        return generar_boletin_nidito_pdf(estudiante, calificaciones, materias, cloudinary_url)

    buffer = io.BytesIO()
    c_canvas = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    if es_nidito:
        _render_nidito(c_canvas, width, height, estudiante, calificaciones, materias, cloudinary_url)
    else:
        _render_regular(c_canvas, width, height, estudiante, calificaciones, materias, cloudinary_url)

    c_canvas.save()
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
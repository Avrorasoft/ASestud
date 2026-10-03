# -*- coding: utf-8 -*-
import os
import io
import tempfile
from datetime import datetime, timezone, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import qrcode
from utils_pdf import ruta_logo, nombre_institucion

BOLIVIA_TZ = timezone(timedelta(hours=-4))

def generar_detalle_calificaciones_pdf(estudiante, calificaciones, materias=None, cloudinary_url=None):
    buffer = io.BytesIO()
    c_canvas = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter  # 612 x 792 pt

    # Datos del estudiante
    if isinstance(estudiante, dict):
        nombre_est = estudiante.get('nombre_completo') or f"{estudiante.get('nombres', '')} {estudiante.get('apellidos', '')}".strip() or "Estudiante"
        curso_est = estudiante.get('curso', '-')
        rude_est = estudiante.get('rude', '-')
        turno_est = estudiante.get('turno', 'Regular')
        ci_est = estudiante.get('ci', '-')
    else:
        nombre_est = getattr(estudiante, 'nombre_completo', None) or f"{getattr(estudiante, 'nombres', '')} {getattr(estudiante, 'apellidos', '')}".strip() or "Estudiante"
        curso_est = getattr(estudiante, 'curso', getattr(estudiante, 'nivel', '-'))
        rude_est = getattr(estudiante, 'rude', '-')
        turno_est = getattr(estudiante, 'turno', 'Regular')
        ci_est = getattr(estudiante, 'ci', '-')

    # Fondo blanco
    c_canvas.setFillColor(colors.white)
    c_canvas.rect(0, 0, width, height, fill=1, stroke=0)

    # Logo institucional
    logo_path = ruta_logo()
    if logo_path and os.path.exists(logo_path):
        try:
            c_canvas.drawImage(logo_path, 36, height - 70, width=54, height=54, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Cabecera
    c_canvas.setFillColor(colors.HexColor('#0F2942'))
    c_canvas.setFont("Helvetica-Bold", 14)
    c_canvas.drawString(98, height - 34, nombre_institucion().upper())

    c_canvas.setFont("Helvetica", 8.5)
    c_canvas.setFillColor(colors.HexColor('#4A5568'))
    c_canvas.drawString(98, height - 46, "REPORTE OFICIAL DETALLADO DE EVALUACIONES Y NOTAS REGISTRADAS")

    c_canvas.setFont("Helvetica-Bold", 11)
    c_canvas.setFillColor(colors.HexColor('#1E4E79'))
    c_canvas.drawRightString(width - 36, height - 34, "CALIFICACIONES OFICIALES")

    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    ahora = datetime.now(BOLIVIA_TZ)
    fecha_txt = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"
    c_canvas.setFont("Helvetica", 8)
    c_canvas.setFillColor(colors.HexColor('#718096'))
    c_canvas.drawRightString(width - 36, height - 46, f"Gestión {ahora.year} • Emisión: {fecha_txt}")

    # Ficha del Estudiante
    c_canvas.setFillColor(colors.HexColor('#F8FAFC'))
    c_canvas.setStrokeColor(colors.HexColor('#CBD5E1'))
    c_canvas.roundRect(36, height - 116, width - 72, 38, 4, fill=1, stroke=1)

    c_canvas.setFont("Helvetica-Bold", 8.5)
    c_canvas.setFillColor(colors.HexColor('#1E293B'))
    c_canvas.drawString(46, height - 94, f"Estudiante: {nombre_est.upper()}")
    c_canvas.drawString(290, height - 94, f"Curso: {curso_est}")
    c_canvas.drawString(450, height - 94, f"C.I.: {ci_est}")

    c_canvas.setFont("Helvetica", 8.5)
    c_canvas.setFillColor(colors.HexColor('#475569'))
    c_canvas.drawString(46, height - 108, f"Código RUDE: {rude_est}")
    c_canvas.drawString(290, height - 108, f"Turno: {turno_est}")

    # Agrupar notas por materia y periodo
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
            m_nom = getattr(cal, 'campo', None) or getattr(cal, 'area', None) or "Materia General"

        if m_nom not in materias_dict:
            materias_dict[m_nom] = []

        materias_dict[m_nom].append(cal)

    # Estilos de texto
    styles = getSampleStyleSheet()
    th_style = ParagraphStyle('THDetalle', fontName='Helvetica-Bold', fontSize=8.5, leading=10, textColor=colors.white, alignment=1)
    td_mat_title = ParagraphStyle('TDMatTitle', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#0F2942'))
    td_eval = ParagraphStyle('TDEval', fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#1E293B'))
    td_eval_bold = ParagraphStyle('TDEvalBold', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.HexColor('#0F2942'))
    td_nota = ParagraphStyle('TDNota', fontName='Helvetica', fontSize=8.5, leading=11, alignment=1, textColor=colors.HexColor('#334155'))
    td_nota_final = ParagraphStyle('TDNotaFinal', fontName='Helvetica-Bold', fontSize=9.5, leading=11, alignment=1, textColor=colors.HexColor('#166534'))

    filas_tabla = [[
        Paragraph("MATERIA", th_style),
        Paragraph("EVALUACIONES Y NOTAS REGISTRADAS", th_style),
        Paragraph("NOTA", th_style)
    ]]

    for m_nom in sorted(materias_dict.keys()):
        lista_cals = materias_dict[m_nom]
        primera_fila = True

        # Ordenar: primero parciales/asistencia/trabajos, al final la Nota Final
        def orden_cal(c):
            t = str(getattr(c, 'tipo', '') or '').lower()
            return 1 if ('final' in t or 'promedio' in t) else 0

        lista_cals_sorted = sorted(lista_cals, key=orden_cal)

        for cal in lista_cals_sorted:
            tipo_eval = getattr(cal, 'tipo', None) or "Evaluación"
            es_final = any(k in tipo_eval.lower() for k in ['final', 'promedio'])
            
            nota_val = getattr(cal, 'nota', None)
            nota_str = f"{float(nota_val):.1f}" if (nota_val is not None and str(nota_val).strip() != '') else "-"

            celda_materia = Paragraph(m_nom, td_mat_title) if primera_fila else Paragraph("", td_mat_title)
            celda_eval = Paragraph(tipo_eval, td_eval_bold if es_final else td_eval)
            celda_nota = Paragraph(f"<b>{nota_str}</b>" if es_final else nota_str, td_nota_final if es_final else td_nota)

            filas_tabla.append([celda_materia, celda_eval, celda_nota])
            primera_fila = False

    # Renderizado de tabla (Ancho total 540 pt)
    col_w = [180, 260, 100]
    t = Table(filas_tabla, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E4E79')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    w_tab, h_tab = t.wrap(width - 72, height)
    pos_y = max(64, height - 128 - h_tab)
    t.drawOn(c_canvas, 36, pos_y)

    # QR de verificación local
    qr_text = cloudinary_url if cloudinary_url else f"COLEGIO VACA DIEZ | DETALLE EVALUACIONES | EST: {nombre_est} | CI: {ci_est}"
    qr = qrcode.QRCode(version=1, box_size=2, border=1)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_qr:
        img_qr.save(tmp_qr.name)
        tmp_qr_path = tmp_qr.name

    try:
        c_canvas.drawImage(tmp_qr_path, width - 74, 14, width=42, height=42)
    except Exception:
        pass
    finally:
        if os.path.exists(tmp_qr_path):
            os.unlink(tmp_qr_path)

    c_canvas.setFont("Helvetica", 7.5)
    c_canvas.setFillColor(colors.HexColor('#64748B'))
    c_canvas.drawString(36, 28, f"Documento oficial de detalle de calificaciones - {nombre_institucion()}")
    c_canvas.drawString(36, 18, "Reporte generado conforme a los registros del sistema académico central.")

    c_canvas.save()
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

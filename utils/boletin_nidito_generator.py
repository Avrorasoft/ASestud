# -*- coding: utf-8 -*-
import io
import os
import tempfile
import qrcode
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from utils_pdf import nombre_institucion, ruta_logo

BOLIVIA_TZ = ZoneInfo("America/La_Paz")

def extraer_trimestre_num(texto):
    t = str(texto or "").lower()
    if any(k in t for k in ["2", "segundo", "2do", "2°"]):
        return 2
    if any(k in t for k in ["3", "tercer", "3ro", "3°"]):
        return 3
    return 1

def generar_boletin_nidito_pdf(estudiante, calificaciones=None, materias=None, cloudinary_url=None):
    calificaciones = calificaciones or []

    buffer = io.BytesIO()
    c_canvas = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    if isinstance(estudiante, dict):
        nombre_est = estudiante.get("nombre_completo") or f"{estudiante.get('nombres', '')} {estudiante.get('apellidos', '')}".strip()
        curso_est = estudiante.get("curso", "Nidito")
        rude_est = str(estudiante.get("rude") or estudiante.get("ci") or "S/R")
        turno_est = estudiante.get("turno", "Tarde")
        ci_est = str(estudiante.get("ci") or "")
    else:
        nombre_est = getattr(estudiante, "nombre_completo", None) or f"{getattr(estudiante, 'nombres', '')} {getattr(estudiante, 'apellidos', '')}".strip()
        curso_est = getattr(estudiante, "curso", "Nidito")
        rude_est = str(getattr(estudiante, "rude", None) or getattr(estudiante, "ci", "S/R"))
        turno_est = getattr(estudiante, "turno", "Tarde")
        ci_est = str(getattr(estudiante, "ci", ""))

    c_canvas.setFillColor(colors.white)
    c_canvas.rect(0, 0, width, height, fill=True, stroke=False)

    # Logo institucional dinámico
    logo_path = ruta_logo()
    if logo_path and os.path.exists(logo_path):
        try:
            c_canvas.drawImage(logo_path, 40, height - 76, width=54, height=54, mask="auto", preserveAspectRatio=True)
        except Exception:
            pass

    # Extraer nombre institucional de forma segura
    inst_nombre = str(nombre_institucion()) if callable(nombre_institucion) else str(nombre_institucion)

    # Cabecera
    c_canvas.setFillColor(HexColor("#0F2942"))
    c_canvas.setFont("Helvetica-Bold", 14)
    c_canvas.drawString(104, height - 38, inst_nombre.upper())

    c_canvas.setFillColor(HexColor("#4A5568"))
    c_canvas.setFont("Helvetica", 8)
    c_canvas.drawString(104, height - 50, "EDUCACIÓN INICIAL EN FAMILIA COMUNITARIA - SEGUIMIENTO DEL DESARROLLO")

    c_canvas.setFillColor(HexColor("#1E4E79"))
    c_canvas.setFont("Helvetica-Bold", 10)
    c_canvas.drawString(104, height - 64, "BOLETÍN OFICIAL CUALITATIVO TRIMESTRAL")

    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    ahora = datetime.now(BOLIVIA_TZ)
    fecha_txt = f"{ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"

    c_canvas.setFillColor(HexColor("#718096"))
    c_canvas.setFont("Helvetica", 8)
    c_canvas.drawRightString(width - 40, height - 38, f"Gestión {ahora.year}")
    c_canvas.drawRightString(width - 40, height - 50, f"Emisión: {fecha_txt}")

    # Datos del Alumno
    c_canvas.setFillColor(HexColor("#F8FAFC"))
    c_canvas.setStrokeColor(HexColor("#CBD5E1"))
    c_canvas.roundRect(40, height - 134, width - 80, 52, 4, fill=True, stroke=True)

    c_canvas.setFillColor(HexColor("#1E293B"))
    c_canvas.setFont("Helvetica-Bold", 9)
    c_canvas.drawString(55, height - 102, f"Estudiante: {nombre_est.upper()}")
    c_canvas.drawString(55, height - 120, f"Nivel / Sala: {curso_est}")

    c_canvas.setFillColor(HexColor("#475569"))
    c_canvas.setFont("Helvetica", 9)
    c_canvas.drawString(width * 0.55, height - 102, f"Código RUDE: {rude_est}")
    c_canvas.drawString(width * 0.55, height - 120, f"Turno: {turno_est}")

    # Mapeo exacto materia por materia y sus evaluaciones trimestrales
    materias_map = {}
    for c in calificaciones:
        m_obj = getattr(c, "materia", None)
        # En Nidito, el área viene en 'tipo' o en materia.nombre
        tipo_area = getattr(c, "tipo", None) or (c.get("tipo") if isinstance(c, dict) else None)
        m_nom = str(tipo_area or getattr(m_obj, "nombre", None) or getattr(c, "materia_nombre", "") or "").strip()
        if not m_nom or m_nom.lower() in ["materia eliminada", "none"]:
            continue

        p_raw = getattr(c, "periodo", "") or getattr(c, "trimestre", "") or (c.get("periodo") if isinstance(c, dict) else "")
        t_num = extraer_trimestre_num(p_raw)

        val = str(getattr(c, "valoracion_cualitativa", "") or getattr(c, "calificacion_cualitativa", "") or (c.get("valoracion_cualitativa") if isinstance(c, dict) else "") or "").strip()
        obs = str(getattr(c, "informe_descriptivo", "") or getattr(c, "observacion", "") or (c.get("informe_descriptivo") if isinstance(c, dict) else "") or "").strip()

        detalle_final = val or obs or "En Seguimiento"

        if m_nom not in materias_map:
            materias_map[m_nom] = {1: "—", 2: "—", 3: "—"}
        materias_map[m_nom][t_num] = detalle_final

    # Si el estudiante no tiene calificaciones registradas, mostrar estructura en blanco
    if not materias_map:
        for default_m in ["Desarrollo Psicomotriz", "Lenguaje y Expresión", "Autonomía y Convivencia", "Pensamiento y Creatividad"]:
            materias_map[default_m] = {1: "—", 2: "—", 3: "—"}

    styles = getSampleStyleSheet()
    th_title = ParagraphStyle("THTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=HexColor("#FFFFFF"))
    th_center = ParagraphStyle("THCenter", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=HexColor("#FFFFFF"), alignment=1)
    td_mat = ParagraphStyle("TDMat", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, textColor=HexColor("#0F172A"))

    filas_tabla = [
        [
            Paragraph("MATERIA / ÁREA FORMATIVA", th_title),
            Paragraph("1° TRIMESTRE", th_center),
            Paragraph("2° TRIMESTRE", th_center),
            Paragraph("3° TRIMESTRE", th_center)
        ]
    ]

    for m_nombre, trimestres in materias_map.items():
        def render_celda(t_val):
            v_low = str(t_val).lower()
            if "proceso" in v_low:
                col = "#B45309"
            elif "logrado" in v_low:
                col = "#166534"
            elif t_val == "—":
                col = "#94A3B8"
            else:
                col = "#1E40AF"
            return Paragraph(f"<para align=center><b><font color='{col}'>{t_val}</font></b></para>", styles["Normal"])

        filas_tabla.append([
            Paragraph(m_nombre, td_mat),
            render_celda(trimestres.get(1, "—")),
            render_celda(trimestres.get(2, "—")),
            render_celda(trimestres.get(3, "—"))
        ])

    col_w = [(width - 80) * 0.43, (width - 80) * 0.19, (width - 80) * 0.19, (width - 80) * 0.19]
    t = Table(filas_tabla, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F2942")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
    ]))

    w_tab, h_tab = t.wrap(width - 80, height)
    pos_y_tab = height - 146 - h_tab
    t.drawOn(c_canvas, 40, pos_y_tab)

    # QR
    qr_text = cloudinary_url if cloudinary_url else f"{inst_nombre.upper()} | INICIAL | EST: {nombre_est} | RUDE: {rude_est}"
    qr = qrcode.QRCode(version=1, box_size=3, border=0)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="#0F2942", back_color="white")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_qr:
        img_qr.save(tmp_qr.name)
        tmp_qr_path = tmp_qr.name

    try:
        c_canvas.drawImage(tmp_qr_path, width - 88, 28, width=48, height=48)
    finally:
        if os.path.exists(tmp_qr_path):
            os.unlink(tmp_qr_path)

    # Pie institucional dinámico
    c_canvas.setFillColor(HexColor("#64748B"))
    c_canvas.setFont("Helvetica", 7)
    c_canvas.drawString(40, 40, f"Documento oficial de valoración pedagógica trimestral - {inst_nombre}.")
    c_canvas.drawString(40, 29, "Válido institucionalmente para el nivel de Educación Inicial en Familia Comunitaria.")

    c_canvas.save()
    buffer.seek(0)
    return buffer.getvalue()
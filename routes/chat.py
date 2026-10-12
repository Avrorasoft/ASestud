# -*- coding: utf-8 -*-
# ==============================================================================
# Archivo: routes/chat.py
# Proyecto: Sistema de Gestión Escolar
# Desarrollado por: Avrora Soft - Vibola LLC
# Descripción: Módulo de Mensajería y Chat con Padres de Familia:
#              - Ruta exclusiva y canónica para adjuntos y boletines: C:\ASestud\uploads
#              - Endpoint dedicado para servir archivos directos desde /uploads/<path:filename>
#              - Endpoint /chat/adjunto/<id>/descargar con soporte de visualización y descarga
#              - Blindaje financiero: Corte Operativo / Inicio de Cómputo respetado
# ==============================================================================

import os
from urllib.parse import urlparse
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
    abort,
    send_file,
    send_from_directory
)
from models import db, Mensaje, Estudiante, Padre, Pago, Calificacion, Materia, ConfiguracionSuperadmin
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
from utils.boletin_generator import generar_boletin_pdf, guardar_boletin_localmente

chat_bp = Blueprint('chat', __name__, template_folder='templates/chat')

# Zona horaria Bolivia
BOLIVIA_TZ = timezone(timedelta(hours=-4))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'mp3', 'wav', 'ogg', 'xls', 'xlsx'}

MESES_ESCOLARES_MAP = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
}

MESES_ORDEN = ["Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre"]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==============================================================================
# FUNCIONES AUXILIARES INSTITUCIONALES Y DE CORTE FINANCIERO
# ==============================================================================

def obtener_nombre_institucion():
    """Obtiene el nombre de la institución dinámicamente sin nombres quemados."""
    try:
        if current_app:
            nom_cfg = current_app.config.get('NOMBRE_INSTITUCION') or current_app.config.get('INSTITUCION_NOMBRE')
            if nom_cfg and str(nom_cfg).strip():
                return str(nom_cfg).strip()

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

    return "UNIDAD EDUCATIVA"

def obtener_corte_operativo():
    """Recupera la fecha de corte operativo configurada por Superadmin."""
    try:
        cfg = ConfiguracionSuperadmin.query.filter_by(clave='fecha_corte_operativo').first()
        if cfg and cfg.valor and str(cfg.valor).strip():
            valor_limpio = str(cfg.valor).strip()
            for fmt in ('%Y-%m-%d', '%Y-%m', '%d/%m/%Y'):
                try:
                    return datetime.strptime(valor_limpio, fmt).date()
                except ValueError:
                    pass
    except Exception:
        pass
    return None

def extraer_adjunto(contenido):
    r"""
    Separa el texto del mensaje y la ruta del archivo adjunto.
    El formato canónico usado es:
    ---ARCHIVO_ADJUNTO---uploads/boletines/archivo.pdf
    """
    if not contenido or '---ARCHIVO_ADJUNTO---' not in contenido:
        return None, contenido or ''

    texto, _, adjunto = contenido.partition('---ARCHIVO_ADJUNTO---')
    return adjunto.strip(), texto.strip()

def ruta_local_segura(ruta):
    r"""
    Resuelve cualquier referencia relativa a la ubicación canónica dentro de C:\ASestud\uploads.
    """
    if not ruta:
        return None

    ruta = ruta.strip()
    parsed = urlparse(ruta)
    if parsed.scheme:
        ruta = parsed.path

    ruta = ruta.replace('\\', '/')

    if ruta.startswith('/uploads/'):
        ruta = ruta[len('/uploads/'):]
    elif ruta.startswith('uploads/'):
        ruta = ruta[len('uploads/'):]
    elif '/uploads/' in ruta:
        ruta = ruta.split('/uploads/', 1)[1]

    base_upload = os.path.abspath(current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads"))
    filepath = os.path.abspath(os.path.join(base_upload, ruta))

    if not filepath.startswith(base_upload):
        return None

    if not os.path.isfile(filepath):
        nombre = os.path.basename(ruta)
        candidatos = [
            os.path.join(base_upload, 'boletines', nombre),
            os.path.join(base_upload, 'chat', nombre),
            os.path.join(base_upload, nombre)
        ]
        for c in candidatos:
            if os.path.isfile(c):
                return c
        return None

    return filepath

def ahora_bolivia():
    """Devuelve la fecha/hora actual en zona horaria Bolivia (UTC-4)"""
    return datetime.now(BOLIVIA_TZ)

def verificar_mora_estricta(estudiante_id):
    """
    Verifica si el estudiante tiene mora real considerando exclusivamente
    los meses transcurridos a partir de la Fecha de Corte Operativo (Inicio de Cómputo).
    """
    est = Estudiante.query.get(estudiante_id)
    if not est:
        return False
        
    pension_base = float(est.pension or 0.0)
    if pension_base <= 0:
        return False

    ahora = ahora_bolivia()
    anio_actual = ahora.year
    mes_actual_num = ahora.month
    corte = obtener_corte_operativo()

    mes_inicio_exigible = 2
    if corte:
        if anio_actual < corte.year:
            return False
        elif anio_actual == corte.year:
            mes_inicio_exigible = corte.month
        else:
            mes_inicio_exigible = 2

    meses_exigibles = [
        m for m in MESES_ORDEN
        if mes_inicio_exigible <= MESES_ESCOLARES_MAP.get(m.lower(), 12) <= mes_actual_num
    ]

    if not meses_exigibles:
        return False

    pagos_est = Pago.query.filter_by(estudiante_id=estudiante_id, anio=anio_actual).all()
    pagos_map = {p.mes.strip().title(): p for p in pagos_est if p.mes}
    
    monto_mora = 0.0
    for mes in meses_exigibles:
        if mes in pagos_map:
            p = pagos_map[mes]
            if p.estado != 'Pagado':
                saldo_mes = float(p.monto_total or pension_base) - float(p.descuento or 0.0) - float(p.monto_pagado or 0.0)
                if saldo_mes > 0:
                    monto_mora += saldo_mes
        else:
            monto_mora += pension_base
            
    return monto_mora > 0

def personalizar_texto_mensaje(texto_base, estudiante, padre, calificaciones=None, materias=None):
    """Reemplaza los comodines por los datos reales y formatea el resumen oficial."""
    if not texto_base:
        return ""
        
    texto = texto_base
    nombre_tutor = padre.nombres if padre and padre.nombres else 'Padre de Familia'
    
    texto = texto.replace('Sr./Sra. Sr./Sra. [Tutor]', f'Sr./Sra. {nombre_tutor}')
    texto = texto.replace('Sr./Sra. [Tutor]', f'Sr./Sra. {nombre_tutor}')
    texto = texto.replace('[Tutor]', nombre_tutor)
    
    texto = texto.replace('[Estudiante]', f"{estudiante.nombres} {estudiante.apellidos}")
    texto = texto.replace('[Curso]', estudiante.curso or 'S/C')
    
    if "RESUMEN ACADÉMICO:" in texto:
        partes = texto.split("RESUMEN ACADÉMICO:")
        texto = partes[0] + "RESUMEN ACADÉMICO:\n• Por favor, descargue y revise el documento PDF adjunto para visualizar las calificaciones y valoraciones oficiales con total precisión."
        
    return texto

def obtener_plantillas():
    """Genera el diccionario de plantillas oficiales con encabezados dinámicos."""
    inst = obtener_nombre_institucion().upper()
    return {
        'General': (
            f"Estimado/a Sr./Sra. {{tutor}}:\n\n"
            f"Reciba un cordial y respetuoso saludo de parte de la Dirección de {inst}.\n\n"
            f"Por medio de la presente, nos dirigimos a usted para comunicarle lo siguiente:\n\n"
            f"[ESCRIBA AQUÍ SU MENSAJE]\n\n"
            f"Agradecemos de antemano su atención y quedamos a su disposición para cualquier consulta.\n\n"
            f"Atentamente,\n"
            f"LA DIRECCIÓN\n"
            f"{inst}"
        ),
        'Citación': (
            f"{inst}\n"
            f"Dirección Administrativa y Académica\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ASUNTO: Citación Obligatoria a Reunión\n\n"
            f"Estimado/a Sr./Sra. {{tutor}}:\n\n"
            f"Por medio de la presente, la Dirección tiene el agrado de citarle a una reunión de carácter OBLIGATORIO.\n\n"
            f"DATOS DEL ESTUDIANTE:\n"
            f"• Nombre: {{estudiante}}\n"
            f"• Curso: {{curso}}\n\n"
            f"DETALLES DE LA REUNIÓN:\n"
            f"• Fecha: {{fecha}}\n"
            f"• Hora: {{hora}}\n"
            f"• Lugar: Salón de Usos Múltiples de la Institución\n\n"
            f"Su puntual asistencia es indispensable.\n\n"
            f"Atentamente,\n"
            f"LA DIRECCIÓN\n"
            f"{inst}"
        ),
        'Recordatorio de Pago': (
            f"{inst}\n"
            f"Departamento de Administración\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ASUNTO: Recordatorio Amistoso de Pago de Pensión\n\n"
            f"Estimado/a Sr./Sra. {{tutor}}:\n\n"
            f"Reciba un cordial saludo. Le recordamos amablemente que el/la estudiante {{estudiante}} del curso {{curso}} presenta pendiente el pago de cuotas vencidas.\n\n"
            f"DETALLE DE LA DEUDA:\n"
            f"• Meses adeudados: {{meses}}\n"
            f"• Monto total pendiente: Bs. {{monto}}\n"
            f"• Gestión: {{gestion}}\n\n"
            f"Le solicitamos comedidamente regularizar esta situación en la oficina de Administración.\n\n"
            f"Si usted ya regularizó el pago, le rogamos hacer caso omiso de este mensaje.\n\n"
            f"Atentamente,\n"
            f"DEPARTAMENTO DE ADMINISTRACIÓN\n"
            f"{inst}"
        ),
        'Comprobante de Pago': (
            f"{inst}\n"
            f"Departamento de Administración\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ASUNTO: Comprobante Oficial de Pago Recibido\n\n"
            f"Estimado/a Sr./Sra. {{tutor}}:\n\n"
            f"Confirmamos la recepción exitosa del pago realizado por concepto de pensión escolar.\n\n"
            f"DETALLE DE LA TRANSACCIÓN:\n"
            f"• Estudiante: {{estudiante}}\n"
            f"• Curso: {{curso}}\n"
            f"• Mes correspondiente: {{mes}}\n"
            f"• Monto cancelado: Bs. {{monto}}\n"
            f"• Fecha de registro: {{fecha}}\n\n"
            f"Este mensaje tiene validez como comprobante de pago.\n\n"
            f"Atentamente,\n"
            f"LA DIRECCIÓN ADMINISTRATIVA\n"
            f"{inst}"
        ),
        'Inasistencia': (
            f"{inst}\n"
            f"Departamento de Disciplina y Seguimiento\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ASUNTO: Comunicado de Inasistencia Injustificada\n\n"
            f"Estimado/a Sr./Sra. {{tutor}}:\n\n"
            f"Le informamos que el/la estudiante {{estudiante}} del curso {{curso}} ha registrado inasistencia a clases el día {{fecha}}, sin la debida justificación.\n\n"
            f"Le solicitamos presentar la justificación correspondiente en la oficina de Dirección dentro del plazo reglamentario.\n\n"
            f"Atentamente,\n"
            f"LA DIRECCIÓN\n"
            f"{inst}"
        ),
        'Felicitación': (
            f"{inst}\n"
            f"Dirección Académica\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ASUNTO: Felicitación y Reconocimiento al Mérito Académico\n\n"
            f"Es un honor expresarle nuestras más sinceras felicitaciones por el excelente desempeño académico de su hijo/a {{estudiante}} del curso {{curso}}.\n\n"
            f"LOGROS DESTACADOS:\n"
            f"• Promedio general ponderado: {{promedio}}\n"
            f"• Mejor materia: {{mejor_materia}} ({{nota_mejor}})\n\n"
            f"Con admiración y respeto,\n"
            f"LA DIRECCIÓN ACADÉMICA\n"
            f"{inst}"
        ),
        'Boletín': (
            f"{inst}\n"
            f"Departamento Académico\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"ASUNTO: Notificación de Disponibilidad de Boletín de Calificaciones\n\n"
            f"Estimado/a Sr./Sra. {{tutor}}:\n\n"
            f"Reciba un cordial saludo. Le informamos que el Boletín de Calificaciones de la gestión actual del estudiante {{estudiante}} ya se encuentra disponible en formato PDF adjunto a este mensaje.\n\n"
            f"RESUMEN ACADÉMICO:\n"
            f"• Promedio General: {{promedio}}\n"
            f"• Materias aprobadas: {{materias_aprobadas}}\n"
            f"• Materias reprobadas: {{materias_reprobadas}}\n\n"
            f"Le rogamos descargar el documento oficial adjunto y revisarlo detalladamente.\n\n"
            f"Atentamente,\n"
            f"LA DIRECCIÓN ACADÉMICA\n"
            f"{inst}"
        )
    }

def guardar_boletin_en_uploads(pdf_bytes, estudiante_id, anio, rude):
    r"""
    Guarda físicamente el boletín en C:\ASestud\uploads\boletines y devuelve
    la ruta web canónica 'uploads/boletines/<archivo>.pdf'.
    """
    base_upload = os.path.abspath(current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads"))
    carpeta_boletines = os.path.join(base_upload, 'boletines')
    os.makedirs(carpeta_boletines, exist_ok=True)

    timestamp = int(datetime.now().timestamp())
    rude_str = str(rude or estudiante_id).strip()
    nombre_archivo = f"boletin_{estudiante_id}_{rude_str}_{anio}_{timestamp}.pdf"
    ruta_disco = os.path.join(carpeta_boletines, nombre_archivo)

    with open(ruta_disco, 'wb') as f:
        f.write(pdf_bytes)

    return f"uploads/boletines/{nombre_archivo}"

# =========================================================================
# RUTA WEB PARA SERVIR ARCHIVOS DIRECTOS DESDE UPLOADS (Evita el 404)
# =========================================================================
@chat_bp.route('/uploads/<path:filename>')
def servir_desde_uploads(filename):
    """Permite que el navegador abra directamente cualquier URL que empiece con /chat/uploads/... o /uploads/..."""
    base_upload = os.path.abspath(current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads"))
    return send_from_directory(base_upload, filename)

# =========================================================================
# LISTA DE CHATS
# =========================================================================
@chat_bp.route('/')
def index():
    mensajes = Mensaje.query.order_by(Mensaje.fecha_envio.desc()).limit(100).all()

    total_mensajes = len(mensajes)
    total_comprobantes = sum(1 for m in mensajes if 'pago' in (m.tipo_mensaje or '').lower() or 'comprobante' in (m.tipo_mensaje or '').lower())
    total_faltas = sum(1 for m in mensajes if 'falta' in (m.tipo_mensaje or '').lower() or 'inasistencia' in (m.tipo_mensaje or '').lower())
    total_citaciones = sum(1 for m in mensajes if 'citación' in (m.tipo_mensaje or '').lower() or 'citacion' in (m.tipo_mensaje or '').lower())
    total_felicitaciones = sum(1 for m in mensajes if 'felicitación' in (m.tipo_mensaje or '').lower() or 'felicitacion' in (m.tipo_mensaje or '').lower())
    total_boletines = sum(1 for m in mensajes if 'boletín' in (m.tipo_mensaje or '').lower() or 'boletin' in (m.tipo_mensaje or '').lower())

    filtro_tipo = request.args.get('tipo', '')
    if filtro_tipo:
        mensajes = [m for m in mensajes if filtro_tipo.lower() in (m.tipo_mensaje or '').lower()]

    return render_template('chat/index.html',
                           mensajes=mensajes,
                           total_mensajes=total_mensajes,
                           total_comprobantes=total_comprobantes,
                           total_faltas=total_faltas,
                           total_citaciones=total_citaciones,
                           total_felicitaciones=total_felicitaciones,
                           total_boletines=total_boletines,
                           filtro_actual=filtro_tipo)

# =========================================================================
# ENVIAR MENSAJE (Individual o Masivo con Archivos en C:\ASestud\uploads)
# =========================================================================
@chat_bp.route('/enviar', methods=['GET', 'POST'])
def enviar():
    if request.method == 'POST':
        try:
            tipo_mensaje = request.form.get('tipo_mensaje', 'General')
            contenido_base = request.form.get('contenido', '').strip()
            modo_envio = request.form.get('modo_envio', 'individual')
            archivo_path_manual = None

            if 'archivo' in request.files:
                file = request.files['archivo']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(f"chat_{int(datetime.now().timestamp())}_{file.filename}")
                    base_upload = current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads")
                    upload_folder = os.path.join(base_upload, 'chat')
                    os.makedirs(upload_folder, exist_ok=True)
                    filepath = os.path.join(upload_folder, filename)
                    file.save(filepath)
                    archivo_path_manual = f"uploads/chat/{filename}"

            # -------------------------------------------------------------
            # MASIVO A TODOS
            # -------------------------------------------------------------
            if modo_envio == 'masivo_todos':
                estudiantes = Estudiante.query.filter_by(estado='Activo').all()
                count = 0
                for est in estudiantes:
                    padre = Padre.query.filter_by(estudiante_id=est.id).first()
                    if padre and padre.nombres:
                        calificaciones = Calificacion.query.filter_by(estudiante_id=est.id).all()
                        materias = Materia.query.all()
                        
                        if tipo_mensaje == 'Boletín':
                            if verificar_mora_estricta(est.id):
                                continue
                                
                            pdf_bytes = generar_boletin_pdf(est, calificaciones, materias)
                            ruta_pdf = guardar_boletin_en_uploads(pdf_bytes, est.id, ahora_bolivia().year, est.rude)
                            
                            texto_limpio = personalizar_texto_mensaje(contenido_base, est, padre, calificaciones, materias)
                            contenido_final = f"{texto_limpio}\n\n---ARCHIVO_ADJUNTO---{ruta_pdf}"
                        
                        else:
                            texto_limpio = personalizar_texto_mensaje(contenido_base, est, padre, calificaciones, materias)
                            if archivo_path_manual:
                                contenido_final = f"{texto_limpio}\n\n---ARCHIVO_ADJUNTO---{archivo_path_manual}"
                            else:
                                contenido_final = texto_limpio

                        msg = Mensaje(
                            destinatario=padre.nombres,
                            estudiante_id=est.id,
                            telefono=padre.telefono1 or 'Sin teléfono',
                            tipo_mensaje=tipo_mensaje,
                            contenido=contenido_final,
                            remitente='Colegio'
                        )
                        db.session.add(msg)
                        count += 1
                db.session.commit()
                flash(f'✅ Mensaje enviado a {count} padres de familia.', 'success')

            # -------------------------------------------------------------
            # MASIVO POR CURSO
            # -------------------------------------------------------------
            elif modo_envio == 'masivo_curso':
                curso = request.form.get('curso_destino', '')
                if not curso:
                    flash('❌ Seleccione un curso', 'danger')
                    return redirect(url_for('chat.enviar'))
                
                estudiantes = Estudiante.query.filter_by(curso=curso, estado='Activo').all()
                count = 0
                for est in estudiantes:
                    padre = Padre.query.filter_by(estudiante_id=est.id).first()
                    if padre and padre.nombres:
                        calificaciones = Calificacion.query.filter_by(estudiante_id=est.id).all()
                        materias = Materia.query.all()
                        
                        if tipo_mensaje == 'Boletín':
                            if verificar_mora_estricta(est.id):
                                continue
                                
                            pdf_bytes = generar_boletin_pdf(est, calificaciones, materias)
                            ruta_pdf = guardar_boletin_en_uploads(pdf_bytes, est.id, ahora_bolivia().year, est.rude)
                            
                            texto_limpio = personalizar_texto_mensaje(contenido_base, est, padre, calificaciones, materias)
                            contenido_final = f"{texto_limpio}\n\n---ARCHIVO_ADJUNTO---{ruta_pdf}"
                            
                        else:
                            texto_limpio = personalizar_texto_mensaje(contenido_base, est, padre, calificaciones, materias)
                            if archivo_path_manual:
                                contenido_final = f"{texto_limpio}\n\n---ARCHIVO_ADJUNTO---{archivo_path_manual}"
                            else:
                                contenido_final = texto_limpio

                        msg = Mensaje(
                            destinatario=padre.nombres,
                            estudiante_id=est.id,
                            telefono=padre.telefono1 or 'Sin teléfono',
                            tipo_mensaje=tipo_mensaje,
                            contenido=contenido_final,
                            remitente='Colegio'
                        )
                        db.session.add(msg)
                        count += 1
                db.session.commit()
                flash(f'✅ Mensaje enviado a {count} padres del curso {curso}.', 'success')

            # -------------------------------------------------------------
            # MASIVO MOROSOS
            # -------------------------------------------------------------
            elif modo_envio == 'masivo_morosos':
                estudiantes = Estudiante.query.filter_by(estado='Activo').all()
                count = 0
                inst_nombre = obtener_nombre_institucion().upper()
                for est in estudiantes:
                    if verificar_mora_estricta(est.id):
                        padre = Padre.query.filter_by(estudiante_id=est.id).first()
                        if padre and padre.nombres:
                            contenido_personalizado = (
                                f"{inst_nombre}\n"
                                f"Departamento de Administración\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"AVISO DE PAGO PENDIENTE\n\n"
                                f"Estimado/a Sr./Sra. {padre.nombres}:\n\n"
                                f"Le informamos que el/la estudiante {est.nombres} {est.apellidos} del curso {est.curso} presenta pagos vencidos pendientes de regularización.\n\n"
                                f"Gestión: {ahora_bolivia().year}\n\n"
                                f"Le solicitamos regularizar su situación en la oficina de Administración a la brevedad.\n\n"
                                f"Atentamente,\nDEPARTAMENTO DE ADMINISTRACIÓN\n{inst_nombre}"
                            )
                            
                            msg = Mensaje(
                                destinatario=padre.nombres,
                                estudiante_id=est.id,
                                telefono=padre.telefono1 or 'Sin teléfono',
                                tipo_mensaje='Recordatorio de Pago',
                                contenido=contenido_personalizado,
                                remitente='Colegio'
                            )
                            db.session.add(msg)
                            count += 1
                db.session.commit()
                flash(f'✅ Recordatorio de pago enviado a {count} padres con cuotas vencidas.', 'success')

            # -------------------------------------------------------------
            # ENVÍO INDIVIDUAL
            # -------------------------------------------------------------
            else:
                estudiante_id = request.form.get('estudiante_id', '')
                if not estudiante_id:
                    flash('❌ Seleccione un estudiante', 'danger')
                    return redirect(url_for('chat.enviar'))
                
                est = Estudiante.query.get(int(estudiante_id))
                padre = Padre.query.filter_by(estudiante_id=int(estudiante_id)).first() if est else None
                
                if est:
                    calificaciones = Calificacion.query.filter_by(estudiante_id=est.id).all()
                    materias = Materia.query.all()
                    
                    if tipo_mensaje == 'Boletín':
                        if verificar_mora_estricta(est.id):
                            flash(f'❌ El estudiante {est.nombres} {est.apellidos} tiene cuotas vencidas pendientes. No se puede enviar el boletín.', 'danger')
                            return redirect(url_for('chat.enviar'))
                            
                        pdf_bytes = generar_boletin_pdf(est, calificaciones, materias)
                        ruta_pdf = guardar_boletin_en_uploads(pdf_bytes, est.id, ahora_bolivia().year, est.rude)
                        
                        texto_limpio = personalizar_texto_mensaje(contenido_base, est, padre, calificaciones, materias)
                        contenido_final = f"{texto_limpio}\n\n---ARCHIVO_ADJUNTO---{ruta_pdf}"
                    else:
                        texto_limpio = personalizar_texto_mensaje(contenido_base, est, padre, calificaciones, materias)
                        if archivo_path_manual:
                            contenido_final = f"{texto_limpio}\n\n---ARCHIVO_ADJUNTO---{archivo_path_manual}"
                        else:
                            contenido_final = texto_limpio
                else:
                    contenido_final = contenido_base
                
                msg = Mensaje(
                    destinatario=padre.nombres if padre else 'Padre de Familia',
                    estudiante_id=int(estudiante_id) if estudiante_id else None,
                    telefono=padre.telefono1 if padre else 'Sin teléfono',
                    tipo_mensaje=tipo_mensaje,
                    contenido=contenido_final,
                    remitente='Colegio'
                )
                db.session.add(msg)
                db.session.commit()
                flash('✅ Mensaje enviado correctamente.', 'success')

            return redirect(url_for('chat.index'))

        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")
            flash(f'❌ Error al enviar: {str(e)}', 'danger')

    estudiantes = Estudiante.query.filter_by(estado='Activo').order_by(Estudiante.apellidos).all()
    cursos = db.session.query(Estudiante.curso).filter_by(estado='Activo').distinct().order_by(Estudiante.curso).all()
    cursos = [c[0] for c in cursos]
    
    return render_template('chat/enviar.html',
                           estudiantes=estudiantes,
                           cursos=cursos,
                           plantillas=obtener_plantillas())

# =========================================================================
# ENVIAR MENSAJE RÁPIDO DESDE VENTANA DE CHAT (conversacion.html)
# =========================================================================
@chat_bp.route('/enviar_mensaje/<int:estudiante_id>', methods=['POST'])
def enviar_mensaje(estudiante_id):
    try:
        estudiante = Estudiante.query.get_or_404(estudiante_id)
        padre = Padre.query.filter_by(estudiante_id=estudiante_id).first()
        contenido_base = request.form.get('contenido', '').strip()
        
        archivo_path_manual = None
        if 'archivo' in request.files:
            file = request.files['archivo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"chat_{int(datetime.now().timestamp())}_{file.filename}")
                base_upload = current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads")
                upload_folder = os.path.join(base_upload, 'chat')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                archivo_path_manual = f"uploads/chat/{filename}"
        
        texto_limpio = personalizar_texto_mensaje(contenido_base, estudiante, padre)
        
        if archivo_path_manual:
            contenido_final = f"{texto_limpio}\n\n---ARCHIVO_ADJUNTO---{archivo_path_manual}"
        else:
            contenido_final = texto_limpio
            
        msg = Mensaje(
            destinatario=padre.nombres if padre else 'Padre de Familia',
            estudiante_id=estudiante.id,
            telefono=padre.telefono1 or 'Sin teléfono',
            tipo_mensaje='General',
            contenido=contenido_final,
            remitente='Colegio'
        )
        db.session.add(msg)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al enviar mensaje: {e}', 'danger')
        
    return redirect(url_for('chat.conversacion', estudiante_id=estudiante_id))

# =========================================================================
# API: OBTENER DATOS DEL ESTUDIANTE PARA PLANTILLA (CON CORTE FINANCIERO)
# =========================================================================
@chat_bp.route('/api/datos_estudiante/<int:id>')
def api_datos_estudiante(id):
    est = Estudiante.query.get(id)
    if not est:
        return jsonify({'error': 'Estudiante no encontrado'}), 404
    
    padre = Padre.query.filter_by(estudiante_id=id).first()
    
    ahora = ahora_bolivia()
    anio_actual = ahora.year
    mes_actual_num = ahora.month
    corte = obtener_corte_operativo()
    pension_base = float(est.pension or 0.0)

    mes_inicio_exigible = 2
    if corte:
        if anio_actual < corte.year:
            mes_inicio_exigible = 13
        elif anio_actual == corte.year:
            mes_inicio_exigible = corte.month
        else:
            mes_inicio_exigible = 2

    meses_exigibles = [
        m for m in MESES_ORDEN
        if mes_inicio_exigible <= MESES_ESCOLARES_MAP.get(m.lower(), 12) <= mes_actual_num
    ]
    
    pagos_est = Pago.query.filter_by(estudiante_id=id, anio=anio_actual).all()
    pagos_map = {p.mes.strip().title(): p for p in pagos_est if p.mes}
    
    monto_mora = 0.0
    meses_adeudados = []
    
    if pension_base > 0 and meses_exigibles:
        for mes in meses_exigibles:
            if mes in pagos_map:
                p = pagos_map[mes]
                if p.estado != 'Pagado':
                    saldo_mes = float(p.monto_total or pension_base) - float(p.descuento or 0.0) - float(p.monto_pagado or 0.0)
                    if saldo_mes > 0:
                        monto_mora += saldo_mes
                        meses_adeudados.append(mes)
            else:
                monto_mora += pension_base
                meses_adeudados.append(mes)
                
    meses_pendientes = ', '.join(meses_adeudados)
    
    return jsonify({
        'tutor': padre.nombres if padre else 'Padre de Familia',
        'estudiante': f"{est.nombres} {est.apellidos}",
        'curso': est.curso or 'S/C',
        'telefono': padre.telefono1 if padre else '',
        'mes': meses_pendientes or 'Ninguno',
        'monto': f"{monto_mora:.2f}" if monto_mora > 0 else '0.00',
        'fecha': ahora.strftime('%d/%m/%Y'),
        'hora': ahora.strftime('%H:%M'),
        'gestion': anio_actual,
        'promedio': "Ver PDF oficial",
        'materias_aprobadas': "Ver PDF oficial",
        'materias_reprobadas': "Ver PDF oficial",
        'mejor_materia': "Ver PDF oficial",
        'nota_mejor': "Ver PDF oficial"
    })

# ==============================================================================
# DESCARGAR / VISUALIZAR ARCHIVO ADJUNTO DE UN MENSAJE DEL CHAT
# ==============================================================================
@chat_bp.route('/adjunto/<int:mensaje_id>/descargar')
def descargar_adjunto(mensaje_id):
    mensaje = Mensaje.query.get_or_404(mensaje_id)

    ruta_adjunto, _ = extraer_adjunto(mensaje.contenido)

    if not ruta_adjunto:
        flash('❌ Este mensaje no tiene archivo adjunto.', 'warning')
        return redirect(url_for('chat.index'))

    filepath = ruta_local_segura(ruta_adjunto)

    if not filepath:
        flash('❌ El archivo adjunto no existe físicamente en el servidor.', 'danger')
        return redirect(url_for('chat.index'))

    nombre_archivo = os.path.basename(filepath)

    if nombre_archivo.lower().endswith('.pdf'):
        mimetype = 'application/pdf'
        return send_file(
            filepath,
            mimetype=mimetype,
            as_attachment=False,
            download_name=nombre_archivo
        )
    else:
        return send_file(
            filepath,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=nombre_archivo
        )

# =========================================================================
# ELIMINAR MENSAJE
# =========================================================================
@chat_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar(id):
    try:
        mensaje = Mensaje.query.get_or_404(id)
        db.session.delete(mensaje)
        db.session.commit()
        flash('✅ Mensaje eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    return redirect(url_for('chat.index'))

# =========================================================================
# CONVERSACIÓN CON ESTUDIANTE
# =========================================================================
@chat_bp.route('/conversacion/<int:estudiante_id>')
def conversacion(estudiante_id):
    estudiante = Estudiante.query.get_or_404(estudiante_id)
    padre = Padre.query.filter_by(estudiante_id=estudiante_id).first()
    mensajes = Mensaje.query.filter_by(estudiante_id=estudiante_id).order_by(Mensaje.fecha_envio.asc()).all()
    return render_template('chat/conversacion.html', estudiante=estudiante, padre=padre, mensajes=mensajes)
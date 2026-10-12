# -*- coding: utf-8 -*-
# ==============================================================================
# Archivo: routes/mensajes.py
# Proyecto: Sistema de Gestión Escolar
# Desarrollado por: Avrora Soft - Vibola LLC
# Descripción: Centro de Comunicaciones INTERNAS (SIN WhatsApp)
#              - Detección precisa de mora respetando el Corte Operativo / Financiero.
#              - Blindaje contra meses previos al corte y meses futuros.
#              - Nombre institucional 100% dinámico y genérico.
# ==============================================================================

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from models import db, Mensaje, Estudiante, Padre, Pago, Calificacion, Materia, ConfiguracionSuperadmin
from sqlalchemy import or_
from datetime import datetime, timedelta, date

mensajes_bp = Blueprint('mensajes', __name__, template_folder='templates/mensajes')

MESES_ESCOLARES = ['Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre']

MES_A_NUMERO = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
}

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

def obtener_datos_tutor(estudiante):
    """Obtiene el nombre y teléfono del tutor del estudiante."""
    padre = Padre.query.filter_by(estudiante_id=estudiante.id).first()
    if not padre:
        return "Padre/Madre de Familia", None
    nombre_tutor = padre.nombres.upper() if padre.nombres else "Padre de Familia"
    telefono = None
    for campo in ['telefono1', 'telefono2', 'telefono3', 'telefono4']:
        if hasattr(padre, campo):
            valor = getattr(padre, campo)
            if valor and str(valor).strip():
                telefono = str(valor).strip()
                break
    return nombre_tutor, telefono

# =========================================================================
# CENTRO DE COMUNICACIONES (LISTADO)
# =========================================================================
@mensajes_bp.route('/')
def centro_mensajes():
    """Muestra el historial de todos los mensajes enviados."""
    mensajes = Mensaje.query.order_by(Mensaje.fecha_envio.desc()).limit(100).all()
    return render_template('mensajes/centro.html', mensajes=mensajes)

# =========================================================================
# ENVIAR NUEVO MENSAJE (FORMULARIO)
# =========================================================================
@mensajes_bp.route('/enviar', methods=['GET', 'POST'])
def enviar_mensaje():
    """Formulario para redactar y enviar un nuevo mensaje interno."""
    if request.method == 'POST':
        try:
            destinatario = request.form.get('destinatario', '').strip()
            telefono = request.form.get('telefono', '').strip()
            tipo_mensaje = request.form.get('tipo_mensaje', 'General').strip()
            contenido = request.form.get('contenido', '').strip()
            
            if not destinatario or not contenido:
                flash('❌ Debe completar destinatario y contenido', 'danger')
                return redirect(url_for('mensajes.enviar_mensaje'))
            
            nuevo = Mensaje(
                destinatario=destinatario,
                telefono=telefono or 'Sin teléfono',
                tipo_mensaje=tipo_mensaje,
                contenido=contenido,
                remitente='Colegio'
            )
            db.session.add(nuevo)
            db.session.commit()
            
            flash('✅ Mensaje registrado exitosamente en el sistema interno.', 'success')
            return redirect(url_for('mensajes.centro_mensajes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al registrar: {str(e)}', 'danger')
    
    return render_template('mensajes/enviar.html')

# =========================================================================
# ELIMINAR MENSAJE
# =========================================================================
@mensajes_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_mensaje(id):
    """Elimina un mensaje del historial."""
    try:
        mensaje = Mensaje.query.get_or_404(id)
        db.session.delete(mensaje)
        db.session.commit()
        flash('✅ Mensaje eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    return redirect(url_for('mensajes.centro_mensajes'))

# =========================================================================
# API: BUSCAR ESTUDIANTES (para autocompletar)
# =========================================================================
@mensajes_bp.route('/api/buscar')
def buscar_estudiantes():
    """API para buscar estudiantes por RUDE, apellido o nombre."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []})
    
    resultados = Estudiante.query.filter(
        Estudiante.estado == 'Activo',
        or_(
            Estudiante.rude.ilike(f'%{query}%'),
            Estudiante.apellidos.ilike(f'%{query}%'),
            Estudiante.nombres.ilike(f'%{query}%'),
            Estudiante.curso.ilike(f'%{query}%')
        )
    ).limit(20).all()
    
    data = [{'id': e.id, 'text': f"RUDE: {e.rude} | {e.apellidos}, {e.nombres} - {e.curso}"} for e in resultados]
    return jsonify({'results': data})

# =========================================================================
# API: VISTA PREVIA DE PLANTILLA OFICIAL (SIN WhatsApp)
# =========================================================================
@mensajes_bp.route('/api/vista_previa')
def vista_previa():
    """Genera la vista previa de un mensaje oficial según el tipo seleccionado."""
    estudiante_id = request.args.get('estudiante_id')
    tipo = request.args.get('tipo_mensaje')
    
    if not estudiante_id or not tipo:
        return jsonify({'error': 'Seleccione estudiante y tipo de mensaje'}), 400
    
    estudiante = Estudiante.query.get(estudiante_id)
    if not estudiante:
        return jsonify({'error': 'Estudiante no encontrado'}), 404
    
    nombre_tutor, telefono_raw = obtener_datos_tutor(estudiante)
    telefono = telefono_raw or 'Sin teléfono registrado'
    
    inst_nombre = obtener_nombre_institucion().upper()
    
    datos = {
        'tutor': nombre_tutor,
        'estudiante': f"{estudiante.nombres} {estudiante.apellidos}",
        'curso': estudiante.curso,
        'gestion': datetime.now().year,
        'fecha': request.args.get('fecha_citacion', (datetime.now() + timedelta(days=2)).strftime('%d/%m/%Y')),
        'hora': request.args.get('hora_citacion', '18:00'),
        'lugar': 'Salón de Usos Múltiples',
        'motivo': request.args.get('motivo', 'Seguimiento académico y disciplinario'),
    }
    
    header = f"{inst_nombre}\nDirección Administrativa y Académica\nComunicado Oficial | Sistema Académico\n" + "="*40 + "\n\n"
    footer = "\n" + "="*40 + f"\nAtentamente,\nLA DIRECCIÓN\n{inst_nombre}\nMensaje generado automáticamente por el Sistema de Gestión Escolar."
    
    contenido_msg = ""
    
    if tipo == 'Citacion':
        contenido_msg = (f"{header}"
            f"CITACIÓN OFICIAL A REUNIÓN DE PADRES DE FAMILIA\n\n"
            f"De nuestra mayor consideración:\n\n"
            f"Por medio de la presente, la Dirección se dirige a usted, Sr./Sra. {datos['tutor']}, para citarle a una reunión de carácter OBLIGATORIO.\n\n"
            f"Estudiante: {datos['estudiante']}\n"
            f"Fecha: {datos['fecha']}\n"
            f"Hora: {datos['hora']}\n"
            f"Lugar: {datos['lugar']}\n"
            f"Orden del Día: {datos['motivo']}\n\n"
            f"Su asistencia es indispensable.\n\n"
            f"Sin otro particular, saludamos a usted atentamente.{footer}")
    
    elif tipo == 'RecordatorioPago':
        corte = obtener_corte_operativo()
        pagos_pendientes = Pago.query.filter_by(estudiante_id=estudiante.id, estado='Pendiente').all()
        pago_exigible = None
        for p in pagos_pendientes:
            num_m = MES_A_NUMERO.get(str(p.mes).strip().lower(), 0)
            anio_p = int(p.anio or datetime.now().year)
            if corte:
                if (anio_p > corte.year) or (anio_p == corte.year and num_m >= corte.month):
                    pago_exigible = p
                    break
            else:
                pago_exigible = p
                break

        datos['mes'] = pago_exigible.mes if pago_exigible else 'Pendiente'
        datos['monto'] = f"{pago_exigible.monto_total:.2f}" if pago_exigible else '0.00'
        contenido_msg = (f"{header}"
            f"RECORDATORIO AMISTOSO DE PAGO DE PENSIÓN\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"Reciba un cordial y respetuoso saludo de parte de la Dirección.\n\n"
            f"Por medio de la presente, queremos recordarle amablemente que el/la estudiante {datos['estudiante']} del curso {datos['curso']} tiene pendiente el pago de la pensión correspondiente al mes de {datos['mes']} de la gestión {datos['gestion']}.\n\n"
            f"Monto pendiente: Bs. {datos['monto']}\n\n"
            f"Le solicitamos realizar el pago a la brevedad posible en la oficina de Administración.\n\n"
            f"Atentamente,\nDEPARTAMENTO DE ADMINISTRACIÓN\n{inst_nombre}{footer}")
    
    elif tipo == 'ComprobantePago':
        pago = Pago.query.filter_by(estudiante_id=estudiante.id, estado='Pagado').order_by(Pago.fecha_pago.desc()).first()
        datos['mes'] = pago.mes if pago else 'Pagado'
        datos['monto'] = f"{pago.monto_pagado:.2f}" if pago else '0.00'
        datos['fecha_pago'] = pago.fecha_pago.strftime('%d/%m/%Y') if pago and pago.fecha_pago else datetime.now().strftime('%d/%m/%Y')
        contenido_msg = (f"{header}"
            f"COMPROBANTE OFICIAL DE PAGO\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"El Departamento de Administración confirma la recepción exitosa del pago realizado por concepto de pensión escolar.\n\n"
            f"DETALLE DEL COMPROBANTE:\n"
            f"Estudiante: {datos['estudiante']}\n"
            f"Curso: {datos['curso']}\n"
            f"Mes correspondiente: {datos['mes']}\n"
            f"Gestión: {datos['gestion']}\n"
            f"Monto cancelado: Bs. {datos['monto']}\n"
            f"Fecha de transacción: {datos['fecha_pago']}\n\n"
            f"Este mensaje tiene validez como comprobante de pago.\n\n"
            f"Atentamente,\nLA DIRECCIÓN ADMINISTRATIVA\n{inst_nombre}{footer}")
    
    elif tipo == 'Inasistencia':
        datos['fecha'] = request.args.get('fecha_falta', datetime.now().strftime('%d/%m/%Y'))
        contenido_msg = (f"{header}"
            f"COMUNICADO DE INASISTENCIA INJUSTIFICADA\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"La Dirección le informa que el/la estudiante {datos['estudiante']} del curso {datos['curso']} ha registrado inasistencia a clases el día {datos['fecha']} sin la debida justificación.\n\n"
            f"Le solicitamos:\n"
            f"1. Presentar la justificación correspondiente en la oficina de Dirección dentro de las 48 horas hábiles.\n"
            f"2. Coordinar una reunión con el asesor/profesor del curso.\n\n"
            f"Atentamente,{footer}")
    
    elif tipo == 'FaltaAsistencia':
        datos['cantidad_faltas'] = request.args.get('cantidad_faltas', '3')
        datos['periodo'] = request.args.get('periodo', 'Primer Trimestre')
        contenido_msg = (f"{header}"
            f"COMUNICADO FORMAL DE FALTA DE ASISTENCIA\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"La Dirección, en cumplimiento del Reglamento Interno, le notifica formalmente que el/la estudiante {datos['estudiante']} del curso {datos['curso']} ha acumulado {datos['cantidad_faltas']} falta(s) de asistencia durante el periodo {datos['periodo']}, sin la debida justificación.\n\n"
            f"Detalle de inasistencias:\n"
            f"- Total de faltas: {datos['cantidad_faltas']}\n"
            f"- Periodo registrado: {datos['periodo']}\n"
            f"- Estado: Sin justificar\n\n"
            f"Consecuencias según Reglamento:\n"
            f"1. Las inasistencias injustificadas reiteradas comprometen el seguimiento académico regular.\n"
            f"2. Se requiere presentación de certificado médico o justificativo válido dentro del plazo reglamentario.\n"
            f"3. De persistir la situación, se convocará a reunión con el área correspondiente.\n\n"
            f"Le solicitamos coordinar una reunión con la Dirección para tratar esta situación.\n\n"
            f"Atentamente,{footer}")
    
    elif tipo == 'Felicitacion':
        calificaciones = Calificacion.query.filter_by(estudiante_id=estudiante.id).all()
        if calificaciones:
            mejor_cal = max(calificaciones, key=lambda c: getattr(c, 'nota', 0) or 0)
            materia_obj = Materia.query.get(mejor_cal.materia_id) if hasattr(mejor_cal, 'materia_id') else None
            notas_validas = [float(c.nota) for c in calificaciones if getattr(c, 'nota', None) is not None]
            datos['promedio'] = f"{sum(notas_validas)/len(notas_validas):.2f}" if notas_validas else 'N/A'
            datos['materia_destacada'] = materia_obj.nombre if materia_obj else 'N/A'
            datos['nota_destacada'] = f"{mejor_cal.nota}"
        else:
            datos['promedio'] = 'N/A'
            datos['materia_destacada'] = 'N/A'
            datos['nota_destacada'] = 'N/A'
        contenido_msg = (f"{header}"
            f"COMUNICADO DE FELICITACIÓN Y RECONOCIMIENTO\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"Es un honor para la Dirección expresarle nuestras más sinceras felicitaciones por el excelente desempeño académico de su hijo/a {datos['estudiante']} del curso {datos['curso']}.\n\n"
            f"Logros destacados:\n"
            f"- Promedio general: {datos['promedio']}\n"
            f"- Materia destacada: {datos['materia_destacada']}\n"
            f"- Calificación obtenida: {datos['nota_destacada']}\n\n"
            f"Con admiración y respeto,{footer}")
    
    elif tipo == 'Boletin':
        ahora = datetime.now()
        anio_actual = ahora.year
        mes_num_actual = ahora.month
        corte = obtener_corte_operativo()
        pension_valor = float(getattr(estudiante, 'pension', 0) or 0)

        # Determinar el mes inicial de exigibilidad respetando el corte operativo
        mes_inicio_exigible = 2  # Febrero por defecto
        if corte:
            if anio_actual < corte.year:
                # La gestión completa es anterior al corte: no hay exigibilidad de mora
                mes_inicio_exigible = 13
            elif anio_actual == corte.year:
                mes_inicio_exigible = corte.month
            else:
                mes_inicio_exigible = 2

        # Meses escolares transcurridos y exigibles (no incluye meses futuros ni meses antes del corte)
        meses_exigibles = [
            m for m in MESES_ESCOLARES
            if mes_inicio_exigible <= MES_A_NUMERO.get(m.lower(), 12) <= mes_num_actual
        ]

        pagos = Pago.query.filter_by(estudiante_id=estudiante.id, anio=anio_actual).all()
        meses_pagados = [p.mes.strip().title() for p in pagos if p.estado == 'Pagado']

        meses_pendientes = []
        if pension_valor > 0 and meses_exigibles:
            meses_pendientes = [m for m in meses_exigibles if m not in meses_pagados]

        total_pendiente = 0.0
        for p in pagos:
            num_mes_pago = MES_A_NUMERO.get(p.mes.strip().lower(), 12)
            if p.estado != 'Pagado' and (mes_inicio_exigible <= num_mes_pago <= mes_num_actual):
                total_pendiente += (p.monto_total - (p.descuento or 0)) - p.monto_pagado

        if not total_pendiente and meses_pendientes:
            total_pendiente = len(meses_pendientes) * pension_valor

        # Solo se retiene si existe deuda real en meses exigibles posteriores al corte
        if meses_pendientes and total_pendiente > 0:
            datos['meses_pendientes'] = ', '.join(meses_pendientes)
            datos['total_pendiente'] = f"{total_pendiente:.2f}"
            contenido_msg = (f"{header}"
                f"AVISO IMPORTANTE: BOLETÍN RETENIDO POR DEUDA PENDIENTE\n\n"
                f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
                f"Por medio de la presente, el Departamento de Administración le informa que el Boletín de Calificaciones del estudiante {datos['estudiante']} se encuentra RETENIDO debido a que presenta cuotas vencidas pendientes de regularización.\n\n"
                f"Meses vencidos pendientes: {datos['meses_pendientes']}\n"
                f"Monto total vencido: Bs. {datos['total_pendiente']}\n\n"
                f"Para poder recibir el Boletín de Calificaciones, solicitamos ponerse al día con las cuotas vencidas en la oficina de Administración.\n\n"
                f"Atentamente,\nLA DIRECCIÓN\n{inst_nombre}{footer}")
        else:
            calificaciones = Calificacion.query.filter_by(estudiante_id=estudiante.id).all()
            promedios = []
            for mat in Materia.query.filter_by(curso_id=estudiante.curso).all():
                notas = [float(c.nota) for c in calificaciones if c.materia_id == mat.id and getattr(c, 'nota', None) is not None]
                if notas:
                    promedios.append(sum(notas)/len(notas))
            datos['promedio'] = f"{sum(promedios)/len(promedios):.2f}" if promedios else "N/A"
            contenido_msg = (f"{header}"
                f"NOTIFICACIÓN DE DISPONIBILIDAD DE BOLETÍN DE CALIFICACIONES\n\n"
                f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
                f"Reciba un cordial saludo. Tenemos el agrado de informarle que el Boletín de Calificaciones de la gestión {datos['gestion']} del estudiante {datos['estudiante']} ya se encuentra disponible.\n\n"
                f"Promedio General Ponderado: {datos['promedio']}\n\n"
                f"Le invitamos a revisar detalladamente el informe académico en el portal o descargar el documento adjunto.\n\n"
                f"Sin otro particular, quedamos a su disposición.{footer}")
    
    else:
        contenido_msg = "Tipo de mensaje no reconocido."
    
    return jsonify({
        'contenido': contenido_msg,
        'telefono': telefono,
        'destinatario': nombre_tutor
    })

# =========================================================================
# API: GUARDAR MENSAJE GENERADO
# =========================================================================
@mensajes_bp.route('/api/guardar', methods=['POST'])
def guardar_mensaje_api():
    """Guarda un mensaje generado desde la vista previa en la base de datos."""
    data = request.json
    try:
        nuevo = Mensaje(
            destinatario=data['destinatario'],
            telefono=data.get('telefono', 'Sin teléfono'),
            tipo_mensaje=data['tipo'],
            contenido=data['contenido'],
            remitente='Colegio'
        )
        db.session.add(nuevo)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
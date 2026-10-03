# -*- coding: utf-8 -*-
# ==============================================================================
# Archivo: routes/mensajes.py
# Proyecto: Sistema de Gestión Escolar - Colegio Dr. Antonio Vaca Díez
# Desarrollado por: Avrora Soft - Vibola LLC
# Descripción: Centro de Comunicaciones INTERNAS (SIN WhatsApp)
# ==============================================================================

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from models import db, Mensaje, Estudiante, Padre, Pago, Calificacion, Materia
from sqlalchemy import or_
from datetime import datetime, timedelta

mensajes_bp = Blueprint('mensajes', __name__, template_folder='templates/mensajes')

MESES_ESCOLARES = ['Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre']

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
    
    header = "COLEGIO DR. ANTONIO VACA DIEZ\nDireccion Administrativa y Academica\nComunicado Oficial | Sistema Avrora Soft\n" + "="*40 + "\n\n"
    footer = "\n" + "="*40 + "\nAtentamente,\nLA DIRECCION DEL COLEGIO\nRiberalta, Beni, Bolivia\nMensaje generado automaticamente por el Sistema de Gestion Escolar."
    
    contenido_msg = ""
    
    if tipo == 'Citacion':
        contenido_msg = (f"{header}"
            f"CITACION OFICIAL A REUNION DE PADRES DE FAMILIA\n\n"
            f"De nuestra mayor consideracion:\n\n"
            f"Por medio de la presente, la Direccion del Colegio Dr. Antonio Vaca Diez se dirige a usted, Sr./Sra. {datos['tutor']}, para citarle a una reunion de caracter OBLIGATORIO.\n\n"
            f"Estudiante: {datos['estudiante']}\n"
            f"Fecha: {datos['fecha']}\n"
            f"Hora: {datos['hora']}\n"
            f"Lugar: {datos['lugar']}\n"
            f"Orden del Dia: {datos['motivo']}\n\n"
            f"Su asistencia es indispensable.\n\n"
            f"Sin otro particular, saludamos a usted atentamente.{footer}")
    
    elif tipo == 'RecordatorioPago':
        pago = Pago.query.filter_by(estudiante_id=estudiante.id, estado='Pendiente').first()
        datos['mes'] = pago.mes if pago else 'Pendiente'
        datos['monto'] = f"{pago.monto_total:.2f}" if pago else '0.00'
        contenido_msg = (f"{header}"
            f"RECORDATORIO AMISTOSO DE PAGO DE PENSION\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"Reciba un cordial y respetuoso saludo de parte de la Direccion del Colegio Dr. Antonio Vaca Diez.\n\n"
            f"Por medio de la presente, queremos recordarle amablemente que el/la estudiante {datos['estudiante']} del curso {datos['curso']} tiene pendiente el pago de la pension correspondiente al mes de {datos['mes']} de la gestion {datos['gestion']}.\n\n"
            f"Monto pendiente: Bs. {datos['monto']}\n\n"
            f"Le solicitamos realizar el pago a la brevedad posible en la oficina de Administracion (horario: 8:00 a 12:00 y 14:00 a 18:00).\n\n"
            f"Atentamente,\nDEPARTAMENTO DE ADMINISTRACION\nColegio Dr. Antonio Vaca Diez{footer}")
    
    elif tipo == 'ComprobantePago':
        pago = Pago.query.filter_by(estudiante_id=estudiante.id, estado='Pagado').order_by(Pago.fecha_pago.desc()).first()
        datos['mes'] = pago.mes if pago else 'Pagado'
        datos['monto'] = f"{pago.monto_pagado:.2f}" if pago else '0.00'
        datos['fecha_pago'] = pago.fecha_pago.strftime('%d/%m/%Y') if pago and pago.fecha_pago else datetime.now().strftime('%d/%m/%Y')
        contenido_msg = (f"{header}"
            f"COMPROBANTE OFICIAL DE PAGO\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"El Departamento de Administracion del Colegio Dr. Antonio Vaca Diez confirma la recepcion exitosa del pago realizado por concepto de pension escolar.\n\n"
            f"DETALLE DEL COMPROBANTE:\n"
            f"Estudiante: {datos['estudiante']}\n"
            f"Curso: {datos['curso']}\n"
            f"Mes correspondiente: {datos['mes']}\n"
            f"Gestion: {datos['gestion']}\n"
            f"Monto cancelado: Bs. {datos['monto']}\n"
            f"Fecha de transaccion: {datos['fecha_pago']}\n\n"
            f"Este mensaje tiene validez como comprobante de pago.\n\n"
            f"Atentamente,\nLA DIRECCION ADMINISTRATIVA\nColegio Dr. Antonio Vaca Diez{footer}")
    
    elif tipo == 'Inasistencia':
        datos['fecha'] = request.args.get('fecha_falta', datetime.now().strftime('%d/%m/%Y'))
        contenido_msg = (f"{header}"
            f"COMUNICADO DE INASISTENCIA INJUSTIFICADA\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"La Direccion del Colegio Dr. Antonio Vaca Diez le informa que el/la estudiante {datos['estudiante']} del curso {datos['curso']} ha registrado inasistencia a clases el dia {datos['fecha']} sin la debida justificacion.\n\n"
            f"Le solicitamos:\n"
            f"1. Presentar la justificacion correspondiente en la oficina de Direccion dentro de las 48 horas habiles.\n"
            f"2. Coordinar una reunion con el tutor del curso.\n\n"
            f"Atentamente,{footer}")
    
    elif tipo == 'FaltaAsistencia':
        datos['cantidad_faltas'] = request.args.get('cantidad_faltas', '3')
        datos['periodo'] = request.args.get('periodo', 'Primer Bimestre')
        contenido_msg = (f"{header}"
            f"COMUNICADO FORMAL DE FALTA DE ASISTENCIA\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"La Direccion del Colegio Dr. Antonio Vaca Diez, en cumplimiento del Reglamento Interno, le notifica formalmente que el/la estudiante {datos['estudiante']} del curso {datos['curso']} ha acumulado {datos['cantidad_faltas']} falta(s) de asistencia durante el periodo {datos['periodo']}, sin la debida justificacion.\n\n"
            f"Detalle de inasistencias:\n"
            f"- Total de faltas: {datos['cantidad_faltas']}\n"
            f"- Periodo registrado: {datos['periodo']}\n"
            f"- Estado: Sin justificar\n\n"
            f"Consecuencias segun Reglamento:\n"
            f"1. Las inasistencias injustificadas superiores a 3 en un bimestre comprometen la aprobacion de la materia.\n"
            f"2. Se requiere presentacion de certificado medico o documento valido dentro de las 48 horas habiles.\n"
            f"3. De persistir la situacion, se convocara a reunion con el Departamento de Consejeria Estudiantil.\n\n"
            f"Le solicitamos coordinar una reunion urgente con la Direccion para tratar esta situacion.\n\n"
            f"Atentamente,{footer}")
    
    elif tipo == 'Felicitacion':
        calificaciones = Calificacion.query.filter_by(estudiante_id=estudiante.id).all()
        if calificaciones:
            mejor_cal = max(calificaciones, key=lambda c: c.nota)
            materia_obj = Materia.query.get(mejor_cal.materia_id)
            datos['promedio'] = f"{sum(c.nota for c in calificaciones)/len(calificaciones):.2f}"
            datos['materia_destacada'] = materia_obj.nombre if materia_obj else 'N/A'
            datos['nota_destacada'] = f"{mejor_cal.nota}"
        else:
            datos['promedio'] = 'N/A'
            datos['materia_destacada'] = 'N/A'
            datos['nota_destacada'] = 'N/A'
        contenido_msg = (f"{header}"
            f"COMUNICADO DE FELICITACION Y RECONOCIMIENTO\n\n"
            f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
            f"Es un honor para la Direccion del Colegio Dr. Antonio Vaca Diez expresarle nuestras mas sinceras felicitaciones por el excelente desempeno academico de su hijo/a {datos['estudiante']} del curso {datos['curso']}.\n\n"
            f"Logros destacados:\n"
            f"- Promedio general: {datos['promedio']}\n"
            f"- Materia destacada: {datos['materia_destacada']}\n"
            f"- Calificacion obtenida: {datos['nota_destacada']}\n\n"
            f"Con admiracion y respeto,{footer}")
    
    elif tipo == 'Boletin':
        anio_actual = datetime.now().year
        pagos = Pago.query.filter_by(estudiante_id=estudiante.id, anio=anio_actual).all()
        meses_pagados = [p.mes for p in pagos if p.estado == 'Pagado']
        meses_pendientes = [m for m in MESES_ESCOLARES if m not in meses_pagados]
        total_pendiente = sum((p.monto_total - (p.descuento or 0)) - p.monto_pagado for p in pagos if p.estado != 'Pagado')
        
        if meses_pendientes:
            datos['meses_pendientes'] = ', '.join(meses_pendientes)
            datos['total_pendiente'] = f"{total_pendiente:.2f}"
            contenido_msg = (f"{header}"
                f"AVISO IMPORTANTE: BOLETIN RETENIDO POR DEUDA PENDIENTE\n\n"
                f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
                f"Por medio de la presente, el Departamento de Administracion le informa que el Boletin de Calificaciones del estudiante {datos['estudiante']} se encuentra RETENIDO debido a que presenta meses de pension pendientes de pago.\n\n"
                f"Meses pendientes: {datos['meses_pendientes']}\n"
                f"Monto total de la deuda: Bs. {datos['total_pendiente']}\n\n"
                f"Para poder recibir el Boletin de Calificaciones, es requisito indispensable ponerse al dia con todas las cuotas pendientes.\n\n"
                f"Atentamente,\nLA DIRECCION DEL COLEGIO\nColegio Dr. Antonio Vaca Diez - Riberalta, Beni{footer}")
        else:
            calificaciones = Calificacion.query.filter_by(estudiante_id=estudiante.id).all()
            promedios = []
            for mat in Materia.query.filter_by(curso_id=estudiante.curso).all():
                notas = [c.nota for c in calificaciones if c.materia_id == mat.id]
                if notas: promedios.append(sum(notas)/len(notas))
            datos['promedio'] = f"{sum(promedios)/len(promedios):.2f}" if promedios else "N/A"
            contenido_msg = (f"{header}"
                f"NOTIFICACION DE DISPONIBILIDAD DE BOLETIN DE CALIFICACIONES\n\n"
                f"Estimado/a Sr./Sra. {datos['tutor']}:\n\n"
                f"Reciba un cordial saludo. Tengo el agrado de informarle que el Boletin de Calificaciones de la gestion {datos['gestion']} del estudiante {datos['estudiante']} ya se encuentra disponible.\n\n"
                f"Promedio General Ponderado: {datos['promedio']}\n\n"
                f"Le rogamos descargar el documento, revisarlo detalladamente y firmar de conformidad.\n\n"
                f"Sin otro particular, quedamos a su disposicion.{footer}")
    
    else:
        contenido_msg = "Tipo de mensaje no reconocido."
    
    # SOLO devolver el contenido, SIN enlace de WhatsApp
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
            telefono=data.get('telefono', 'Sin telefono'),
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
# -*- coding: utf-8 -*-
# ==============================================================================
# Archivo: routes/faltas.py
# Proyecto: Sistema de Gestión Escolar
# Desarrollado por: Avrora Soft - Vibola LLC
# Descripción: Blueprint unificado para la gestión y administración de Asistencia
# ==============================================================================

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import db, Falta, Estudiante, Profesor, PersonalAdministrativo, Padre, Mensaje
from datetime import datetime
from werkzeug.utils import secure_filename

faltas_bp = Blueprint('faltas', __name__, template_folder='templates/faltas')

# =========================================================================
# LISTADO GENERAL DE ASISTENCIA (ADMINISTRATIVO)
# =========================================================================
@faltas_bp.route('/')
def lista_faltas():
    """Muestra el historial unificado de asistencia de estudiantes con filtros y paginación."""
    curso_filtro = request.args.get('curso', '')
    tipo_filtro = request.args.get('tipo', 'Todos')
    estado_filtro = request.args.get('estado', 'Todos')
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = 25

    query = Falta.query.filter(Falta.tipo_sujeto == 'Estudiante')

    if curso_filtro:
        estudiante_ids = [e.id for e in Estudiante.query.filter_by(curso=curso_filtro, estado='Activo').all()]
        query = query.filter(Falta.sujeto_id.in_(estudiante_ids))

    if tipo_filtro != 'Todos':
        query = query.filter(Falta.tipo_falta == tipo_filtro)

    if estado_filtro != 'Todos':
        query = query.filter(Falta.estado == estado_filtro)

    pagination = query.order_by(Falta.fecha.desc()).paginate(
        page=pagina, per_page=por_pagina, error_out=False
    )
    faltas = pagination.items

    ids = {f.sujeto_id for f in faltas}
    mapa = {}
    if ids:
        estudiantes = Estudiante.query.filter(Estudiante.id.in_(ids)).all()
        mapa = {e.id: f"{e.apellidos}, {e.nombres}" for e in estudiantes}

    for falta in faltas:
        falta.nombre_estudiante = mapa.get(falta.sujeto_id, f"ID: {falta.sujeto_id}")

    cursos = db.session.query(Estudiante.curso).filter_by(estado='Activo').distinct().all()
    cursos = [c[0] for c in cursos]

    return render_template('faltas/lista.html', faltas=faltas, cursos=cursos,
                         curso_actual=curso_filtro, tipo_actual=tipo_filtro,
                         estado_actual=estado_filtro, pagination=pagination)

# =========================================================================
# REGISTRAR ASISTENCIA / LICENCIA ADMINISTRATIVA
# =========================================================================
@faltas_bp.route('/nuevo', methods=['GET', 'POST'])
def nueva_falta():
    if request.method == 'POST':
        try:
            estudiante_id = int(request.form['estudiante_id'])
            est = Estudiante.query.get_or_404(estudiante_id)

            fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
            tipo_falta = request.form['tipo_falta']
            observaciones = request.form.get('observaciones', '')

            archivo_nombre = None
            if 'archivo' in request.files:
                archivo = request.files['archivo']
                if archivo and archivo.filename != '':
                    filename = secure_filename(f"asistencia_{estudiante_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.filename}")
                    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'faltas')
                    os.makedirs(upload_folder, exist_ok=True)
                    archivo.save(os.path.join(upload_folder, filename))
                    archivo_nombre = filename

            nueva = Falta(
                tipo_sujeto='Estudiante',
                sujeto_id=estudiante_id,
                rude_estudiante=est.rude,
                fecha=fecha,
                tipo_falta=tipo_falta,
                observaciones=observaciones,
                estado=tipo_falta,
                archivo_adjunto=archivo_nombre
            )
            db.session.add(nueva)
            db.session.commit()

            # Notificación automática al chat del padre
            try:
                padre = Padre.query.filter_by(estudiante_id=estudiante_id).first()
                nombre_tutor = padre.nombres if padre and padre.nombres else "Padre/Tutor"
                telefono = (padre.telefono1 or padre.telefono2) if padre else "Sin teléfono"
                nombre_estudiante = f"{est.nombres} {est.apellidos}"

                fecha_formato = fecha.strftime('%d/%m/%Y')
                contenido = (
                    f"ACTUALIZACIÓN DE ASISTENCIA - INSTITUCIÓN EDUCATIVA\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Estimado/a Sr./Sra. {nombre_tutor}:\n\n"
                    f"Le informamos sobre el registro de asistencia de {nombre_estudiante} para el día {fecha_formato}: *{tipo_falta}*.\n\n"
                    f"Observaciones: {observaciones or 'Ninguna'}\n\n"
                    f"Atentamente,\nLA DIRECCIÓN"
                )

                mensaje_interno = Mensaje(
                    destinatario=nombre_tutor,
                    estudiante_id=estudiante_id,
                    telefono=telefono,
                    tipo_mensaje=f'Asistencia {tipo_falta}',
                    contenido=contenido,
                    remitente='Institución'
                )
                db.session.add(mensaje_interno)
                db.session.commit()
            except Exception as msg_err:
                print(f"⚠️ Aviso: No se pudo generar el mensaje interno: {msg_err}")

            flash('✅ Registro de asistencia guardado y comunicado correctamente.', 'success')
            return redirect(url_for('faltas.lista_faltas'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al registrar: {str(e)}', 'danger')

    curso_filtro = request.args.get('curso', '')
    estudiantes = []
    if curso_filtro:
        estudiantes = Estudiante.query.filter_by(curso=curso_filtro, estado='Activo').order_by(Estudiante.apellidos).all()

    cursos = db.session.query(Estudiante.curso).filter_by(estado='Activo').distinct().all()
    cursos = [c[0] for c in cursos]

    return render_template('faltas/form.html', estudiantes=estudiantes, cursos=cursos,
                         curso_actual=curso_filtro, today=datetime.now().strftime('%Y-%m-%d'))

# =========================================================================
# EDITAR / JUSTIFICAR ASISTENCIA (EXCLUSIVO ADMINISTRACIÓN)
# =========================================================================
@faltas_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_falta(id):
    falta = Falta.query.get_or_404(id)
    estudiante_actual = Estudiante.query.get(falta.sujeto_id)

    if request.method == 'POST':
        try:
            falta.fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
            falta.tipo_falta = request.form['tipo_falta']
            falta.estado = 'Justificada' if falta.tipo_falta in ['Justificada', 'Licencia', 'Permiso', 'Falta Justificada'] else 'Injustificada'
            falta.observaciones = request.form.get('observaciones', '')

            if 'archivo' in request.files:
                archivo = request.files['archivo']
                if archivo and archivo.filename != '':
                    filename = secure_filename(f"asistencia_{falta.sujeto_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.filename}")
                    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'faltas')
                    os.makedirs(upload_folder, exist_ok=True)
                    archivo.save(os.path.join(upload_folder, filename))
                    falta.archivo_adjunto = filename

            db.session.commit()

            flash('✅ Registro de asistencia actualizado y justificado correctamente.', 'success')
            return redirect(url_for('faltas.lista_faltas'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al actualizar: {str(e)}', 'danger')

    cursos = db.session.query(Estudiante.curso).filter_by(estado='Activo').distinct().all()
    cursos = [c[0] for c in cursos]
    
    estudiantes = []
    if estudiante_actual and estudiante_actual.curso:
        estudiantes = Estudiante.query.filter_by(curso=estudiante_actual.curso, estado='Activo').order_by(Estudiante.apellidos).all()

    return render_template('faltas/form.html', falta=falta, estudiante_actual=estudiante_actual,
                         estudiantes=estudiantes, cursos=cursos, 
                         curso_actual=estudiante_actual.curso if estudiante_actual else '',
                         today=datetime.now().strftime('%Y-%m-%d'))

# =========================================================================
# ELIMINAR REGISTRO DE ASISTENCIA
# =========================================================================
@faltas_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_falta(id):
    falta = Falta.query.get_or_404(id)
    try:
        db.session.delete(falta)
        db.session.commit()
        flash('✅ Registro eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar: {str(e)}', 'danger')

    return redirect(url_for('faltas.lista_faltas'))

# =========================================================================
# REPORTE DE ASISTENCIA POR ESTUDIANTE
# =========================================================================
@faltas_bp.route('/reporte/<int:estudiante_id>')
def reporte_estudiante(estudiante_id):
    faltas = Falta.query.filter_by(sujeto_id=estudiante_id, tipo_sujeto='Estudiante').order_by(Falta.fecha.desc()).all()
    estudiante = Estudiante.query.get_or_404(estudiante_id)
    return render_template('faltas/reporte.html', faltas=faltas, estudiante=estudiante)

# =========================================================================
# MONITOR EXTERNO DE DIRECCIÓN (ASISTENCIAS + CUADRO DE HONOR + VALORES)
# =========================================================================
@faltas_bp.route('/monitor-direccion')
def monitor_direccion():
    """Pantalla pública en tiempo real para colocar fuera de dirección."""
    from datetime import date
    hoy = date.today()
    
    # 1. Ausencias del día (registradas como Falta Injustificada, Ausente o Falta)
    ausencias_hoy = Falta.query.filter(
        Falta.tipo_sujeto == 'Estudiante',
        Falta.fecha == hoy,
        Falta.tipo_falta.in_(['Falta Injustificada', 'Ausente', 'Falta'])
    ).all()
    
    est_ids = [a.sujeto_id for a in ausencias_hoy]
    estudiantes_ausentes = Estudiante.query.filter(Estudiante.id.in_(est_ids)).all() if est_ids else []
    mapa_est = {e.id: e for e in estudiantes_ausentes}
    
    lista_ausentes = []
    for aus in ausencias_hoy:
        est = mapa_est.get(aus.sujeto_id)
        if est:
            lista_ausentes.append({
                'apellidos': est.apellidos,
                'nombres': est.nombres,
                'curso': est.curso
            })

    # Ordenar ausentes por curso y apellido
    lista_ausentes = sorted(lista_ausentes, key=lambda x: (x['curso'], x['apellidos']))

    return render_template(
        'faltas/monitor.html',
        ausentes=lista_ausentes,
        fecha_hoy=hoy.strftime('%d/%m/%Y')
    )
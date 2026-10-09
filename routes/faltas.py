# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/faltas.py
Proyecto: ASestud-Konetz / Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Panel Central Administrativo para el control de asistencias.
             Acceso libre a visualización, blindado con contraseña para modificaciones.
==============================================================================
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import func
from models import db, Asistencia, Estudiante, ControlAsistenciaDiaria, ConfiguracionSuperadmin, ahora_bolivia

faltas_bp = Blueprint('faltas', __name__, template_folder='templates/faltas')

# ==============================================================================
# SEGURIDAD ESTRICTA: CANDADO DE BÓVEDA OBLIGATORIO PARA ACCIONES DE ESCRITURA
# ==============================================================================
def boveda_requerida(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('faltas_boveda_abierta'):
            flash('🔒 Se requiere ingresar la contraseña de Bóveda para realizar esta modificación.', 'warning')
            return redirect(url_for('faltas.login_boveda', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# ACCESO A LA BÓVEDA DE ASISTENCIAS
# ==============================================================================
@faltas_bp.route('/boveda', methods=['GET', 'POST'])
def login_boveda():
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        # Centralización profesional: Prioriza la variable de entorno y usa respaldo de BD
        clave_boveda = os.getenv('BOVEDA_PASSWORD_MASTER')
        if not clave_boveda:
            config = ConfiguracionSuperadmin.query.filter_by(clave='superadmin_password').first()
            clave_boveda = config.valor if config and config.valor else 'admin2026'

        if password == clave_boveda:
            session['faltas_boveda_abierta'] = True
            flash('🔓 Acceso concedido: Bóveda de Asistencia desbloqueada.', 'success')
            
            siguiente = request.args.get('next') or url_for('faltas.index')
            if any(ruta in siguiente for ruta in ['/editar/', '/eliminar/', '/desbloquear']):
                siguiente = url_for('faltas.index')
                
            return redirect(siguiente)
        else:
            flash('❌ Contraseña de Bóveda incorrecta. Acceso denegado.', 'danger')
            
    return render_template('faltas/login_boveda.html')

@faltas_bp.route('/cerrar_boveda')
def cerrar_boveda():
    session.pop('faltas_boveda_abierta', None)
    flash('🔒 Bóveda de Asistencia cerrada por seguridad.', 'info')
    return redirect(url_for('dashboard.index'))

# ==============================================================================
# PANEL GLOBAL DE ASISTENCIAS (ACCESO LIBRE DE VISUALIZACIÓN)
# ==============================================================================
@faltas_bp.route('/')
def index():
    fecha_str = request.args.get('fecha', ahora_bolivia().strftime('%Y-%m-%d'))
    curso = request.args.get('curso', '').strip()
    
    turno = request.args.get('turno', 'Mañana').strip()
    if turno not in ['Mañana', 'Tarde']:
        turno = 'Mañana'
        
    solo_faltas = request.args.get('solo_faltas') 

    query = db.session.query(Asistencia, Estudiante).join(
        Estudiante, Asistencia.estudiante_id == Estudiante.id
    ).filter(
        db.func.date(Asistencia.fecha) == fecha_str,
        db.func.trim(db.func.lower(Estudiante.turno)) == turno.lower()
    )
    
    if curso:
        query = query.filter(func.lower(func.trim(Asistencia.curso)) == curso.lower())
        
    if solo_faltas:
        query = query.filter(Asistencia.estado == 'Falta')

    resultados = query.order_by(Asistencia.curso, Estudiante.apellidos).all()
    asistencias = [r[0] for r in resultados]

    controles = ControlAsistenciaDiaria.query.filter(db.func.date(ControlAsistenciaDiaria.fecha) == fecha_str).all()

    cursos_estandar = set()
    cursos_asistencia = db.session.query(Asistencia.curso).filter(Asistencia.curso != None).distinct().all()
    for c in cursos_asistencia:
        cursos_estandar.add(c[0].strip())
        
    cursos_db = db.session.query(Estudiante.curso).filter(Estudiante.estado == 'Activo', Estudiante.curso != None).distinct().all()
    for c in cursos_db:
        nombre = c[0].strip().upper().replace(' DE ', ' ')
        partes = nombre.split()
        clean_partes = []
        for p in partes:
            if len(p) == 1 and p in 'ABCDEFGH':
                clean_partes.append(p)
            else:
                clean_partes.append(p.capitalize())
        cursos_estandar.add(" ".join(clean_partes))

    return render_template(
        'faltas/index.html', 
        asistencias=asistencias, 
        fecha_str=fecha_str, 
        curso_seleccionado=curso, 
        turno_seleccionado=turno,
        solo_faltas=solo_faltas,
        cursos=sorted(list(cursos_estandar)), 
        controles=controles
    )

# ==============================================================================
# EDITAR / JUSTIFICAR ASISTENCIA Y SUBIR ARCHIVO A C:\ASestud\uploads (PROTEGIDO)
# ==============================================================================
@faltas_bp.route('/editar/<int:id>', methods=['POST'])
@boveda_requerida
def editar(id):
    asistencia = Asistencia.query.get_or_404(id)
    nuevo_estado = request.form.get('estado', asistencia.estado)
    nueva_obs = request.form.get('observacion', asistencia.observacion)
    
    asistencia.estado = nuevo_estado
    asistencia.observacion = nueva_obs
    
    if 'documento' in request.files:
        file = request.files['documento']
        if file and file.filename != '':
            filename = secure_filename(f"justificativo_{asistencia.id}_{file.filename}")
            
            # Usar la ruta absoluta centralizada en C:\ASestud\uploads
            base_upload = current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads")
            upload_folder = os.path.join(base_upload, 'justificaciones')
            os.makedirs(upload_folder, exist_ok=True)
            
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            asistencia.archivo_adjunto = f"justificaciones/{filename}"
    
    try:
        db.session.commit()
        flash('✅ Registro de asistencia actualizado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al actualizar: {str(e)}', 'danger')
        
    return redirect(request.referrer or url_for('faltas.index'))

# ==============================================================================
# ELIMINAR ASISTENCIA (PROTEGIDO)
# ==============================================================================
@faltas_bp.route('/eliminar/<int:id>', methods=['POST'])
@boveda_requerida
def eliminar(id):
    asistencia = Asistencia.query.get_or_404(id)
    
    if asistencia.estado in ['Justificada', 'Retraso']:
        flash(f'⚠️ No se puede eliminar este registro porque cuenta con estado de "{asistencia.estado}". Por normativa institucional, las justificaciones y retrasos deben conservarse en el kárdex.', 'danger')
        return redirect(url_for('faltas.index'))

    try:
        db.session.delete(asistencia)
        db.session.commit()
        flash('🗑 Registro de asistencia eliminado definitivamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar: {str(e)}', 'danger')
        
    return redirect(request.referrer or url_for('faltas.index'))

# ==============================================================================
# DESBLOQUEAR CURSO (PROTEGIDO)
# ==============================================================================
@faltas_bp.route('/desbloquear', methods=['POST'])
@boveda_requerida
def desbloquear():
    control_id = request.form.get('control_id')
    control = ControlAsistenciaDiaria.query.get_or_404(control_id)
    curso_nombre = control.curso
    
    try:
        db.session.delete(control)
        db.session.commit()
        flash(f'🔓 El curso {curso_nombre} ha sido desbloqueado. Regencia ya puede volver a tomar lista.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al desbloquear el curso: {str(e)}', 'danger')
        
    return redirect(request.referrer or url_for('faltas.index'))
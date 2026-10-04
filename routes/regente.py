# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/regente.py
Proyecto: ASestud-Konetz / Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Blueprint exclusivo para Regencia con enrutamiento inteligente.
             Identifica automáticamente el turno y genera dinámicamente
             los paralelos reales (A, B, C...) desde la base de datos.
==============================================================================
"""

import os
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func
from models import (
    db, Estudiante, Asistencia, ControlAsistenciaDiaria, 
    Padre, Mensaje, ahora_bolivia
)

regente_bp = Blueprint(
    'regente',
    __name__,
    url_prefix='/regente',
    template_folder='templates/regente'
)

# ==============================================================================
# DICCIONARIO DE ACCESOS INTELIGENTES
# ==============================================================================
ACCESOS_REGENCIA = {
    "regencia2026": {"nombre": "Regencia Central", "turno": "Mañana"},
    "marita 2026": {"nombre": "Marita", "turno": "Tarde"},
    "12345": {"nombre": "Emergencia", "turno": "Mañana"}
}

# ==============================================================================
# SEGURIDAD Y OBTENCIÓN DINÁMICA DE PARALELOS
# ==============================================================================
def regente_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('regente_autenticado'):
            return redirect(url_for('regente.login'))
        return f(*args, **kwargs)
    return decorated_function

def obtener_cursos_del_turno(turno):
    """
    Lee los cursos reales de los alumnos en este turno y extrae dinámicamente los paralelos.
    Limpia el texto para mostrarlo bonito en el desplegable (Ej: '5to Secundaria A').
    """
    cursos_db = db.session.query(Estudiante.curso).filter(
        Estudiante.estado == 'Activo',
        Estudiante.turno == turno,
        Estudiante.curso != None
    ).distinct().all()
    
    cursos_limpios = set()
    for c in cursos_db:
        nombre = c[0].strip().upper()
        nombre = nombre.replace(' DE ', ' ') # Quitamos conectores
        
        partes = nombre.split()
        clean_partes = []
        for p in partes:
            # Si es una letra suelta (paralelo), se mantiene en mayúscula
            if len(p) == 1 and p in 'ABCDEFGH':
                clean_partes.append(p)
            else:
                clean_partes.append(p.capitalize())
                
        cursos_limpios.add(" ".join(clean_partes))
        
    return sorted(list(cursos_limpios))

# ==============================================================================
# LOGIN INTELIGENTE
# ==============================================================================
@regente_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        if password in ACCESOS_REGENCIA:
            datos = ACCESOS_REGENCIA[password]
            session['regente_autenticado'] = True
            session['nombre_regente'] = datos['nombre']
            session['turno_regente'] = datos['turno']
            
            flash(f"¡Bienvenida/o {datos['nombre']}! Has ingresado al turno {datos['turno']}.", "success")
            return redirect(url_for('regente.monitor'))
        else:
            flash('❌ Contraseña incorrecta. Acceso denegado.', 'danger')
            
    return render_template('regente/login.html')

@regente_bp.route('/logout')
def logout():
    session.pop('regente_autenticado', None)
    session.pop('nombre_regente', None)
    session.pop('turno_regente', None)
    return redirect(url_for('regente.login'))

@regente_bp.route('/')
def index():
    return redirect(url_for('regente.monitor'))

# ==============================================================================
# MONITOR DIARIO EN VIVO (FILTRADO POR TURNO DE LA REGENCIA)
# ==============================================================================
@regente_bp.route('/monitor')
@regente_requerido
def monitor():
    hoy = ahora_bolivia().date()
    turno_actual = session.get('turno_regente', 'Mañana')
    
    faltas_hoy = Asistencia.query.join(Estudiante).filter(
        db.func.date(Asistencia.fecha) == hoy,
        Asistencia.estado == 'Falta',
        Estudiante.turno == turno_actual
    ).order_by(Asistencia.curso, Asistencia.ci_estudiante).all()
    
    controles = ControlAsistenciaDiaria.query.filter(
        ControlAsistenciaDiaria.fecha == hoy,
        ControlAsistenciaDiaria.curso.like(f"%[{turno_actual}]%")
    ).all()
    
    cursos_procesados = [c.curso for c in controles if c.bloqueado]
    
    return render_template(
        'regente/monitor.html',
        faltas=faltas_hoy,
        cursos_procesados=cursos_procesados,
        hoy=hoy
    )

# ==============================================================================
# PORTAL DE TOMA DE ASISTENCIA (SOPORTA PARALELOS A, B, C...)
# ==============================================================================
@regente_bp.route('/tomar_asistencia', methods=['GET', 'POST'])
@regente_requerido
def tomar_asistencia():
    hoy = ahora_bolivia().date()
    turno_actual = session.get('turno_regente', 'Mañana')
    
    # La lista desplegable ahora nace directamente de la base de datos
    cursos_limpios = obtener_cursos_del_turno(turno_actual)
    curso_seleccionado = request.args.get('curso')
    
    if request.method == 'POST':
        curso = request.form.get('curso')
        estudiantes_ids = request.form.getlist('estudiante_id')
        faltas_ids = request.form.getlist('faltas') 
        
        curso_bloqueo = f"{curso} [{turno_actual}]"
        
        control_existente = ControlAsistenciaDiaria.query.filter_by(fecha=hoy, curso=curso_bloqueo).first()
        if control_existente and control_existente.bloqueado:
            flash(f'⚠️ Seguridad: La asistencia del curso {curso} ya fue enviada y está bloqueada.', 'danger')
            return redirect(url_for('regente.monitor'))
        
        estudiantes = Estudiante.query.filter(Estudiante.id.in_(estudiantes_ids)).all()
        estudiantes_dict = {str(e.id): e for e in estudiantes}
        
        for eid in estudiantes_ids:
            estudiante = estudiantes_dict.get(eid)
            if not estudiante:
                continue
                
            es_falta = eid in faltas_ids
            
            nueva_asistencia = Asistencia(
                estudiante_id=estudiante.id,
                ci_estudiante=estudiante.ci,
                rude_estudiante=estudiante.rude,
                curso=curso,
                fecha=hoy,
                estado='Falta' if es_falta else 'Presente',
                notificado_padre=False
            )
            db.session.add(nueva_asistencia)
            
            if es_falta:
                padre = Padre.query.filter_by(estudiante_id=estudiante.id).first()
                telefono_contacto = None
                nombre_contacto = "Tutor/Padre de Familia"
                
                if padre:
                    telefono_contacto = padre.telefono1 or padre.telefono2
                    nombre_contacto = padre.nombres
                    
                if telefono_contacto:
                    mensaje_alerta = Mensaje(
                        destinatario=nombre_contacto,
                        estudiante_id=estudiante.id,
                        telefono=telefono_contacto,
                        tipo_mensaje='Alerta de Inasistencia',
                        contenido=f"AVISO INSTITUCIONAL: Estimado/a {nombre_contacto}, le informamos de manera urgente que su hijo/a {estudiante.apellidos}, {estudiante.nombres} NO se presentó a clases el día de hoy {hoy.strftime('%d/%m/%Y')}. Por favor justifique su falta.",
                        remitente='Regencia'
                    )
                    db.session.add(mensaje_alerta)
                    nueva_asistencia.notificado_padre = True
        
        responsable_turno = session.get('nombre_regente', 'Regencia')
        nuevo_control = ControlAsistenciaDiaria(
            fecha=hoy,
            curso=curso_bloqueo,
            bloqueado=True,
            registrado_por=responsable_turno
        )
        db.session.add(nuevo_control)
        
        try:
            db.session.commit()
            flash(f'✅ Asistencia de {curso} procesada y bloqueada exitosamente por {responsable_turno}.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Hubo un error al guardar la asistencia: {str(e)}', 'danger')
            
        return redirect(url_for('regente.monitor'))
        
    estudiantes = []
    control = None
    if curso_seleccionado:
        curso_bloqueo = f"{curso_seleccionado} [{turno_actual}]"
        control = ControlAsistenciaDiaria.query.filter_by(fecha=hoy, curso=curso_bloqueo).first()
        
        if not control or not control.bloqueado:
            query = Estudiante.query.filter(
                Estudiante.estado == 'Activo',
                Estudiante.turno == turno_actual
            )
            terminos_busqueda = curso_seleccionado.lower().replace(' de ', ' ').replace('-', ' ').split()
            
            # FILTRO DE ALTA PRECISIÓN PARA PARALELOS
            for termino in terminos_busqueda:
                if len(termino) == 1:
                    # Si es una letra sola (ej. 'a'), exige que tenga un espacio antes para no confundirse con Secundari[a]
                    query = query.filter(Estudiante.curso.ilike(f'% {termino}%'))
                else:
                    query = query.filter(Estudiante.curso.ilike(f'%{termino}%'))
                
            estudiantes = query.order_by(Estudiante.apellidos, Estudiante.nombres).all()
        
    return render_template(
        'regente/tomar_asistencia.html',
        cursos=cursos_limpios,
        curso_seleccionado=curso_seleccionado,
        estudiantes=estudiantes,
        hoy=hoy,
        control=control
    )

# ==============================================================================
# HISTORIAL KÁRDEX / FILTRO DE INASISTENCIAS
# ==============================================================================
@regente_bp.route('/historial')
@regente_requerido
def historial():
    curso = request.args.get('curso', '')
    mes = request.args.get('mes', str(ahora_bolivia().month))
    anio = request.args.get('anio', str(ahora_bolivia().year))
    turno_actual = session.get('turno_regente', 'Mañana')
    
    query = Asistencia.query.join(Estudiante).filter(
        Asistencia.estado == 'Falta',
        db.extract('year', Asistencia.fecha) == int(anio),
        Estudiante.turno == turno_actual
    )
    
    if mes:
        query = query.filter(db.extract('month', Asistencia.fecha) == int(mes))
    if curso:
        query = query.filter(Asistencia.curso == curso)
        
    faltas_historial = query.order_by(Asistencia.fecha.desc(), Asistencia.curso).all()
    
    return render_template(
        'regente/historial.html',
        faltas=faltas_historial,
        curso_seleccionado=curso,
        mes_seleccionado=mes,
        anio_seleccionado=anio,
        cursos=obtener_cursos_del_turno(turno_actual)
    )
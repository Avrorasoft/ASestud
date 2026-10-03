# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/padres_portal.py
Proyecto: ASestud-Konetz - Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Portal para padres y tutores con pizarra de mosaicos por materia
             y semáforo de 4 colores para seguimiento de tareas.
==============================================================================
"""

from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort

from models import db, Estudiante, Materia, Tarea, EntregaTarea

padres_portal_bp = Blueprint('padres_portal', __name__, url_prefix='/padres-portal')


def padre_login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'estudiante_id' not in session:
            flash('Por favor ingrese con las credenciales del estudiante para ver la pizarra.', 'info')
            return redirect(url_for('padres_portal.login'))
        return f(*args, **kwargs)
    return decorated_function


@padres_portal_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ci_rude = request.form.get('ci_rude', '').strip()
        
        # Búsqueda por C.I. o código RUDE
        estudiante = Estudiante.query.filter(
            ((Estudiante.ci == ci_rude) | (Estudiante.rude == ci_rude)),
            Estudiante.estado == 'Activo'
        ).first()

        if estudiante:
            session['estudiante_id'] = estudiante.id
            session['estudiante_nombre'] = f"{estudiante.nombres} {estudiante.apellidos}"
            session['estudiante_curso'] = estudiante.curso
            flash(f"Bienvenido/a a la Pizarra Escolar de {estudiante.nombres}", 'success')
            return redirect(url_for('padres_portal.pizarra'))
        else:
            flash('No se encontró ningún estudiante activo con esa identificación.', 'danger')

    return render_template('padres_portal/login.html')


@padres_portal_bp.route('/logout')
def logout():
    session.pop('estudiante_id', None)
    session.pop('estudiante_nombre', None)
    session.pop('estudiante_curso', None)
    return redirect(url_for('padres_portal.login'))


# --- PIZARRA DE MOSAICOS CUADRADOS ---
@padres_portal_bp.route('/pizarra')
@padre_login_requerido
def pizarra():
    est_id = int(session['estudiante_id'])
    estudiante = Estudiante.query.get_or_404(est_id)

    # Materias asignadas al curso del estudiante
    materias = Materia.query.filter_by(curso_id=estudiante.curso).order_by(Materia.nombre.asc()).all()

    ahora = datetime.now()
    mosaicos = []

    for m in materias:
        tareas_materia = Tarea.query.filter_by(materia_id=m.id).all()
        
        # Contadores por color
        conteo = {'verde': 0, 'amarillo': 0, 'rojo': 0, 'morado': 0}

        for t in tareas_materia:
            entrega = EntregaTarea.query.filter_by(tarea_id=t.id, estudiante_id=est_id).first()
            if entrega:
                if entrega.calificacion is not None:
                    conteo['verde'] += 1
                else:
                    conteo['amarillo'] += 1
            else:
                if ahora > t.fecha_entrega:
                    conteo['rojo'] += 1
                else:
                    conteo['morado'] += 1

        # Color prioritario del mosaico para alerta rápida
        if conteo['rojo'] > 0:
            color_resumen = '#dc3545'  # Rojo (urgente)
        elif conteo['morado'] > 0:
            color_resumen = '#6f42c1'  # Morado (en plazo)
        elif conteo['amarillo'] > 0:
            color_resumen = '#ffc107'  # Amarillo (por calificar)
        elif conteo['verde'] > 0:
            color_resumen = '#28a745'  # Verde (todo al día)
        else:
            color_resumen = '#6c757d'  # Gris (sin tareas)

        # Abreviatura de 3 letras para el mosaico compacto
        sigla = (m.nombre[:3]).upper() if m.nombre else 'MAT'

        mosaicos.append({
            'materia': m,
            'sigla': sigla,
            'color_resumen': color_resumen,
            'conteo': conteo,
            'total_tareas': len(tareas_materia)
        })

    return render_template(
        'padres_portal/pizarra.html',
        estudiante=estudiante,
        mosaicos=mosaicos
    )


# --- DETALLE DE LA MATERIA AL TOCAR EL MOSAICO ---
@padres_portal_bp.route('/materia/<int:materia_id>')
@padre_login_requerido
def detalle_materia(materia_id):
    est_id = int(session['estudiante_id'])
    estudiante = Estudiante.query.get_or_404(est_id)
    materia = Materia.query.get_or_404(materia_id)

    tareas = Tarea.query.filter_by(materia_id=materia_id).order_by(Tarea.fecha_entrega.desc()).all()
    ahora = datetime.now()

    lista_tareas = []
    for t in tareas:
        entrega = EntregaTarea.query.filter_by(tarea_id=t.id, estudiante_id=est_id).first()

        if entrega:
            if entrega.calificacion is not None:
                color = 'verde'
                color_hex = '#28a745'
                estado_texto = 'Presentada y Calificada'
            else:
                color = 'amarillo'
                color_hex = '#ffc107'
                estado_texto = 'Presentada (Pendiente de Calificación)'
        else:
            if ahora > t.fecha_entrega:
                color = 'rojo'
                color_hex = '#dc3545'
                estado_texto = 'Plazo Vencido (No Presentada)'
            else:
                color = 'morado'
                color_hex = '#6f42c1'
                estado_texto = 'En Plazo Vigente para Entrega'

        lista_tareas.append({
            'tarea': t,
            'entrega': entrega,
            'color': color,
            'color_hex': color_hex,
            'estado_texto': estado_texto,
            'es_vencida': (ahora > t.fecha_entrega)
        })

    return render_template(
        'padres_portal/materia_detalle.html',
        estudiante=estudiante,
        materia=materia,
        tareas=lista_tareas,
        ahora=ahora
    )
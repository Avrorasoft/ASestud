# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/superadmin_api.py
Proyecto: Sistema de Gestión Escolar - Colegio Dr. Antonio Vaca Díez
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Endpoints de búsqueda por C.I. y Apellidos para la auditoría
             y rectificación directa de Calificaciones y Comprobantes de Pago.
==============================================================================
"""

from flask import Blueprint, request, jsonify, session
from models import db, Estudiante, Calificacion, Pago, Materia

superadmin_api_bp = Blueprint('superadmin_api', __name__, url_prefix='/superadmin/api')


def superadmin_autorizado():
    return (
        session.get('superadmin_activo') is True or
        session.get('superadmin_boveda') is True or
        session.get('es_superadmin') is True or
        session.get('superadmin') is True or
        session.get('rol') == 'superadmin'
    )


@superadmin_api_bp.route('/buscar_calificaciones')
def buscar_calificaciones():
    if not superadmin_autorizado():
        return jsonify({'error': 'Acceso no autorizado'}), 403

    query = request.args.get('q', '').strip()
    curso_filtro = request.args.get('curso', '').strip()
    tipo_filtro = request.args.get('tipo', '').strip()

    est_query = Estudiante.query
    if curso_filtro:
        est_query = est_query.filter(Estudiante.curso.ilike(f"%{curso_filtro}%"))

    if query and len(query) >= 2:
        est_query = est_query.filter(
            (Estudiante.ci.ilike(f"%{query}%")) |
            (Estudiante.apellidos.ilike(f"%{query}%")) |
            (Estudiante.nombres.ilike(f"%{query}%"))
        )

    estudiantes = est_query.limit(30).all()
    est_ids = [e.id for e in estudiantes]
    mapa_est = {e.id: e for e in estudiantes}

    cal_query = Calificacion.query
    if est_ids:
        cal_query = cal_query.filter(Calificacion.estudiante_id.in_(est_ids))
    elif query and len(query) >= 2:
        # Si no hay estudiantes pero se buscó texto, permitimos buscar directo en calificaciones si fuera necesario
        return jsonify([])

    if tipo_filtro:
        cal_query = cal_query.filter(Calificacion.tipo.ilike(f"%{tipo_filtro}%"))

    calificaciones = cal_query.order_by(Calificacion.fecha.desc()).limit(50).all()

    resultados = []
    for c in calificaciones:
        est = mapa_est.get(c.estudiante_id)
        materia_nombre = c.materia.nombre if c.materia else 'Materia N/A'
        valor_nota = f"{c.nota} pts" if c.nota is not None else (c.valoracion_cualitativa or 'Sin Nota')

        resultados.append({
            'calificacion_id': c.id,
            'estudiante_nombre': f"{est.apellidos}, {est.nombres}" if est else 'N/A',
            'estudiante_ci': est.ci if est else 'N/A',
            'curso': est.curso if est else 'N/A',
            'materia': materia_nombre,
            'periodo': c.periodo or '1er Trimestre',
            'tipo': c.tipo or 'Parcial',
            'nota_actual': valor_nota,
            'url_editar': f"/superadmin/editar_nota/{c.id}"
        })

    return jsonify(resultados)


@superadmin_api_bp.route('/buscar_pagos')
def buscar_pagos():
    if not superadmin_autorizado():
        return jsonify({'error': 'Acceso no autorizado'}), 403

    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])

    # Búsqueda por C.I. o Nombre del Estudiante
    estudiantes = Estudiante.query.filter(
        (Estudiante.ci.ilike(f"%{query}%")) |
        (Estudiante.apellidos.ilike(f"%{query}%")) |
        (Estudiante.nombres.ilike(f"%{query}%"))
    ).limit(10).all()

    if not estudiantes:
        return jsonify([])

    est_ids = [e.id for e in estudiantes]
    mapa_est = {e.id: e for e in estudiantes}

    pagos = Pago.query.filter(
        Pago.estudiante_id.in_(est_ids)
    ).order_by(Pago.fecha_pago.desc(), Pago.id.desc()).limit(40).all()

    resultados = []
    for p in pagos:
        est = mapa_est.get(p.estudiante_id)
        fecha_str = p.fecha_pago.strftime('%d/%m/%Y') if p.fecha_pago else 'Sin Fecha'

        resultados.append({
            'pago_id': p.id,
            'estudiante_nombre': f"{est.apellidos}, {est.nombres}" if est else 'N/A',
            'estudiante_ci': est.ci if est else 'N/A',
            'mes': p.mes,
            'anio': p.anio,
            'monto_pagado': f"Bs. {p.monto_pagado:.2f}",
            'metodo': p.metodo_pago or 'Efectivo',
            'turno': p.turno_responsable or 'Mañana',
            'estado': p.estado or 'Pagado',
            'fecha': fecha_str,
            'url_editar': f"/superadmin/editar_pago/{p.id}"
        })

    return jsonify(resultados)
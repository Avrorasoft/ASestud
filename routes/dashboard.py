# -*- coding: utf-8 -*-
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from models import db, Estudiante, Profesor, PersonalAdministrativo, Pago, Gasto, Calificacion, Materia
from sqlalchemy import func
from datetime import date, timedelta

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates/dashboard')

@dashboard_bp.route('/')
def index():
    hoy = date.today()
    anio_actual = hoy.year
    mes_actual = hoy.month
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes = hoy.replace(day=1)
    
    if hoy.month == 1:
        inicio_mes_pasado = date(hoy.year - 1, 12, 1)
        fin_mes_pasado = date(hoy.year - 1, 12, 31)
    else:
        inicio_mes_pasado = date(hoy.year, hoy.month - 1, 1)
        fin_mes_pasado = inicio_mes - timedelta(days=1)

    try:
        total_estudiantes = Estudiante.query.filter_by(estado='Activo').count()
    except:
        total_estudiantes = 0
    
    try:
        total_profesores = Profesor.query.filter_by(estado='Activo').count()
    except:
        total_profesores = 0
    
    try:
        total_admin = PersonalAdministrativo.query.filter_by(estado='Activo').count()
    except:
        total_admin = 0
    
    try:
        total_materias = Materia.query.count()
    except:
        total_materias = 0

    try:
        pagos_hoy = Pago.query.filter(Pago.estado == 'Pagado', func.date(Pago.fecha_pago) == hoy).all()
        ingresos_hoy = sum(p.monto_pagado for p in pagos_hoy)
    except Exception as e:
        print(f"Error ingresos_hoy: {e}")
        ingresos_hoy = 0.0

    try:
        pagos_semana = Pago.query.filter(Pago.estado == 'Pagado', Pago.fecha_pago >= inicio_semana).all()
        ingresos_semana = sum(p.monto_pagado for p in pagos_semana)
    except Exception as e:
        print(f"Error ingresos_semana: {e}")
        ingresos_semana = 0.0

    try:
        pagos_mes = Pago.query.filter(Pago.estado == 'Pagado', Pago.fecha_pago >= inicio_mes).all()
        ingresos_mes = sum(p.monto_pagado for p in pagos_mes)
    except Exception as e:
        print(f"Error ingresos_mes: {e}")
        ingresos_mes = 0.0

    try:
        pagos_mes_pasado = Pago.query.filter(
            Pago.estado == 'Pagado',
            Pago.fecha_pago >= inicio_mes_pasado,
            Pago.fecha_pago <= fin_mes_pasado
        ).all()
        ingresos_mes_pasado = sum(p.monto_pagado for p in pagos_mes_pasado)
    except Exception as e:
        print(f"Error ingresos_mes_pasado: {e}")
        ingresos_mes_pasado = 0.0

    try:
        gastos_mes = Gasto.query.filter(Gasto.fecha >= inicio_mes).all()
        egresos_sueldos = 0.0
        egresos_electricidad = 0.0
        egresos_agua = 0.0
        egresos_otros = 0.0
        for g in gastos_mes:
            categoria = (g.categoria or '').lower()
            if 'sueldo' in categoria:
                egresos_sueldos += g.monto
            elif 'electricidad' in categoria or 'luz' in categoria:
                egresos_electricidad += g.monto
            elif 'agua' in categoria:
                egresos_agua += g.monto
            else:
                egresos_otros += g.monto
        total_egresos_mes = sum(g.monto for g in gastos_mes)
    except Exception as e:
        print(f"Error egresos: {e}")
        egresos_sueldos = 0.0
        egresos_electricidad = 0.0
        egresos_agua = 0.0
        egresos_otros = 0.0
        total_egresos_mes = 0.0

    try:
        estudiantes_activos = Estudiante.query.filter_by(estado='Activo').count()
        
        # MOROSIDAD: se calcula SOLO con datos insertados en la BD
        # Si un pago no está en la BD, no se cuenta como mora (no se asume nada)
        # Solo se considera mora los pagos registrados con estado Pendiente o Moroso
        pagos_morosos = Pago.query.filter(
            Pago.estado.in_(['Pendiente', 'Moroso'])
        ).all()
        
        morosidad_total = sum(
            (p.monto_total or 0) - (p.monto_pagado or 0) 
            for p in pagos_morosos
        )
        morosidad_total = max(0.0, float(morosidad_total))
    except Exception as e:
        print(f"Error morosidad: {e}")
        estudiantes_activos = 0
        morosidad_total = 0.0

    try:
        promedio_general = db.session.query(func.avg(Calificacion.nota)).scalar() or 0.0
    except Exception as e:
        print(f"Error promedio: {e}")
        promedio_general = 0.0

    return render_template('dashboard/index.html',
        total_estudiantes=total_estudiantes,
        total_profesores=total_profesores,
        total_admin=total_admin,
        total_materias=total_materias,
        promedio_general=promedio_general,
        ingresos_hoy=ingresos_hoy,
        ingresos_semana=ingresos_semana,
        ingresos_mes=ingresos_mes,
        ingresos_mes_pasado=ingresos_mes_pasado,
        egresos_sueldos=egresos_sueldos,
        egresos_electricidad=egresos_electricidad,
        egresos_agua=egresos_agua,
        egresos_otros=egresos_otros,
        total_egresos_mes=total_egresos_mes,
        estudiantes_activos=estudiantes_activos,
        morosidad_total=morosidad_total,
        egresos_mes=total_egresos_mes,
        mora_total=morosidad_total,
        mes_actual=hoy.strftime('%m/%Y')
    )
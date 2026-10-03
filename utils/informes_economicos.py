# -*- coding: utf-8 -*-
"""
Generador de informes económicos confidenciales.
"""

from datetime import datetime, timedelta, date
from models import db, Pago, Gasto, InformeEconomico
import json


def calcular_totales_periodo(fecha_inicio, fecha_fin):
    """
    Calcula ingresos y gastos de un período específico.
    Retorna diccionario con totales por método de pago.
    """
    # Ingresos (Pagos de estudiantes)
    pagos = Pago.query.filter(
        Pago.fecha_pago >= datetime.combine(fecha_inicio, datetime.min.time()),
        Pago.fecha_pago <= datetime.combine(fecha_fin, datetime.max.time()),
        Pago.estado == 'Pagado'
    ).all()
    
    ingresos_efectivo = sum(p.monto_pagado for p in pagos if p.metodo_pago == 'Efectivo')
    ingresos_bancario = sum(p.monto_pagado for p in pagos if p.metodo_pago == 'Bancario')
    
    # Gastos
    gastos = Gasto.query.filter(
        Gasto.fecha >= fecha_inicio,
        Gasto.fecha <= fecha_fin
    ).all()
    
    gastos_efectivo = sum(g.monto for g in gastos if g.metodo_pago == 'Efectivo')
    gastos_bancario = sum(g.monto for g in gastos if g.metodo_pago == 'Bancario')
    
    return {
        'ingresos_efectivo': ingresos_efectivo,
        'ingresos_bancario': ingresos_bancario,
        'total_ingresos': ingresos_efectivo + ingresos_bancario,
        'gastos_efectivo': gastos_efectivo,
        'gastos_bancario': gastos_bancario,
        'total_gastos': gastos_efectivo + gastos_bancario,
        'saldo_efectivo': ingresos_efectivo - gastos_efectivo,
        'saldo_bancario': ingresos_bancario - gastos_bancario,
        'saldo_total': (ingresos_efectivo + ingresos_bancario) - (gastos_efectivo + gastos_bancario),
        'detalle': {
            'pagos': [{
                'id': p.id,
                'estudiante_id': p.estudiante_id,
                'monto': p.monto_pagado,
                'metodo_pago': p.metodo_pago,
                'fecha': p.fecha_pago.strftime('%Y-%m-%d %H:%M') if p.fecha_pago else '',
                'mes': p.mes,
                'anio': p.anio
            } for p in pagos],
            'gastos': [{
                'id': g.id,
                'categoria': g.categoria,
                'descripcion': g.descripcion,
                'monto': g.monto,
                'metodo_pago': g.metodo_pago,
                'fecha': g.fecha.strftime('%Y-%m-%d'),
                'proveedor': g.proveedor or 'N/A',
                'responsable': g.responsable or 'N/A'
            } for g in gastos]
        }
    }


def generar_informe_diario(fecha=None):
    """
    Genera informe económico diario.
    Si no se especifica fecha, usa el día actual.
    """
    if fecha is None:
        fecha = date.today()
    
    # Verificar si ya existe informe para este día
    informe_existente = InformeEconomico.query.filter_by(
        tipo_informe='Diario',
        fecha_inicio=fecha,
        fecha_fin=fecha
    ).first()
    
    if informe_existente:
        return informe_existente
    
    totales = calcular_totales_periodo(fecha, fecha)
    
    informe = InformeEconomico(
        tipo_informe='Diario',
        fecha_inicio=fecha,
        fecha_fin=fecha,
        ingresos_efectivo=totales['ingresos_efectivo'],
        ingresos_bancario=totales['ingresos_bancario'],
        total_ingresos=totales['total_ingresos'],
        gastos_efectivo=totales['gastos_efectivo'],
        gastos_bancario=totales['gastos_bancario'],
        total_gastos=totales['total_gastos'],
        saldo_efectivo=totales['saldo_efectivo'],
        saldo_bancario=totales['saldo_bancario'],
        saldo_total=totales['saldo_total'],
        detalle_json=json.dumps(totales['detalle'], ensure_ascii=False)
    )
    
    db.session.add(informe)
    db.session.commit()
    
    return informe


def generar_informe_semanal(fecha_fin=None):
    """
    Genera informe económico semanal (últimos 7 días).
    """
    if fecha_fin is None:
        fecha_fin = date.today()
    
    fecha_inicio = fecha_fin - timedelta(days=6)
    
    # Verificar si ya existe
    informe_existente = InformeEconomico.query.filter_by(
        tipo_informe='Semanal',
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    ).first()
    
    if informe_existente:
        return informe_existente
    
    totales = calcular_totales_periodo(fecha_inicio, fecha_fin)
    
    informe = InformeEconomico(
        tipo_informe='Semanal',
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        ingresos_efectivo=totales['ingresos_efectivo'],
        ingresos_bancario=totales['ingresos_bancario'],
        total_ingresos=totales['total_ingresos'],
        gastos_efectivo=totales['gastos_efectivo'],
        gastos_bancario=totales['gastos_bancario'],
        total_gastos=totales['total_gastos'],
        saldo_efectivo=totales['saldo_efectivo'],
        saldo_bancario=totales['saldo_bancario'],
        saldo_total=totales['saldo_total'],
        detalle_json=json.dumps(totales['detalle'], ensure_ascii=False)
    )
    
    db.session.add(informe)
    db.session.commit()
    
    return informe


def generar_informe_mensual(anio=None, mes=None):
    """
    Genera informe económico mensual.
    """
    if anio is None or mes is None:
        hoy = date.today()
        anio = hoy.year
        mes = hoy.month
    
    # Primer día del mes
    fecha_inicio = date(anio, mes, 1)
    
    # Último día del mes
    if mes == 12:
        fecha_fin = date(anio + 1, 1, 1) - timedelta(days=1)
    else:
        fecha_fin = date(anio, mes + 1, 1) - timedelta(days=1)
    
    # Verificar si ya existe
    informe_existente = InformeEconomico.query.filter_by(
        tipo_informe='Mensual',
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    ).first()
    
    if informe_existente:
        return informe_existente
    
    totales = calcular_totales_periodo(fecha_inicio, fecha_fin)
    
    informe = InformeEconomico(
        tipo_informe='Mensual',
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        ingresos_efectivo=totales['ingresos_efectivo'],
        ingresos_bancario=totales['ingresos_bancario'],
        total_ingresos=totales['total_ingresos'],
        gastos_efectivo=totales['gastos_efectivo'],
        gastos_bancario=totales['gastos_bancario'],
        total_gastos=totales['total_gastos'],
        saldo_efectivo=totales['saldo_efectivo'],
        saldo_bancario=totales['saldo_bancario'],
        saldo_total=totales['saldo_total'],
        detalle_json=json.dumps(totales['detalle'], ensure_ascii=False)
    )
    
    db.session.add(informe)
    db.session.commit()
    
    return informe


def inicializar_configuracion_superadmin():
    """
    Inicializa la configuración del superadmin si no existe.
    """
    from werkzeug.security import generate_password_hash
    
    config_existente = ConfiguracionSuperadmin.query.filter_by(clave='password_superadmin').first()
    
    if not config_existente:
        # Contraseña por defecto: admin2026 (el superadmin debe cambiarla)
        password_hash = generate_password_hash('admin2026')
        
        config = ConfiguracionSuperadmin(
            clave='password_superadmin',
            valor=password_hash,
            descripcion='Contraseña hash del superadministrador para informes económicos'
        )
        
        db.session.add(config)
        db.session.commit()
        
        return True
    
    return False
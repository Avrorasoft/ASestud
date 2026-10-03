# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import db, Estudiante, Mensaje, Pago, Padre, ahora_bolivia
import os

admin_envios_bp = Blueprint('admin_envios', __name__, url_prefix='/admin/envios')

def verificar_mora_admin(estudiante_id):
    """
    Calcula si el estudiante tiene alguna deuda vencida (Mora).
    Utiliza la misma lógica estandarizada del reporte de deudores y portal de padres,
    verificando la lista fija de meses escolares y la pensión base.
    """
    estudiante = Estudiante.query.get(estudiante_id)
    if not estudiante:
        return False

    meses_escolares = ["Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre"]
    hoy = ahora_bolivia()
    anio_actual = hoy.year
    pension_base = float(estudiante.pension or 0.0)
    
    # Si no tiene pensión asignada, no se le puede calcular mora
    if pension_base <= 0:
        return False

    pagos_est = Pago.query.filter_by(estudiante_id=estudiante_id, anio=anio_actual).all()
    pagos_map = {p.mes.strip().capitalize(): p for p in pagos_est if p.mes}
    
    monto_mora = 0.0
    
    for mes in meses_escolares:
        if mes in pagos_map:
            p = pagos_map[mes]
            saldo_mes = float(p.monto_total or pension_base) - float(p.monto_pagado or 0.0)
            if saldo_mes > 0:
                monto_mora += saldo_mes
        else:
            monto_mora += pension_base

    # Si hay cualquier monto de mora mayor a 0, el estudiante es deudor
    return monto_mora > 0

@admin_envios_bp.route('/boletines')
def panel_envios():
    estudiantes = Estudiante.query.filter_by(estado='Activo').all()
    lista_envio = []
    hoy = ahora_bolivia()
    
    for est in estudiantes:
        tiene_mora = verificar_mora_admin(est.id)
        # Búsqueda genérica del PDF. Ajustar si el nombre difiere.
        filename = f"boletin_{est.id}_{hoy.year}_{est.rude}.pdf" 
        filepath = os.path.join(current_app.root_path, 'static', 'boletines', filename)
        tiene_pdf = os.path.exists(filepath)
        
        lista_envio.append({
            'estudiante': est,
            'tiene_mora': tiene_mora,
            'tiene_pdf': tiene_pdf,
            'filename': filename
        })
        
    return render_template('admin_envios_boletines.html', lista=lista_envio)

@admin_envios_bp.route('/boletines/enviar_masivo', methods=['POST'])
def enviar_masivo():
    estudiantes = Estudiante.query.filter_by(estado='Activo').all()
    hoy = ahora_bolivia()
    enviados = 0
    
    for est in estudiantes:
        if not verificar_mora_admin(est.id):
            filename = f"boletin_{est.id}_{hoy.year}_{est.rude}.pdf"
            filepath = os.path.join(current_app.root_path, 'static', 'boletines', filename)
            
            if os.path.exists(filepath):
                base_url = request.host_url.rstrip('/')
                archivo_url = f"{base_url}/static/boletines/{filename}"
                padre = Padre.query.filter_by(estudiante_id=est.id).first()
                telefono = padre.telefono1 if padre else 'Sin teléfono'
                
                mensaje = Mensaje(
                    destinatario='Padre',
                    estudiante_id=est.id,
                    telefono=telefono,
                    tipo_mensaje='Boletín',
                    contenido=f"Estimado tutor, le hacemos entrega del boletín de calificaciones oficial del estudiante {est.nombres}.\n\n---ARCHIVO_ADJUNTO---\n{archivo_url}",
                    remitente='Institución'
                )
                db.session.add(mensaje)
                enviados += 1
                
    db.session.commit()
    flash(f'✅ Se enviaron {enviados} boletines al chat de tutores habilitados (sin mora).', 'success')
    return redirect(url_for('admin_envios.panel_envios'))

@admin_envios_bp.route('/boletines/enviar/<int:estudiante_id>', methods=['POST'])
def enviar_individual(estudiante_id):
    est = Estudiante.query.get_or_404(estudiante_id)
    hoy = ahora_bolivia()
    filename = f"boletin_{est.id}_{hoy.year}_{est.rude}.pdf"
    filepath = os.path.join(current_app.root_path, 'static', 'boletines', filename)
    
    if not os.path.exists(filepath):
        flash('❌ El PDF del boletín no ha sido generado aún.', 'danger')
        return redirect(url_for('admin_envios.panel_envios'))
        
    base_url = request.host_url.rstrip('/')
    archivo_url = f"{base_url}/static/boletines/{filename}"
    padre = Padre.query.filter_by(estudiante_id=est.id).first()
    telefono = padre.telefono1 if padre else 'Sin teléfono'
    
    mensaje = Mensaje(
        destinatario='Padre',
        estudiante_id=est.id,
        telefono=telefono,
        tipo_mensaje='Boletín',
        contenido=f"Estimado tutor, adjuntamos el boletín de calificaciones de {est.nombres}.\n\n---ARCHIVO_ADJUNTO---\n{archivo_url}",
        remitente='Institución'
    )
    db.session.add(mensaje)
    db.session.commit()
    
    flash(f'✅ Boletín enviado correctamente al chat del estudiante {est.nombres}.', 'success')
    return redirect(url_for('admin_envios.panel_envios'))
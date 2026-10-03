# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_from_directory
from models import db, Padre, Estudiante, Mensaje, Pago, Calificacion, ahora_bolivia
from functools import wraps
from datetime import datetime, timezone, timedelta
import os
from werkzeug.utils import secure_filename

portal_padres_bp = Blueprint('portal_padres', __name__, template_folder='templates/portal_padres')

def login_required_padre(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'padre_id' not in session:
            flash('⚠️ Debe iniciar sesión para acceder al Portal de Padres', 'warning')
            return redirect(url_for('portal_padres.login'))
        return f(*args, **kwargs)
    return decorated_function

@portal_padres_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ci = request.form.get('ci', '').strip()
        rude = request.form.get('rude', '').strip()
        padre = None
        
        if ci:
            padre = Padre.query.filter_by(ci=ci).first()
        if not padre and rude:
            estudiante = Estudiante.query.filter_by(rude=rude).first()
            if estudiante:
                padre = Padre.query.filter_by(estudiante_id=estudiante.id).first()
        
        if padre:
            session['padre_id'] = padre.id
            session['padre_nombre'] = padre.nombres
            flash('✅ Bienvenido al Portal de Padres', 'success')
            return redirect(url_for('portal_padres.dashboard'))
        else:
            flash('❌ CI o RUDE no encontrado. Verifique sus datos.', 'danger')
    return render_template('portal_padres/login.html')

@portal_padres_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('portal_padres.login'))
@portal_padres_bp.route('/dashboard')
@login_required_padre
def dashboard():
    padre = Padre.query.get_or_404(session['padre_id'])
    estudiante = Estudiante.query.get(padre.estudiante_id)
    mensajes_recientes = Mensaje.query.filter_by(estudiante_id=estudiante.id).order_by(Mensaje.fecha_envio.desc()).limit(10).all()
    
    # ---------------------------------------------------------------------
    # CÁLCULO DE MORA Y MESES ADEUDADOS
    # ---------------------------------------------------------------------
    meses_escolares = ["Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre"]
    anio_actual = 2026
    pension_base = float(estudiante.pension or 0.0)
    
    pagos_est = Pago.query.filter_by(estudiante_id=estudiante.id, anio=anio_actual).all()
    pagos_map = {p.mes.strip().capitalize(): p for p in pagos_est if p.mes}
    
    monto_mora = 0.0
    meses_adeudados = []
    
    if pension_base > 0:
        for mes in meses_escolares:
            if mes in pagos_map:
                p = pagos_map[mes]
                saldo_mes = float(p.monto_total or pension_base) - float(p.monto_pagado or 0.0)
                if saldo_mes > 0:
                    monto_mora += saldo_mes
                    meses_adeudados.append(mes)
            else:
                monto_mora += pension_base
                meses_adeudados.append(mes)
                
    detalle_meses = ", ".join(meses_adeudados)
    # ---------------------------------------------------------------------
    
    todos_los_pagos = Pago.query.filter_by(estudiante_id=estudiante.id).all()
    pagos_pendientes = []
    
    for p in todos_los_pagos:
        estado = str(p.estado or '').strip().lower()
        if estado != 'pagado':
            saldo = float(p.monto_total or pension_base) - float(p.monto_pagado or 0.0)
            if saldo > 0:
                pagos_pendientes.append(p)
                
    return render_template('portal_padres/dashboard.html', 
                         padre=padre, 
                         estudiante=estudiante, 
                         mensajes_recientes=mensajes_recientes, 
                         pagos_pendientes=pagos_pendientes, 
                         monto_pendiente=monto_mora,
                         monto_mora=monto_mora,
                         detalle_meses=detalle_meses)

@portal_padres_bp.route('/mensajes')
@login_required_padre
def mensajes():
    padre = Padre.query.get_or_404(session['padre_id'])
    estudiante = Estudiante.query.get(padre.estudiante_id)
    mensajes_lista = Mensaje.query.filter_by(estudiante_id=estudiante.id).order_by(Mensaje.fecha_envio.desc()).all()
    return render_template('portal_padres/mensajes.html', mensajes=mensajes_lista, estudiante=estudiante)

@portal_padres_bp.route('/ver_mensaje/<int:id>')
@login_required_padre
def ver_mensaje(id):
    mensaje = Mensaje.query.get_or_404(id)
    return render_template('portal_padres/ver_mensaje.html', mensaje=mensaje)

@portal_padres_bp.route('/nuevo_mensaje', methods=['GET', 'POST'])
@login_required_padre
def nuevo_mensaje():
    padre = Padre.query.get_or_404(session['padre_id'])
    estudiante = Estudiante.query.get(padre.estudiante_id)
    
    if request.method == 'POST':
        contenido = request.form.get('contenido', '').strip()
        archivo_url = None
        
        if 'archivo' in request.files:
            file = request.files['archivo']
            if file and file.filename != '':
                ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'mp3', 'wav', 'ogg'}
                def allowed_file(filename):
                    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
                
                if allowed_file(file.filename):
                    filename = secure_filename(f"padre_{padre.id}_{int(ahora_bolivia().timestamp())}_{file.filename}")
                    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
                    os.makedirs(upload_folder, exist_ok=True)
                    filepath = os.path.join(upload_folder, filename)
                    file.save(filepath)
                    
                    base_url = request.host_url.rstrip('/')
                    archivo_url = f"{base_url}/static/uploads/chat/{filename}"
        
        if not contenido and not archivo_url:
            flash('⚠️ Debe escribir un mensaje o adjuntar un archivo', 'warning')
            return redirect(url_for('portal_padres.nuevo_mensaje'))
        
        try:
            contenido_final = contenido
            if archivo_url:
                if contenido:
                    contenido_final += f"\n\n---ARCHIVO_ADJUNTO---\n{archivo_url}"
                else:
                    contenido_final = f"---ARCHIVO_ADJUNTO---\n{archivo_url}"
            
            mensaje = Mensaje(
                destinatario='Institución Educativa',
                estudiante_id=estudiante.id,
                telefono=padre.telefono1 or padre.telefono2 or 'Sin teléfono',
                tipo_mensaje='Mensaje de Padre',
                contenido=contenido_final,
                remitente='Padre'
            )
            db.session.add(mensaje)
            db.session.commit()
            
            flash('✅ Mensaje enviado correctamente a la institución', 'success')
            return redirect(url_for('portal_padres.mensajes'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error al enviar mensaje: {e}")
            flash(f'❌ Error al enviar el mensaje: {str(e)}', 'danger')
            return redirect(url_for('portal_padres.nuevo_mensaje'))
    
    return render_template('portal_padres/nuevo_mensaje.html', estudiante=estudiante)

@portal_padres_bp.route('/responder_mensaje/<int:id>', methods=['POST'])
@login_required_padre
def responder_mensaje(id):
    mensaje_original = Mensaje.query.get_or_404(id)
    padre = Padre.query.get_or_404(session['padre_id'])
    estudiante = Estudiante.query.get(padre.estudiante_id)
    
    contenido = request.form.get('respuesta', '').strip()
    archivo_url = None
    
    if 'archivo' in request.files:
        file = request.files['archivo']
        if file and file.filename != '':
            ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'mp3', 'wav', 'ogg'}
            def allowed_file(filename):
                return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
            
            if allowed_file(file.filename):
                filename = secure_filename(f"padre_{padre.id}_{int(ahora_bolivia().timestamp())}_{file.filename}")
                upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                
                base_url = request.host_url.rstrip('/')
                archivo_url = f"{base_url}/static/uploads/chat/{filename}"
    
    if not contenido and not archivo_url:
        flash('⚠️ Debe escribir un mensaje o adjuntar un archivo', 'warning')
        return redirect(url_for('portal_padres.ver_mensaje', id=id))
    
    try:
        contenido_final = contenido
        if archivo_url:
            if contenido:
                contenido_final += f"\n\n---ARCHIVO_ADJUNTO---\n{archivo_url}"
            else:
                contenido_final = f"---ARCHIVO_ADJUNTO---\n{archivo_url}"
        
        respuesta = Mensaje(
            destinatario='Institución Educativa',
            estudiante_id=estudiante.id,
            telefono=padre.telefono1 or padre.telefono2 or 'Sin teléfono',
            tipo_mensaje='Respuesta de Padre',
            contenido=contenido_final,
            remitente='Padre'
        )
        db.session.add(respuesta)
        db.session.commit()
        
        flash('✅ Respuesta enviada correctamente a la institución', 'success')
        return redirect(url_for('portal_padres.mensajes'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error al enviar respuesta: {e}")
        flash(f'❌ Error al enviar la respuesta: {str(e)}', 'danger')
        return redirect(url_for('portal_padres.ver_mensaje', id=id))

@portal_padres_bp.route('/boletin')
@login_required_padre
def ver_boletin():
    padre = Padre.query.get_or_404(session['padre_id'])
    estudiante = Estudiante.query.get(padre.estudiante_id)
    filename = f"boletin_{estudiante.id}_{ahora_bolivia().year}_{estudiante.rude}.pdf"
    
    boletines_dir = os.path.join(current_app.root_path, 'static', 'boletines')
    filepath = os.path.join(boletines_dir, filename)
    
    if not os.path.exists(filepath):
        flash('⚠️ El boletín aún no ha sido generado por la administración', 'warning')
        return redirect(url_for('portal_padres.dashboard'))
    
    return send_from_directory(boletines_dir, filename, as_attachment=True)

@portal_padres_bp.route('/pagos')
@login_required_padre
def pagos():
    padre = Padre.query.get_or_404(session['padre_id'])
    estudiante = Estudiante.query.get(padre.estudiante_id)
    pagos = Pago.query.filter_by(estudiante_id=estudiante.id).order_by(Pago.anio.desc(), Pago.id.desc()).all()
    
    # ---------------------------------------------------------------------
    # CÁLCULO DE MORA Y MESES ADEUDADOS
    # ---------------------------------------------------------------------
    meses_escolares = ["Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre"]
    anio_actual = 2026
    pension_base = float(estudiante.pension or 0.0)
    
    pagos_anio = Pago.query.filter_by(estudiante_id=estudiante.id, anio=anio_actual).all()
    pagos_map = {p.mes.strip().capitalize(): p for p in pagos_anio if p.mes}
    
    monto_mora = 0.0
    meses_adeudados = []
    
    if pension_base > 0:
        for mes in meses_escolares:
            if mes in pagos_map:
                p = pagos_map[mes]
                saldo_mes = float(p.monto_total or pension_base) - float(p.monto_pagado or 0.0)
                if saldo_mes > 0:
                    monto_mora += saldo_mes
                    meses_adeudados.append(mes)
            else:
                monto_mora += pension_base
                meses_adeudados.append(mes)
                
    detalle_meses = ", ".join(meses_adeudados)
    # ---------------------------------------------------------------------

    estado_pagos = {}
    
    for p in pagos:
        estado = str(p.estado or '').strip().lower()
        if estado != 'pagado':
            saldo = float(p.monto_total or pension_base) - float(p.monto_pagado or 0.0)
            if saldo > 0:
                estado_pagos[p.id] = True 
            else:
                estado_pagos[p.id] = False
        else:
            estado_pagos[p.id] = False

    return render_template('portal_padres/pagos.html', 
                         estudiante=estudiante, 
                         pagos=pagos, 
                         estado_pagos=estado_pagos,
                         monto_mora=monto_mora,
                         monto_pendiente_actual=0.0,
                         detalle_meses=detalle_meses)

@portal_padres_bp.route('/descargar_archivo/<path:filename>')
@login_required_padre
def descargar_archivo(filename):
    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
    if not os.path.exists(os.path.join(upload_folder, filename)):
        flash('❌ El archivo no existe o fue eliminado', 'danger')
        return redirect(url_for('portal_padres.mensajes'))
    return send_from_directory(upload_folder, filename, as_attachment=True)
# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/portal_padres.py
Proyecto: ASestud-Konetz - Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Portal Integral Unificado para Padres y Tutores:
             - Autenticación exclusivamente por C.I. del Tutor.
             - Persistencia garantizada de password_hash en base de datos.
             - Dashboard financiero ajustado al Corte Operativo.
             - Pizarra escolar de mosaicos por materia y semáforo de 4 colores.
             - Lectura directa de archivos adjuntos de tareas desde base de datos.
             - Centro de mensajería y justificaciones con adjuntos.
             - Descarga de boletines oficiales en PDF.
==============================================================================
"""

import os
from functools import wraps
from datetime import datetime, date

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, current_app, send_from_directory
)
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import (
    db, Padre, Estudiante, Materia, Tarea, EntregaTarea,
    Mensaje, Pago, ConfiguracionSuperadmin, ahora_bolivia
)

portal_padres_bp = Blueprint(
    'portal_padres',
    __name__,
    url_prefix='/portal-padres',
    template_folder='templates/portal_padres'
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'mp3', 'wav', 'ogg'}
UPLOAD_FOLDER_TAREAS = 'static/uploads/tareas'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required_padre(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        padre_id = session.get('padre_id')
        if not padre_id:
            flash('⚠️ Debe iniciar sesión con su carnet de tutor para acceder al Portal.', 'warning')
            return redirect(url_for('portal_padres.login'))
        return f(*args, **kwargs)
    return decorated_function


def asegurar_columna_password_en_bd():
    """Garantiza que la columna password_hash exista físicamente en la tabla padres de SQLite."""
    try:
        db.session.execute(text("ALTER TABLE padres ADD COLUMN password_hash TEXT"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def obtener_hash_padre_directo(padre_id):
    """Lee el hash directamente de la base de datos física para evitar fallos de caché de SQLAlchemy."""
    try:
        res = db.session.execute(text("SELECT password_hash FROM padres WHERE id = :id"), {"id": padre_id}).fetchone()
        if res and res[0]:
            return str(res[0]).strip()
    except Exception:
        pass
    return None


def obtener_corte_operativo():
    """Recupera la fecha de corte operativo configurada por Superadmin."""
    try:
        cfg = ConfiguracionSuperadmin.query.filter_by(clave='fecha_corte_operativo').first()
        if cfg and cfg.valor and str(cfg.valor).strip():
            valor_limpio = str(cfg.valor).strip()
            for fmt in ('%Y-%m-%d', '%Y-%m', '%d/%m/%Y'):
                try:
                    return datetime.strptime(valor_limpio, fmt).date()
                except ValueError:
                    pass
    except Exception:
        pass
    return None


def obtener_meses_mora_padre(anio_evaluado=None):
    """
    Calcula los meses exigibles para mora respetando el corte operativo y
    excluyendo el mes en curso y meses posteriores.
    """
    mapa_meses = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    mapa_inv = {v.lower(): k for k, v in mapa_meses.items()}
    meses_base = ['Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre']

    corte = obtener_corte_operativo()
    hoy = datetime.now().date()
    anio_calc = anio_evaluado or hoy.year
    mes_actual_num = hoy.month

    mes_inicio_corte = 2
    if corte:
        mes_inicio_corte = corte.month

    meses_mora = []
    for m in meses_base:
        num_m = mapa_inv.get(m.lower(), 0)
        if num_m == 0:
            continue
        if num_m < mes_inicio_corte:
            continue
        if int(anio_calc) > hoy.year:
            continue
        if int(anio_calc) == hoy.year and num_m >= mes_actual_num:
            continue

        meses_mora.append(m)

    return meses_mora


# ==============================================================================
# AUTENTICACIÓN EXCLUSIVA POR C.I. DEL PADRE / TUTOR
# ==============================================================================

@portal_padres_bp.route('/login', methods=['GET', 'POST'])
def login():
    asegurar_columna_password_en_bd()

    if request.method == 'POST':
        ci_ingresado = request.form.get('ci', '').strip()
        password_ingresada = request.form.get('password', '').strip()

        if not ci_ingresado or not password_ingresada:
            flash('⚠️ Ingrese el número de Carnet de Identidad del tutor y su contraseña.', 'warning')
            return render_template('portal_padres/login.html', ci_previo=ci_ingresado)

        padre = Padre.query.filter_by(ci=ci_ingresado).first()

        if not padre:
            flash('❌ Carnet de Identidad no encontrado. El acceso es únicamente con el C.I. del padre o tutor.', 'danger')
            return render_template('portal_padres/login.html', ci_previo=ci_ingresado)

        estudiante = Estudiante.query.get(padre.estudiante_id) if padre.estudiante_id else None
        if not estudiante:
            flash('❌ Su registro de tutor no cuenta con un estudiante asignado en el sistema.', 'danger')
            return render_template('portal_padres/login.html', ci_previo=ci_ingresado)

        hash_actual = obtener_hash_padre_directo(padre.id)
        if hash_actual:
            password_valida = check_password_hash(hash_actual, password_ingresada)
        else:
            password_valida = (password_ingresada == '1234')

        if not password_valida:
            flash('❌ Contraseña incorrecta. Acceso denegado.', 'danger')
            return render_template('portal_padres/login.html', ci_previo=ci_ingresado)

        session['padre_id'] = padre.id
        session['estudiante_id'] = estudiante.id
        session['padre_nombre'] = padre.nombres
        session['estudiante_nombre'] = f"{estudiante.nombres} {estudiante.apellidos}"
        session['estudiante_curso'] = estudiante.curso

        flash(f"✅ Bienvenido/a {padre.nombres}", 'success')
        return redirect(url_for('portal_padres.dashboard'))

    return render_template('portal_padres/login.html')


@portal_padres_bp.route('/logout')
def logout():
    session.pop('padre_id', None)
    session.pop('estudiante_id', None)
    session.pop('padre_nombre', None)
    session.pop('estudiante_nombre', None)
    session.pop('estudiante_curso', None)
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('portal_padres.login'))


# ==============================================================================
# CAMBIO DE CONTRASEÑA EXCLUSIVO PARA EL PADRE / TUTOR
# ==============================================================================

@portal_padres_bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required_padre
def cambiar_password():
    asegurar_columna_password_en_bd()
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)

    hash_existente = obtener_hash_padre_directo(padre.id)
    tiene_clave_personalizada = bool(hash_existente)

    if request.method == 'POST':
        actual = request.form.get('password_actual', '').strip()
        nueva = request.form.get('password_nueva', '').strip()
        confirmacion = request.form.get('password_confirmar', '').strip()

        if tiene_clave_personalizada:
            if not check_password_hash(hash_existente, actual):
                flash('❌ La contraseña actual no es correcta.', 'danger')
                return render_template('portal_padres/cambiar_password.html', padre=padre, tiene_clave_personalizada=tiene_clave_personalizada)
        else:
            if actual != '1234':
                flash('❌ La contraseña actual no es correcta. Su clave inicial es 1234.', 'danger')
                return render_template('portal_padres/cambiar_password.html', padre=padre, tiene_clave_personalizada=tiene_clave_personalizada)

        if len(nueva) < 4:
            flash('⚠️ La nueva contraseña debe tener al menos 4 caracteres.', 'warning')
            return render_template('portal_padres/cambiar_password.html', padre=padre, tiene_clave_personalizada=tiene_clave_personalizada)

        if nueva != confirmacion:
            flash('❌ Las nuevas contraseñas no coinciden.', 'danger')
            return render_template('portal_padres/cambiar_password.html', padre=padre, tiene_clave_personalizada=tiene_clave_personalizada)

        try:
            nuevo_hash = generate_password_hash(nueva)
            db.session.execute(
                text("UPDATE padres SET password_hash = :hash WHERE id = :id"),
                {"hash": nuevo_hash, "id": padre.id}
            )
            db.session.commit()

            flash('✅ Su contraseña ha sido cambiada y guardada exitosamente.', 'success')
            return redirect(url_for('portal_padres.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al guardar la contraseña en base de datos: {str(e)}', 'danger')

    return render_template('portal_padres/cambiar_password.html', padre=padre, tiene_clave_personalizada=tiene_clave_personalizada)


# ==============================================================================
# DASHBOARD GENERAL Y FINANCIERO (CON CORTE OPERATIVO)
# ==============================================================================

@portal_padres_bp.route('/dashboard')
@login_required_padre
def dashboard():
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)

    mensajes_recientes = Mensaje.query.filter_by(
        estudiante_id=estudiante.id
    ).order_by(Mensaje.fecha_envio.desc()).limit(5).all()

    anio_actual = datetime.now().year
    meses_para_mora = obtener_meses_mora_padre(anio_evaluado=anio_actual)
    pension_base = float(estudiante.pension or 430.0)

    todos_los_pagos = Pago.query.filter_by(estudiante_id=estudiante.id).all()
    pagos_est = [p for p in todos_los_pagos if str(p.anio) == str(anio_actual)]

    pagos_por_mes = {}
    for p in pagos_est:
        if getattr(p, 'estado', 'Pagado') == 'Anulado':
            continue
        if p.mes:
            mes_norm = str(p.mes).strip().capitalize()
            if mes_norm not in pagos_por_mes:
                pagos_por_mes[mes_norm] = {'abonado': 0.0, 'descuento': 0.0}
            pagos_por_mes[mes_norm]['abonado'] += float(p.monto_pagado or 0.0)
            pagos_por_mes[mes_norm]['descuento'] += float(p.descuento or 0.0)

    monto_mora = 0.0
    meses_adeudados = []

    for mes in meses_para_mora:
        info = pagos_por_mes.get(mes, {'abonado': 0.0, 'descuento': 0.0})
        costo_efectivo = max(0.0, pension_base - info['descuento'])
        saldo_mes = max(0.0, costo_efectivo - info['abonado'])

        if saldo_mes > 0.5:
            monto_mora += saldo_mes
            meses_adeudados.append(f"{mes} (Bs. {saldo_mes:,.2f})")

    detalle_meses = ", ".join(meses_adeudados) if meses_adeudados else "Al día con el ciclo escolar"

    pagos_pendientes = []
    for p in todos_los_pagos:
        estado = str(p.estado or '').strip().lower()
        if estado != 'pagado' and estado != 'anulado':
            saldo = float(p.monto_total or pension_base) - float(p.monto_pagado or 0.0)
            if saldo > 0:
                pagos_pendientes.append(p)

    total_materias = Materia.query.filter_by(curso_id=estudiante.curso).count()

    return render_template(
        'portal_padres/dashboard.html',
        padre=padre,
        estudiante=estudiante,
        mensajes_recientes=mensajes_recientes,
        pagos_pendientes=pagos_pendientes,
        monto_pendiente=monto_mora,
        monto_mora=monto_mora,
        meses_mora=meses_para_mora,
        detalle_meses=detalle_meses,
        total_materias=total_materias
    )


# ==============================================================================
# PIZARRA ESCOLAR Y SEGUIMIENTO DE TAREAS (SEMÁFORO DE 4 COLORES)
# ==============================================================================

@portal_padres_bp.route('/pizarra')
@login_required_padre
def pizarra():
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)

    materias = Materia.query.filter_by(curso_id=estudiante.curso).order_by(Materia.nombre.asc()).all()
    ahora = datetime.now()
    mosaicos = []

    for m in materias:
        tareas_materia = Tarea.query.filter_by(materia_id=m.id).all()
        conteo = {'verde': 0, 'amarillo': 0, 'rojo': 0, 'morado': 0}

        for t in tareas_materia:
            entrega = EntregaTarea.query.filter_by(tarea_id=t.id, estudiante_id=estudiante.id).first()
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

        if conteo['rojo'] > 0:
            color_resumen = '#dc3545'
        elif conteo['morado'] > 0:
            color_resumen = '#6f42c1'
        elif conteo['amarillo'] > 0:
            color_resumen = '#ffc107'
        elif conteo['verde'] > 0:
            color_resumen = '#28a745'
        else:
            color_resumen = '#6c757d'

        sigla = (m.nombre[:3]).upper() if m.nombre else 'MAT'

        mosaicos.append({
            'materia': m,
            'sigla': sigla,
            'color_resumen': color_resumen,
            'conteo': conteo,
            'total_tareas': len(tareas_materia)
        })

    return render_template(
        'portal_padres/pizarra.html',
        estudiante=estudiante,
        mosaicos=mosaicos
    )


# ==============================================================================
# DETALLE DE MATERIA (CON LECTURA DIRECTA DEL ADJUNTO DESDE SQL)
# ==============================================================================

@portal_padres_bp.route('/materia/<int:materia_id>')
@login_required_padre
def detalle_materia(materia_id):
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)
    materia = Materia.query.get_or_404(materia_id)

    tareas = Tarea.query.filter_by(materia_id=materia_id).order_by(Tarea.fecha_entrega.desc(), Tarea.id.desc()).all()
    ahora = datetime.now()

    lista_tareas = []
    for t in tareas:
        entrega = EntregaTarea.query.filter_by(tarea_id=t.id, estudiante_id=estudiante.id).first()

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
            if t.fecha_entrega and ahora > t.fecha_entrega:
                color = 'rojo'
                color_hex = '#dc3545'
                estado_texto = 'Plazo Vencido (No Presentada)'
            else:
                color = 'morado'
                color_hex = '#6f42c1'
                estado_texto = 'En Plazo Vigente para Entrega'

        # Recuperar el nombre del archivo adjunto directamente desde la base física
        adjunto = None
        try:
            res = db.session.execute(text("SELECT archivo_adjunto FROM tareas WHERE id = :id"), {"id": t.id}).fetchone()
            if res and res[0]:
                adjunto = str(res[0]).strip()
        except Exception:
            pass

        if not adjunto:
            adjunto = getattr(t, 'archivo_adjunto', None) or getattr(t, 'archivo', None)

        lista_tareas.append({
            'tarea': t,
            'entrega': entrega,
            'color': color,
            'color_hex': color_hex,
            'estado_texto': estado_texto,
            'es_vencida': (t.fecha_entrega and ahora > t.fecha_entrega),
            'adjunto': adjunto
        })

    return render_template(
        'portal_padres/materia_detalle.html',
        estudiante=estudiante,
        materia=materia,
        tareas=lista_tareas,
        ahora=ahora
    )


# ==============================================================================
# DESCARGA DE ADJUNTOS DE TAREAS PARA TUTORES
# ==============================================================================

@portal_padres_bp.route('/descargar-tarea/<path:filename>')
@login_required_padre
def descargar_tarea_adjunto(filename):
    """Permite al tutor descargar o abrir el material adjunto por el docente."""
    folder = os.path.join(current_app.root_path, UPLOAD_FOLDER_TAREAS)
    if not os.path.exists(os.path.join(folder, filename)):
        flash('❌ El archivo no existe o fue removido por el docente.', 'danger')
        return redirect(url_for('portal_padres.pizarra'))
    return send_from_directory(folder, filename, as_attachment=False)


# ==============================================================================
# HISTORIAL FINANCIERO Y PAGOS DEL ESTUDIANTE
# ==============================================================================

@portal_padres_bp.route('/pagos')
@login_required_padre
def pagos():
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)

    todos_los_pagos = Pago.query.filter_by(
        estudiante_id=estudiante.id
    ).order_by(Pago.anio.desc(), Pago.fecha_pago.desc(), Pago.id.desc()).all()

    anio_actual = datetime.now().year
    meses_para_mora = obtener_meses_mora_padre(anio_evaluado=anio_actual)
    pension_base = float(estudiante.pension or 430.0)

    pagos_por_mes = {}
    for p in todos_los_pagos:
        if getattr(p, 'estado', 'Pagado') == 'Anulado':
            continue
        if p.mes and (p.anio == anio_actual or str(p.anio) == str(anio_actual)):
            mes_norm = str(p.mes).strip().capitalize()
            if mes_norm not in pagos_por_mes:
                pagos_por_mes[mes_norm] = {'abonado': 0.0, 'descuento': 0.0}
            pagos_por_mes[mes_norm]['abonado'] += float(p.monto_pagado or 0.0)
            pagos_por_mes[mes_norm]['descuento'] += float(p.descuento or 0.0)

    monto_mora = 0.0
    meses_adeudados = []

    for mes in meses_para_mora:
        info = pagos_por_mes.get(mes, {'abonado': 0.0, 'descuento': 0.0})
        costo_efectivo = max(0.0, pension_base - info['descuento'])
        saldo_mes = max(0.0, costo_efectivo - info['abonado'])

        if saldo_mes > 0.5:
            monto_mora += saldo_mes
            meses_adeudados.append(f"{mes} (Bs. {saldo_mes:,.2f})")

    detalle_meses = ", ".join(meses_adeudados) if meses_adeudados else "Al día con el ciclo escolar"

    estado_pagos = {}
    for p in todos_los_pagos:
        estado = str(p.estado or '').strip().lower()
        if estado != 'pagado':
            saldo = float(p.monto_total or pension_base) - float(p.monto_pagado or 0.0)
            estado_pagos[p.id] = (saldo > 0)
        else:
            estado_pagos[p.id] = False

    return render_template(
        'portal_padres/pagos.html',
        estudiante=estudiante,
        padre=padre,
        pagos=todos_los_pagos,
        estado_pagos=estado_pagos,
        monto_mora=monto_mora,
        monto_pendiente_actual=monto_mora,
        meses_mora=meses_para_mora,
        detalle_meses=detalle_meses
    )


# ==============================================================================
# MENSAJERÍA Y COMUNICADOS
# ==============================================================================

@portal_padres_bp.route('/mensajes')
@login_required_padre
def mensajes():
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)

    mensajes_lista = Mensaje.query.filter_by(
        estudiante_id=estudiante.id
    ).order_by(Mensaje.fecha_envio.desc()).all()

    return render_template('portal_padres/mensajes.html', mensajes=mensajes_lista, estudiante=estudiante)


@portal_padres_bp.route('/ver_mensaje/<int:id>')
@login_required_padre
def ver_mensaje(id):
    mensaje = Mensaje.query.get_or_404(id)
    return render_template('portal_padres/ver_mensaje.html', mensaje=mensaje)


@portal_padres_bp.route('/nuevo_mensaje', methods=['GET', 'POST'])
@login_required_padre
def nuevo_mensaje():
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)

    if request.method == 'POST':
        contenido = request.form.get('contenido', '').strip()
        archivo_url = None

        if 'archivo' in request.files:
            file = request.files['archivo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"padre_{estudiante.id}_{int(ahora_bolivia().timestamp())}_{file.filename}")
                upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)

                base_url = request.host_url.rstrip('/')
                archivo_url = f"{base_url}/static/uploads/chat/{filename}"

        if not contenido and not archivo_url:
            flash('⚠️ Debe escribir un mensaje o adjuntar un archivo.', 'warning')
            return redirect(url_for('portal_padres.nuevo_mensaje'))

        try:
            contenido_final = contenido
            if archivo_url:
                if contenido:
                    contenido_final += f"\n\n---ARCHIVO_ADJUNTO---\n{archivo_url}"
                else:
                    contenido_final = f"---ARCHIVO_ADJUNTO---\n{archivo_url}"

            telefono_padre = padre.telefono1 or padre.telefono2 if padre else 'Sin teléfono'
            mensaje = Mensaje(
                destinatario='Institución Educativa',
                estudiante_id=estudiante.id,
                telefono=telefono_padre,
                tipo_mensaje='Mensaje de Padre',
                contenido=contenido_final,
                remitente='Padre'
            )
            db.session.add(mensaje)
            db.session.commit()

            flash('✅ Mensaje enviado correctamente a la institución.', 'success')
            return redirect(url_for('portal_padres.mensajes'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al enviar el mensaje: {str(e)}', 'danger')
            return redirect(url_for('portal_padres.nuevo_mensaje'))

    return render_template('portal_padres/nuevo_mensaje.html', estudiante=estudiante)


@portal_padres_bp.route('/responder_mensaje/<int:id>', methods=['POST'])
@login_required_padre
def responder_mensaje(id):
    mensaje_original = Mensaje.query.get_or_404(id)
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)

    contenido = request.form.get('respuesta', '').strip()
    archivo_url = None

    if 'archivo' in request.files:
        file = request.files['archivo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(f"resp_padre_{estudiante.id}_{int(ahora_bolivia().timestamp())}_{file.filename}")
            upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
            os.makedirs(upload_folder, exist_ok=True)
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)

            base_url = request.host_url.rstrip('/')
            archivo_url = f"{base_url}/static/uploads/chat/{filename}"

    if not contenido and not archivo_url:
        flash('⚠️ Debe escribir una respuesta o adjuntar un archivo.', 'warning')
        return redirect(url_for('portal_padres.ver_mensaje', id=id))

    try:
        contenido_final = contenido
        if archivo_url:
            if contenido:
                contenido_final += f"\n\n---ARCHIVO_ADJUNTO---\n{archivo_url}"
            else:
                contenido_final = f"---ARCHIVO_ADJUNTO---\n{archivo_url}"

        telefono_padre = padre.telefono1 or padre.telefono2 if padre else 'Sin teléfono'
        respuesta = Mensaje(
            destinatario='Institución Educativa',
            estudiante_id=estudiante.id,
            telefono=telefono_padre,
            tipo_mensaje='Respuesta de Padre',
            contenido=contenido_final,
            remitente='Padre'
        )
        db.session.add(respuesta)
        db.session.commit()

        flash('✅ Respuesta enviada correctamente a la institución.', 'success')
        return redirect(url_for('portal_padres.mensajes'))

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al enviar la respuesta: {str(e)}', 'danger')
        return redirect(url_for('portal_padres.ver_mensaje', id=id))


@portal_padres_bp.route('/descargar_archivo/<path:filename>')
@login_required_padre
def descargar_archivo(filename):
    upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
    if not os.path.exists(os.path.join(upload_folder, filename)):
        flash('❌ El archivo no existe o fue eliminado.', 'danger')
        return redirect(url_for('portal_padres.mensajes'))
    return send_from_directory(upload_folder, filename, as_attachment=True)


# ==============================================================================
# BOLETÍN DE CALIFICACIONES
# ==============================================================================

@portal_padres_bp.route('/boletin')
@login_required_padre
def ver_boletin():
    padre_id = session.get('padre_id')
    padre = Padre.query.get_or_404(padre_id)
    estudiante = Estudiante.query.get_or_404(padre.estudiante_id)
    filename = f"boletin_{estudiante.id}_{ahora_bolivia().year}.pdf"

    boletines_dir = os.path.join(current_app.root_path, 'static', 'boletines')
    filepath = os.path.join(boletines_dir, filename)

    if not os.path.exists(filepath):
        flash('⚠️ El boletín oficial aún no ha sido emitido por la administración.', 'warning')
        return redirect(url_for('portal_padres.dashboard'))

    return send_from_directory(boletines_dir, filename, as_attachment=True)
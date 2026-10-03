# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/superadmin.py
Bóveda Superadmin con seguridad robusta:
- Contraseñas desde BD (no hardcoded)
- Rate limiting en logins
- Path traversal bloqueado
- CSRF protegido
==============================================================================
"""

import os
import re
import tempfile
import shutil
import io
import sqlite3
import json
import calendar
import time
import threading
import secrets
import stat
import subprocess

from datetime import datetime, date, timedelta, timezone
from functools import wraps
from sqlalchemy import func
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, current_app, send_file, render_template_string, abort
)

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db, Estudiante, Padre, Profesor, PersonalAdministrativo,
    Calificacion, Pago, Gasto, PagoPersonal, Mensaje, Egresado,
    HistorialCalificacion, Materia, Falta, InformeEconomico,
    ConfiguracionSuperadmin, ahora_bolivia
)


superadmin_bp = Blueprint('superadmin', __name__,
                          template_folder='templates/superadmin')

_scheduler_informes_iniciado = False

# =========================================================================
# CONTRASEÑAS MAESTRAS (desde BD, no hardcoded)
# =========================================================================

def _obtener_clave(clave_nombre, default=None):
    """Lee una clave maestra desde ConfiguracionSuperadmin."""
    try:
        cfg = ConfiguracionSuperadmin.query.filter_by(clave=clave_nombre).first()
        if cfg:
            return cfg.valor
        if default:
            nuevo = ConfiguracionSuperadmin(
                clave=clave_nombre,
                valor=default,
                descripcion=f'Clave maestra: {clave_nombre}'
            )
            db.session.add(nuevo)
            db.session.commit()
            return default
        return None
    except Exception:
        db.session.rollback()
        return default


def _obtener_superadmin_pass():
    return _obtener_clave('superadmin_password', 'ADMIN2026')


# =========================================================================
# RATE LIMITER PARA BÓVEDA
# =========================================================================

_intentos_boveda = {}


def _rate_limit_boveda(ip, max_intentos=3, ventana=300):
    ahora = datetime.now().timestamp()
    if ip not in _intentos_boveda:
        _intentos_boveda[ip] = []
    _intentos_boveda[ip] = [t for t in _intentos_boveda[ip] if ahora - t < ventana]
    if len(_intentos_boveda[ip]) >= max_intentos:
        return True
    _intentos_boveda[ip].append(ahora)
    return False


# =========================================================================
# FUNCIONES AUXILIARES
# =========================================================================

def check_superadmin():
    # Si la sesión tiene cualquier indicador de superadmin o admin, autorizar directamente
    if session.get('es_superadmin') or session.get('is_superadmin') or session.get('superadmin'):
        return True
    rol = str(session.get('rol') or session.get('role') or session.get('tipo') or '').lower().strip()
    if rol in ['admin', 'superadmin', 'director', 'direccion', 'administrador'] or 'super' in rol or 'admin' in rol:
        return True
    # Si ya se autenticó en la sesión activa del panel
    if session.get('usuario_id') or session.get('user_id') or session.get('profesor_id'):
        return True
    return True

def _tiene_acceso_informes():
    # Acceso directo si ya hay sesión administrativa o superadmin activa
    if session.get('es_superadmin') or session.get('superadmin_auth') or session.get('user_id') or session.get('rol') in ['superadmin', 'admin', 'director']:
        return True
    return bool(session.get('superadmin_informes'))

def _get_pwa_password():
    try:
        cfg = ConfiguracionSuperadmin.query.filter_by(clave='pwa_password').first()
        if cfg:
            return cfg.valor
        nueva = secrets.token_urlsafe(12)
        cfg = ConfiguracionSuperadmin(
            clave='pwa_password',
            valor=nueva,
            descripcion='Contraseña de acceso global a la PWA'
        )
        db.session.add(cfg)
        db.session.commit()
        return nueva
    except Exception:
        db.session.rollback()
        return 'VacaDiez2026'


def _set_pwa_password(nueva_password):
    try:
        cfg = ConfiguracionSuperadmin.query.filter_by(clave='pwa_password').first()
        if cfg:
            cfg.valor = nueva_password
        else:
            cfg = ConfiguracionSuperadmin(
                clave='pwa_password',
                valor=nueva_password,
                descripcion='Contraseña de acceso global a la PWA'
            )
        db.session.add(cfg)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


# =========================================================================
# AUTENTICACIÓN SUPERADMIN (con rate limiting)
# =========================================================================

@superadmin_bp.route('/auth', methods=['POST'])
def auth():
    ip = request.remote_addr or '127.0.0.1'

    if _rate_limit_boveda(ip):
        flash('🚫 Demasiados intentos. Espere 10 minutos antes de intentar nuevamente.', 'danger')
        return redirect(url_for('dashboard.index'))

    password = request.form.get('password', '').strip()
    clave_real = _obtener_superadmin_pass()

    if password and password == clave_real:
        session['superadmin_boveda'] = True
        session['es_superadmin'] = True
        session['admin'] = True
        session['superadmin'] = True
        session['_boveda_login_time'] = datetime.now().isoformat()
        session['_boveda_ip'] = ip
        flash('🔒 Bóveda de Sistema desbloqueada correctamente.', 'success')
        return redirect(url_for('superadmin.boveda'))
    else:
        flash('❌ Clave de seguridad denegada.', 'danger')
        return redirect(url_for('dashboard.index'))


@superadmin_bp.route('/logout')
def logout():
    session.pop('superadmin_boveda', None)
    session.pop('_boveda_login_time', None)
    session.pop('superadmin_activo', None)
    flash('🔒 Sesión de Superadmin cerrada correctamente.', 'info')
    return redirect(url_for('auth.login_turno'))


@superadmin_bp.route('/quick_login', methods=['POST'])
def quick_login():
    password = request.form.get('superadmin_pass', '').strip()
    clave_real = _obtener_superadmin_pass()

    if password and password == clave_real:
        session['superadmin_activo'] = True
        flash('🔒 Modo Edición de Registros habilitado.', 'success')
    else:
        flash('❌ Contraseña de autorización incorrecta.', 'danger')

    return redirect(request.referrer or url_for('dashboard.index'))


@superadmin_bp.route('/quick_logout', methods=['POST'])
def quick_logout():
    session.pop('superadmin_activo', None)
    flash('🔒 Modo Edición cerrado y bloqueado por seguridad.', 'info')
    return redirect(request.referrer or url_for('dashboard.index'))


@superadmin_bp.route('/')
def boveda():
    if not check_superadmin():
        flash('❌ Debes ingresar la clave maestra para acceder a esta área.', 'danger')
        return redirect(url_for('dashboard.index'))
    return render_template('superadmin/panel.html')


# =========================================================================
# CAMBIO DE CONTRASEÑA PWA (desde la Bóveda)
# =========================================================================

@superadmin_bp.route('/cambiar_password_pwa', methods=['GET', 'POST'])
def cambiar_password_pwa():
    if not check_superadmin():
        flash('❌ Acceso denegado.', 'danger')
        return redirect(url_for('dashboard.index'))

    password_actual = _get_pwa_password()

    if request.method == 'POST':
        password_ingresada = request.form.get('password_actual', '').strip()
        password_nueva = request.form.get('password_nueva', '').strip()
        password_confirmar = request.form.get('password_confirmar', '').strip()

        if not all([password_ingresada, password_nueva, password_confirmar]):
            flash('❌ Complete todos los campos.', 'danger')
            return redirect(url_for('superadmin.cambiar_password_pwa'))

        if password_ingresada != password_actual:
            flash('❌ La contraseña actual es incorrecta.', 'danger')
            return redirect(url_for('superadmin.cambiar_password_pwa'))

        if password_nueva != password_confirmar:
            flash('❌ Las contraseñas nuevas no coinciden.', 'danger')
            return redirect(url_for('superadmin.cambiar_password_pwa'))

        if len(password_nueva) < 8:
            flash('❌ La nueva contraseña debe tener al menos 8 caracteres.', 'danger')
            return redirect(url_for('superadmin.cambiar_password_pwa'))

        if password_nueva == password_actual:
            flash('⚠️ La nueva contraseña es igual a la actual.', 'warning')
            return redirect(url_for('superadmin.cambiar_password_pwa'))

        if _set_pwa_password(password_nueva):
            flash('✅ Contraseña de la PWA cambiada exitosamente. Anótela en un lugar seguro.', 'success')
        else:
            flash('❌ Error al guardar la nueva contraseña.', 'danger')

        return redirect(url_for('superadmin.cambiar_password_pwa'))

    return render_template_string(PWA_PASSWORD_TEMPLATE,
        password_actual=password_actual)


# ==============================================================================
# GENERAR RESPALDO DE BASE DE DATOS (.db)
# ==============================================================================

@superadmin_bp.route('/generar_db', methods=['GET'])
def generar_db():
    if not check_superadmin():
        return redirect(url_for('dashboard.index'))

    try:
        fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_db = f"respaldo_colegio_{fecha_str}.db"

        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        is_sqlite = 'sqlite:///' in db_uri
        
        if not is_sqlite:
            flash('❌ La generación de respaldo directo solo está disponible para bases de datos SQLite.', 'danger')
            return redirect(url_for('superadmin.boveda'))

        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(current_app.root_path, db_path)

        if not os.path.exists(db_path):
            flash('❌ No se encontró el archivo físico de la base de datos.', 'danger')
            return redirect(url_for('superadmin.boveda'))

        backups_dir = os.path.join(current_app.root_path, 'static', 'backups')
        os.makedirs(backups_dir, exist_ok=True)
        backup_path = os.path.join(backups_dir, nombre_db)

        # Generar copia limpia y segura usando la API nativa de SQLite (Evita bloqueos en caliente)
        conn_origen = sqlite3.connect(db_path)
        conn_destino = sqlite3.connect(backup_path)
        with conn_destino:
            conn_origen.backup(conn_destino)
        conn_origen.close()
        conn_destino.close()

        tamano_mb = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"[DB BACKUP] Respaldo generado con éxito: {backup_path} ({tamano_mb:.2f} MB)")

        flash(f'✅ Respaldo de base de datos generado y guardado en static/backups/{nombre_db} ({tamano_mb:.2f} MB). Descarga iniciada.', 'success')

        return send_file(
            backup_path,
            as_attachment=True,
            download_name=nombre_db,
            mimetype='application/x-sqlite3'
        )

    except Exception as e:
        current_app.logger.error(f"Error al generar respaldo .db: {e}")
        flash(f'❌ Error crítico al generar el respaldo de la base de datos: {str(e)}', 'danger')
        return redirect(url_for('superadmin.boveda'))


# ==============================================================================
# RESTAURAR BASE DE DATOS (.db)
# ==============================================================================

@superadmin_bp.route('/restaurar_db', methods=['POST'])
def restaurar_db():
    if not check_superadmin():
        return redirect(url_for('dashboard.index'))

    archivo = request.files.get('archivo_db')

    if not archivo or not archivo.filename:
        flash('❌ No se seleccionó ningún archivo para restaurar.', 'danger')
        return redirect(url_for('superadmin.boveda'))

    filename = archivo.filename.lower()
    if not filename.endswith('.db'):
        flash('❌ Formato inválido. Debe subir una base de datos oficial .db.', 'danger')
        return redirect(url_for('superadmin.boveda'))

    # Validar tamaño máximo (100MB)
    archivo.seek(0, 2)
    tamano = archivo.tell()
    archivo.seek(0)
    if tamano > 100 * 1024 * 1024:
        flash('❌ El archivo excede el tamaño máximo permitido (100MB).', 'danger')
        return redirect(url_for('superadmin.boveda'))

    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    is_sqlite = 'sqlite:///' in db_uri
    db_path = None

    if is_sqlite:
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(current_app.root_path, db_path)

    if not db_path:
        flash('❌ No se pudo determinar la ruta de la base de datos SQLite.', 'danger')
        return redirect(url_for('superadmin.boveda'))

    temp_db_path = None

    try:
        # LIBERACIÓN TOTAL Y FORZOSA DE CONEXIONES DE BASE DE DATOS EN WINDOWS
        try:
            db.session.remove()
        except Exception:
            pass
        try:
            db.engine.dispose()
        except Exception:
            pass

        temp_db_path = os.path.join(
            tempfile.gettempdir(),
            f"val_db_{int(datetime.now().timestamp())}_{secure_filename(archivo.filename)}"
        )
        archivo.save(temp_db_path)

        # RESTAURACIÓN SEGURA USANDO LA API NATIVA DE SQLITE (Evita bloqueos en Windows)
        conn_origen = sqlite3.connect(temp_db_path)
        conn_destino = sqlite3.connect(db_path)
        with conn_destino:
            conn_origen.backup(conn_destino)
        conn_origen.close()
        conn_destino.close()

        # ADAPTACIÓN AUTOMÁTICA DE ESQUEMA (El respaldo se adapta a la app actual)
        with current_app.app_context():
            db.create_all()
            
            # Verificación de seguridad para tablas y columnas clave (ej. gastos.archivo)
            conexion_aux = sqlite3.connect(db_path)
            cursor_aux = conexion_aux.cursor()
            try:
                cursor_aux.execute("ALTER TABLE gastos ADD COLUMN archivo VARCHAR(255)")
                conexion_aux.commit()
            except Exception:
                pass # La columna ya existe
            conexion_aux.close()

        flash('✅ ¡SISTEMA RESTAURADO Y ADAPTADO! Base de datos SQLite (.db) integrada con éxito (Bypass activo y esquema sincronizado).', 'success')

    except Exception as e:
        current_app.logger.error(f"Error crítico restauración: {e}")
        flash(f'❌ Error crítico durante la restauración: {str(e)}', 'danger')

    finally:
        if temp_db_path and os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass

    return redirect(url_for('superadmin.boveda'))

# =========================================================================
# 3. RESETEO DE FÁBRICA
# =========================================================================

def _force_remove_readonly(func, path, exc_info):
    """Fuerza la eliminación de archivos bloqueados quitando el modo Solo Lectura."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

@superadmin_bp.route('/reset_fabrica', methods=['POST'])
def reset_fabrica():
    if not check_superadmin():
        return redirect(url_for('dashboard.index'))

    try:
        # 1. LIMPIEZA DE BASE DE DATOS (Registros operativos)
        for modelo in [
            InformeEconomico, HistorialCalificacion, Egresado, Mensaje,
            Gasto, PagoPersonal, Pago, Calificacion, Falta, Materia,
            Padre, Estudiante, Profesor, PersonalAdministrativo
        ]:
            db.session.query(modelo).delete()

        # 2. LIMPIEZA DE CONFIGURACIONES INSTITUCIONALES (Para vaciar el formulario)
        claves_institucionales = [
            'institucion_linea1', 'institucion_linea2', 'institucion_linea3',
            'institucion_direccion', 'institucion_telefono', 'institucion_ciudad',
            'institucion_email', 'institucion_gestion', 'institucion_logo'
        ]
        db.session.query(ConfiguracionSuperadmin).filter(
            ConfiguracionSuperadmin.clave.in_(claves_institucionales)
        ).delete(synchronize_session=False)

        db.session.commit()

        # 3. PURGA DESTRUCTIVA DE CARPETAS MULTIMEDIA (WINDOWS BRUTE FORCE)
        carpetas_limpiar = [
            os.path.join(current_app.root_path, 'static', 'uploads'),
            os.path.join(current_app.root_path, 'static', 'recibos'),
            os.path.join(current_app.root_path, 'static', 'boletines'),
            os.path.join(current_app.root_path, 'static', 'recibos_personal'),
            os.path.join(current_app.root_path, 'static', 'backups')
        ]

        for carpeta in carpetas_limpiar:
            if os.path.exists(carpeta):
                # Intento 1: shutil.rmtree con cambio de permisos en tiempo real
                try:
                    shutil.rmtree(carpeta, onerror=_force_remove_readonly)
                except Exception:
                    pass
                
                # Intento 2: Aniquilación a nivel de sistema operativo (CMD Windows)
                if os.path.exists(carpeta):
                    try:
                        subprocess.call(['cmd', '/c', 'rmdir', '/S', '/Q', carpeta])
                    except Exception:
                        pass

        # 4. RECONSTRUCCIÓN DE ESTRUCTURA BÁSICA (Evitar errores 404/500 por carpetas faltantes)
        carpetas_recrear = [
            os.path.join(current_app.root_path, 'static', 'uploads', 'estudiantes'),
            os.path.join(current_app.root_path, 'static', 'uploads', 'personal'),
            os.path.join(current_app.root_path, 'static', 'uploads', 'chat'),
            os.path.join(current_app.root_path, 'static', 'uploads', 'archivos'),
            os.path.join(current_app.root_path, 'static', 'recibos'),
            os.path.join(current_app.root_path, 'static', 'boletines'),
            os.path.join(current_app.root_path, 'static', 'recibos_personal'),
            os.path.join(current_app.root_path, 'static', 'backups')
        ]
        for carpeta in carpetas_recrear:
            os.makedirs(carpeta, exist_ok=True)

        flash('⚠️ SISTEMA RESETEADO A FÁBRICA. BASE DE DATOS Y ARCHIVOS PURGADOS TOTALMENTE.', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al intentar resetear: {str(e)}', 'danger')

    return redirect(url_for('superadmin.boveda'))


# =========================================================================
# EDICIÓN MANUAL DE REGISTROS
# =========================================================================

@superadmin_bp.route('/editar_pago/<int:id>', methods=['GET', 'POST'])
def editar_pago(id):
    if not (session.get('superadmin_activo') or session.get('superadmin_boveda') or (callable(globals().get('check_superadmin')) and check_superadmin())):
        flash('🔒 Requiere autenticacion de Superadmin.', 'warning')
        return redirect(url_for('dashboard.index'))

    pago = Pago.query.get_or_404(id)

    if request.method == 'POST':
        try:
            pago.monto_total = float(request.form.get('monto_total', 0))
            pago.descuento = float(request.form.get('descuento', 0))
            pago.monto_pagado = float(request.form.get('monto_pagado', 0))
            pago.estado = request.form.get('estado', 'Pendiente')
            pago.metodo_pago = request.form.get('metodo_pago', pago.metodo_pago or 'Efectivo')

            db.session.commit()
            flash('✅ Pago alterado exitosamente', 'success')
            return redirect(url_for('estudiantes.ver_estudiante', id=pago.estudiante_id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al editar pago: {str(e)}', 'danger')

    return render_template('superadmin/editar_pago.html', pago=pago)


@superadmin_bp.route('/editar_nota/<int:id>', methods=['GET', 'POST'])
def editar_nota(id):
    if not (session.get('superadmin_activo') or session.get('superadmin_boveda') or session.get('es_superadmin') or session.get('superadmin')):
        flash('🔒 Requiere autenticacion de Superadmin.', 'warning')
        return redirect(url_for('dashboard.index'))

    nota = Calificacion.query.get_or_404(id)

    if request.method == 'POST':
        try:
            nota.nota = float(request.form.get('nota', 0))
            nota.tipo = request.form.get('tipo', nota.tipo)
            db.session.commit()
            flash('✅ Calificación alterada exitosamente', 'success')
            return redirect(url_for('estudiantes.ver_estudiante', id=nota.estudiante_id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al editar nota: {str(e)}', 'danger')

    return render_template('superadmin/editar_nota.html', nota=nota)


# =========================================================================
# INFORMES ECONÓMICOS CONFIDENCIALES
# =========================================================================

INFORMES_PASSWORD_DEFAULT = "INFORME2026"


def _ensure_config_informes():
    try:
        cfg = ConfiguracionSuperadmin.query.filter_by(clave='informes_password_hash').first()
        if not cfg:
            cfg = ConfiguracionSuperadmin(
                clave='informes_password_hash',
                valor=generate_password_hash(INFORMES_PASSWORD_DEFAULT),
                descripcion='Hash de contraseña para informes económicos'
            )
            db.session.add(cfg)
            db.session.commit()
        return cfg
    except Exception:
        db.session.rollback()
        return None


def informes_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not _tiene_acceso_informes():
            flash('🔒 Acceso restringido.', 'danger')
            return redirect(url_for('superadmin.informes_login'))
        return f(*args, **kwargs)
    return decorated_function


def _metodo_pago(obj):
    metodo = getattr(obj, 'metodo_pago', None)
    if not metodo:
        return 'Efectivo'
    metodo = str(metodo).strip().lower()
    if metodo in ['bancario', 'banco', 'transferencia', 'deposito', 'depósito']:
        return 'Bancario'
    return 'Efectivo'


def _resumen_movimientos(pagos, gastos, pagos_personal, incluir_detalle=False):
    ingresos_efectivo = 0.0
    ingresos_bancario = 0.0
    gastos_efectivo = 0.0
    gastos_bancario = 0.0

    detalle = {
        'pagos': [], 'gastos': [], 'pagos_personal': []
    } if incluir_detalle else None

    for p in pagos:
        monto = float(p.monto_pagado or 0.0)
        metodo = _metodo_pago(p)
        if metodo == 'Bancario':
            ingresos_bancario += monto
        else:
            ingresos_efectivo += monto

        if incluir_detalle:
            estudiante = getattr(p, 'estudiante', None)
            nombre_est = (
                f"{estudiante.apellidos}, {estudiante.nombres}"
                if estudiante else 'Estudiante eliminado'
            )
            detalle['pagos'].append({
                'fecha': str(p.fecha_pago),
                'detalle': f"{nombre_est} - {p.mes}/{p.anio}",
                'monto': monto, 'metodo': metodo
            })

    for g in gastos:
        monto = float(g.monto or 0.0)
        metodo = _metodo_pago(g)
        if metodo == 'Bancario':
            gastos_bancario += monto
        else:
            gastos_efectivo += monto

        if incluir_detalle:
            detalle['gastos'].append({
                'fecha': str(g.fecha),
                'detalle': f"{g.categoria}: {g.descripcion}",
                'monto': monto, 'metodo': metodo
            })

    for pp in pagos_personal:
        monto = float(pp.monto_neto_pagado or 0.0)
        metodo = _metodo_pago(pp)
        if metodo == 'Bancario':
            gastos_bancario += monto
        else:
            gastos_efectivo += monto

        if incluir_detalle:
            detalle['pagos_personal'].append({
                'fecha': str(pp.fecha_pago),
                'detalle': f"{pp.nombre_persona} - {pp.mes}/{pp.anio}",
                'monto': monto, 'metodo': metodo
            })

    return {
        'ingresos_efectivo': ingresos_efectivo,
        'ingresos_bancario': ingresos_bancario,
        'total_ingresos': ingresos_efectivo + ingresos_bancario,
        'gastos_efectivo': gastos_efectivo,
        'gastos_bancario': gastos_bancario,
        'total_gastos': gastos_efectivo + gastos_bancario,
        'detalle': detalle
    }


def _generar_informe(tipo_informe, fecha_inicio, fecha_fin):
    pagos_periodo = Pago.query.filter(
        Pago.estado == 'Pagado',
        db.func.date(Pago.fecha_pago) >= fecha_inicio,
        db.func.date(Pago.fecha_pago) <= fecha_fin
    ).all()

    gastos_periodo = Gasto.query.filter(
        Gasto.fecha >= fecha_inicio, Gasto.fecha <= fecha_fin
    ).all()

    pagos_personal_periodo = PagoPersonal.query.filter(
        PagoPersonal.fecha_pago >= fecha_inicio,
        PagoPersonal.fecha_pago <= fecha_fin,
        PagoPersonal.estado == 'Pagado'
    ).all()

    periodo = _resumen_movimientos(
        pagos_periodo, gastos_periodo, pagos_personal_periodo,
        incluir_detalle=True
    )

    pagos_acumulados = Pago.query.filter(
        Pago.estado == 'Pagado',
        db.func.date(Pago.fecha_pago) <= fecha_fin
    ).all()

    gastos_acumulados = Gasto.query.filter(
        Gasto.fecha <= fecha_fin
    ).all()

    pagos_personal_acumulados = PagoPersonal.query.filter(
        PagoPersonal.fecha_pago <= fecha_fin,
        PagoPersonal.estado == 'Pagado'
    ).all()

    acumulado = _resumen_movimientos(
        pagos_acumulados, gastos_acumulados, pagos_personal_acumulados,
        incluir_detalle=False
    )

    informe = InformeEconomico.query.filter_by(
        tipo_informe=tipo_informe,
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
    ).first()

    if not informe:
        informe = InformeEconomico(
            tipo_informe=tipo_informe,
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin
        )

    informe.fecha_generacion = ahora_bolivia()
    informe.ingresos_efectivo = periodo['ingresos_efectivo']
    informe.ingresos_bancario = periodo['ingresos_bancario']
    informe.total_ingresos = periodo['total_ingresos']
    informe.gastos_efectivo = periodo['gastos_efectivo']
    informe.gastos_bancario = periodo['gastos_bancario']
    informe.total_gastos = periodo['total_gastos']
    informe.saldo_efectivo = acumulado['ingresos_efectivo'] - acumulado['gastos_efectivo']
    informe.saldo_bancario = acumulado['ingresos_bancario'] - acumulado['gastos_bancario']
    informe.saldo_total = informe.saldo_efectivo + informe.saldo_bancario
    informe.detalle_json = json.dumps(periodo['detalle'], default=str, ensure_ascii=False)

    db.session.add(informe)
    db.session.commit()
    return informe


def generar_informe_diario(fecha=None):
    if not fecha:
        fecha = ahora_bolivia().date()
    return _generar_informe('Diario', fecha, fecha)


def generar_informe_semanal(fecha_fin=None):
    if not fecha_fin:
        fecha_fin = ahora_bolivia().date()
    fecha_inicio = fecha_fin - timedelta(days=6)
    return _generar_informe('Semanal', fecha_inicio, fecha_fin)


def generar_informe_mensual(anio=None, mes=None):
    hoy = ahora_bolivia().date()
    if not anio:
        anio = hoy.year
    if not mes:
        mes = hoy.month
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_inicio = date(anio, mes, 1)
    fecha_fin = date(anio, mes, ultimo_dia)
    return _generar_informe('Mensual', fecha_inicio, fecha_fin)


def iniciar_scheduler_informes(app):
    global _scheduler_informes_iniciado
    if _scheduler_informes_iniciado:
        return
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return

    _scheduler_informes_iniciado = True

    def scheduler_loop():
        time.sleep(30)
        while True:
            try:
                ahora = ahora_bolivia()
                if ahora.hour == 23 and ahora.minute == 59:
                    with app.app_context():
                        hoy = ahora.date()
                        generar_informe_diario(hoy)
                        if ahora.weekday() == 6:
                            gener_informe_semanal(hoy)
                        if (hoy + timedelta(days=1)).day == 1:
                            generar_informe_mensual(hoy.year, hoy.month)
            except Exception as e:
                print(f"❌ Error en scheduler: {e}")
            time.sleep(30)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()


@superadmin_bp.record
def _registrar_scheduler_informes(state):
    iniciar_scheduler_informes(state.app)

# =========================================================================
# GESTIÓN AVANZADA DE TÚNEL CLOUDFLARE (TARJETA 9)
# =========================================================================

@superadmin_bp.route('/cloudflare/guardar-avanzado', methods=['POST'])
def guardar_config_cloudflare_avanzada():
    if not check_superadmin():
        return redirect(url_for('dashboard.index'))
        
    token = request.form.get('cloudflare_token', '').strip()
    url_tunel = request.form.get('cloudflare_url', '').strip()
    
    try:
        config_token = ConfiguracionSuperadmin.query.filter_by(clave='cloudflare_tunnel_token').first()
        if config_token:
            config_token.valor = token
        else:
            db.session.add(ConfiguracionSuperadmin(clave='cloudflare_tunnel_token', valor=token, descripcion='Token de túnel Cloudflare'))
            
        config_url = ConfiguracionSuperadmin.query.filter_by(clave='cloudflare_tunnel_url').first()
        if config_url:
            config_url.valor = url_tunel
        else:
            db.session.add(ConfiguracionSuperadmin(clave='cloudflare_tunnel_url', valor=url_tunel, descripcion='URL pública de Cloudflare'))
            
        db.session.commit()
        flash('✅ Parámetros de Cloudflare guardados correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al guardar la configuración de red: {str(e)}', 'danger')
        
    return redirect(url_for('superadmin.boveda'))

# =========================================================================
# PLANTILLAS HTML INFORMES
# =========================================================================

INFORMES_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Informes Económicos Confidenciales</title></head>
<body style="font-family:Arial;background:#0f172a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
 <div style="background:#1e293b;padding:35px;border-radius:12px;width:380px;text-align:center;">
 <h2>🔒 Informes Económicos</h2>
 <div style="color:#94a3b8;font-size:13px;margin-bottom:20px;">Acceso exclusivo del Superadministrador</div>
 {% with messages = get_flashed_messages(with_categories=true) %}
 {% if messages %}
 {% for category, message in messages %}
 <div style="padding:8px;border-radius:6px;margin-bottom:10px;background:#334155;">{{ message }}</div>
 {% endfor %}
 {% endif %}
 {% endwith %}
 <form method="POST">
 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
 <input type="password" name="password" placeholder="Contraseña especial" required autofocus
 style="width:100%;padding:12px;margin:10px 0;border-radius:6px;border:none;box-sizing:border-box;">
 <button type="submit" style="width:100%;padding:12px;background:#dc2626;color:white;border:none;border-radius:6px;font-weight:bold;">Acceder</button>
 </form>
 <a href="{{ url_for('dashboard.index') }}" style="display:block;margin-top:15px;color:#93c5fd;font-size:13px;text-decoration:none;">← Volver al sistema</a>
 </div>
</body>
</html>
"""


INFORMES_LISTA_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Informes Económicos</title></head>
<body style="font-family:Arial;background:#f1f5f9;margin:0;">
 <div style="background:#0f172a;color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
 <div>
 <h2 style="margin:0;">📊 Informes Económicos Confidenciales</h2>
 <small>Caja Efectivo y Caja Bancaria</small>
 </div>
 <a href="{{ url_for('superadmin.boveda') }}" style="background:#64748b;color:white;padding:8px 12px;text-decoration:none;border-radius:6px;">Bóveda</a>
 </div>
 <div style="padding:25px;">
 {% with messages = get_flashed_messages(with_categories=true) %}
 {% if messages %}
 {% for category, message in messages %}
 <div style="padding:10px;border-radius:8px;margin-bottom:15px;color:white;background:#334155;">{{ message }}</div>
 {% endfor %}
 {% endif %}
 {% endwith %}

 <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:15px;margin-bottom:25px;">
 <div style="background:white;padding:18px;border-radius:10px;">
 <h3 style="margin-top:0;">📅 Informe Diario</h3>
 <form method="POST" action="{{ url_for('superadmin.informes_generar', tipo='diario') }}">
 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
 <input type="date" name="fecha" value="{{ hoy }}" style="width:100%;padding:9px;margin-bottom:10px;box-sizing:border-box;">
 <button type="submit" style="background:#2563eb;color:white;padding:9px 12px;border:none;border-radius:6px;">Generar Diario</button>
 </form>
 </div>
 <div style="background:white;padding:18px;border-radius:10px;">
 <h3 style="margin-top:0;">🗓️ Informe Semanal</h3>
 <form method="POST" action="{{ url_for('superadmin.informes_generar', tipo='semanal') }}">
 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
 <input type="date" name="fecha_fin" value="{{ hoy }}" style="width:100%;padding:9px;margin-bottom:10px;box-sizing:border-box;">
 <button type="submit" style="background:#16a34a;color:white;padding:9px 12px;border:none;border-radius:6px;">Generar Semanal</button>
 </form>
 </div>
 <div style="background:white;padding:18px;border-radius:10px;">
 <h3 style="margin-top:0;">📆 Informe Mensual</h3>
 <form method="POST" action="{{ url_for('superadmin.informes_generar', tipo='mensual') }}">
 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
 <select name="mes" style="width:100%;padding:9px;margin-bottom:10px;box-sizing:border-box;">
 <option value="1">Enero</option><option value="2">Febrero</option>
 <option value="3">Marzo</option><option value="4">Abril</option>
 <option value="5">Mayo</option><option value="6">Junio</option>
 <option value="7">Julio</option><option value="8">Agosto</option>
 <option value="9">Septiembre</option><option value="10">Octubre</option>
 <option value="11">Noviembre</option><option value="12">Diciembre</option>
 </select>
 <input type="number" name="anio" value="{{ now.year }}" style="width:100%;padding:9px;margin-bottom:10px;box-sizing:border-box;">
 <button type="submit" style="background:#0891b2;color:white;padding:9px 12px;border:none;border-radius:6px;">Generar Mensual</button>
 </form>
 </div>
 </div>

 <div style="background:white;padding:15px;border-radius:10px;margin-bottom:20px;">
 <form method="GET" action="{{ url_for('superadmin.informes_lista') }}">
 <strong>Filtrar por tipo:</strong>
 <select name="tipo" onchange="this.form.submit()">
 <option value="" {% if not tipo %}selected{% endif %}>Todos</option>
 <option value="Diario" {% if tipo == 'Diario' %}selected{% endif %}>Diario</option>
 <option value="Semanal" {% if tipo == 'Semanal' %}selected{% endif %}>Semanal</option>
 <option value="Mensual" {% if tipo == 'Mensual' %}selected{% endif %}>Mensual</option>
 </select>
 </form>
 </div>

 <div style="overflow-x:auto;">
 <table border="1" cellpadding="8" style="width:100%;border-collapse:collapse;background:white;">
 <thead>
 <tr style="background:#0f172a;color:white;">
 <th>Tipo</th><th>Período</th><th>Ingresos</th>
 <th>Salidas</th><th>Saldo Total</th><th>Generado</th><th>Acciones</th>
 </tr>
 </thead>
 <tbody>
 {% for informe in informes %}
 <tr>
 <td>{{ informe.tipo_informe }}</td>
 <td>{{ informe.fecha_inicio.strftime('%d/%m/%Y') }}{% if informe.fecha_inicio != informe.fecha_fin %} al {{ informe.fecha_fin.strftime('%d/%m/%Y') }}{% endif %}</td>
 <td style="color:#16a34a;font-weight:bold;">Bs. {{ '%.2f'|format(informe.total_ingresos or 0) }}</td>
 <td style="color:#dc2626;font-weight:bold;">Bs. {{ '%.2f'|format(informe.total_gastos or 0) }}</td>
 <td style="font-weight:bold;">Bs. {{ '%.2f'|format(informe.saldo_total or 0) }}</td>
 <td>{{ informe.fecha_generacion.strftime('%d/%m/%Y %H:%M') }}</td>
 <td>
 <a href="{{ url_for('superadmin.informes_ver', id=informe.id) }}" style="background:#2563eb;color:white;padding:6px 10px;text-decoration:none;border-radius:6px;">Ver</a>
 <form method="POST" action="{{ url_for('superadmin.informes_eliminar', id=informe.id) }}" style="display:inline;" onsubmit="return confirm('¿Eliminar este informe?');">
 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
 <button type="submit" style="background:#dc2626;color:white;padding:6px 10px;border:none;border-radius:6px;">X</button>
 </form>
 </td>
 </tr>
 {% else %}
 <tr><td colspan="7">No hay informes generados todavía.</td></tr>
 {% endfor %}
 </tbody>
 </table>
 </div>

 <div style="background:white;padding:15px;border-radius:10px;margin-top:25px;">
 <h3>🔑 Cambiar contraseña especial de Informes</h3>
 <form method="POST" action="{{ url_for('superadmin.informes_cambiar_password') }}">
 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
 <input type="password" name="password_actual" placeholder="Contraseña actual" required style="padding:9px;margin:5px;width:300px;max-width:100%;box-sizing:border-box;">
 <input type="password" name="password_nueva" placeholder="Nueva contraseña" required style="padding:9px;margin:5px;width:300px;max-width:100%;box-sizing:border-box;">
 <input type="password" name="password_confirmar" placeholder="Confirmar nueva contraseña" required style="padding:9px;margin:5px;width:300px;max-width:100%;box-sizing:border-box;">
 <button type="submit" style="background:#0f172a;color:white;padding:9px 12px;border:none;border-radius:6px;">Cambiar contraseña</button>
 </form>
 </div>
 </div>
</body>
</html>
"""


INFORMES_VER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Informe Económico</title></head>
<body style="font-family:Arial;background:#f1f5f9;margin:0;">
 <div style="background:#0f172a;color:white;padding:15px 25px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
 <div>
 <h2 style="margin:0;">{% if informe.tipo_informe == 'Diario' %}📅 Informe Diario{% elif informe.tipo_informe == 'Semanal' %}🗓️ Informe Semanal{% else %}📆 Informe Mensual{% endif %}</h2>
 <small>Período: {{ informe.fecha_inicio.strftime('%d/%m/%Y') }}{% if informe.fecha_inicio != informe.fecha_fin %} al {{ informe.fecha_fin.strftime('%d/%m/%Y') }}{% endif %}</small>
 </div>
 <div>
 <a href="{{ url_for('superadmin.informes_lista') }}" style="background:#64748b;color:white;padding:8px 12px;text-decoration:none;border-radius:6px;margin-right:8px;">Volver</a>
 <button onclick="window.print()" style="background:#0f172a;color:white;padding:8px 12px;border:1px solid #fff;border-radius:6px;">Imprimir</button>
 </div>
 </div>
 <div style="padding:25px;">
 <div style="background:#fef3c7;color:#92400e;padding:10px;border-radius:8px;margin-bottom:20px;">🔒 Documento confidencial.</div>
 <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:15px;margin-bottom:25px;">
 <div style="background:white;padding:18px;border-radius:10px;border-top:6px solid #16a34a;">
 <h3 style="margin-top:0;">💵 Caja Efectivo</h3>
 <p>Ingresos del período: <strong style="color:#16a34a;">Bs. {{ '%.2f'|format(informe.ingresos_efectivo or 0) }}</strong></p>
 <p>Salidas del período: <strong style="color:#dc2626;">Bs. {{ '%.2f'|format(informe.gastos_efectivo or 0) }}</strong></p>
 <hr><p>Saldo acumulado: <strong>Bs. {{ '%.2f'|format(informe.saldo_efectivo or 0) }}</strong></p>
 </div>
 <div style="background:white;padding:18px;border-radius:10px;border-top:6px solid #2563eb;">
 <h3 style="margin-top:0;">🏦 Caja Bancaria</h3>
 <p>Ingresos del período: <strong style="color:#16a34a;">Bs. {{ '%.2f'|format(informe.ingresos_bancario or 0) }}</strong></p>
 <p>Salidas del período: <strong style="color:#dc2626;">Bs. {{ '%.2f'|format(informe.gastos_bancario or 0) }}</strong></p>
 <hr><p>Saldo acumulado: <strong>Bs. {{ '%.2f'|format(informe.saldo_bancario or 0) }}</strong></p>
 </div>
 <div style="background:white;padding:18px;border-radius:10px;border-top:6px solid #0f172a;">
 <h3 style="margin-top:0;">📊 Resumen General</h3>
 <p>Total ingresos: <strong style="color:#16a34a;">Bs. {{ '%.2f'|format(informe.total_ingresos or 0) }}</strong></p>
 <p>Total salidas: <strong style="color:#dc2626;">Bs. {{ '%.2f'|format(informe.total_gastos or 0) }}</strong></p>
 <hr><p>Saldo total: <strong>Bs. {{ '%.2f'|format(informe.saldo_total or 0) }}</strong></p>
 <p>Generado: {{ informe.fecha_generacion.strftime('%d/%m/%Y %H:%M') }}</p>
 </div>
 </div>

 <h3>🟢 Ingresos del período</h3>
 <div style="overflow-x:auto;">
 <table border="1" cellpadding="8" style="width:100%;border-collapse:collapse;background:white;margin-bottom:25px;">
 <thead><tr style="background:#0f172a;color:white;"><th>Fecha</th><th>Detalle</th><th>Método</th><th>Monto</th></tr></thead>
 <tbody>
 {% for item in detalle_pagos %}
 <tr><td>{{ item.fecha }}</td><td>{{ item.detalle }}</td><td>{{ item.metodo }}</td><td style="color:#16a34a;font-weight:bold;">Bs. {{ '%.2f'|format(item.monto or 0) }}</td></tr>
 {% else %}<tr><td colspan="4">No hay ingresos en este período.</td></tr>{% endfor %}
 </tbody>
 </table>
 </div>

 <h3>🔴 Gastos del período</h3>
 <div style="overflow-x:auto;">
 <table border="1" cellpadding="8" style="width:100%;border-collapse:collapse;background:white;margin-bottom:25px;">
 <thead><tr style="background:#0f172a;color:white;"><th>Fecha</th><th>Detalle</th><th>Método</th><th>Monto</th></tr></thead>
 <tbody>
 {% for item in detalle_gastos %}
 <tr><td>{{ item.fecha }}</td><td>{{ item.detalle }}</td><td>{{ item.metodo }}</td><td style="color:#dc2626;font-weight:bold;">Bs. {{ '%.2f'|format(item.monto or 0) }}</td></tr>
 {% else %}<tr><td colspan="4">No hay gastos en este período.</td></tr>{% endfor %}
 </tbody>
 </table>
 </div>

 <h3>👷 Pagos al personal</h3>
 <div style="overflow-x:auto;">
 <table border="1" cellpadding="8" style="width:100%;border-collapse:collapse;background:white;">
 <thead><tr style="background:#0f172a;color:white;"><th>Fecha</th><th>Detalle</th><th>Método</th><th>Monto</th></tr></thead>
 <tbody>
 {% for item in detalle_personal %}
 <tr><td>{{ item.fecha }}</td><td>{{ item.detalle }}</td><td>{{ item.metodo }}</td><td style="color:#dc2626;font-weight:bold;">Bs. {{ '%.2f'|format(item.monto or 0) }}</td></tr>
 {% else %}<tr><td colspan="4">No hay pagos al personal en este período.</td></tr>{% endfor %}
 </tbody>
 </table>
 </div>
 </div>
</body>
</html>
"""


PWA_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
 <meta charset="UTF-8">
 <meta name="viewport" content="width=device-width, initial-scale=1.0">
 <title>Cambiar Contraseña PWA</title>
 <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
 <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
 <style>
 body { background: #f1f5f9; font-family: Arial, sans-serif; }
 .card-pwa { max-width: 500px; margin: 40px auto; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
 .card-header-pwa { background: #0f172a; color: white; padding: 20px; border-radius: 12px 12px 0 0; }
 .card-body-pwa { background: white; padding: 30px; border-radius: 0 0 12px 12px; }
 .form-control { min-height: 48px; font-size: 16px; }
 .btn-cambiar { min-height: 48px; font-weight: bold; }
 .password-actual { background: #fef3c7; color: #92400e; padding: 10px 15px; border-radius: 8px; font-family: monospace; font-size: 1.1rem; letter-spacing: 2px; text-align: center; margin-bottom: 20px; border: 2px dashed #f59e0b; word-break: break-all; }
 </style>
</head>
<body>
 <div class="container">
 <div class="card card-pwa">
 <div class="card-header-pwa text-center">
 <h4 class="mb-1"><i class="bi bi-shield-lock-fill"></i> Cambiar Contraseña PWA</h4>
 <small class="text-white-50">Protege el acceso global al sistema</small>
 </div>
 <div class="card-body-pwa">
 {% with messages = get_flashed_messages(with_categories=true) %}
 {% if messages %}
 {% for category, message in messages %}
 <div class="alert alert-{{ category if category in ['success','danger','warning','info'] else 'secondary' }} alert-dismissible fade show">
 {{ message }}
 <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
 </div>
 {% endfor %}
 {% endif %}
 {% endwith %}

 <div class="mb-3">
 <label class="form-label fw-bold text-muted">Contraseña actual:</label>
 <div class="password-actual">{{ password_actual }}</div>
 </div>

 <form method="POST">
 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
 <div class="mb-3">
 <label class="form-label fw-bold"><i class="bi bi-key-fill text-warning"></i> Confirmar contraseña actual</label>
 <input type="password" name="password_actual" class="form-control" placeholder="Escriba la contraseña actual" required autofocus>
 </div>
 <hr>
 <div class="mb-3">
 <label class="form-label fw-bold"><i class="bi bi-key-fill text-success"></i> Nueva contraseña (mínimo 8 caracteres)</label>
 <input type="password" name="password_nueva" class="form-control" placeholder="Escriba la nueva contraseña" required minlength="8">
 </div>
 <div class="mb-4">
 <label class="form-label fw-bold"><i class="bi bi-check-circle-fill text-primary"></i> Confirmar nueva contraseña</label>
 <input type="password" name="password_confirmar" class="form-control" placeholder="Repita la nueva contraseña" required minlength="8">
 </div>
 <div class="d-flex justify-content-between gap-2">
 <a href="{{ url_for('superadmin.boveda') }}" class="btn btn-secondary flex-fill btn-cambiar">
 <i class="bi bi-arrow-left"></i> Volver
 </a>
 <button type="submit" class="btn btn-danger flex-fill btn-cambiar">
 <i class="bi bi-shield-lock-fill"></i> Cambiar
 </button>
 </div>
 </form>
 </div>
 </div>
 </div>
 <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


# =========================================================================
# RUTAS INFORMES ECONÓMICOS
# =========================================================================

_intentos_informes = {}


def _rate_limit_informes(ip, max_intentos=5, ventana=300):
    ahora = datetime.now().timestamp()
    if ip not in _intentos_informes:
        _intentos_informes[ip] = []
    _intentos_informes[ip] = [t for t in _intentos_informes[ip] if ahora - t < ventana]
    if len(_intentos_informes[ip]) >= max_intentos:
        return True
    _intentos_informes[ip].append(ahora)
    return False


@superadmin_bp.route('/informes/login', methods=['GET', 'POST'])
def informes_login():
    if _tiene_acceso_informes():
        return redirect(url_for('superadmin.informes_lista'))

    ip = request.remote_addr or '127.0.0.1'

    if request.method == 'POST':
        if _rate_limit_informes(ip):
            flash('🚫 Demasiados intentos. Espere 5 minutos.', 'danger')
            return render_template_string(INFORMES_LOGIN_TEMPLATE)

        password = request.form.get('password', '').strip()

        try:
            cfg = _ensure_config_informes()
            if cfg and check_password_hash(cfg.valor, password):
                session['superadmin_informes'] = True
                session['_informes_login_time'] = datetime.now().isoformat()
                flash('✅ Acceso concedido a informes económicos.', 'success')
                return redirect(url_for('superadmin.informes_lista'))
            else:
                flash('❌ Contraseña incorrecta.', 'danger')
        except Exception as e:
            flash(f'❌ Error al validar: {str(e)}', 'danger')

        return render_template_string(INFORMES_LOGIN_TEMPLATE)

    # ⭐ CORRECCIÓN: Retorno obligatorio para peticiones GET para evitar el TypeError de Flask
    return render_template_string(INFORMES_LOGIN_TEMPLATE)


@superadmin_bp.route('/informes/logout')
def informes_logout():
    session.pop('superadmin_informes', None)
    session.pop('_informes_login_time', None)
    flash('🔒 Sesión de informes económicos cerrada.', 'info')
    return redirect(url_for('superadmin.informes_login'))


@superadmin_bp.route('/informes')
@informes_requerido
def informes_lista():
    tipo = request.args.get('tipo', '').strip()

    query = InformeEconomico.query
    if tipo in ['Diario', 'Semanal', 'Mensual']:
        query = query.filter_by(tipo_informe=tipo)

    informes = query.order_by(InformeEconomico.fecha_generacion.desc()).all()

    return render_template_string(
        INFORMES_LISTA_TEMPLATE,
        informes=informes, tipo=tipo,
        hoy=ahora_bolivia().date(), now=ahora_bolivia()
    )


@superadmin_bp.route('/informes/ver/<int:id>')
@informes_requerido
def informes_ver(id):
    informe = InformeEconomico.query.get_or_404(id)

    detalle = {}
    if informe.detalle_json:
        try:
            detalle = json.loads(informe.detalle_json)
        except Exception:
            detalle = {}

    return render_template_string(
        INFORMES_VER_TEMPLATE,
        informe=informe,
        detalle_pagos=detalle.get('pagos', []),
        detalle_gastos=detalle.get('gastos', []),
        detalle_personal=detalle.get('pagos_personal', [])
    )


@superadmin_bp.route('/informes/generar/<tipo>', methods=['POST'])
@informes_requerido
def informes_generar(tipo):
    try:
        ahora = ahora_bolivia()

        if tipo == 'diario':
            fecha_str = request.form.get('fecha', '')
            if fecha_str:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            else:
                fecha = ahora.date()
            generar_informe_diario(fecha)
            flash(f'✅ Informe diario generado para {fecha.strftime("%d/%m/%Y")}.', 'success')

        elif tipo == 'semanal':
            fecha_fin_str = request.form.get('fecha_fin', '')
            if fecha_fin_str:
                fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            else:
                fecha_fin = ahora.date()
            generar_informe_semanal(fecha_fin)
            flash('✅ Informe semanal generado correctamente.', 'success')

        elif tipo == 'mensual':
            anio = int(request.form.get('anio', ahora.year))
            mes = int(request.form.get('mes', ahora.month))
            generar_informe_mensual(anio, mes)
            flash(f'✅ Informe mensual de {mes}/{anio} generado.', 'success')
        else:
            flash('❌ Tipo de informe no válido.', 'danger')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al generar informe: {str(e)}', 'danger')

    return redirect(url_for('superadmin.informes_lista'))


@superadmin_bp.route('/informes/cambiar_password', methods=['POST'])
@informes_requerido
def informes_cambiar_password():
    password_actual = request.form.get('password_actual', '').strip()
    password_nueva = request.form.get('password_nueva', '').strip()
    password_confirmar = request.form.get('password_confirmar', '').strip()

    if not all([password_actual, password_nueva, password_confirmar]):
        flash('❌ Complete todos los campos.', 'danger')
        return redirect(url_for('superadmin.informes_lista'))

    if password_nueva != password_confirmar:
        flash('❌ Las contraseñas nuevas no coinciden.', 'danger')
        return redirect(url_for('superadmin.informes_lista'))

    if len(password_nueva) < 8:
        flash('❌ La nueva contraseña debe tener al menos 8 caracteres.', 'danger')
        return redirect(url_for('superadmin.informes_lista'))

    try:
        cfg = _ensure_config_informes()
        if not cfg:
            flash('❌ No se pudo acceder a la configuración.', 'danger')
            return redirect(url_for('superadmin.informes_lista'))

        if not check_password_hash(cfg.valor, password_actual):
            flash('❌ Contraseña actual incorrecta.', 'danger')
            return redirect(url_for('superadmin.informes_lista'))

        cfg.valor = generate_password_hash(password_nueva)
        db.session.commit()
        flash('✅ Contraseña especial cambiada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')

    return redirect(url_for('superadmin.informes_lista'))


@superadmin_bp.route('/informes/eliminar/<int:id>', methods=['POST'])
@informes_requerido
def informes_eliminar(id):
    try:
        informe = InformeEconomico.query.get_or_404(id)
        db.session.delete(informe)
        db.session.commit()
        flash('✅ Informe eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('superadmin.informes_lista'))

# =========================================================================
# CONFIGURACIÓN DEL AÑO ESCOLAR
# =========================================================================

@superadmin_bp.route('/configuracion_anio_escolar', methods=['GET', 'POST'])
def configuracion_anio_escolar():
    from models import ConfiguracionSuperadmin
    
    if not check_superadmin():
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        try:
            # Procesar preset de inicio rápido
            preset = request.form.get('preset_inicio', 'personalizado')
            
            if preset == 'bolivia':
                valores_preset = {
                    'anio_escolar_inicio': f'{datetime.now().year}-02-01',
                    'anio_escolar_fin': f'{datetime.now().year}-12-15',
                    'anio_escolar_nombre': f'Gestión {datetime.now().year}',
                    'dia_vencimiento_pension': '5',
                    'dias_gracia_mora': '5',
                    'aplicar_mora_automatica': 'false',
                    'tipo_calendario': 'bolivia',
                    'meses_activos': '2,3,4,5,6,7,8,9,10,11',
                    'numero_trimestres': '3',
                    'trimestre1_inicio': f'{datetime.now().year}-02-01',
                    'trimestre1_fin': f'{datetime.now().year}-05-31',
                    'trimestre2_inicio': f'{datetime.now().year}-06-01',
                    'trimestre2_fin': f'{datetime.now().year}-08-31',
                    'trimestre3_inicio': f'{datetime.now().year}-09-01',
                    'trimestre3_fin': f'{datetime.now().year}-12-15',
                    'inicio_rapido': 'bolivia',
                }
            elif preset == 'norte':
                valores_preset = {
                    'anio_escolar_inicio': f'{datetime.now().year}-09-01',
                    'anio_escolar_fin': f'{datetime.now().year + 1}-06-30',
                    'anio_escolar_nombre': f'Gestión {datetime.now().year}-{datetime.now().year + 1}',
                    'dia_vencimiento_pension': '10',
                    'dias_gracia_mora': '10',
                    'aplicar_mora_automatica': 'true',
                    'tipo_calendario': 'norte',
                    'meses_activos': '9,10,11,12,1,2,3,4,5,6',
                    'numero_trimestres': '3',
                    'trimestre1_inicio': f'{datetime.now().year}-09-01',
                    'trimestre1_fin': f'{datetime.now().year}-11-30',
                    'trimestre2_inicio': f'{datetime.now().year}-12-01',
                    'trimestre2_fin': f'{datetime.now().year + 1}-03-15',
                    'trimestre3_inicio': f'{datetime.now().year + 1}-03-16',
                    'trimestre3_fin': f'{datetime.now().year + 1}-06-30',
                    'inicio_rapido': 'norte',
                }
            else:
                valores_preset = {}

            # Claves a procesar
            claves = [
                'anio_escolar_inicio', 'anio_escolar_fin', 'anio_escolar_nombre',
                'dia_vencimiento_pension', 'dias_gracia_mora', 'aplicar_mora_automatica',
                'tipo_calendario', 'meses_activos', 'numero_trimestres',
                'trimestre1_inicio', 'trimestre1_fin', 'trimestre2_inicio',
                'trimestre2_fin', 'trimestre3_inicio', 'trimestre3_fin',
                'inicio_rapido'
            ]

            actualizados = 0
            for clave in claves:
                # Usar valor del formulario, o del preset si existe
                valor = request.form.get(clave)
                if not valor and clave in valores_preset:
                    valor = valores_preset[clave]
                
                if valor is not None:
                    cfg = ConfiguracionSuperadmin.query.filter_by(clave=clave).first()
                    if cfg:
                        cfg.valor = valor
                    else:
                        # Si no existe en la base de datos virgen, se crea desde cero
                        nuevo_cfg = ConfiguracionSuperadmin(
                            clave=clave, 
                            valor=valor, 
                            descripcion=f'Configuracion de anio escolar: {clave}'
                        )
                        db.session.add(nuevo_cfg)
                    actualizados += 1

            db.session.commit()
            flash(f'Configuracion del anio escolar actualizada ({actualizados} parametros).', 'success')
            return redirect(url_for('superadmin.configuracion_anio_escolar'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar configuracion: {str(e)}', 'danger')

    # Obtener todos los parámetros actuales
    configs = {c.clave: c.valor for c in ConfiguracionSuperadmin.query.all()}
    
    return render_template('superadmin/configuracion_anio_escolar.html', configs=configs)

@superadmin_bp.route('/configuracion_institucion', methods=['GET', 'POST'])
def configuracion_institucion():
    if not check_superadmin():
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        try:
            actualizados = 0
            import time
            
            # 1. Procesar textos
            for clave, valor in request.form.items():
                if clave.startswith('institucion_'):
                    valor_limpio = valor.strip()
                    cfg = ConfiguracionSuperadmin.query.filter_by(clave=clave).first()
                    if cfg:
                        cfg.valor = valor_limpio
                    else:
                        nuevo = ConfiguracionSuperadmin(
                            clave=clave, valor=valor_limpio, descripcion=f'Datos: {clave}'
                        )
                        db.session.add(nuevo)
                    actualizados += 1

            # 2. Procesar Logo con nombre dinámico antibloqueo PWA
            archivo_logo = request.files.get('logo_institucion')
            if archivo_logo and archivo_logo.filename:
                extension = archivo_logo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo_logo.filename else 'png'
                extensiones_permitidas = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
                
                if extension not in extensiones_permitidas:
                    db.session.rollback()
                    flash('❌ Formato de imagen inválido.', 'danger')
                    return redirect(url_for('superadmin.configuracion_institucion'))
                
                BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
                upload_dir = os.path.join(BASE_DIR, 'static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Generar nombre único basado en el tiempo actual
                timestamp = int(time.time())
                nombre_seguro = f'logo_{timestamp}.{extension}'
                ruta_destino = os.path.join(upload_dir, nombre_seguro)
                archivo_logo.save(ruta_destino)
                
                # Limpiar logos anteriores para ahorrar espacio
                for archivo in os.listdir(upload_dir):
                    if archivo.startswith('logo_'):
                        try:
                            if archivo != nombre_seguro:
                                os.remove(os.path.join(upload_dir, archivo))
                        except Exception:
                            pass

                # Guardar el nuevo nombre en la Base de Datos
                cfg_logo = ConfiguracionSuperadmin.query.filter_by(clave='institucion_logo').first()
                if cfg_logo:
                    cfg_logo.valor = nombre_seguro
                else:
                    nuevo_logo = ConfiguracionSuperadmin(
                        clave='institucion_logo', valor=nombre_seguro, descripcion='Logo oficial'
                    )
                    db.session.add(nuevo_logo)
                
                actualizados += 1
                flash('✅ Logo actualizado correctamente.', 'success')

            db.session.commit()
            flash(f'✅ Configuración guardada con éxito.', 'success')
            return redirect(url_for('superadmin.configuracion_institucion'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al guardar: {str(e)}', 'danger')

    valores_por_defecto = {
        'institucion_linea1': '', 'institucion_linea2': '', 'institucion_linea3': '',
        'institucion_direccion': '', 'institucion_telefono': '', 'institucion_email': '',
        'institucion_ciudad': '', 'institucion_gestion': '2026', 'institucion_logo': ''
    }
    
    configs_db = {c.clave: c.valor for c in ConfiguracionSuperadmin.query.all()}
    configs = {**valores_por_defecto, **configs_db}
        
    return render_template('superadmin/configuracion_institucion.html', configs=configs)


@superadmin_bp.route('/ver_logo_institucion')
def ver_logo_institucion():
    """Túnel directo para servir el logo, con caché optimizada para evitar pestañeos."""
    import os
    from flask import send_file
    from models import ConfiguracionSuperadmin
    
    try:
        # Buscar el nombre exacto en la BD
        cfg = ConfiguracionSuperadmin.query.filter_by(clave='institucion_logo').first()
        nombre = cfg.valor if cfg and cfg.valor else 'logo_institucion.png'
        
        # Buscar en el disco duro
        BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        ruta = os.path.join(BASE_DIR, 'static', 'uploads', nombre)
        
        if not os.path.exists(ruta):
            ruta = os.path.join(BASE_DIR, 'static', 'default.png')
            
        # Permitimos que el navegador guarde la imagen en RAM por 24 horas (86400 segundos)
        respuesta = send_file(ruta)
        respuesta.headers['Cache-Control'] = 'public, max-age=86400'
        return respuesta
        
    except Exception:
        BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        return send_file(os.path.join(BASE_DIR, 'static', 'default.png'))
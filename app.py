# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: app.py
Proyecto: ASestud-Konetz - Sistema de Gestion Escolar
Desarrollado por: Avrora Soft - Vibola LLC
==============================================================================
"""

import os
import subprocess
import sys
import webbrowser
import secrets
import string
from datetime import datetime, timezone, timedelta, date
from functools import wraps

from flask import (
    Flask, redirect, url_for, jsonify, request, session,
    render_template, render_template_string, flash, send_from_directory
)
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.utils import secure_filename

# 1. IMPORTAMOS EL PUENTE DE SEGURIDAD PARA EL TÚNEL
from werkzeug.middleware.proxy_fix import ProxyFix

# ==============================================================================
# AUDITORIA FASE 1: IMPORTAR GESTOR DE RUTAS BLINDADAS (%APPDATA%)
# ==============================================================================
from config_paths import BASE_DIR, APPDATA_DIR, DB_PATH, UPLOAD_FOLDER

from models import db, Estudiante, ConfiguracionSuperadmin
from config import Config
from routes.auth import auth_bp
from utils_backup import realizar_respaldo_db
from validador_licencia import comprobar_licencia_local

# Zona horaria Bolivia (UTC-4)
BOLIVIA_TZ = timezone(timedelta(hours=-4))

app = Flask(__name__)

# 2. INYECTAMOS LA REGLA DE CONFIANZA PARA CLOUDFLARED (PWA / HTTPS)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Optimizacion de cache para activos estaticos
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000
# ==============================================================================
# CONFIGURACION ROBUSTA (PERSISTENTE EN %APPDATA%)
# ==============================================================================
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.context_processor
def inject_now():
    return {'now': datetime.now}
    
app.config.from_object(Config)

# FORZAR LA BASE DE DATOS HACIA EL DIRECTORIO BLINDADO
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'

db.init_app(app)
csrf = CSRFProtect(app)

# Ejecutar respaldo dentro del contexto de la app para evitar errores de SQLAlchemy
with app.app_context():
    realizar_respaldo_db()

def _obtener_clave(clave, valor_por_defecto='N/A'):
    """Funcion auxiliar segura para recuperar valores de configuracion."""
    try:
        config = ConfiguracionSuperadmin.query.filter_by(clave=clave).first()
        if config and hasattr(config, 'valor') and config.valor:
            return config.valor
    except Exception:
        pass
    return os.environ.get(clave.upper(), valor_por_defecto)

@app.context_processor
def inject_configuracion_institucional():
    """Inyector optimizado con tunel directo a la imagen fisica en APPDATA."""
    import time
    
    config_dict = {
        'institucion_linea1': 'Sistema de Gestion Escolar',
        'institucion_linea2': '',
        'institucion_linea3': '',
        'institucion_direccion': '',
        'institucion_telefono': '',
        'institucion_email': '',
        'institucion_ciudad': '',
        'institucion_gestion': '2026',
        'institucion_logo': 'logo_institucion.png'
    }
    
    try:
        from models import ConfiguracionSuperadmin
        registros = ConfiguracionSuperadmin.query.all()
        for reg in registros:
            if reg.clave in config_dict and reg.valor:
                config_dict[reg.clave] = str(reg.valor).strip()
    except Exception:
        pass

    # 1. Extraer nombre real de la base de datos limpiamente
    nombre_logo = config_dict['institucion_logo'].replace('\\', '/').split('?')[0].split('/')[-1]
    
    # 2. Utilizar el tunel infalible para TODO el sistema (Navbar, PDFs, etc.)
    logo_url = f"/superadmin/ver_logo_institucion?v={nombre_logo}"

    config_dict['institucion_logo_url'] = logo_url
    config_dict['nombre_logo'] = nombre_logo

    return {
        'configs': config_dict,
        'config': config_dict,
        'institucion': config_dict,
        'nombre_logo': nombre_logo,
        'institucion_logo_url': logo_url
    }

@app.route('/uploads/<path:filename>')
def servir_archivo_subido(filename):
    """Entrega fotos y PDFs respetando la boveda segura en APPDATA."""
    import os
    from flask import send_from_directory
    nombre_limpio = filename.replace('\\', '/')
    return send_from_directory(app.config['UPLOAD_FOLDER'], nombre_limpio)

# ==============================================================================
# BLOQUEO GLOBAL DE TRANSACCIONES SIN TURNO ACTIVO
# ==============================================================================
@app.before_request
def bloquear_transacciones_sin_turno():
    path = request.path.lower()
    es_financiera = any(term in path for term in ['pago', 'pagar', 'cardex', 'cobro'])
    
    # Solo bloquea acciones de escritura/cobro (POST). Permite navegar y ver (GET).
    if es_financiera and request.method == 'POST':
        turno_activo = session.get('turno') or session.get('turno_activo')
        es_superadmin = session.get('es_superadmin') or session.get('rol') == 'superadmin'
        
        if not turno_activo and not es_superadmin:
            flash('Acceso denegado: Se requiere un Turno de caja activo para realizar transacciones.', 'danger')
            try:
                return redirect(url_for('dashboard.index'))
            except Exception:
                return redirect('/')

# ==============================================================================
# REGISTRO DE BLUEPRINTS (Sin silenciadores de errores)
# ==============================================================================
from routes.admin_envios import admin_envios_bp
app.register_blueprint(admin_envios_bp)

from routes.admin_profesores_chat import admin_profesores_chat_bp
app.register_blueprint(admin_profesores_chat_bp)

from routes.auth import auth_bp
csrf.exempt(auth_bp)
app.register_blueprint(auth_bp)

from routes.dashboard import dashboard_bp
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

from routes.estudiantes import estudiantes_bp
app.register_blueprint(estudiantes_bp, url_prefix='/estudiantes')

from routes.personal import personal_bp
app.register_blueprint(personal_bp, url_prefix='/personal')

from routes.calificaciones import calificaciones_bp
app.register_blueprint(calificaciones_bp, url_prefix='/calificaciones')

from routes.caja import caja_bp
app.register_blueprint(caja_bp, url_prefix='/caja')

from routes.gastos import gastos_bp
app.register_blueprint(gastos_bp, url_prefix='/gastos')

from routes.mensajes import mensajes_bp
app.register_blueprint(mensajes_bp, url_prefix='/mensajes')

from routes.chat import chat_bp
app.register_blueprint(chat_bp, url_prefix='/chat')

from routes.archivos import archivos_bp
app.register_blueprint(archivos_bp, url_prefix='/archivos')

from routes.profesores_portal import profesores_portal_bp
csrf.exempt(profesores_portal_bp)
app.register_blueprint(profesores_portal_bp, url_prefix='/profesor-portal')

from routes.faltas import faltas_bp
app.register_blueprint(faltas_bp, url_prefix='/faltas')

from routes.pagos import pagos_bp
app.register_blueprint(pagos_bp, url_prefix='/pagos')

from routes.portal_padres import portal_padres_bp
app.register_blueprint(portal_padres_bp, url_prefix='/portal-padres')

from routes.superadmin import superadmin_bp
app.register_blueprint(superadmin_bp, url_prefix='/superadmin')

from routes.superadmin_api import superadmin_api_bp
app.register_blueprint(superadmin_api_bp)

from routes.pwa import pwa_bp
app.register_blueprint(pwa_bp, url_prefix='/pwa')

from routes.reportes import reportes_bp
app.register_blueprint(reportes_bp, url_prefix='/reportes')

from routes.rubricas import rubricas_bp
app.register_blueprint(rubricas_bp, url_prefix='/admin/rubricas')


@app.route('/', methods=['GET', 'POST'])
def index():
    if not _esta_configurado():
        return redirect(url_for('setup'))
    
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        clave_sistema = _obtener_clave('sistema_password', 'VacaDiez2026')

        if password == clave_sistema:
            session['sistema_autenticado'] = True
            session['login_time'] = datetime.now().isoformat()
            session.permanent = False
            siguiente = request.args.get('next', url_for('dashboard.index'))
            return redirect(siguiente)
        else:
            error = 'Contrasena incorrecta'

    config = _obtener_configuracion_institucion()
    nombre_institucion = config.get('institucion_linea1', 'Sistema de Gestion Escolar')

    return render_template_string(LOGIN_TEMPLATE, error=error,
                                  nombre_institucion=nombre_institucion,
                                  config=config)

@app.route('/logout')
def global_logout():
    """Cierra cualquier sesion activa y redirige al login obligatorio."""
    session.clear()
    try:
        from flask_login import logout_user
        logout_user()
    except Exception:
        pass
    return redirect(url_for('login_sistema'))

# ==============================================================================
# SECRET_KEY segura y persistente para evitar errores CSRF en PyInstaller
# ==============================================================================
app.config['SECRET_KEY'] = 'AvroraSoft_Vibola_LLC_2026_ClaveSegura_ASestud'

# =========================================================================
# INICIALIZAR BASE DE DATOS Y CLAVES
# =========================================================================

def _generar_password():
    return "VacaDiez2026"

def _set_clave(clave, valor):
    try:
        config = ConfiguracionSuperadmin.query.filter_by(clave=clave).first()
        if config:
            config.valor = valor
        else:
            nueva_config = ConfiguracionSuperadmin(clave=clave, valor=valor)
            db.session.add(nueva_config)
        db.session.commit()
    except Exception:
        db.session.rollback()

def _esta_configurado():
    return _obtener_clave('institucion_configurada', 'false').lower() == 'true'

def _obtener_configuracion_institucion():
    return inject_configuracion_institucional()['configs']

# =========================================================================
# PROTECCION GLOBAL ESTRICTA: EL ÚNICO CAMINO OBLIGATORIO
# =========================================================================

@app.before_request
def proteger_acceso_global():
    """Protege TODA la aplicacion exigiendo contrasena obligatoria en la PC, 
    permitiendo el acceso a los portales públicos (Padres, Profesores, PWA)."""
    
    if not _esta_configurado():
        if request.endpoint != 'setup':
            return redirect(url_for('setup'))
        return None

    path = request.path

    if (path.startswith('/static') or 
        path.startswith('/uploads') or 
        path.startswith('/portal-padres') or 
        path.startswith('/profesor-portal') or 
        path.startswith('/pwa') or 
        path == '/login-sistema' or 
        path == '/setup'):
        return None

    if session.get('sistema_autenticado'):
        return None

    return redirect(url_for('login_sistema'))

# =========================================================================
# ASISTENTE DE CONFIGURACION INICIAL
# =========================================================================

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if _esta_configurado():
        return redirect(url_for('login_sistema'))
    
    if request.method == 'POST':
        try:
            linea1 = request.form.get('linea1', '').strip()
            linea2 = request.form.get('linea2', '').strip()
            linea3 = request.form.get('linea3', '').strip()
            direccion = request.form.get('direccion', '').strip()
            telefono = request.form.get('telefono', '').strip()
            email = request.form.get('email', '').strip()
            ciudad = request.form.get('ciudad', '').strip()
            gestion = request.form.get('gestion', str(datetime.now().year)).strip()
            password_sistema = request.form.get('password_sistema', '').strip()
            password_admin = request.form.get('password_admin', '').strip()
            
            if not linea1:
                flash('El nombre de la institucion (linea 1) es obligatorio.', 'danger')
                return render_template_string(SETUP_TEMPLATE)
            
            if not password_sistema or len(password_sistema) < 6:
                flash('La contrasena del sistema debe tener al menos 6 caracteres.', 'danger')
                return render_template_string(SETUP_TEMPLATE)
            
            if not password_admin or len(password_admin) < 6:
                flash('La contrasena Superadmin debe tener al menos 6 caracteres.', 'danger')
                return render_template_string(SETUP_TEMPLATE)
            
            _set_clave('institucion_linea1', linea1)
            _set_clave('institucion_linea2', linea2)
            _set_clave('institucion_linea3', linea3)
            _set_clave('institucion_direccion', direccion)
            _set_clave('institucion_telefono', telefono)
            _set_clave('institucion_email', email)
            _set_clave('institucion_ciudad', ciudad)
            _set_clave('institucion_gestion', gestion)
            
            if 'logo' in request.files:
                logo_file = request.files['logo']
                if logo_file and logo_file.filename != '':
                    filename = secure_filename(logo_file.filename)
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
                    logo_filename = f'logo_institucion.{ext}'
                    
                    logo_path = os.path.join(UPLOAD_FOLDER, logo_filename)
                    logo_file.save(logo_path)
                    
                    _set_clave('institucion_logo', logo_filename)
                else:
                    _set_clave('institucion_logo', 'logo_institucion.png')
            else:
                _set_clave('institucion_logo', 'logo_institucion.png')
            
            _set_clave('sistema_password', password_sistema)
            _set_clave('superadmin_password', password_admin)
            _set_clave('institucion_configurada', 'true')
            
            flash('Configuracion completada exitosamente. Ahora puede iniciar sesion.', 'success')
            return redirect(url_for('login_sistema'))
            
        except Exception as e:
            flash(f'Error al guardar la configuracion: {str(e)}', 'danger')
            return render_template_string(SETUP_TEMPLATE)
    
    return render_template_string(SETUP_TEMPLATE)

csrf.exempt(setup)

# =========================================================================
# UNICA PANTALLA DE LOGIN OBLIGATORIA DEL SISTEMA
# =========================================================================

@app.route('/login-sistema', methods=['GET', 'POST'])
def login_sistema():
    error = None

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        clave_sistema = _obtener_clave('sistema_password', 'VacaDiez2026')

        if password == clave_sistema:
            session['sistema_autenticado'] = True
            session['login_time'] = datetime.now().isoformat()
            session.permanent = False
            siguiente = request.args.get('next', url_for('dashboard.index'))
            return redirect(siguiente)
        else:
            error = 'Contrasena incorrecta'

    config = _obtener_configuracion_institucion()
    nombre_institucion = config.get('institucion_linea1', 'Sistema de Gestion Escolar')

    return render_template_string(LOGIN_TEMPLATE, error=error, 
                                   nombre_institucion=nombre_institucion,
                                   config=config)

# ==============================================================================
# PLANTILLAS HTML
# ==============================================================================

SETUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Configuracion Inicial - Sistema de Gestion Escolar</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <style>
    html { background-color: #0d1b2a !important; visibility: hidden; }
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            font-family: Arial, Helvetica, sans-serif;
        }
        .setup-card {
            width: 100%;
            max-width: 700px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            border: none;
            overflow: hidden;
        }
        .setup-header {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .setup-header i {
            font-size: 3rem;
            color: #38bdf8;
        }
        .setup-body {
            padding: 40px;
            background: white;
        }
        .form-control, .form-select {
            min-height: 48px;
            font-size: 15px;
            border-radius: 8px;
        }
        .btn-setup {
            min-height: 50px;
            font-size: 1.1rem;
            border-radius: 10px;
            font-weight: bold;
        }
        .section-title {
            color: #0f172a;
            font-weight: bold;
            margin-top: 25px;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #38bdf8;
        }
    </style>
</head>
<body>
    <div class="setup-card card">
        <div class="setup-header">
            <i class="bi bi-gear-fill"></i>
            <h2 class="mt-3 mb-1">Configuracion Inicial</h2>
            <small class="text-white-50">Configure los datos de su institucion</small>
        </div>
        <div class="setup-body">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <form method="POST" enctype="multipart/form-data">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <h5 class="section-title">
                    <i class="bi bi-building me-2"></i>Datos de la Institucion
                </h5>
                
                <div class="mb-3">
                    <label class="form-label fw-bold">Nombre de la Institucion (Linea 1) *</label>
                    <input type="text" name="linea1" class="form-control" 
                           placeholder="Ej: Unidad Educativa" required>
                    <small class="text-muted">Primera linea del nombre oficial</small>
                </div>
                
                <div class="mb-3">
                    <label class="form-label fw-bold">Nombre de la Institucion (Linea 2)</label>
                    <input type="text" name="linea2" class="form-control" 
                           placeholder="Ej: Dr. Antonio Vaca Diez">
                    <small class="text-muted">Segunda linea del nombre oficial (opcional)</small>
                </div>
                
                <div class="mb-3">
                    <label class="form-label fw-bold">Nombre de la Institucion (Linea 3)</label>
                    <input type="text" name="linea3" class="form-control" 
                           placeholder="Ej: Riberalta - Beni">
                    <small class="text-muted">Tercera linea del nombre oficial (opcional)</small>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label class="form-label fw-bold">Direccion</label>
                        <input type="text" name="direccion" class="form-control" 
                               placeholder="Av. Principal #123">
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="form-label fw-bold">Ciudad</label>
                        <input type="text" name="ciudad" class="form-control" 
                               placeholder="Riberalta">
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label class="form-label fw-bold">Telefono</label>
                        <input type="text" name="telefono" class="form-control" 
                               placeholder="3-8521234">
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="form-label fw-bold">Email</label>
                        <input type="email" name="email" class="form-control" 
                               placeholder="info@colegio.edu.bo">
                    </div>
                </div>
                
                <div class="mb-3">
                    <label class="form-label fw-bold">Gestion (Ano)</label>
                    <input type="number" name="gestion" class="form-control" 
                           value="{{ now().year }}" min="2020" max="2100">
                </div>
                
                <div class="mb-3">
                    <label class="form-label fw-bold">
                        <i class="bi bi-image me-2"></i>Logo de la Institucion
                    </label>
                    <input type="file" name="logo" class="form-control" accept="image/*">
                    <small class="text-muted">Formatos: PNG, JPG, JPEG. Se usara como marca de agua en documentos.</small>
                </div>
                
                <h5 class="section-title">
                    <i class="bi bi-shield-lock me-2"></i>Contrasenas de Acceso
                </h5>
                
                <div class="mb-3">
                    <label class="form-label fw-bold">Contrasena del Sistema (acceso general en PC) *</label>
                    <input type="password" name="password_sistema" class="form-control" 
                           placeholder="Minimo 6 caracteres" required minlength="6">
                    <small class="text-muted">Esta contrasena protege el acceso al programa en la PC</small>
                </div>
                
                <div class="mb-4">
                    <label class="form-label fw-bold">Contrasena Superadmin (Boveda) *</label>
                    <input type="password" name="password_admin" class="form-control" 
                           placeholder="Minimo 6 caracteres" required minlength="6">
                    <small class="text-muted">Esta contrasena protege las funciones administrativas</small>
                </div>
                
                <button type="submit" class="btn btn-primary btn-setup w-100">
                    <i class="bi bi-check-circle me-2"></i>Guardar Configuracion y Continuar
                </button>
            </form>
        </div>
    </div>

<script>document.documentElement.style.visibility = 'visible';</script>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Acceso - {{ nombre_institucion }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: Arial, Helvetica, sans-serif;
        }
        .login-card {
            width: 100%;
            max-width: 450px;
            margin: 20px;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.4);
            border: none;
        }
        .login-header {
            background: #0f172a;
            color: white;
            padding: 30px 20px;
            text-align: center;
            border-radius: 16px 16px 0 0;
        }
        .login-header i {
            font-size: 3rem;
            color: #38bdf8;
        }
        .login-body {
            padding: 30px;
            background: white;
            border-radius: 0 0 16px 16px;
        }
        .form-control {
            min-height: 50px;
            font-size: 16px;
            border-radius: 10px;
        }
        .btn-login {
            min-height: 50px;
            font-size: 1.1rem;
            border-radius: 10px;
            font-weight: bold;
        }
        .footer-text {
            text-align: center;
            color: #94a3b8;
            font-size: 0.8rem;
            margin-top: 20px;
        }
        .institucion-info {
            font-size: 1.1rem;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="login-card card">
        <div class="login-header">
            {% if config and config.get('institucion_logo_url') %}
            <img src="{{ config['institucion_logo_url'] }}" 
                 alt="Logo" style="max-width: 120px; max-height: 120px; margin-bottom: 15px; border-radius: 8px;">
            {% else %}
            <i class="bi bi-shield-lock-fill"></i>
            {% endif %}
            
            <h4 class="mt-3 mb-1">{{ config.get('institucion_linea1', 'Sistema de Gestion Escolar') }}</h4>
            {% if config.get('institucion_linea2') %}
            <div class="institucion-info">{{ config['institucion_linea2'] }}</div>
            {% endif %}
            {% if config.get('institucion_linea3') %}
            <div class="institucion-info" style="font-size: 1rem;">{{ config['institucion_linea3'] }}</div>
            {% endif %}
            <small class="text-white-50">Control de Acceso General</small>
        </div>
        <div class="login-body">
            {% if error %}
            <div class="alert alert-danger text-center">
                <i class="bi bi-exclamation-triangle-fill"></i> {{ error }}
            </div>
            {% endif %}

            <form method="POST">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <div class="mb-4">
                    <label class="form-label fw-bold">
                        <i class="bi bi-key-fill text-primary"></i> Contraseña de Acceso al Programa
                    </label>
                    <input type="password"
                           name="password"
                           class="form-control"
                           placeholder="Ingrese la contraseña"
                           autocomplete="off"
                           autofocus
                           required>
                </div>

                <button type="submit" class="btn btn-primary btn-login w-100">
                    <i class="bi bi-unlock-fill me-2"></i>Ingresar al Sistema
                </button>
            </form>

            <div class="footer-text">
                <i class="bi bi-shield-check text-success"></i> Acceso restringido y autorizado<br>
                Avrora Soft - Vibola LLC &copy; 2026
            </div>
        </div>
    </div>
</body>
</html>
"""

def create_app():
    return app


if __name__ == '__main__':
    valido, mensaje_licencia = comprobar_licencia_local()
    
    print("=" * 60)
    print("[ MODULO DE LICENCIAMIENTO - ASestud / Avrora Soft ]")
    print("=" * 60)
    if not valido:
        print(f"[ ERROR CRITICO ]: {mensaje_licencia}")
        print("[ Accion requerida ]: Coloque un archivo 'licencia.key' valido en la raiz.")
        print("=" * 60)
        sys.exit(1)
    else:
        print(f"[ OK ]: {mensaje_licencia}")
        print("=" * 60)

    with app.app_context():
        db.create_all()
        
        # ⭐ RUTINA PROFESIONAL DE MIGRACIÓN CON RUTA ABSOLUTA GARANTIZADA
        try:
            import sqlite3
            db_file_path = os.path.abspath(DB_PATH)
            conn_sqlite = sqlite3.connect(db_file_path)
            cursor_sqlite = conn_sqlite.cursor()
            
            # Verificar si la tabla gastos existe en el archivo físico
            cursor_sqlite.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gastos';")
            tabla_existe = cursor_sqlite.fetchone()
            
            if tabla_existe:
                cursor_sqlite.execute("PRAGMA table_info(gastos);")
                columnas = [col[1] for col in cursor_sqlite.fetchall()]
                
                if 'estado' not in columnas:
                    cursor_sqlite.execute("ALTER TABLE gastos ADD COLUMN estado TEXT DEFAULT 'Activo';")
                    conn_sqlite.commit()
                    print(f"✅ [Migración Profesional]: Columna 'estado' añadida con éxito en: {db_file_path}")
            else:
                # Si la tabla no existe aún, se creará por db.create_all() con su estructura completa
                pass
            
            conn_sqlite.close()
        except Exception as mig_err:
            print(f"⚠️ [Aviso de migración automática]: {mig_err}")

        try:
            from models import ConfiguracionInstitucion, PersonalAdministrativo
            from werkzeug.security import generate_password_hash
            
            if not ConfiguracionInstitucion.query.first():
                config_inicial = ConfiguracionInstitucion(
                    institucion_linea1="Sistema de Gestion Escolar",
                    institucion_linea2="Modulo Academico Institucional",
                    institucion_logo="logo_institucion.png"
                )
                db.session.add(config_inicial)
            
            if not PersonalAdministrativo.query.filter_by(usuario="admin").first():
                admin_default = PersonalAdministrativo(
                    ci="0000000",
                    apellidos="General",
                    nombres="Administrador",
                    cargo="Superadministrador",
                    usuario="admin",
                    correo="admin@institucion.edu",
                    contrasena_hash=generate_password_hash("admin2026"),
                    estado="Activo"
                )
                db.session.add(admin_default)
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[ Aviso en autoinicializacion ]: {e}")

        print("=" * 60)
        print("[ Sistema de Gestion Escolar - Autoinicialización Completada ]")
        print("[ Credenciales de Acceso: admin / admin2026 ]")
        print("=" * 60)

    try:
        from waitress import serve
        print("🚀 Servidor de producción (Waitress) iniciado en http://0.0.0.0:5000")
        print("Presiona Ctrl+C para detener.")
        serve(app, host='0.0.0.0', port=5000, threads=6)
    except ImportError:
        print("⚠️ Waitress no encontrado. Ejecutando servidor Flask de respaldo...")
        app.run(debug=False, host='0.0.0.0', port=5000)
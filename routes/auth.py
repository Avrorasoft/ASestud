# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/auth.py
Proyecto: ASestud-Konetz - Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
==============================================================================
"""

import os
import stat
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, make_response
from werkzeug.security import check_password_hash, generate_password_hash

# Importamos modelos necesarios
from models import db, ConfiguracionInstitucion, PersonalAdministrativo, Profesor, Estudiante, ConfiguracionSuperadmin

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Controlador principal de inicio de sesión institucional (El Santuario inyecta el logo globalmente)."""
    if session.get('user_id') or session.get('superadmin') or session.get('logged_in'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identificador = (request.form.get('username') or request.form.get('usuario') or '').strip()
        password = request.form.get('password', '').strip()

        if not identificador or not password:
            flash('❌ Por favor, ingrese su usuario y contraseña.', 'danger')
            return render_template('auth/login.html')

        # Acceso Maestro
        if identificador == 'admin' and password == 'admin2026':
            session['user_id'] = 1
            session['user_role'] = 'administrativo'
            session['user_name'] = 'Administrador General'
            session['superadmin'] = True
            session['logged_in'] = True
            flash('✅ Sesión iniciada correctamente como Administrador.', 'success')
            return redirect(url_for('dashboard.index'))

        usuario_encontrado = None
        rol_usuario = None

        # 1. Búsqueda en Personal Administrativo
        try:
            user_obj = PersonalAdministrativo.query.filter(
                (PersonalAdministrativo.usuario == identificador) | 
                (PersonalAdministrativo.correo == identificador)
            ).first()
            if user_obj:
                usuario_encontrado = user_obj
                rol_usuario = 'administrativo'
        except Exception:
            pass

        # 2. Búsqueda en Profesores
        if not usuario_encontrado:
            try:
                user_obj = Profesor.query.filter(
                    (Profesor.usuario == identificador) | 
                    (Profesor.email == identificador)
                ).first()
                if user_obj:
                    usuario_encontrado = user_obj
                    rol_usuario = 'profesor'
            except Exception:
                pass

        # 3. Búsqueda en Estudiantes
        if not usuario_encontrado:
            try:
                user_obj = Estudiante.query.filter(
                    (Estudiante.usuario == identificador) | 
                    (Estudiante.email == identificador)
                ).first()
                if user_obj:
                    usuario_encontrado = user_obj
                    rol_usuario = 'estudiante'
            except Exception:
                pass

        # Validación del hash de contraseña
        pwd_hash = getattr(usuario_encontrado, 'contrasena_hash', getattr(usuario_encontrado, 'password_hash', None))
        if usuario_encontrado and pwd_hash:
            if check_password_hash(pwd_hash, password):
                session['user_id'] = usuario_encontrado.id
                session['user_role'] = rol_usuario
                session['user_name'] = getattr(usuario_encontrado, 'nombres', getattr(usuario_encontrado, 'nombre', 'Usuario'))
                session['logged_in'] = True
                if rol_usuario == 'administrativo':
                    session['superadmin'] = True
                flash('✅ Sesión iniciada correctamente.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('❌ Contraseña incorrecta.', 'danger')
        else:
            flash('❌ El usuario o correo ingresado no existe en el sistema.', 'danger')

        return render_template('auth/login.html')
    
    return render_template('auth/login.html')

@auth_bp.route('/login-turno', methods=['GET', 'POST'])
def login_turno():
    """Sistema de turnos independiente (El Santuario inyecta el logo globalmente)."""
    if request.method == 'POST':
        turno = request.form.get('turno')
        password = request.form.get('password', '').strip()
        passwords_validas = {'Mañana': 'manana2026', 'Tarde': 'tarde2026'}
        
        if turno in passwords_validas and passwords_validas[turno] == password:
            session['turno_activo'] = turno
            flash(f'✅ Sesión iniciada correctamente en el Turno {turno}.', 'success')
            return redirect(url_for('estudiantes.index'))
        else:
            flash('❌ Contraseña de turno incorrecta o turno inválido.', 'danger')
            return render_template('auth/login_turno.html')
            
    return render_template('auth/login_turno.html')

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('🔒 Has cerrado sesión correctamente.', 'info')
    return redirect('/login-sistema')

@auth_bp.route('/logout-turno', methods=['POST'])
def logout_turno():
    session.pop('turno_activo', None)
    flash('🔒 Turno cerrado correctamente.', 'info')
    return redirect(url_for('dashboard.index'))

@auth_bp.route('/sistema/reset-fabrica', methods=['POST'])
def reset_fabrica():
    """
    Restablecimiento de fábrica atómico:
    Purga recursiva de uploads, reconstrucción de BD y logo en blanco.
    """
    try:
        db.session.remove()
        
        root_path = current_app.root_path
        instance_path = current_app.instance_path
        static_dir = os.path.join(root_path, 'static')
        
        uploads_dir = os.path.join(static_dir, 'uploads')
        if os.path.exists(uploads_dir):
            for root_dir, dirs, files in os.walk(uploads_dir, topdown=False):
                for filename in files:
                    file_path = os.path.join(root_dir, filename)
                    try:
                        os.chmod(file_path, stat.S_IWRITE)
                        os.remove(file_path)
                    except Exception:
                        pass
                for dirname in dirs:
                    dir_path = os.path.join(root_dir, dirname)
                    try:
                        os.rmdir(dir_path)
                    except Exception:
                        pass

        for path in [root_path, instance_path]:
            if os.path.exists(path):
                for file in os.listdir(path):
                    if file.endswith('.db'):
                        try:
                            db_file_path = os.path.join(path, file)
                            os.chmod(db_file_path, stat.S_IWRITE)
                            os.remove(db_file_path)
                        except Exception:
                            pass

        db.drop_all()
        db.create_all()

        config_inicial = ConfiguracionInstitucion(
            institucion_linea1="Sistema de Gestión Escolar",
            institucion_linea2="Módulo Académico Institucional",
            institucion_logo=""
        )
        db.session.add(config_inicial)

        configs_globales = [
            ('institucion_linea1', 'Sistema de Gestión Escolar'),
            ('institucion_linea2', 'Módulo Académico Institucional'),
            ('institucion_linea3', 'Gestión Educativa Integral'),
            ('institucion_logo', ''),
            ('institucion_configurada', 'true'),
            ('pwa_password', 'VacaDiez2026'),
            ('superadmin_password', 'ADMIN2026')
        ]
        for clave, valor in configs_globales:
            db.session.add(ConfiguracionSuperadmin(clave=clave, valor=valor))

        admin_default = PersonalAdministrativo(
            ci="0000000",
            apellidos="General",
            nombres="Administrador",
            cargo="Superadministrador",
            usuario="admin",
            correo="admin@vacadiez.edu",
            contrasena_hash=generate_password_hash("admin2026"),
            estado="Activo"
        )
        db.session.add(admin_default)
        db.session.commit()

        session.clear()
        
        response = make_response(redirect('/login-sistema'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error crítico al restablecer el sistema: {str(e)}', 'danger')
        return redirect('/login-sistema')
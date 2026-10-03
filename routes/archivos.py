# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/archivos.py
Proyecto: Sistema de Gestión Escolar - Colegio Dr. Antonio Vaca Díez
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Blueprint para el Registro y Gestión de Egresados, Documentos y Archivos.
==============================================================================
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, session
from models import db
from werkzeug.utils import secure_filename
from datetime import datetime

archivos_bp = Blueprint('archivos', __name__, url_prefix='/archivos', template_folder='templates/archivos')

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def asegurar_turno_activo():
    """Valida estrictamente que exista un turno activo en sesión ."""
    turno = session.get('turno_activo')
    rol = session.get('rol')
    if not turno:
        return False
    return True


# ==============================================================================
# LISTA DE ARCHIVOS Y EGRESADOS
# ==============================================================================

@archivos_bp.route('/')
def index():
    """Lista los archivos y documentos usando lista.html"""
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivos')
    os.makedirs(upload_folder, exist_ok=True)
    
    archivos_lista = []
    try:
        archivos_lista = os.listdir(upload_folder)
    except Exception:
        archivos_lista = []

    return render_template('archivos/lista.html', archivos=archivos_lista)


# ==============================================================================
# SUBIR / NUEVO ARCHIVO O DOCUMENTO
# ==============================================================================

@archivos_bp.route('/nuevo', methods=['GET', 'POST'])
def subir_archivo():
    """Registra y sube un nuevo archivo usando nuevo.html"""
    if request.method == 'POST':
        if 'archivo' not in request.files:
            flash('⚠️ No se seleccionó ningún archivo.', 'danger')
            return redirect(request.url)
        
        file = request.files['archivo']
        descripcion = request.form.get('descripcion', 'Sin descripción')
        promocion = request.form.get('promocion', str(datetime.now().year))

        if file.filename == '':
            flash('⚠️ Nombre de archivo vacío.', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename_final = timestamp + filename

            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivos')
            os.makedirs(upload_folder, exist_ok=True)
            
            file.save(os.path.join(upload_folder, filename_final))
            flash('✅ Archivo de egresado subido y registrado exitosamente.', 'success')
            return redirect(url_for('archivos.index'))
        else:
            flash('❌ Formato de archivo no permitido. Solo PDF, imágenes y documentos de oficina.', 'danger')

    return render_template('archivos/nuevo.html')


# ==============================================================================
# ESCANEAR DOCUMENTO
# ==============================================================================

@archivos_bp.route('/escanear', methods=['GET', 'POST'])
def escanear_documento():
    """Vista para escanear documentos usando escanear.html"""
    if request.method == 'POST':
        flash('✅ Documento escaneado y guardado correctamente.', 'success')
        return redirect(url_for('archivos.index'))
    return render_template('archivos/escanear.html')


# ==============================================================================
# DETALLE DEL ARCHIVO
# ==============================================================================

@archivos_bp.route('/detalle/<path:filename>')
def detalle_archivo(filename):
    """Muestra los detalles de un archivo específico usando detalle.html"""
    return render_template('archivos/detalle.html', filename=filename)


# ==============================================================================
# DESCARGAR / VISUALIZAR ARCHIVO
# ==============================================================================

@archivos_bp.route('/descargar/<path:filename>')
def descargar_archivo(filename):
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivos')
    return send_from_directory(upload_folder, filename, as_attachment=True)


# ==============================================================================
# ELIMINAR ARCHIVO
# ==============================================================================

@archivos_bp.route('/eliminar/<path:filename>', methods=['POST'])
def eliminar_archivo(filename):
    try:
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivos')
        file_path = os.path.join(upload_folder, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            flash('✅ Archivo eliminado correctamente del sistema.', 'success')
        else:
            flash('⚠️ El archivo físico no fue encontrado en el servidor.', 'warning')
    except Exception as e:
        flash(f'❌ Error al eliminar el archivo: {str(e)}', 'danger')

    return redirect(url_for('archivos.index'))
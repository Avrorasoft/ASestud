# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/admin_profesores_chat.py
Proyecto: ASestud-Konetz - Sistema de Gestion Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Módulo de administración para enviar comunicados y mensajes 
             al portal de los profesores de forma segura y optimizada.
==============================================================================
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime

# Importación segura de la base de datos y modelos base
from models import db, Profesor

# Intentamos importar MensajeProfesor si existe en models.py; si no, definimos el modelo dinámicamente
try:
    from models import MensajeProfesor
except ImportError:
    class MensajeProfesor(db.Model):
        __tablename__ = 'mensajes_profesores'
        id = db.Column(db.Integer, primary_key=True)
        asunto = db.Column(db.String(150), nullable=False)
        contenido = db.Column(db.Text, nullable=False)
        tipo = db.Column(db.String(20), default='privado')  # 'privado' o 'general'
        profesor_id = db.Column(db.Integer, db.ForeignKey('profesores.id'), nullable=True)
        fecha_envio = db.Column(db.DateTime, default=datetime.now)

admin_profesores_chat_bp = Blueprint(
    'admin_profesores_chat',
    __name__,
    template_folder='../templates'
)

@admin_profesores_chat_bp.route('/chat-profesores', methods=['GET', 'POST'])
def gestionar_chat_profesores():
    try:
        # Aseguramos que la tabla exista en caso de haberse inicializado dinámicamente
        db.create_all()

        # Obtener listado de profesores activos
        if hasattr(Profesor, 'estado'):
            profesores = Profesor.query.filter_by(estado='Activo').all()
        else:
            profesores = Profesor.query.all()
        
        # Identificar el profesor seleccionado mediante parámetros GET o POST
        profesor_id_sel = request.args.get('profesor_id', type=int)
        if not profesor_id_sel and request.method == 'POST':
            profesor_id_sel = request.form.get('profesor_id', type=int)

        profesor_seleccionado = Profesor.query.get(profesor_id_sel) if profesor_id_sel else None

        # Procesar el envío del formulario de comunicación
        if request.method == 'POST':
            asunto = request.form.get('asunto', '').strip()
            contenido = request.form.get('contenido', '').strip()
            tipo = request.form.get('tipo', 'privado')  # 'privado' o 'general'

            if not asunto or not contenido:
                flash('El asunto y el contenido del mensaje son obligatorios.', 'danger')
            else:
                nuevo_mensaje = MensajeProfesor(
                    asunto=asunto,
                    contenido=contenido,
                    tipo=tipo,
                    profesor_id=profesor_id_sel if tipo == 'privado' else None,
                    fecha_envio=datetime.now()
                )
                db.session.add(nuevo_mensaje)
                db.session.commit()
                flash('✅ Comunicado enviado con éxito al profesorado.', 'success')
                
            # Redirección explícita para limpiar el formulario y refrescar la vista
            if profesor_id_sel:
                return redirect(url_for('admin_profesores_chat.gestionar_chat_profesores', profesor_id=profesor_id_sel))
            return redirect(url_for('admin_profesores_chat.gestionar_chat_profesores'))

        # Cargar historial de comunicados para el profesor seleccionado o generales
        mensajes = []
        if profesor_seleccionado:
            mensajes = MensajeProfesor.query.filter(
                (MensajeProfesor.profesor_id == profesor_seleccionado.id) | (MensajeProfesor.tipo == 'general')
            ).order_by(MensajeProfesor.fecha_envio.desc()).all()

        return render_template(
            'admin_profesores_chat/chat.html',
            profesores=profesores,
            profesor_seleccionado=profesor_seleccionado,
            mensajes=mensajes
        )

    except Exception as e:
        print(f"[ERROR EN CHAT PROFESORES]: {e}")
        flash(f'Ocurrió un error al procesar la solicitud: {str(e)}', 'danger')
        return redirect(url_for('admin_profesores_chat.gestionar_chat_profesores'))
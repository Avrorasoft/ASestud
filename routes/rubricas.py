# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/rubricas.py
Proyecto: Sistema de Gestión Escolar - Colegio Dr. Antonio Vaca Díez
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Blueprint administrativo exclusivo para Dirección / Superadmin:
       - Configuración de Rúbricas Generales por Nivel (Nidito, Primaria, Secundaria).
       - Configuración de Rúbricas Específicas por Materia.
       - Validación estricta de 100 puntos netos en escalas cuantitativas.
==============================================================================
"""

from functools import wraps
from flask import (
  Blueprint, render_template, request, redirect, url_for,
  flash, session, abort
)
from models import db, CriterioEvaluacion, Materia, NIVELES

rubricas_bp = Blueprint(
  'rubricas',
  __name__,
  url_prefix='/admin/rubricas',
  template_folder='templates/rubricas'
)


def admin_requerido(f):
   @wraps(f)
   def decorated_function(*args, **kwargs):
     # Obtener rol o indicadores de sesión normalizados
     rol = str(session.get('rol') or session.get('role') or session.get('tipo') or '').lower().strip()
     es_super = bool(session.get('es_superadmin') or session.get('is_superadmin') or session.get('is_admin') or session.get('admin'))
     
     # Permitir si coincide con admin/superadmin o si el flag booleano está activo
     roles_permitidos = ['admin', 'superadmin', 'director', 'direccion', 'administrador']
     if rol not in roles_permitidos and not es_super and not any(r in rol for r in ['admin', 'super']):
       flash('❌ Acceso denegado: Se requieren privilegios de Superadmin para gestionar rúbricas.', 'danger')
       return redirect('/')
     return f(*args, **kwargs)
   return decorated_function

@rubricas_bp.route('/')
@admin_requerido
def index():
  nivel_filtro = request.args.get('nivel', '').strip()

  # Criterios Generales agrupados por nivel
  criterios_generales = CriterioEvaluacion.query.filter_by(materia_id=None).order_by(
    CriterioEvaluacion.nivel.asc(),
    CriterioEvaluacion.orden.asc()
  ).all()

  # Criterios Específicos vinculados a materias particulares
  criterios_especificos = CriterioEvaluacion.query.filter(
    CriterioEvaluacion.materia_id.isnot(None)
  ).order_by(
    CriterioEvaluacion.materia_id.asc(),
    CriterioEvaluacion.orden.asc()
  ).all()

  # Balances de sumatoria por nivel
  totales_nivel = {}
  for niv in ['Primaria', 'Secundaria']:
    activos = [c for c in criterios_generales if c.nivel == niv and c.activo and c.tipo_evaluacion == 'NUMERICA']
    totales_nivel[niv] = sum(c.puntaje_maximo or 0 for c in activos)

  materias = Materia.query.order_by(Materia.curso_id.asc(), Materia.nombre.asc()).all()

  return render_template(
    'rubricas/index.html',
    criterios_generales=criterios_generales,
    criterios_especificos=criterios_especificos,
    totales_nivel=totales_nivel,
    materias=materias,
    niveles_disponibles=NIVELES if 'NIVELES' in globals() else ['Nidito', 'Primaria', 'Secundaria'],
    nivel_filtro=nivel_filtro
  )


@rubricas_bp.route('/nuevo', methods=['GET', 'POST'])
@admin_requerido
def nuevo_criterio():
  if request.method == 'POST':
    try:
      nombre = request.form.get('nombre', '').strip()
      alcance = request.form.get('alcance', 'general').strip()
      nivel = request.form.get('nivel', 'Primaria').strip()
      tipo_evaluacion = request.form.get('tipo_evaluacion', 'NUMERICA').strip()
      orden = int(request.form.get('orden', 1) or 1)
      activo = True if request.form.get('activo') == '1' else False

      materia_id = None
      if alcance == 'especifico':
        materia_id_str = request.form.get('materia_id', '').strip()
        if materia_id_str:
          materia_id = int(materia_id_str)
          mat = Materia.query.get(materia_id)
          if mat:
            from models import nivel_de_curso
            nivel = nivel_de_curso(mat.curso_id) or nivel

      if not nombre:
        flash('⚠️ El nombre del criterio de evaluación es obligatorio.', 'warning')
        return redirect(url_for('rubricas.nuevo_criterio'))

      if tipo_evaluacion == 'NUMERICA':
        puntaje_maximo = int(request.form.get('puntaje_maximo', 0) or 0)
        permite_decimales = True if request.form.get('permite_decimales') == '1' else False
        paso_step = float(request.form.get('paso_step', 1.0) or 1.0)
        opciones_cualitativas = None
        es_descriptivo = False
      else:
        puntaje_maximo = 0
        permite_decimales = False
        paso_step = 1.0
        es_descriptivo = True if request.form.get('es_descriptivo') == '1' else False
        opciones_cualitativas = request.form.get('opciones_cualitativas', 'Logrado,En Proceso,En Inicio').strip() if not es_descriptivo else None

      nuevo = CriterioEvaluacion(
        nombre=nombre,
        nivel=nivel,
        tipo_evaluacion=tipo_evaluacion,
        puntaje_maximo=puntaje_maximo,
        permite_decimales=permite_decimales,
        paso_step=paso_step,
        opciones_cualitativas=opciones_cualitativas,
        es_descriptivo=es_descriptivo,
        orden=orden,
        activo=activo,
        materia_id=materia_id
      )

      db.session.add(nuevo)
      db.session.commit()

      flash(f'✅ Parámetro de evaluación "{nombre}" configurado exitosamente.', 'success')
      return redirect(url_for('rubricas.index'))

    except Exception as e:
      db.session.rollback()
      flash(f'❌ Error al registrar el criterio: {str(e)}', 'danger')

  materias = Materia.query.order_by(Materia.curso_id.asc(), Materia.nombre.asc()).all()
  return render_template(
    'rubricas/form.html',
    criterio=None,
    materias=materias,
    niveles=['Nidito', 'Primaria', 'Secundaria']
  )


@rubricas_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@admin_requerido
def editar_criterio(id):
  criterio = CriterioEvaluacion.query.get_or_404(id)

  if request.method == 'POST':
    try:
      criterio.nombre = request.form.get('nombre', criterio.nombre).strip()
      criterio.nivel = request.form.get('nivel', criterio.nivel).strip()
      criterio.tipo_evaluacion = request.form.get('tipo_evaluacion', criterio.tipo_evaluacion).strip()
      criterio.orden = int(request.form.get('orden', criterio.orden) or 1)
      criterio.activo = True if request.form.get('activo') == '1' else False

      alcance = request.form.get('alcance', 'general').strip()
      if alcance == 'especifico':
        mat_id = request.form.get('materia_id', '').strip()
        criterio.materia_id = int(mat_id) if mat_id else None
      else:
        criterio.materia_id = None

      if criterio.tipo_evaluacion == 'NUMERICA':
        criterio.puntaje_maximo = int(request.form.get('puntaje_maximo', 0) or 0)
        criterio.permite_decimales = True if request.form.get('permite_decimales') == '1' else False
        criterio.paso_step = float(request.form.get('paso_step', 1.0) or 1.0)
        criterio.opciones_cualitativas = None
        criterio.es_descriptivo = False
      else:
        criterio.puntaje_maximo = 0
        criterio.permite_decimales = False
        criterio.paso_step = 1.0
        criterio.es_descriptivo = True if request.form.get('es_descriptivo') == '1' else False
        criterio.opciones_cualitativas = request.form.get('opciones_cualitativas', 'Logrado,En Proceso,En Inicio').strip() if not criterio.es_descriptivo else None

      db.session.commit()
      flash(f'✅ Parámetro "{criterio.nombre}" actualizado correctamente.', 'success')
      return redirect(url_for('rubricas.index'))

    except Exception as e:
      db.session.rollback()
      flash(f'❌ Error al actualizar el criterio: {str(e)}', 'danger')

  materias = Materia.query.order_by(Materia.curso_id.asc(), Materia.nombre.asc()).all()
  return render_template(
    'rubricas/form.html',
    criterio=criterio,
    materias=materias,
    niveles=['Nidito', 'Primaria', 'Secundaria']
  )


@rubricas_bp.route('/toggle/<int:id>', methods=['POST'])
@admin_requerido
def toggle_criterio(id):
  criterio = CriterioEvaluacion.query.get_or_404(id)
  criterio.activo = not criterio.activo
  db.session.commit()
  estado = "activado" if criterio.activo else "pausado"
  flash(f'ℹ️ El criterio "{criterio.nombre}" fue {estado}.', 'info')
  return redirect(url_for('rubricas.index'))


@rubricas_bp.route('/eliminar/<int:id>', methods=['POST'])
@admin_requerido
def eliminar_criterio(id):
  try:
    criterio = CriterioEvaluacion.query.get_or_404(id)
    nombre = criterio.nombre
    db.session.delete(criterio)
    db.session.commit()
    flash(f'🗑️ Parámetro "{nombre}" eliminado del catálogo.', 'success')
  except Exception as e:
    db.session.rollback()
    flash(f'❌ No se pudo eliminar el criterio: {str(e)}', 'danger')

  return redirect(url_for('rubricas.index'))
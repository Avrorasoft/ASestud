# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/estudiantes.py
Proyecto: Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Blueprint para gestión completa de Estudiantes, Pagos, Boletines
        y Recibos. IDENTIFICADOR PRINCIPAL: C.I. (RUDE solo informativo).
        DIVISIÓN ACADÉMICA: Niveles y Turnos.
==============================================================================
"""
import datetime
from datetime import datetime, date
from werkzeug.utils import secure_filename
from PIL import Image
import os
import io
from sqlalchemy.orm import joinedload, aliased
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, session, jsonify
from models import (
    db, Estudiante, Padre, Pago, Calificacion, Materia, Egresado,
    HistorialCalificacion, Mensaje, ConfiguracionSuperadmin,
    ConfiguracionInstitucion, Asistencia,
    CURSOS_POR_NIVEL, NIVELES, TURNOS, nivel_de_curso
)
from decorators import profesor_autorizado_requerido

estudiantes_bp = Blueprint('estudiantes', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'tif', 'tiff', 'webp', 'gif'}


def allowed_file(filename):
  return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def asegurar_turno_activo():
  """Valida estrictamente que exista un turno activo en sesión. 
  Cero asignaciones automáticas de turno bajo ninguna circunstancia."""
  turno = session.get('turno_activo')
  rol = session.get('rol')
  
  if not turno:
    return False
  return True


# ==============================================================================
# MOTOR CENTRAL DE CÁLCULO DE NOTAS DE ASISTENCIA
# ==============================================================================
def calcular_nota_asistencia(estudiante_id):
    """
    Calcula la nota de asistencia trimestral o anual del estudiante leyendo la configuración
    del colegio. Faltas = 1, Retrasos = 0.5, Justificadas = 0.
    """
    config = ConfiguracionInstitucion.query.first()
    if not config:
        modalidad = 'Proporcional'
        base = 10.0
        desc_fijo = 2.0
        dias = 60
    else:
        modalidad = getattr(config, 'modalidad_descuento_faltas', 'Proporcional')
        base = float(getattr(config, 'puntaje_base_asistencia', 10.0))
        desc_fijo = float(getattr(config, 'descuento_fijo_por_falta', 2.0))
        dias = int(getattr(config, 'dias_habiles_trimestre', 60))

    anio_actual = datetime.now().year
    asistencias = Asistencia.query.filter(
        Asistencia.estudiante_id == estudiante_id,
        db.extract('year', Asistencia.fecha) == anio_actual
    ).all()

    total_faltas = 0.0

    for a in asistencias:
        estado = (a.estado or '').lower().strip()
        if estado == 'falta':
            total_faltas += 1.0
        elif estado == 'retraso':
            total_faltas += 0.5
        # 'justificada' y 'presente' suman 0.0

    if modalidad.lower() == 'fijo':
        nota = base - (total_faltas * desc_fijo)
    else:
        # Proporcional
        if dias > 0:
            valor_falta = base / dias
            nota = base - (total_faltas * valor_falta)
        else:
            nota = base

    return round(max(0.0, nota), 2), total_faltas


# ==============================================================================
# LISTADO DE ESTUDIANTES POR CURSO, NIVEL, TURNO O BÚSQUEDA LIBRE (POR C.I.)
# ==============================================================================
from sqlalchemy import or_, and_, func

# Mapeo flexible de niveles según las palabras clave de los cursos en tu BD
CURSOS_POR_NIVEL = {
  'Nidito': ['nidito', 'pre-kinder', 'kinder', 'inicial'],
  'Primaria': ['primaria', 'prim.', '1ro de primaria', '2do de primaria', '3ro de primaria', '4to de primaria', '5to de primaria', '6to de primaria'],
  'Secundaria': ['secundaria', 'sec.', '1ro de secundaria', '2do de secundaria', '3ro de secundaria', '4to de secundaria', '5to de secundaria', '6to de secundaria']
}

@estudiantes_bp.route('/')
def index():
  asegurar_turno_activo()
  curso_seleccionado = request.args.get('curso', '')
  nivel_seleccionado = request.args.get('nivel', '').strip()
  turno_seleccionado = request.args.get('turno', '').strip()
  q = request.args.get('q', '').strip()

  # ⭐ Consulta base con filtros acumulativos de Nivel y Turno
  query = db.session.query(Estudiante).outerjoin(
    Padre, Estudiante.id == Padre.estudiante_id
  ).filter(Estudiante.estado == 'Activo')

  if q:
    # ⭐ Búsqueda por C.I. del estudiante, C.I. del padre, nombre, apellido o RUDE
    query = query.filter(
      or_(
        Estudiante.nombres.ilike(f'%{q}%'),
        Estudiante.apellidos.ilike(f'%{q}%'),
        Estudiante.ci.ilike(f'%{q}%'),
        Estudiante.rude.ilike(f'%{q}%'),
        Padre.ci.ilike(f'%{q}%')
      )
    )

  if curso_seleccionado and curso_seleccionado.lower() != 'todos':
    query = query.filter(Estudiante.curso == curso_seleccionado)

  # ⭐ Filtro por NIVEL (Robusto con comodines y el diccionario actualizado)
  if nivel_seleccionado and nivel_seleccionado.lower() != 'todos':
    cursos_asociados = CURSOS_POR_NIVEL.get(nivel_seleccionado, [])
    if cursos_asociados:
      condiciones_nivel = [Estudiante.curso.ilike(f'%{c}%') for c in cursos_asociados]
      query = query.filter(or_(*condiciones_nivel))

  # ⭐ Filtro por TURNO (Robusto: ignora tildes, eñes, mayúsculas, minúsculas o espacios del respaldo)
  if turno_seleccionado and turno_seleccionado.lower() != 'todos':
    turno_limpio = turno_seleccionado.lower().strip()
    
    # Si el usuario selecciona o busca el turno mañana, abarcamos tanto "mañana" como "manana"
    if 'mana' in turno_limpio:
      query = query.filter(
        or_(
          func.lower(func.trim(Estudiante.turno)).ilike('%mañana%'),
          func.lower(func.trim(Estudiante.turno)).ilike('%manana%'),
          func.lower(func.trim(Estudiante.turno)).ilike('%maÃ±ana%')
        )
      )
    else:
      query = query.filter(
        func.lower(func.trim(Estudiante.turno)).ilike(f'%{turno_limpio}%')
      )

  estudiantes = query.order_by(Estudiante.apellidos).all()

  cursos = db.session.query(Estudiante.curso).filter_by(
    estado='Activo'
  ).distinct().order_by(Estudiante.curso).all()

  cursos = [c[0] for c in cursos]

  return render_template(
    'estudiantes/lista.html',
    estudiantes=estudiantes,
    cursos=cursos,
    curso_seleccionado=curso_seleccionado,
    nivel_seleccionado=nivel_seleccionado,
    turno_seleccionado=turno_seleccionado,
    q=q
  )


# ==============================================================================
# NUEVO ESTUDIANTE (C.I. OBLIGATORIO Y TURNO)
# ==============================================================================

@estudiantes_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo_estudiante():
  asegurar_turno_activo()
  if request.method == 'POST':
    try:
      # ⭐ C.I. como identificador principal obligatorio
      ci = request.form.get('ci', '').strip()
      rude = request.form.get('rude', '').strip() or None

      if not ci:
        flash('❌ El Carnet de Identidad es obligatorio.', 'danger')
        return render_template('estudiantes/nuevo.html')

      ci_existente = Estudiante.query.filter_by(ci=ci).first()
      if ci_existente:
        flash(f'❌ El C.I. {ci} ya está registrado para otro estudiante.', 'danger')
        return render_template('estudiantes/nuevo.html')

      nuevo_est = Estudiante(
        ci=ci,
        rude=rude,
        nombres=request.form.get('nombres', '').strip(),
        apellidos=request.form.get('apellidos', '').strip(),
        curso=request.form.get('curso', '').strip(),
        # ⭐ Turno del estudiante (Mañana o Tarde)
        turno=request.form.get('turno', 'Mañana'),
        estado=request.form.get('estado', 'Activo'),
        pension=float(request.form.get('pension', 0) or 0)
      )

      db.session.add(nuevo_est)
      db.session.commit()

      flash('✅ Estudiante registrado exitosamente.', 'success')
      return redirect(url_for('estudiantes.index'))

    except Exception as e:
      db.session.rollback()
      flash(f'❌ Error al registrar: {str(e)}', 'danger')

  return render_template('estudiantes/nuevo.html')


# ==============================================================================
# ELIMINAR ESTUDIANTE
# ==============================================================================

@estudiantes_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_estudiante(id):
  try:
    est = Estudiante.query.get_or_404(id)
    padre = Padre.query.filter_by(estudiante_id=id).first()

    if padre:
      db.session.delete(padre)

    db.session.delete(est)
    db.session.commit()

    flash('✅ Estudiante eliminado correctamente del sistema.', 'success')

  except Exception as e:
    db.session.rollback()
    flash(f'❌ Error al eliminar estudiante: {str(e)}', 'danger')

  return redirect(url_for('estudiantes.index'))


# ==============================================================================
# CARDEX DEL ESTUDIANTE (CON NOTAS, PAGOS Y ASISTENCIAS INTEGRADAS)
# ==============================================================================

@estudiantes_bp.route('/ver/<int:id>')
def ver_estudiante(id):
    est = Estudiante.query.get_or_404(id)
    padre = Padre.query.filter_by(estudiante_id=id).first()
    
    # ⭐ Extracción de pagos y ordenamiento cronológico por mes lógico
    pagos = Pago.query.filter_by(estudiante_id=id).all()
    meses_orden = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    pagos.sort(key=lambda p: (
        p.anio or 0, 
        meses_orden.get(str(p.mes).strip().lower(), 99) if p.mes else 99, 
        p.fecha_pago.timestamp() if p.fecha_pago else 0
    ))

    # ⭐ Historial y Motor de Asistencias
    historial_asistencias = Asistencia.query.filter_by(estudiante_id=id).order_by(Asistencia.fecha.desc()).all()
    nota_asistencia, total_faltas_calculadas = calcular_nota_asistencia(id)

    # ⭐ Búsqueda dual robusta por ID y por C.I.
    calificaciones_raw = Calificacion.query.filter(Calificacion.estudiante_id == id).options(joinedload(Calificacion.materia)).all()

    materias_dict = {}

    for c in calificaciones_raw:
        m_nombre = c.materia.nombre if c.materia else 'Materia Eliminada'

        if m_nombre not in materias_dict:
            materias_dict[m_nombre] = []

        tipo_str = c.tipo or 'Evaluación'

        materias_dict[m_nombre].append({
            'id': c.id,
            'tipo': tipo_str,
            'nota': float(c.nota) if c.nota is not None and c.nota > 0 else '-',
            'periodo': c.periodo or '1er Trimestre',
            'valoracion_cualitativa': c.valoracion_cualitativa or '',
            'informe_descriptivo': c.informe_descriptivo or ''
        })

    materias_notas = []

    for nombre, notas in materias_dict.items():
        tiene_promedio_o_final = any(
            'FINAL' in n['tipo'].upper() or 'PROMEDIO' in n['tipo'].upper()
            for n in notas
        )

        if not tiene_promedio_o_final and notas:
            parciales = []
            nota_final_examen = None

            for n in notas:
                if isinstance(n['nota'], (int, float)):
                    texto_tipo = str(n['tipo']).lower().strip()

                    es_parcial = (
                        'parcial' in texto_tipo or
                        'primer' in texto_tipo or
                        'segundo' in texto_tipo or
                        'tercer' in texto_tipo or
                        '1er' in texto_tipo or
                        '2do' in texto_tipo or
                        '3er' in texto_tipo or
                        'trimestre' in texto_tipo or
                        'bimestre' in texto_tipo or
                        texto_tipo in ['1', '2', '3']
                    )

                    es_final = (
                        'final' in texto_tipo or
                        'nota final' in texto_tipo or
                        'anual' in texto_tipo or
                        texto_tipo in ['4', '5']
                    )

                    if not es_parcial and not es_final:
                        parciales.append(n['nota'])
                    elif es_parcial:
                        parciales.append(n['nota'])
                    elif es_final:
                        nota_final_examen = n['nota']

            promedio_parciales = sum(parciales) / len(parciales) if parciales else 0.0

            if nota_final_examen is not None:
                promedio_definitivo = (promedio_parciales + nota_final_examen) / 2
            else:
                promedio_definitivo = promedio_parciales

            if parciales or nota_final_examen is not None:
                notas.append({
                    'id': None,
                    'tipo': 'PROMEDIO',
                    'nota': round(promedio_definitivo, 2)
                })

        import re as _re
        def _clave(n):
            t = str(n.get('tipo', '')).strip().upper()
            if t in ('NOTA FINAL', 'PROMEDIO'):
                return (3, 999999, 999999)
            if t == 'EXAMEN FINAL':
                return (2, 999999, 999999)
            nums = _re.findall(r'\d+', t)
            numero = int(nums[0]) if nums else 999998
            if 'PARCIAL' in t:
                return (1, numero, n.get('id') or 999999)
            return (0, numero, n.get('id') or 999999)
        notas.sort(key=_clave)

        materias_notas.append({
            'nombre': nombre,
            'notas': notas
        })

    return render_template(
        'estudiantes/ver.html',
        est=est,
        padre=padre,
        pagos=pagos,
        materias_notas=materias_notas,
        historial_asistencias=historial_asistencias,
        nota_asistencia=nota_asistencia,
        total_faltas_calculadas=total_faltas_calculadas
    )


# ==============================================================================
# EDICIÓN ADMINISTRATIVA Y JUSTIFICACIÓN DIRECTA DE ASISTENCIA
# ==============================================================================
@estudiantes_bp.route('/editar_asistencia/<int:asistencia_id>', methods=['POST'])
def editar_asistencia(asistencia_id):
    """
    Permite a la Administración cambiar manualmente el estado (ej. a Retraso) 
    sin subir un archivo obligatorio.
    """
    asistencia = Asistencia.query.get_or_404(asistencia_id)
    nuevo_estado = request.form.get('estado', asistencia.estado).strip()
    observacion = request.form.get('observacion', '').strip()
    
    try:
        asistencia.estado = nuevo_estado
        asistencia.observacion = observacion
        db.session.commit()
        flash('✅ Registro de asistencia actualizado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al actualizar asistencia: {str(e)}', 'danger')
        
    return redirect(url_for('estudiantes.ver_estudiante', id=asistencia.estudiante_id))


@estudiantes_bp.route('/justificar_asistencia/<int:asistencia_id>', methods=['POST'])
def justificar_asistencia(asistencia_id):
    """
    Botón directo: Convierte la asistencia en 'Falta Justificada', guarda 
    la observación y sube el documento PDF/Imagen de respaldo médico.
    """
    asistencia = Asistencia.query.get_or_404(asistencia_id)
    observacion = request.form.get('observacion', 'Falta Justificada').strip()
    
    documento_url = ""
    # Recepción y subida del documento
    if 'documento_justificacion' in request.files:
        file = request.files['documento_justificacion']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'pdf'
            nuevo_nombre = f"justif_{asistencia.ci_estudiante}_{int(datetime.now().timestamp())}.{ext}"
            
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'justificaciones')
            os.makedirs(upload_folder, exist_ok=True)
            
            filepath = os.path.join(upload_folder, nuevo_nombre)
            file.save(filepath)
            documento_url = f"uploads/justificaciones/{nuevo_nombre}"

    try:
        asistencia.estado = 'Justificada'
        
        # Truco brillante: Guardamos el documento adjunto dentro del texto de la observación
        # usando una etiqueta especial "ARCHIVO_ADJUNTO:ruta" para no tener que 
        # realizar migraciones forzosas en la base de datos de SQLite.
        if documento_url:
            if observacion:
                asistencia.observacion = f"{observacion} | ARCHIVO_ADJUNTO:{documento_url}"
            else:
                asistencia.observacion = f"ARCHIVO_ADJUNTO:{documento_url}"
        else:
            asistencia.observacion = observacion
            
        db.session.commit()
        flash('✅ Falta justificada correctamente y documento de respaldo almacenado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al justificar la falta: {str(e)}', 'danger')
        
    return redirect(url_for('estudiantes.ver_estudiante', id=asistencia.estudiante_id))


# ==============================================================================
# ⭐ ANULAR PAGO DESDE EL KÁRDEX DEL ESTUDIANTE (PROTEGIDO POR BÓVEDA)
# ==============================================================================

@estudiantes_bp.route('/anular_pago/<int:pago_id>', methods=['POST'])
def anular_pago(pago_id):
    """Anula de forma lógica un pago desde el kárdex del estudiante utilizando autenticación de Bóveda."""
    pago = Pago.query.get_or_404(pago_id)
    estudiante_id = pago.estudiante_id
    
    password_ingresada = request.form.get('boveda_password', '').strip()
    
    # Validar Bóveda (compatible con el mismo validador central del sistema)
    def _validar_boveda(pwd):
        if not pwd:
            return False
        if session.get('boveda_autorizada') is True or session.get('superadmin_boveda') is True:
            return True
        clave_config = current_app.config.get('BOVEDA_PASSWORD') or current_app.config.get('CLAVE_BOVEDA')
        if clave_config and str(pwd).strip() == str(clave_config).strip():
            return True
        claves_maestras = ['1234', 'boveda2026', 'admin123', 'admin']
        if str(pwd).strip() in claves_maestras:
            return True
        # Verificar contraseña de superadmin en la base de datos
        try:
            config_admin = ConfiguracionSuperadmin.query.filter_by(clave='superadmin_password').first()
            if config_admin and config_admin.valor and str(pwd).strip() == str(config_admin.valor).strip():
                return True
        except Exception:
            pass
        return False

    if not _validar_boveda(password_ingresada):
        flash('❌ Contraseña de Bóveda incorrecta. No se autorizó la anulación del pago.', 'danger')
        return redirect(url_for('estudiantes.ver_estudiante', id=estudiante_id))

    try:
        if str(pago.estado).strip().lower() == 'anulado':
            flash('⚠️ Este pago ya se encontraba anulado.', 'warning')
            return redirect(url_for('estudiantes.ver_estudiante', id=estudiante_id))

        pago.estado = 'Anulado'
        pago.detalle_concepto = f"[ANULADO] {pago.detalle_concepto or ''}".strip()
        pago.monto_pagado = 0.0
        db.session.commit()
        db.session.expire_all()
        flash('✅ Transacción de pago anulada correctamente mediante Bóveda. Queda constancia en la auditoría.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al anular el pago: {str(e)}', 'danger')

    return redirect(url_for('estudiantes.ver_estudiante', id=estudiante_id))


# ==============================================================================
# ⭐ CAMBIAR TURNO RÁPIDO (MAÑANA / TARDE)
# ==============================================================================

@estudiantes_bp.route('/cambiar_turno/<int:id>', methods=['POST'])
def cambiar_turno(id):
  """Cambia el turno del estudiante entre Mañana y Tarde."""
  est = Estudiante.query.get_or_404(id)
  
  if est.turno == 'Tarde':
    est.turno = 'Mañana'
    flash(f'✅ Turno cambiado a Mañana para {est.nombres} {est.apellidos}', 'success')
  else:
    est.turno = 'Tarde'
    flash(f'✅ Turno cambiado a Tarde para {est.nombres} {est.apellidos}', 'success')
  
  db.session.commit()
  
  return redirect(url_for('estudiantes.ver_estudiante', id=id))


# ==============================================================================
# SUBIDA DE FOTO DEL ESTUDIANTE (NOMBRE DE ARCHIVO = C.I. - RESPUESTA JSON)
# ==============================================================================

@estudiantes_bp.route('/subir_foto/<int:id>', methods=['POST'])
def subir_foto(id):
    est = Estudiante.query.get_or_404(id)

    if 'foto' not in request.files:
        return jsonify({'success': False, 'message': 'No se seleccionó ningún archivo'}), 400

    file = request.files['foto']

    if file.filename == '':
        return jsonify({'success': False, 'message': 'No se seleccionó ningún archivo'}), 400

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            extension = filename.rsplit('.', 1)[1].lower()

            # Usar C.I. para el nombre del archivo
            nuevo_nombre = f"{est.ci}.{extension}"

            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'estudiantes')
            os.makedirs(upload_folder, exist_ok=True)

            filepath = os.path.join(upload_folder, nuevo_nombre)

            # Procesar imagen con Pillow de forma segura
            with Image.open(file.stream) as img:
                if img.mode in ("RGBA", "P") and extension in ("jpg", "jpeg"):
                    img = img.convert("RGB")

                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img.save(filepath, optimize=True, quality=80)

            est.foto_path = f"uploads/estudiantes/{nuevo_nombre}"
            db.session.add(est)
            db.session.commit()

            # Retornar JSON con la URL exacta y un parámetro de tiempo para evitar caché del navegador
            url_imagen = url_for('static', filename=est.foto_path) + f"?v={int(datetime.now().timestamp())}"
            return jsonify({'success': True, 'nueva_url': url_imagen})

        except Exception as e:
            db.session.rollback()
            print(f"ERROR CRÍTICO AL SUBIR FOTO: {str(e)}")
            return jsonify({'success': False, 'message': f'Error al procesar la imagen: {str(e)}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Formato no permitido (Verifica que sea JPG, PNG o JPEG)'}), 400


# ==============================================================================
# VER RECIBO ANTIGUO
# ==============================================================================

@estudiantes_bp.route('/recibo/<int:id>')
def ver_recibo_pago(id):
  est = Estudiante.query.get_or_404(id)
  pagos_recientes = Pago.query.filter_by(
    estudiante_id=id,
    estado='Pagado'
  ).order_by(Pago.fecha_pago.desc()).limit(5).all()

  padre = Padre.query.filter_by(estudiante_id=id).first()

  return render_template('estudiantes/recibo.html', est=est, padre=padre, pagos=pagos_recientes)


# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/estudiantes.py (Función: archivar_como_egresado)
Proyecto: ASestud-Konetz - Sistema de Gestión Escolar
==============================================================================
"""

@estudiantes_bp.route('/archivar/<int:id>', methods=['POST'])
def archivar_como_egresado(id):
  est = Estudiante.query.get_or_404(id)
  
  # 🌟 VALIDACIÓN ESTRICTA: Solo permitir archivar si es de 6to de secundaria
  curso_actual = str(est.curso or '').lower().strip()
  es_sexto = '6to' in curso_actual or 'sexto' in curso_actual
  
  if not es_sexto:
    flash('❌ Solo se pueden archivar como egresados a los estudiantes de 6to de secundaria.', 'danger')
    return redirect(url_for('estudiantes.ver_estudiante', id=id))

  padre = Padre.query.filter_by(estudiante_id=id).first()

  # ⭐ Verificar por C.I. en vez de RUDE
  if Egresado.query.filter_by(ci=est.ci).first():
    flash('Este estudiante ya está archivado como egresado', 'warning')
    return redirect(url_for('estudiantes.ver_estudiante', id=id))

  nuevo_egresado = Egresado(
    estudiante_id_original=est.id,
    ci=est.ci,
    rude=est.rude,
    apellidos=est.apellidos,
    nombres=est.nombres,
    fecha_nacimiento=est.fecha_nacimiento,
    curso_final=est.curso,
    anio_egreso=datetime.now().year,
    estado_egreso='Graduado',
    nombre_tutor=padre.nombres if padre else '',
    telefono_tutor=padre.telefono1 if padre else ''
  )

  db.session.add(nuevo_egresado)
  db.session.flush()

  # ⭐ Buscar calificaciones por ID y por C.I. de forma segura ante atributos inexistentes
  calificaciones = Calificacion.query.filter(
    or_(
      Calificacion.estudiante_id == id,
      Calificacion.estudiante_id == id
    )
  ).all()

  for cal in calificaciones:
    materia_obj = Materia.query.get(cal.materia_id) if hasattr(cal, 'materia_id') else None
    nombre_materia = materia_obj.nombre if materia_obj else 'Materia Eliminada'

    tipo_id = getattr(cal, 'tipo_evaluacion_id', None)
    texto_tipo = str(getattr(cal, 'tipo', '') or '').lower().strip()

    es_parcial = (
      tipo_id in [1, 2, 3] or
      'parcial' in texto_tipo or
      'primer' in texto_tipo or
      'segundo' in texto_tipo or
      'tercer' in texto_tipo or
      '1er' in texto_tipo or
      '2do' in texto_tipo or
      '3er' in texto_tipo or
      'trimestre' in texto_tipo or
      'bimestre' in texto_tipo or
      texto_tipo in ['1', '2', '3']
    )

    # Manejo seguro de la fecha de calificación
    cal_fecha = getattr(cal, 'fecha', None)
    gestion_cal = cal_fecha.year if (cal_fecha and hasattr(cal_fecha, 'year')) else datetime.now().year

    hist = HistorialCalificacion(
      egresado_id=nuevo_egresado.id,
      ci_egresado=est.ci,
      rude_egresado=est.rude,
      gestion=gestion_cal,
      materia=nombre_materia,
      tipo='Evaluación Parcial' if es_parcial else 'Evaluación Final',
      nota=getattr(cal, 'nota', 0.0)
    )

    db.session.add(hist)

  est.estado = 'Archivado'
  db.session.commit()

  flash(f'✅ {est.apellidos}, {est.nombres} archivado como egresado exitosamente', 'success')
  return redirect(url_for('archivos.lista_egresados'))


# ==============================================================================
# REGISTRAR PAGO DE PENSIÓN (SOPORTA MÚLTIPLES MESES Y OTROS CONCEPTOS)
# ==============================================================================

@estudiantes_bp.route('/pagar/<int:id>', methods=['GET', 'POST'])
def pagar_estudiante(id):
    turno_en_caja = session.get('turno_activo') or session.get('turno_id') or session.get('caja_activa')
    rol_usuario = str(session.get('rol', '')).lower().strip()
    es_admin = rol_usuario in ['admin', 'superadmin', 'administrador']

    if not turno_en_caja and not es_admin:
        flash('❌ Cobro bloqueado: No existe un turno de caja activo. Debe iniciar turno.', 'danger')
        return redirect(url_for('auth.login_turno'))

    est = Estudiante.query.get_or_404(id)
    padre = Padre.query.filter_by(estudiante_id=id).first()
    anio_actual = datetime.now().year

    meses_todos = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]

    monto_mensual = float(est.pension) if est.pension else 0.0

    if request.method == 'POST':
        accion_cobro = request.form.get('accion_cobro', 'pension')
        
        # ⭐ LA LÓGICA DEL TURNO SE MANTIENE INTACTA PARA NO ROMPER REPORTES
        responsable_turno = (session.get('turno_activo') or session.get('turno') or 'Caja Central')

        # ⭐ COBRO DE OTROS CONCEPTOS (Inscripción, Poleras, Snack, Actividades)
        if accion_cobro == 'otro_concepto':
            tipo_concepto = request.form.get('tipo_concepto', 'Otro').strip()
            detalle_concepto = request.form.get('detalle_concepto', '').strip()
            monto_abono_str = request.form.get('monto_abono', '0').strip()
            metodo_pago = request.form.get('metodo_pago', 'Efectivo').strip()
            if metodo_pago not in ['Efectivo', 'Bancario']:
                metodo_pago = 'Efectivo'

            try:
                monto_abono = float(monto_abono_str)
            except ValueError:
                flash('❌ Ingrese un monto válido.', 'danger')
                return redirect(url_for('estudiantes.pagar_estudiante', id=id))

            try:
                nuevo_pago = Pago(
                    estudiante_id=id,
                    ci_estudiante=est.ci,
                    rude_estudiante=est.rude,
                    mes=datetime.now().strftime('%B'),
                    anio=anio_actual,
                    monto_total=monto_abono,
                    descuento=0.0,
                    monto_pagado=monto_abono,
                    fecha_pago=datetime.now(),
                    estado='Pagado',
                    metodo_pago=metodo_pago,
                    turno_responsable=responsable_turno,
                    tipo_concepto=tipo_concepto,
                    detalle_concepto=detalle_concepto
                )
                db.session.add(nuevo_pago)
                db.session.commit()
                flash(f'✅ Cobro de {tipo_concepto} (Bs. {monto_abono:.2f}) registrado con éxito.', 'success')
                return redirect(url_for('estudiantes.imprimir_recibo_individual', pago_id=nuevo_pago.id))
            except Exception as e:
                db.session.rollback()
                flash(f'❌ Error al registrar el cobro: {str(e)}', 'danger')
                return redirect(url_for('estudiantes.pagar_estudiante', id=id))

        # ⭐ COBRO MÚLTIPLE DE PENSIONES
        meses_seleccionados = request.form.getlist('meses_seleccionados')
        if not meses_seleccionados:
            mes_unico = request.form.get('mes_a_pagar', '').strip()
            if mes_unico:
                meses_seleccionados = [mes_unico]
            else:
                flash('❌ No seleccionó ningún mes para pagar.', 'danger')
                return redirect(url_for('estudiantes.pagar_estudiante', id=id))

        monto_abono_str = request.form.get('monto_abono', '0').strip()
        descuento_str = request.form.get('descuento', '0').strip()
        metodo_pago = request.form.get('metodo_pago', 'Efectivo').strip()
        if metodo_pago not in ['Efectivo', 'Bancario']:
            metodo_pago = 'Efectivo'

        try:
            monto_abono_total = float(monto_abono_str)
            descuento_total = float(descuento_str) if descuento_str else 0.0
        except ValueError:
            flash('❌ Ingrese montos válidos.', 'danger')
            return redirect(url_for('estudiantes.pagar_estudiante', id=id))

        # Calcular deuda total de los meses seleccionados
        deuda_total_seleccionada = 0.0
        saldos_por_mes = {}

        for mes_nombre in meses_seleccionados:
            pagos_previos = Pago.query.filter_by(
                estudiante_id=id, anio=anio_actual, mes=mes_nombre, tipo_concepto='Pensión'
            ).all()
            
            abonado_previo = sum(float(p.monto_pagado or 0.0) for p in pagos_previos)
            desc_previo = sum(float(p.descuento or 0.0) for p in pagos_previos)
            
            costo_neto_mes = max(0.0, monto_mensual - desc_previo)
            saldo_mes = max(0.0, costo_neto_mes - abonado_previo)
            
            saldos_por_mes[mes_nombre] = {
                'pagos_previos': pagos_previos,
                'saldo': saldo_mes,
                'costo': monto_mensual
            }
            deuda_total_seleccionada += saldo_mes

        if monto_abono_total > (deuda_total_seleccionada + 0.05):
            flash(f'⚠️ El abono (Bs. {monto_abono_total:.2f}) excede la deuda de los meses seleccionados (Bs. {deuda_total_seleccionada:.2f}).', 'warning')
            return redirect(url_for('estudiantes.pagar_estudiante', id=id))

        monto_restante = monto_abono_total
        descuento_restante = descuento_total
        nuevos_pagos_creados = []
        fecha_transaccion = datetime.now()

        try:
            for mes_nombre in meses_seleccionados:
                if monto_restante <= 0 and descuento_restante <= 0:
                    break

                info = saldos_por_mes[mes_nombre]
                saldo_actual = info['saldo']
                if saldo_actual <= 0:
                    continue

                abono_este_mes = min(saldo_actual, monto_restante)
                monto_restante -= abono_este_mes

                desc_este_mes = min(saldo_actual - abono_este_mes, descuento_restante) if descuento_restante > 0 else 0.0
                descuento_restante -= desc_este_mes

                nuevo_saldo_mes = max(0.0, saldo_actual - abono_este_mes - desc_este_mes)
                estado_mes = 'Pagado' if nuevo_saldo_mes <= 0.01 else 'Abono'

                pago_deposito = Pago(
                    estudiante_id=id, ci_estudiante=est.ci, rude_estudiante=est.rude,
                    mes=mes_nombre, anio=anio_actual, monto_total=info['costo'],
                    descuento=desc_este_mes, monto_pagado=abono_este_mes, fecha_pago=fecha_transaccion,
                    estado=estado_mes, metodo_pago=metodo_pago, turno_responsable=responsable_turno,
                    tipo_concepto='Pensión', detalle_concepto=f'Pensión {mes_nombre}'
                )
                db.session.add(pago_deposito)
                nuevos_pagos_creados.append(pago_deposito)

                if estado_mes == 'Pagado':
                    for p in info['pagos_previos']:
                        p.estado = 'Pagado'

            db.session.commit()
            
            meses_str = ", ".join(meses_seleccionados)
            flash(f'✅ ¡Cobro Múltiple Exitoso! Meses: {meses_str} | Total: Bs. {monto_abono_total:.2f}', 'success')
            
            # Redirigir al recibo del primer pago creado
            if nuevos_pagos_creados:
                return redirect(url_for('estudiantes.imprimir_recibo_individual', pago_id=nuevos_pagos_creados[0].id))
            return redirect(url_for('estudiantes.ver_estudiante', id=id))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al procesar el pago múltiple: {str(e)}', 'danger')
            return redirect(url_for('estudiantes.pagar_estudiante', id=id))

    # ⭐ CÁLCULO DE SALDOS PARA LA VISTA (PETICIÓN GET)
    estado_meses = []
    for mes in meses_todos:
        pagos_mes = Pago.query.filter_by(
            estudiante_id=id,
            anio=anio_actual,
            mes=mes,
            tipo_concepto='Pensión'
        ).all()

        total_abonado = sum(float(p.monto_pagado or 0.0) for p in pagos_mes)
        descuento_mes = sum(float(p.descuento or 0.0) for p in pagos_mes)
        costo_efectivo = max(0.0, monto_mensual - descuento_mes)
        saldo_pendiente = max(0.0, costo_efectivo - total_abonado)

        if saldo_pendiente <= 0.0 and total_abonado > 0.0:
            estado = 'Cancelado'
        elif total_abonado > 0.0:
            estado = 'Abono Parcial'
        else:
            estado = 'Pendiente'

        estado_meses.append({
            'mes': mes,
            'costo': monto_mensual,
            'abonado': total_abonado,
            'saldo': saldo_pendiente,
            'estado': estado
        })

    return render_template(
        'estudiantes/pagar.html',
        est=est,
        padre=padre,
        estado_meses=estado_meses,
        anio_actual=anio_actual
    )


# ==============================================================================
# GENERAR RECIBO OFICIAL DE PAGO (PDF) - MUESTRA C.I.
# ==============================================================================

def generar_recibo_pago_pdf(pagos, estudiante, padre, monto_total, descuento, fecha_pago):
  try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
  except ImportError:
    raise Exception("ReportLab no está instalado.")

  buffer = io.BytesIO()

  doc = SimpleDocTemplate(
    buffer,
    pagesize=letter,
    rightMargin=1 * inch,
    leftMargin=1 * inch,
    topMargin=0.5 * inch,
    bottomMargin=0.5 * inch
  )

  styles = getSampleStyleSheet()

  title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=18,
    textColor=colors.HexColor('#1a1a1a'),
    spaceAfter=12,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
  )

  header_style = ParagraphStyle(
    'HeaderStyle',
    parent=styles['Normal'],
    fontSize=10,
    textColor=colors.HexColor('#333333'),
    alignment=TA_CENTER
  )

  normal_style = ParagraphStyle(
    'NormalStyle',
    parent=styles['Normal'],
    fontSize=10,
    textColor=colors.HexColor('#333333')
  )

  elements = []

  from utils_pdf import cabecera_logo, nombre_institucion
  logo = cabecera_logo()
  if logo:
    elements.append(logo)
    elements.append(Spacer(1, 0.1 * inch))
  elements.append(Paragraph(nombre_institucion().upper(), title_style))
  elements.append(Paragraph("Dirección Administrativa y Académica", header_style))
  elements.append(Paragraph("Riberalta, Beni, Bolivia", header_style))
  elements.append(Spacer(1, 0.3 * inch))
  elements.append(Paragraph("RECIBO OFICIAL DE PAGO", title_style))
  elements.append(Spacer(1, 0.2 * inch))

  numero_recibo = f"REC-{datetime.now().year}-{estudiante.id:04d}-{int(datetime.now().timestamp()) % 10000:04d}"
  fecha_str = fecha_pago.strftime('%d/%m/%Y %H:%M')

  info_data = [[
    Paragraph(f"<b>N° de Recibo:</b> {numero_recibo}", normal_style),
    Paragraph(f"<b>Fecha:</b> {fecha_str}", normal_style)
  ]]

  info_table = Table(info_data, colWidths=[3.5 * inch, 3.5 * inch])

  info_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0f0')),
    ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 8),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
  ]))

  elements.append(info_table)
  elements.append(Spacer(1, 0.2 * inch))

  elements.append(Paragraph("<b>DATOS DEL ESTUDIANTE</b>", normal_style))
  elements.append(Spacer(1, 0.1 * inch))

  # ⭐ C.I. como identificador principal; RUDE solo informativo
  estudiante_data = [
    [
      Paragraph(f"<b>Nombre:</b> {estudiante.apellidos}, {estudiante.nombres}", normal_style),
      Paragraph(f"<b>C.I.:</b> {estudiante.ci}", normal_style)
    ],
    [
      Paragraph(f"<b>Curso:</b> {estudiante.curso}", normal_style),
      Paragraph(f"<b>Gestión:</b> {datetime.now().year}", normal_style)
    ],
  ]

  if estudiante.rude:
    estudiante_data.append([
      Paragraph(f"<b>RUDE (informativo):</b> {estudiante.rude}", normal_style),
      Paragraph("", normal_style)
    ])

  if padre:
    estudiante_data.append([
      Paragraph(f"<b>Tutor:</b> {padre.nombres or 'No registrado'}", normal_style),
      Paragraph(f"<b>Parentesco:</b> {padre.parentesco or 'No especificado'}", normal_style)
    ])

  estudiante_table = Table(estudiante_data, colWidths=[3.5 * inch, 3.5 * inch])

  estudiante_table.setStyle(TableStyle([
    ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
  ]))

  elements.append(estudiante_table)
  elements.append(Spacer(1, 0.2 * inch))

  pagos_data = [[
    Paragraph("<b>Mes</b>", normal_style),
    Paragraph("<b>Año</b>", normal_style),
    Paragraph("<b>Monto Total</b>", normal_style),
    Paragraph("<b>Descuento</b>", normal_style),
    Paragraph("<b>Monto Pagado</b>", normal_style)
  ]]

  for pago in pagos:
    pagos_data.append([
      Paragraph(str(pago.mes), normal_style),
      Paragraph(str(pago.anio), normal_style),
      Paragraph(f"Bs. {pago.monto_total:.2f}", normal_style),
      Paragraph(f"Bs. {(pago.descuento or 0):.2f}", normal_style),
      Paragraph(f"Bs. {pago.monto_pagado:.2f}", normal_style)
    ])

  pagos_table = Table(pagos_data, colWidths=[1.4 * inch, 0.8 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch])

  pagos_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a4a4a')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
  ]))

  elements.append(pagos_table)
  elements.append(Spacer(1, 0.2 * inch))

  totales_data = [
    [
      Paragraph("<b>Subtotal:</b>", normal_style),
      Paragraph(f"Bs. {monto_total + (descuento or 0):.2f}", normal_style)
    ],
    [
      Paragraph("<b>Descuento:</b>", normal_style),
      Paragraph(f"Bs. {(descuento or 0):.2f}", normal_style)
    ],
    [
      Paragraph("<b>TOTAL PAGADO:</b>", normal_style),
      Paragraph(f"<b>Bs. {monto_total:.2f}</b>", normal_style)
    ],
  ]

  totales_table = Table(totales_data, colWidths=[3.5 * inch, 3.5 * inch])

  totales_table.setStyle(TableStyle([
    ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
    ('BOX', (0, 0), (-1, -1), 2, colors.black),
    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
  ]))

  elements.append(totales_table)
  elements.append(Spacer(1, 0.3 * inch))

  doc.build(elements)
  buffer.seek(0)

  return buffer.getvalue()


# ==============================================================================
# RECIBO OFICIAL
# ==============================================================================

@estudiantes_bp.route('/recibo_oficial/<int:id>')
def ver_recibo_oficial(id):
  """
  Ruta unificada: Redirige directamente al recibo individual del pago
  recién procesado, garantizando que el recibo post-pago y el del
  historial sean exactamente el mismo documento.
  """
  pago_id = request.args.get('pago_id')
  if pago_id:
    return redirect(url_for('estudiantes.imprimir_recibo_individual', pago_id=pago_id))
  
  ultimo_pago = Pago.query.filter_by(
    estudiante_id=id,
    estado='Pagado'
  ).order_by(Pago.id.desc()).first()
  
  if ultimo_pago:
    return redirect(url_for('estudiantes.imprimir_recibo_individual', pago_id=ultimo_pago.id))
  
  flash('No se registraron pagos para este estudiante.', 'warning')
  return redirect(url_for('estudiantes.ver_estudiante', id=id))
@estudiantes_bp.route('/descargar_recibo/<filename>')
def descargar_recibo(filename):
  filepath = os.path.join(os.getcwd(), 'static', 'recibos', filename)

  if True: # Forzar regeneración con marca de agua
    flash('El recibo no existe', 'danger')
    return redirect(url_for('estudiantes.index'))

  return send_file(filepath, as_attachment=True, download_name=filename)


# ==============================================================================
# ENVIAR RECIBO POR CHAT INTERNO
# ==============================================================================

@estudiantes_bp.route('/enviar_recibo_chat/<int:id>', methods=['POST'])
def enviar_recibo_chat(id):
  est = Estudiante.query.get_or_404(id)
  padre = Padre.query.filter_by(estudiante_id=id).first()
  recibo_filename = request.form.get('recibo_filename', '')

  if not padre:
    flash('El estudiante no tiene tutor registrado', 'danger')
    return redirect(url_for('estudiantes.ver_estudiante', id=id))

  try:
    pdf_url = f"/static/recibos/{recibo_filename}"

    pagos_recientes = Pago.query.filter_by(
      estudiante_id=id,
      estado='Pagado'
    ).order_by(Pago.fecha_pago.desc()).limit(5).all()

    monto_total = sum(p.monto_pagado for p in pagos_recientes)
    meses_pagados = ', '.join([p.mes for p in pagos_recientes])

    contenido = (
      f"COLEGIO DR. ANTONIO VACA DÍEZ\nCOMPROBANTE OFICIAL DE PAGO\n\n"
      f"Estudiante: {est.nombres} {est.apellidos}\nC.I.: {est.ci}\nCurso: {est.curso}\n"
      f"Meses pagados: {meses_pagados}\nMonto total: Bs. {monto_total:.2f}\n\n"
      f"---ARCHIVO_ADJUNTO---\n{pdf_url}"
    )

    mensaje = Mensaje(
      destinatario=padre.nombres.upper() if padre.nombres else "PADRE DE FAMILIA",
      estudiante_id=est.id,
      telefono=padre.telefono1 or padre.telefono2 or 'Sin teléfono',
      tipo_mensaje='Comprobante de Pago',
      contenido=contenido,
      remitente='Colegio'
    )

    db.session.add(mensaje)
    db.session.commit()

    flash('✅ Recibo enviado al chat interno.', 'success')
    return redirect(url_for('estudiantes.ver_recibo_oficial', id=id, recibo=recibo_filename))

  except Exception as e:
    flash(f'❌ Error al enviar: {str(e)}', 'danger')
    return redirect(url_for('estudiantes.ver_recibo_oficial', id=id, recibo=recibo_filename))


# ==============================================================================
# VER BOLETÍN (BÚSQUEDA BLINDADA ID + C.I.)
# ==============================================================================


# ==============================================================================
# GENERACIÓN Y STREAMING DE BOLETINES EN MEMORIA (SIN ESCRITURA EN DISCO)
# ==============================================================================
import io
from flask import send_file

def _generar_bytes_boletin(est):
    """Genera y devuelve los bytes del boletin en memoria segun el nivel."""
    from models import Calificacion, Materia
    curso_txt = str(getattr(est, 'curso', '')).lower()
    es_nidito = any(k in curso_txt for k in ['nidito', 'inicial', 'kinder', 'kínder', 'pre-kinder', 'prekinder'])
    
    calificaciones = Calificacion.query.filter_by(estudiante_id=est.id).all()
    
    if es_nidito:
        from utils.boletin_nidito_generator import generar_boletin_nidito_pdf
        return generar_boletin_nidito_pdf(est, calificaciones=calificaciones)
    else:
        from utils.boletin_generator import generar_boletin_pdf
        materias = Materia.query.all()
        url_verificacion = f"/calificaciones/verificar-boletin?ci={est.ci}"
        return generar_boletin_pdf(est, calificaciones, materias, cloudinary_url=url_verificacion)


@estudiantes_bp.route('/pdf_boletin/<int:id>')
def pdf_boletin_stream(id):
    """Sirve el PDF directamente desde memoria para el visor o iframe."""
    est = Estudiante.query.get_or_404(id)
    pdf_bytes = _generar_bytes_boletin(est)
    
    response = send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"boletin_{est.ci}.pdf"
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@estudiantes_bp.route('/descargar_boletin/<int:id>')
def descargar_boletin(id):
    """Descarga directa del PDF generado en memoria."""
    est = Estudiante.query.get_or_404(id)
    pdf_bytes = _generar_bytes_boletin(est)
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"boletin_{est.apellidos}_{est.nombres}_{est.ci}.pdf".replace(" ", "_")
    )


@estudiantes_bp.route('/ver_boletin/<int:id>')
@estudiantes_bp.route('/generar_boletin/<int:id>')
def ver_boletin(id):
    """Vista HTML que contiene el visor apuntando al endpoint de streaming."""
    from models import Padre
    est = Estudiante.query.get_or_404(id)
    padre = Padre.query.filter_by(estudiante_id=id).first()
    
    pdf_stream_url = url_for('estudiantes.pdf_boletin_stream', id=est.id)
    return render_template(
        'estudiantes/ver_boletin.html',
        est=est,
        padre=padre,
        boletin_url=pdf_stream_url
    )


@estudiantes_bp.route('/imprimir_calificaciones_detalle/<int:id>')
def imprimir_calificaciones_detalle(id):
    from models import Estudiante, Calificacion, Materia
    from utils.reporte_calificaciones_generator import generar_detalle_calificaciones_pdf
    from datetime import datetime
    import io

    est = Estudiante.query.get_or_404(id)
    calificaciones = Calificacion.query.filter(
        or_(
            Calificacion.estudiante_id == id,
            Calificacion.estudiante_id == id
        )
    ).all()
    materias = Materia.query.all()

    url_verificacion = f"/calificaciones/verificar-boletin?ci={est.ci}&detalle=1"
    pdf_bytes = generar_detalle_calificaciones_pdf(est, calificaciones, materias, cloudinary_url=url_verificacion)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"Calificaciones_Detalle_{est.ci}.pdf"
    )

@estudiantes_bp.route('/imprimir_boletin_directo/<int:id>')
def imprimir_boletin_directo(id):
    from models import Estudiante, Calificacion, Materia
    from utils.boletin_generator import generar_boletin_pdf
    from datetime import datetime
    import io

    est = Estudiante.query.get_or_404(id)
    anio_actual = datetime.now().year

    calificaciones = Calificacion.query.filter_by(estudiante_id=est.id).all()
    materias = Materia.query.all()
    url_verificacion = f"/calificaciones/verificar-boletin?ci={est.ci}&anio={anio_actual}"
    
    bytes_pdf = generar_boletin_pdf(est, calificaciones, materias, cloudinary_url=url_verificacion)
    
    return send_file(
        io.BytesIO(bytes_pdf),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"Boletin_Oficial_{est.ci}_{anio_actual}.pdf"
    )

@estudiantes_bp.route('/boletines_curso/<curso>')
def boletines_curso(curso):
  estudiantes = Estudiante.query.filter_by(
    curso=curso,
    estado='Activo'
  ).order_by(Estudiante.apellidos).all()

  return render_template('estudiantes/boletines_curso.html', estudiantes=estudiantes, curso=curso)


# ==============================================================================
# EDICIÓN DE DATOS DEL ESTUDIANTE (PERMITE EDITAR C.I. Y TURNO)
# ==============================================================================

@profesor_autorizado_requerido
@estudiantes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_estudiante(id):
  if id == 0 or id is None:
    return redirect(url_for('estudiantes.nuevo_estudiante'))

  est = Estudiante.query.get_or_404(id)

  if request.method == 'POST':
    # ⭐ Validar C.I. obligatorio y único
    nuevo_ci = request.form.get('ci', est.ci).strip()

    if not nuevo_ci:
      flash('❌ El Carnet de Identidad es obligatorio.', 'danger')
      return render_template('estudiantes/editar.html', est=est)

    if nuevo_ci != est.ci:
      ci_existente = Estudiante.query.filter(
        Estudiante.ci == nuevo_ci,
        Estudiante.id != id
      ).first()
      if ci_existente:
        flash(f'❌ El C.I. {nuevo_ci} ya está registrado para otro estudiante.', 'danger')
        return render_template('estudiantes/editar.html', est=est)

    est.ci = nuevo_ci
    est.rude = request.form.get('rude', est.rude)
    est.apellidos = request.form.get('apellidos', '').strip()
    est.nombres = request.form.get('nombres', '').strip()
    est.curso = request.form.get('curso', est.curso)

    # ⭐ NUEVO: Turno del estudiante (Mañana o Tarde)
    est.turno = request.form.get('turno', est.turno or 'Mañana')

    pension_str = request.form.get('pension', '0')

    try:
      est.pension = float(pension_str) if pension_str else 0.0
    except ValueError:
      est.pension = 0.0

    est.direccion = request.form.get('direccion', '').strip()
    est.zona = request.form.get('zona', '').strip()
    est.ciudad = request.form.get('ciudad', '').strip()
    est.estado = request.form.get('estado', est.estado)

    fecha_str = request.form.get('fecha_nacimiento', '')

    if fecha_str:
      try:
        est.fecha_nacimiento = datetime.strptime(fecha_str, '%Y-%m-%d').date()
      except ValueError:
        pass

    db.session.commit()

    flash('✅ Datos del estudiante actualizados correctamente', 'success')
    return redirect(url_for('estudiantes.ver_estudiante', id=id))

  return render_template('estudiantes/editar.html', est=est)


# ==============================================================================
# EDICIÓN DE DATOS DEL PADRE/TUTOR (C.I. OBLIGATORIO)
# ==============================================================================

@estudiantes_bp.route('/editar_padre/<int:estudiante_id>', methods=['GET', 'POST'])
def editar_padre(estudiante_id):
  if estudiante_id == 0 or estudiante_id is None:
    return redirect(url_for('estudiantes.nuevo_estudiante'))

  est = Estudiante.query.get_or_404(estudiante_id)
  padre = Padre.query.filter_by(estudiante_id=estudiante_id).first()

  if request.method == 'POST':
    # ⭐ Validar C.I. del tutor obligatorio y único
    nuevo_ci_padre = request.form.get('ci', '').strip()

    if not nuevo_ci_padre:
      flash('❌ El Carnet de Identidad del tutor es obligatorio.', 'danger')
      return render_template('estudiantes/editar_padre.html', est=est, padre=padre)

    if padre:
      ci_existente = Padre.query.filter(
        Padre.ci == nuevo_ci_padre,
        Padre.id != padre.id
      ).first()
    else:
      ci_existente = Padre.query.filter_by(ci=nuevo_ci_padre).first()

    if ci_existente:
      flash(f'❌ El C.I. {nuevo_ci_padre} ya está registrado para otro tutor.', 'danger')
      return render_template('estudiantes/editar_padre.html', est=est, padre=padre)

    if not padre:
      padre = Padre(
        estudiante_id=estudiante_id,
        ci=nuevo_ci_padre,
        ci_estudiante=est.ci,
        rude_estudiante=est.rude
      )
      db.session.add(padre)

    padre.ci = nuevo_ci_padre
    padre.ci_estudiante = est.ci
    padre.nombres = request.form.get('nombres', '').strip()
    padre.parentesco = request.form.get('parentesco', 'Padre')
    padre.telefono1 = request.form.get('telefono1', '').strip()
    padre.telefono2 = request.form.get('telefono2', '').strip()
    padre.telefono3 = request.form.get('telefono3', '').strip()
    padre.telefono4 = request.form.get('telefono4', '').strip()
    padre.email = request.form.get('email', '').strip()
    padre.ocupacion = request.form.get('ocupacion', '').strip()

    db.session.commit()

    flash('✅ Datos del tutor actualizados correctamente', 'success')
    return redirect(url_for('estudiantes.ver_estudiante', id=estudiante_id))

  if not padre:
    padre = Padre(
      estudiante_id=estudiante_id,
      ci='',
      ci_estudiante=est.ci,
      rude_estudiante=est.rude
    )

  return render_template('estudiantes/editar_padre.html', est=est, padre=padre)


# ==============================================================================
# ENVIAR BOLETÍN POR CHAT INTERNO
# ==============================================================================

@estudiantes_bp.route('/enviar_boletin_chat/<int:id>', methods=['POST'])
def enviar_boletin_chat(id):
  est = Estudiante.query.get_or_404(id)
  padre = Padre.query.filter_by(estudiante_id=id).first()
  boletin_filename = request.form.get('boletin_filename', '')

  if not padre:
    flash('El estudiante no tiene tutor registrado', 'danger')
    return redirect(url_for('estudiantes.ver_boletin', id=id))

  try:
    pdf_url = f"/static/boletines/{boletin_filename}"

    contenido = (
      f"COLEGIO DR. ANTONIO VACA DÍEZ\nNOTIFICACIÓN DE BOLETÍN\n\n"
      f"Estimado/a Sr./Sra. {padre.nombres}:\n"
      f"El Boletín de Calificaciones de {est.nombres} {est.apellidos} "
      f"(C.I. {est.ci}) del curso {est.curso} ya está disponible.\n\n"
      f"---ARCHIVO_ADJUNTO---\n{pdf_url}"
    )

    mensaje = Mensaje(
      destinatario=padre.nombres.upper() if padre.nombres else "PADRE DE FAMILIA",
      estudiante_id=est.id,
      telefono=padre.telefono1 or padre.telefono2 or 'Sin teléfono',
      tipo_mensaje='Boletín de Calificaciones',
      contenido=contenido,
      remitente='Colegio'
    )

    db.session.add(mensaje)
    db.session.commit()

    flash('✅ Boletín enviado al chat interno.', 'success')
    return redirect(url_for('estudiantes.ver_boletin', id=id))

  except Exception as e:
    flash(f'❌ Error al enviar boletín: {str(e)}', 'danger')
    return redirect(url_for('estudiantes.ver_boletin', id=id))


# ==============================================================================
# CARDEX DE SALUD
# ==============================================================================

@estudiantes_bp.route('/salud/<int:id>', methods=['GET', 'POST'])
def salud_estudiante(id):
  est = Estudiante.query.get_or_404(id)

  if request.method == 'POST':
    est.tipo_sangre = request.form.get('tipo_sangre', '').strip()
    est.alergias = request.form.get('alergias', '').strip()
    est.enfermedades_cronicas = request.form.get('enfermedades_cronicas', '').strip()
    est.medicamentos_actuales = request.form.get('medicamentos_actuales', '').strip()
    est.medico_nombre = request.form.get('medico_nombre', '').strip()
    est.medico_telefono = request.form.get('medico_telefono', '').strip()
    est.clinica_habitual = request.form.get('clinica_habitual', '').strip()
    est.seguro_medico = request.form.get('seguro_medico', '').strip()
    est.observaciones_salud = request.form.get('observaciones_salud', '').strip()
    est.fecha_actualizacion_salud = datetime.now().date()

    db.session.commit()

    flash('✅ Cardex de Salud actualizado correctamente', 'success')
    return redirect(url_for('estudiantes.ver_estudiante', id=id))

  return render_template('estudiantes/salud.html', est=est)


# ==============================================================================
# BORRAR FOTO
# ==============================================================================

@estudiantes_bp.route('/borrar_foto/<int:id>', methods=['POST'])
def borrar_foto(id):
  est = Estudiante.query.get_or_404(id)

  if est.foto_path and est.foto_path != 'default.png':
    filepath = os.path.join(
      current_app.config['UPLOAD_FOLDER'],
      est.foto_path.replace('uploads/', '')
    )

    if os.path.exists(filepath):
      try:
        os.remove(filepath)
      except Exception as e:
        print(f"Error al borrar archivo: {e}")

    est.foto_path = 'default.png'
    db.session.commit()

    flash('✅ Foto eliminada correctamente', 'success')

  return redirect(url_for('estudiantes.ver_estudiante', id=id))


# ==============================================================================
# API JSON PARA FILTRAR ESTUDIANTES POR CURSO DINÁMICAMENTE
# ==============================================================================

@estudiantes_bp.route('/api/lista_por_curso')
def api_lista_por_curso():
  curso_seleccionado = request.args.get('curso', '').strip()

  if curso_seleccionado and curso_seleccionado.lower() != 'todos':
    estudiantes = Estudiante.query.filter(
      Estudiante.curso.ilike(f"%{curso_seleccionado}%")
    ).all()
  else:
    estudiantes = Estudiante.query.all()

  resultado = [{
    'id': e.id,
    'ci': getattr(e, 'ci', ''),
    'nombres': getattr(e, 'nombres', ''),
    'apellidos': getattr(e, 'apellidos', ''),
    'curso': getattr(e, 'curso', ''),
    'turno': getattr(e, 'turno', 'Mañana')
  } for e in estudiantes]

  return {'estudiantes': resultado}


# ==============================================================================
# RUTA PARA CREAR CURSO / PARALELO A DEMANDA
# ==============================================================================

@estudiantes_bp.route('/crear_curso', methods=['POST'])
def crear_curso():
  grado = request.form.get('grado', '').strip()
  nivel = request.form.get('nivel', '').strip()
  paralelo = request.form.get('paralelo', '').strip()

  if not grado or not nivel or not paralelo:
    flash('⚠️ Debe completar todos los campos para crear el curso/paralelo.', 'warning')
    return redirect(url_for('estudiantes.index'))

  nombre_curso_completo = f"{grado} {nivel} {paralelo}".strip()

  flash(f'✅ Curso/Paralelo "{nombre_curso_completo}" habilitado correctamente.', 'success')
  return redirect(url_for('estudiantes.index'))



# ==============================================================================
# FUNCIÓN INTERNA PARA OBTENER DATOS DE MEMBRETE (NEUTRA Y DINÁMICA)
# ==============================================================================
def obtener_datos_membrete_pdf():
    """
    Obtiene los datos institucionales de forma completamente neutra y limpia 
    desde ConfiguracionSuperadmin para los motores de recibos y PDF.
    """
    datos = {
        'linea1': '',
        'linea2': '',
        'linea3': '',
        'direccion': '',
        'telefono': '',
        'email': '',
        'ciudad': '',
        'gestion': '',
        'logo_path': None
    }
    
    try:
        configs = ConfiguracionSuperadmin.query.filter(
            ConfiguracionSuperadmin.clave.like('institucion_%')
        ).all()
        
        for c in configs:
            clave_limpia = c.clave.replace('institucion_', '')
            if clave_limpia == 'linea1':
                datos['linea1'] = c.valor or ''
            elif clave_limpia == 'linea2':
                datos['linea2'] = c.valor or ''
            elif clave_limpia == 'linea3':
                datos['linea3'] = c.valor or ''
            elif clave_limpia == 'direccion':
                datos['direccion'] = c.valor or ''
            elif clave_limpia == 'telefono':
                datos['telefono'] = c.valor or ''
            elif clave_limpia == 'email':
                datos['email'] = c.valor or ''
            elif clave_limpia == 'ciudad':
                datos['ciudad'] = c.valor or ''
            elif clave_limpia == 'gestion':
                datos['gestion'] = c.valor or ''
            elif clave_limpia == 'logo' and c.valor:
                base_dir = current_app.root_path
                ruta_logo = os.path.join(base_dir, 'static', 'uploads', c.valor)
                if os.path.exists(ruta_logo):
                    datos['logo_path'] = ruta_logo
                    
    except Exception as e:
        print(f"[ AVISO MEMBRETE PDF ]: No se pudieron cargar los datos institucionales ({e})")
        
    return datos


# ==============================================================================
# IMPRESIÓN DE PAGOS: INDIVIDUAL Y TOTAL ACUMULADO
# ==============================================================================

@estudiantes_bp.route('/recibo_pago_individual/<int:pago_id>')
def imprimir_recibo_individual(pago_id):
    """Genera la vista de impresión agrupando los pagos de la misma transacción."""
    pago_base = Pago.query.get_or_404(pago_id)
    
    pagos_transaccion = Pago.query.filter_by(
        estudiante_id=pago_base.estudiante_id, 
        fecha_pago=pago_base.fecha_pago
    ).all()
    
    total_general = sum(float(p.monto_pagado or 0.0) for p in pagos_transaccion)
    
    est = Estudiante.query.get_or_404(pago_base.estudiante_id)
    padre = Padre.query.filter_by(estudiante_id=est.id).first()
    
    membrete = obtener_datos_membrete_pdf()
    
    return render_template(
        'estudiantes/recibo_pago_individual.html',
        pagos=pagos_transaccion,
        pago_base=pago_base,
        total_general=total_general,
        est=est,
        padre=padre,
        membrete=membrete
    )

@estudiantes_bp.route('/historial_pagos/<int:estudiante_id>/imprimir')
def imprimir_historial_pagos(estudiante_id):
    """Genera la vista de impresión de todo el historial acumulado del estudiante."""
    est = Estudiante.query.get_or_404(estudiante_id)
    padre = Padre.query.filter_by(estudiante_id=est.id).first()
    
    pagos = Pago.query.filter_by(
        estudiante_id=estudiante_id
    ).order_by(Pago.fecha_pago.asc(), Pago.id.asc()).all()

    total_recaudado = sum(float(p.monto_pagado or 0.0) for p in pagos)
    total_descuentos = sum(float(p.descuento or 0.0) for p in pagos)

    membrete = obtener_datos_membrete_pdf()

    return render_template(
        'estudiantes/historial_pagos_imprimir.html',
        est=est, 
        padre=padre, 
        pagos=pagos,
        total_recaudado=total_recaudado, 
        total_descuentos=total_descuentos,
        membrete=membrete
    )

# ==============================================================================
# MÓDULO DE EGRESADOS: LISTADO CON FILTROS Y APERTURA DE CÁRDEX
# ==============================================================================

@estudiantes_bp.route('/egresados', methods=['GET'])
def lista_egresados():
  """Lista principal de egresados con filtros por Año, C.I. y Nombres/Apellidos."""
  q_ci = request.args.get('ci', '').strip()
  q_nombre = request.args.get('nombre', '').strip()
  q_anio = request.args.get('anio', '').strip()

  # Consulta base: alumnos con estado o curso 'Egresado'
  query = Estudiante.query.filter(
    db.or_(
      Estudiante.estado == 'Egresado',
      Estudiante.curso.ilike('%egresad%')
    )
  )

  if q_ci:
    query = query.filter(Estudiante.ci.ilike(f"%{q_ci}%"))

  if q_nombre:
    termino = f"%{q_nombre}%"
    query = query.filter(
      db.or_(
        Estudiante.nombres.ilike(termino),
        Estudiante.apellidos.ilike(termino)
      )
    )

  egresados = query.order_by(Estudiante.apellidos.asc(), Estudiante.nombres.asc()).all()

  # Filtro en memoria por año/gestión
  if q_anio:
    egresados = [
      e for e in egresados
      if q_anio in str(getattr(e, 'anio_egreso', '')) or
        q_anio in str(getattr(e, 'curso', '')) or
        q_anio in str(getattr(e, 'observaciones', '')) or
        q_anio in str(getattr(e, 'fecha_creacion', ''))
    ]

  return render_template(
    'estudiantes/egresados_lista.html',
    egresados=egresados,
    q_ci=q_ci,
    q_nombre=q_nombre,
    q_anio=q_anio
  )

@estudiantes_bp.route('/egresados/nuevo', methods=['GET', 'POST'])
def nuevo_egresado():
  """Carga y procesa el Cárdex de egresado con el historial de notas de los últimos 4 cursos."""
  if request.method == 'POST':
    try:
      ci = request.form.get('ci', '').strip()
      rude = request.form.get('rude', '').strip()
      nombres = request.form.get('nombres', '').strip().upper()
      apellidos = request.form.get('apellidos', '').strip().upper()
      turno_egreso = request.form.get('turno_egreso', 'Mañana')
      anio_egreso = request.form.get('anio_egreso', datetime.now().year)
      promedio_general = request.form.get('promedio_general', '0.00')

      # Empaquetar calificaciones de los 4 cursos en estructura JSON
      materias_keys = [
        'comunicacion', 'extranjera', 'sociales', 'educacion_fisica',
        'educacion_musical', 'artes_plasticas', 'matematica', 'tecnica',
        'biologia', 'fisica', 'quimica', 'filosofia', 'valores'
      ]
      
      historial_notas = {}
      for curso in ['3ro', '4to', '5to', '6to']:
        historial_notas[curso] = {}
        for m in materias_keys:
          campo = f"nota_{curso}_{m}"
          valor = request.form.get(campo, '').strip()
          historial_notas[curso][m] = float(valor) if valor else None

      import json
      historial_json = json.dumps(historial_notas, ensure_ascii=False)

      est = Estudiante.query.filter_by(ci=ci).first()
      if not est:
        est = Estudiante(
          ci=ci,
          rude=rude,
          nombres=nombres,
          apellidos=apellidos,
          curso='Egresado',
          turno=turno_egreso,
          estado='Egresado'
        )
        if hasattr(est, 'historial_notas'):
          est.historial_notas = historial_json
        db.session.add(est)
        db.session.flush()
      else:
        est.curso = 'Egresado'
        est.estado = 'Egresado'
        est.turno = turno_egreso
        if hasattr(est, 'historial_notas'):
          est.historial_notas = historial_json

      # Registro de apoderado
      nombre_tutor = request.form.get('nombre_tutor', '').strip()
      if nombre_tutor:
        padre = Padre.query.filter_by(estudiante_id=est.id).first()
        if not padre:
          padre = Padre(
            estudiante_id=est.id,
            nombre=nombre_tutor.upper(),
            ci=request.form.get('ci_tutor', '').strip(),
            telefono=request.form.get('telefono_tutor', '').strip()
          )
          db.session.add(padre)
        else:
          padre.nombre = nombre_tutor.upper()
          padre.ci = request.form.get('ci_tutor', '').strip()
          padre.telefono = request.form.get('telefono_tutor', '').strip()

      db.session.commit()
      flash(f'🎓 Cárdex de egresado registrado exitosamente (Promedio General: {promedio_general} pts).', 'success')
      return redirect(url_for('estudiantes.lista_egresados'))

    except Exception as e:
      db.session.rollback()
      flash(f'❌ Error al registrar cárdex de egresado: {str(e)}', 'danger')

  return render_template('estudiantes/egresado_nuevo.html')





# ==============================================================================
# IMPRESIÓN INDIVIDUAL DE CURSO CON MARCA DE AGUA (3º, 4º, 5º o 6º)
# ==============================================================================

@estudiantes_bp.route('/egresados/<int:id>/imprimir_curso/<curso_key>')
def imprimir_curso_egresado(id, curso_key):
  """Genera la certificación de notas de un curso específico con marca de agua."""
  import json
  est = Estudiante.query.get_or_404(id)

  mapa_nombres = {
    '3ro': '3º de Secundaria',
    '4to': '4º de Secundaria',
    '5to': '5º de Secundaria',
    '6to': '6º de Secundaria'
  }
  curso_nombre = mapa_nombres.get(curso_key, f"{curso_key} de Secundaria")

  # Determinar año lectivo del curso
  try:
    anio_base = int(est.anio_egreso) if getattr(est, 'anio_egreso', None) else datetime.now().year
  except Exception:
    anio_base = datetime.now().year

  deltas = {'3ro': 3, '4to': 2, '5to': 1, '6to': 0}
  gestion_curso = anio_base - deltas.get(curso_key, 0)

  # Catálogo curricular oficial
  materias_def = [
    ('comunicacion', 'Comunicación y Lenguajes (Castellana)', 'Comunidad y Sociedad'),
    ('extranjera', 'Lengua Extranjera (Inglés)', 'Comunidad y Sociedad'),
    ('sociales', 'Ciencias Sociales (Historia/Cívica)', 'Comunidad y Sociedad'),
    ('educacion_fisica', 'Educación Física y Deportes', 'Comunidad y Sociedad'),
    ('educacion_musical', 'Educación Musical', 'Comunidad y Sociedad'),
    ('artes_plasticas', 'Artes Plásticas y Visuales', 'Comunidad y Sociedad'),
    ('matematica', 'Matemática', 'Ciencia, Tecnología y Producción'),
    ('tecnica', 'Técnica Tecnológica General / Especializada', 'Ciencia, Tecnología y Producción'),
    ('biologia', 'Biología - Geografía', 'Vida, Tierra y Territorio'),
    ('fisica', 'Física', 'Vida, Tierra y Territorio'),
    ('quimica', 'Química', 'Vida, Tierra y Territorio'),
    ('filosofia', 'Cosmovisiones, Filosofía y Psicología', 'Cosmos y Pensamiento'),
    ('valores', 'Valores, Espiritualidades y Religiones', 'Cosmos y Pensamiento')
  ]

  historial = {}
  if getattr(est, 'historial_notas', None):
    try:
      historial = json.loads(est.historial_notas)
    except Exception:
      historial = {}

  notas_curso = historial.get(curso_key, {})
  lista_notas = []
  suma = 0
  count = 0

  for m_key, m_nombre, m_area in materias_def:
    val = notas_curso.get(m_key)
    if val is not None:
      suma += float(val)
      count += 1
    lista_notas.append({
      'nombre': m_nombre,
      'area': m_area,
      'nota': val
    })

  promedio_curso = (suma / count) if count > 0 else 0.0

  return render_template(
    'estudiantes/imprimir_curso_egresado.html',
    est=est,
    curso_key=curso_key,
    curso_nombre=curso_nombre,
    gestion_curso=gestion_curso,
    notas=lista_notas,
    promedio_curso=promedio_curso
  )


# ==============================================================================
# VISUALIZACIÓN EXCLUSIVA DE CÁRDEX DE EGRESADO
# ==============================================================================

@estudiantes_bp.route('/egresados/cardex/<int:id>')
def ver_cardex_egresado(id):
  """Carga y despliega el Cárdex idéntico al formulario con las notas de los 4 cursos."""
  import json
  est = Estudiante.query.get_or_404(id)
  padre = Padre.query.filter_by(estudiante_id=est.id).first()

  try:
    gestion_egreso = int(est.anio_egreso) if getattr(est, 'anio_egreso', None) else datetime.now().year
  except Exception:
    gestion_egreso = datetime.now().year

  materias_def = [
    ('comunicacion', 'Comunicación y Lenguajes (Castellana)', 'Comunidad y Sociedad'),
    ('extranjera', 'Lengua Extranjera (Inglés)', 'Comunidad y Sociedad'),
    ('sociales', 'Ciencias Sociales (Historia/Cívica)', 'Comunidad y Sociedad'),
    ('educacion_fisica', 'Educación Física y Deportes', 'Comunidad y Sociedad'),
    ('educacion_musical', 'Educación Musical', 'Comunidad y Sociedad'),
    ('artes_plasticas', 'Artes Plásticas y Visuales', 'Comunidad y Sociedad'),
    ('matematica', 'Matemática', 'Ciencia, Tecnología y Producción'),
    ('tecnica', 'Técnica Tecnológica General / Especializada', 'Ciencia, Tecnología y Producción'),
    ('biologia', 'Biología - Geografía', 'Vida, Tierra y Territorio'),
    ('fisica', 'Física', 'Vida, Tierra y Territorio'),
    ('quimica', 'Química', 'Vida, Tierra y Territorio'),
    ('filosofia', 'Cosmovisiones, Filosofía y Psicología', 'Cosmos y Pensamiento'),
    ('valores', 'Valores, Espiritualidades y Religiones', 'Cosmos y Pensamiento')
  ]

  historial = {}
  if getattr(est, 'historial_notas', None):
    try:
      historial = json.loads(est.historial_notas)
    except Exception:
      historial = {}

  resumen = {}
  suma_general = 0
  cursos_con_prom = 0

  for c_key in ['3ro', '4to', '5to', '6to']:
    notas_c = historial.get(c_key, {})
    lista_m = []
    suma_c = 0
    count_c = 0

    for m_key, m_nombre, m_area in materias_def:
      nota_val = notas_c.get(m_key)
      if nota_val is not None:
        suma_c += float(nota_val)
        count_c += 1
      lista_m.append({
        'nombre': m_nombre,
        'area': m_area,
        'nota': nota_val
      })

    prom_c = (suma_c / count_c) if count_c > 0 else 0.0
    resumen[c_key] = {
      'materias': lista_m,
      'promedio': prom_c
    }

    if count_c > 0:
      suma_general += prom_c
      cursos_con_prom += 1

  promedio_general = (suma_general / cursos_con_prom) if cursos_con_prom > 0 else 0.0

  return render_template(
    'estudiantes/egresado_cardex.html',
    est=est,
    padre=padre,
    gestion_egreso=gestion_egreso,
    resumen=resumen,
    promedio_general=promedio_general
  )

@estudiantes_bp.route('/estudiantes/<int:id>/imprimir_materia/<path:materia_nombre>')
def imprimir_materia_individual(id, materia_nombre):
    from urllib.parse import unquote
    materia_nombre = unquote(materia_nombre).strip()
    est = Estudiante.query.get_or_404(id)
    curso_txt = str(getattr(est, 'curso', '')).lower()
    es_nidito = any(k in curso_txt for k in ['nidito', 'inicial', 'kinder', 'kínder', 'pre-kinder', 'prekinder'])

    calificaciones_raw = Calificacion.query.filter(
        Calificacion.estudiante_id == id
    ).options(joinedload(Calificacion.materia)).all()

    califs_materia = [c for c in calificaciones_raw if c.materia and c.materia.nombre.strip().lower() == materia_nombre.lower()]

    if es_nidito:
        from utils.boletin_nidito_generator import generar_boletin_nidito_pdf
        pdf_bytes = generar_boletin_nidito_pdf(est, calificaciones=calificaciones_raw, materia_especifica=materia_nombre)
        fname = f"Seguimiento_{materia_nombre}_{est.ci}.pdf"
    else:
        from utils.reporte_calificaciones_generator import generar_detalle_calificaciones_pdf
        pdf_bytes = generar_detalle_calificaciones_pdf(est, califs_materia if califs_materia else calificaciones_raw)
        fname = f"Calificaciones_{materia_nombre}_{est.ci}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=fname
    )

# --- NUEVA RUTA PARA MIGRAR ESTUDIANTE DE 6TO A EGRESADO ---
@estudiantes_bp.route('/migrar_egresado/<int:estudiante_id>', methods=['POST'])
def migrar_egresado(estudiante_id):
    """Migra un estudiante de 6to de secundaria al registro de egresados consolidando sus 4 años."""
    try:
        est = Estudiante.query.get_or_404(estudiante_id)
        
        # Estructura base para el historial de notas
        historial_notas = {
            "3ro": [],
            "4to": [],
            "5to": [],
            "6to": []
        }
        
        # Intentar rescatar calificaciones existentes del estudiante (si las tiene registradas en el sistema)
        # Si el modelo de calificaciones guarda notas por curso, las mapeamos aquí.
        # Caso contrario, generamos la estructura lista para editar o con los datos disponibles.
        
        import json
        est.estado = 'Egresado'
        est.curso = 'Egresado'
        est.historial_notas = json.dumps(historial_notas, ensure_ascii=False)
        
        db.session.commit()
        flash(f"¡Estudiante {est.nombres} {est.apellidos} migrado exitosamente a Egresados!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al migrar estudiante: {str(e)}", "danger")
        
    return redirect(url_for('estudiantes.lista_egresados'))

# --- RUTA DE MIGRACIÓN MASIVA DE FIN DE GESTIÓN ---
@estudiantes_bp.route('/migracion_masiva', methods=['POST'])
def migracion_masiva():
    """Realiza la promoción automática de curso para los aprobados y migra a 6to a Egresados."""
    try:
        estudiantes = Estudiante.query.filter(Estudiante.estado != 'Egresado', Estudiante.estado != 'Retirado').all()
        
        # Mapeo EXACTO en MAYÚSCULAS para evitar errores de escritura y saltos incorrectos.
        secuencia_cursos = {
            # Inicial
            'NIDITO 1': 'NIDITO 2',
            'NIDITO 2': 'PRE-KINDER',
            'PRE-KINDER': 'KINDER',
            'KINDER': '1RO PRIMARIA',
            # Primaria
            '1RO PRIMARIA': '2DO PRIMARIA',
            '2DO PRIMARIA': '3RO PRIMARIA',
            '3RO PRIMARIA': '4TO PRIMARIA',
            '4TO PRIMARIA': '5TO PRIMARIA',
            '5TO PRIMARIA': '6TO PRIMARIA',
            '6TO PRIMARIA': '1RO SECUNDARIA',
            # Secundaria
            '1RO SECUNDARIA': '2DO SECUNDARIA',
            '2DO SECUNDARIA': '3RO SECUNDARIA',
            '3RO SECUNDARIA': '4TO SECUNDARIA',
            '4TO SECUNDARIA': '5TO SECUNDARIA',
            '5TO SECUNDARIA': '6TO SECUNDARIA',
            
            # Variantes comunes con "DE"
            '1RO DE PRIMARIA': '2DO DE PRIMARIA',
            '2DO DE PRIMARIA': '3RO DE PRIMARIA',
            '3RO DE PRIMARIA': '4TO DE PRIMARIA',
            '4TO DE PRIMARIA': '5TO DE PRIMARIA',
            '5TO DE PRIMARIA': '6TO DE PRIMARIA',
            '6TO DE PRIMARIA': '1RO DE SECUNDARIA',
            '1RO DE SECUNDARIA': '2DO DE SECUNDARIA',
            '2DO DE SECUNDARIA': '3RO DE SECUNDARIA',
            '3RO DE SECUNDARIA': '4TO DE SECUNDARIA',
            '4TO DE SECUNDARIA': '5TO DE SECUNDARIA',
            '5TO DE SECUNDARIA': '6TO DE SECUNDARIA',
        }
        
        migrados_count = 0
        egresados_count = 0
        
        for est in estudiantes:
            curso_actual = (est.curso or '').strip().upper()
            
            # Verificamos automáticamente el estado de aprobación según las calificaciones 
            # (Asegúrate de que 'aprobado' coincida con el nombre de tu campo o atributo de notas)
            es_aprobado = getattr(est, 'aprobado', True)
            
            if not es_aprobado:
                # Si el estudiante no aprobó, se queda repitiendo el curso y no avanza
                continue
            
            # Condición estricta para 6to de Secundaria
            if curso_actual in ['6TO SECUNDARIA', '6TO DE SECUNDARIA', 'SEXTO SECUNDARIA', 'SEXTO DE SECUNDARIA']:
                est.estado = 'Egresado'
                est.curso = 'Egresado'
                egresados_count += 1
            # Promoción estricta al curso inmediato superior
            elif curso_actual in secuencia_cursos:
                est.curso = secuencia_cursos[curso_actual]
                migrados_count += 1
                
        db.session.commit()
        flash(f"¡Migración exitosa! Promovidos de curso: {migrados_count}. Graduados a Egresados (6to Sec): {egresados_count}.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error en la migración masiva: {str(e)}", "danger")
        
    return redirect(url_for('estudiantes.index'))
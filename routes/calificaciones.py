# -*- coding: utf-8 -*-
# ==============================================================================
# Archivo: routes/calificaciones.py
# Proyecto: Sistema de Gestión Escolar - Colegio Dr. Antonio Vaca Díez
# Desarrollado por: Avrora Soft - Vibola LLC
# Descripción: Blueprint para gestión de Calificaciones, Libro de Notas,
#              Carga de Notas por Materia/Curso y Verificación de Boletines por QR
# ==============================================================================

import os
import io
import random
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify, abort
from models import db, Calificacion, Estudiante, Materia, Padre, Egresado, HistorialCalificacion
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone, timedelta
from routes.estudiantes import estudiantes_bp

# Configuración del Blueprint
calificaciones_bp = Blueprint('calificaciones', __name__, template_folder='templates/calificaciones')

# Zona horaria Bolivia (UTC-4)
BOLIVIA_TZ = timezone(timedelta(hours=-4))

def ahora_bolivia():
    """Devuelve la fecha/hora actual en zona horaria Bolivia (UTC-4)"""
    return datetime.now(BOLIVIA_TZ)

def actualizar_promedio_materia(estudiante_id, materia_id):
    """
    Calcula automáticamente el promedio de las notas regulares (bimestres/exámenes)
    de una materia y lo almacena/actualiza en la base de datos como tipo 'Promedio'.
    """
    try:
        cals = Calificacion.query.filter(
            Calificacion.estudiante_id == estudiante_id,
            Calificacion.materia_id == materia_id,
            Calificacion.tipo != 'Promedio'
        ).all()

        if not cals:
            return

        notas = [c.nota for c in cals if c.nota is not None]
        if not notas:
            return

        promedio_calculado = round(sum(notas) / len(notas), 2)

        cal_prom = Calificacion.query.filter_by(
            estudiante_id=estudiante_id,
            materia_id=materia_id,
            tipo='Promedio'
        ).first()

        if cal_prom:
            cal_prom.nota = promedio_calculado
            cal_prom.fecha = ahora_bolivia()
        else:
            nuevo_prom = Calificacion(
                estudiante_id=estudiante_id,
                materia_id=materia_id,
                tipo='Promedio',
                nota=promedio_calculado,
                fecha=ahora_bolivia()
            )
            db.session.add(nuevo_prom)
            
        db.session.flush()
    except Exception as e:
        print(f"Error al calcular promedio automático para materia {materia_id}: {e}")

# =========================================================================
# LIBRO DE NOTAS (Vista principal por curso - Lógica Independiente por Fila)
# =========================================================================
@calificaciones_bp.route('/libro')
def libro_notas():
    """Muestra el libro de notas por curso permitiendo la convivencia de alumnos con y sin notas."""
    curso_seleccionado = request.args.get('curso', '')
    gestion = request.args.get('gestion', ahora_bolivia().year, type=int)
    tipo_evaluacion = request.args.get('tipo', '')

    cursos = db.session.query(Estudiante.curso).filter_by(estado='Activo').distinct().order_by(Estudiante.curso).all()
    cursos = [c[0] for c in cursos]

    estudiantes = []
    materias = []
    calificaciones_dict = {}

    if curso_seleccionado:
        # 1. Traemos TODOS los estudiantes activos del curso de forma independiente
        estudiantes = Estudiante.query.filter_by(
            curso=curso_seleccionado, estado='Activo'
        ).order_by(Estudiante.apellidos, Estudiante.nombres).all()

        # 2. Traemos las materias correspondientes al curso
        materias = Materia.query.filter_by(curso_id=curso_seleccionado).order_by(Materia.nombre).all()
        if not materias:
            materias = Materia.query.order_by(Materia.nombre).all()

        estudiante_ids = [e.id for e in estudiantes]
        if estudiante_ids:
            # 3. Consultamos las notas de los alumnos que SÍ tienen registros, sin excluir a los demás
            query_cal = Calificacion.query.filter(
                Calificacion.estudiante_id.in_(estudiante_ids)
            ).options(joinedload(Calificacion.materia))

            if tipo_evaluacion:
                query_cal = query_cal.filter(Calificacion.tipo == tipo_evaluacion)

            calificaciones = query_cal.all()

            # 4. Agrupamos en un diccionario por estudiante y materia de forma aislada
            for cal in calificaciones:
                if cal.estudiante_id not in calificaciones_dict:
                    calificaciones_dict[cal.estudiante_id] = {}
                if cal.materia_id not in calificaciones_dict[cal.estudiante_id]:
                    calificaciones_dict[cal.estudiante_id][cal.materia_id] = []
                calificaciones_dict[cal.estudiante_id][cal.materia_id].append(cal)

    tipos_evaluacion = ['Parcial 1', 'Parcial 2', 'Parcial 3', 'Examen Final', 'Promedio']

    return render_template('calificaciones/libro.html',
                           cursos=cursos,
                           curso_seleccionado=curso_seleccionado,
                           gestion=gestion,
                           estudiantes=estudiantes,
                           materias=materias,
                           calificaciones_dict=calificaciones_dict,
                           tipos_evaluacion=tipos_evaluacion,
                           tipo_actual=tipo_evaluacion)

@calificaciones_bp.route('/cargar_notas/<int:materia_id>', methods=['GET', 'POST'])
def cargar_notas(materia_id):
    """Permite ingresar y actualizar notas basadas en los criterios dinámicos de forma 100% parcial y flexible."""
    materia = Materia.query.get_or_404(materia_id)
    curso = request.args.get('curso', '') or request.form.get('curso', '')

    estudiantes = Estudiante.query.filter_by(
        curso=curso, estado='Activo'
    ).order_by(Estudiante.apellidos, Estudiante.nombres).all()

    # Obtenemos los criterios dinámicos para esta materia
    from routes.profesores_portal import obtener_criterios_materia
    criterios, origen, es_nidito, nivel = obtener_criterios_materia(materia_id)

    if request.method == 'POST':
        try:
            guardados_count = 0
            for est in estudiantes:
                for crit in criterios:
                    nombre_campo = f"criterio_{est.id}_{crit.id}"
                    nota_str = request.form.get(nombre_campo, '').strip()

                    # Si el usuario dejó el campo vacío, permitimos que se quede vacío o limpiamos si ya no aplica,
                    # pero NUNCA tocamos ni borramos los demás registros de sus compañeros.
                    if not nota_str:
                        continue

                    try:
                        if crit.tipo_evaluacion == 'NUMERICA':
                            valor = float(nota_str)
                            if 0 <= valor <= crit.puntaje_maximo:
                                cal_existente = Calificacion.query.filter_by(
                                    estudiante_id=est.id,
                                    materia_id=materia.id,
                                    tipo=crit.nombre
                                ).first()

                                if cal_existente:
                                    cal_existente.nota = valor
                                    cal_existente.fecha = ahora_bolivia()
                                else:
                                    nueva_cal = Calificacion(
                                        estudiante_id=est.id,
                                        materia_id=materia.id,
                                        tipo=crit.nombre,
                                        nota=valor,
                                        fecha=ahora_bolivia()
                                    )
                                    db.session.add(nueva_cal)
                                guardados_count += 1
                        elif crit.tipo_evaluacion == 'CUALITATIVA':
                            cal_existente = Calificacion.query.filter_by(
                                estudiante_id=est.id,
                                materia_id=materia.id,
                                tipo=crit.nombre
                            ).first()

                            if cal_existente:
                                cal_existente.observacion = nota_str
                                cal_existente.fecha = ahora_bolivia()
                            else:
                                nueva_cal = Calificacion(
                                    estudiante_id=est.id,
                                    materia_id=materia.id,
                                    tipo=crit.nombre,
                                    observacion=nota_str,
                                    fecha=ahora_bolivia()
                                )
                                db.session.add(nueva_cal)
                            guardados_count += 1
                    except ValueError:
                        pass

            db.session.flush()

            # Recalculamos los promedios y totales de los estudiantes
            for est in estudiantes:
                actualizar_promedio_materia(est.id, materia.id)

            db.session.commit()
            if guardados_count > 0:
                flash(f'✅ Se guardaron {guardados_count} registros correctamente', 'success')
            else:
                flash('ℹ️ No se detectaron cambios nuevos para guardar.', 'info')
                
            return redirect(url_for('calificaciones.cargar_notas', materia_id=materia_id, curso=curso))

        except Exception as e:
            db.session.rollback()
            print(f"Error al guardar notas por criterios: {e}")
            flash(f'❌ Error al guardar las calificaciones: {str(e)}', 'danger')

    # Diccionario adaptado para emparejar exactamente con el ID del criterio en la vista
    promedios = {}
    notas_dict = {}
    for est in estudiantes:
        cals = Calificacion.query.filter(
            Calificacion.estudiante_id == est.id,
            Calificacion.materia_id == materia.id
        ).all()
        
        # Mapeamos usando el nombre del criterio para que la interfaz lo recupere perfecto
        notas_dict[est.id] = {c.tipo: (c.nota if c.nota is not None else c.observacion) for c in cals}
        
        notas_validas = [c.nota for c in cals if c.tipo != 'Promedio' and c.nota is not None]
        if notas_validas:
            promedios[est.id] = round(sum(notas_validas), 2)
        else:
            promedios[est.id] = 0.0

    return render_template('calificaciones/cargar_notas.html',
                           materia=materia,
                           curso=curso,
                           estudiantes=estudiantes,
                           criterios=criterios,
                           promedios=promedios,
                           notas_dict=notas_dict)

# =========================================================================
# REGISTRAR / ACTUALIZAR CALIFICACIÓN INDIVIDUAL (Versión Flexible)
# =========================================================================
@calificaciones_bp.route('/registrar', methods=['POST'])
def registrar_calificacion():
    """Registra, actualiza o limpia una calificación individual de forma flexible."""
    try:
        estudiante_id = int(request.form.get('estudiante_id'))
        materia_id = int(request.form.get('materia_id'))
        tipo = request.form.get('tipo', 'Parcial 1')
        nota_str = request.form.get('nota', '').strip()

        # Si mandan el campo vacío, podemos optar por eliminar el registro o ignorarlo
        if not nota_str:
            cal_existente = Calificacion.query.filter_by(
                estudiante_id=estudiante_id,
                materia_id=materia_id,
                tipo=tipo
            ).first()
            if cal_existente:
                db.session.delete(cal_existente)
                db.session.flush()
                actualizar_promedio_materia(estudiante_id, materia_id)
                db.session.commit()
                flash('ℹ️ Calificación retirada correctamente', 'info')
            return redirect(url_for('calificaciones.libro_notas', curso=request.form.get('curso', '')))

        try:
            nota = float(nota_str)
        except ValueError:
            flash('❌ La nota ingresada no es válida', 'danger')
            return redirect(url_for('calificaciones.libro_notas', curso=request.form.get('curso', '')))

        if nota < 0 or nota > 100:
            flash('❌ La nota debe estar entre 0 y 100', 'danger')
            return redirect(url_for('calificaciones.libro_notas', curso=request.form.get('curso', '')))

        cal_existente = Calificacion.query.filter_by(
            estudiante_id=estudiante_id,
            materia_id=materia_id,
            tipo=tipo
        ).first()

        if cal_existente:
            cal_existente.nota = nota
            cal_existente.fecha = ahora_bolivia()
            flash('✅ Calificación actualizada correctamente', 'success')
        else:
            nueva_cal = Calificacion(
                estudiante_id=estudiante_id,
                materia_id=materia_id,
                tipo=tipo,
                nota=nota,
                fecha=ahora_bolivia()
            )
            db.session.add(nueva_cal)
            flash('✅ Calificación registrada correctamente', 'success')

        db.session.flush()

        if tipo != 'Promedio':
            actualizar_promedio_materia(estudiante_id, materia_id)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"Error al registrar calificación: {e}")
        flash(f'❌ Error al registrar calificación: {str(e)}', 'danger')

    return redirect(url_for('calificaciones.libro_notas',
                            curso=request.form.get('curso', '')))

# =========================================================================
# REGISTRO MASIVO DE CALIFICACIONES
# =========================================================================
@calificaciones_bp.route('/registrar_masivo', methods=['POST'])
def registrar_masivo():
    """Registra calificaciones de forma masiva y recalcula promedios afectados."""
    try:
        curso = request.form.get('curso', '')
        tipo = request.form.get('tipo', 'Parcial 1')
        count = 0
        parejas_afectadas = set()

        for key, value in request.form.items():
            if key.startswith('nota_'):
                partes = key.split('_')
                if len(partes) == 3:
                    try:
                        estudiante_id = int(partes[1])
                        materia_id = int(partes[2])
                        nota = float(value) if value else 0.0

                        if nota < 0 or nota > 100:
                            continue

                        cal_existente = Calificacion.query.filter_by(
                            estudiante_id=estudiante_id,
                            materia_id=materia_id,
                            tipo=tipo
                        ).first()

                        if cal_existente:
                            cal_existente.nota = nota
                            cal_existente.fecha = ahora_bolivia()
                        else:
                            nueva_cal = Calificacion(
                                estudiante_id=estudiante_id,
                                materia_id=materia_id,
                                tipo=tipo,
                                nota=nota,
                                fecha=ahora_bolivia()
                            )
                            db.session.add(nueva_cal)
                        
                        parejas_afectadas.add((estudiante_id, materia_id))
                        count += 1
                    except (ValueError, IndexError):
                        continue

        db.session.flush()

        if tipo != 'Promedio':
            for est_id, mat_id in parejas_afectadas:
                actualizar_promedio_materia(est_id, mat_id)

        db.session.commit()
        flash(f'✅ {count} calificaciones registradas/actualizadas correctamente y promedios recalculados', 'success')

    except Exception as e:
        db.session.rollback()
        print(f"Error en registro masivo: {e}")
        flash(f'❌ Error al registrar calificaciones: {str(e)}', 'danger')

    return redirect(url_for('calificaciones.libro_notas', curso=curso))

# =========================================================================
# ELIMINAR CALIFICACIÓN
# =========================================================================
@calificaciones_bp.route('/eliminar/<int:id>', methods=['POST'])
def eliminar_calificacion(id):
    """Elimina una calificación específica y actualiza su promedio."""
    try:
        cal = Calificacion.query.get_or_404(id)
        estudiante_id = cal.estudiante_id
        materia_id = cal.materia_id
        tipo = cal.tipo
        curso = request.form.get('curso', '')

        db.session.delete(cal)
        db.session.flush()

        if tipo != 'Promedio':
            actualizar_promedio_materia(estudiante_id, materia_id)

        db.session.commit()
        flash('✅ Calificación eliminada y promedio recalculado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
        curso = ''

    return redirect(url_for('calificaciones.libro_notas', curso=curso))

# =========================================================================
# REPORTE DE CALIFICACIONES POR ESTUDIANTE
# =========================================================================
@calificaciones_bp.route('/reporte/<int:estudiante_id>')
def reporte_estudiante(estudiante_id):
    """Muestra el reporte completo de calificaciones y sus promedios por materia."""
    estudiante = Estudiante.query.get_or_404(estudiante_id)
    # Ordenamiento correcto por materia, fecha (trimestre) y secuencia logica de evaluacion
    from sqlalchemy import case
    orden_tipo = case(
        (Calificacion.tipo == 'P1', 1),
        (Calificacion.tipo == 'P2', 2),
        (Calificacion.tipo == 'P3', 3),
        (Calificacion.tipo == 'E1', 4),
        (Calificacion.tipo == 'EF', 5),
        (Calificacion.tipo == 'NF', 6),
        else_=99
    )
    calificaciones = Calificacion.query.filter_by(
        estudiante_id=estudiante_id
    ).options(joinedload(Calificacion.materia)).order_by(
        Calificacion.materia_id, Calificacion.fecha, orden_tipo
    ).all()

    materias_notas = {}
    for cal in calificaciones:
        mat_nombre = cal.materia.nombre if cal.materia else 'Materia Eliminada'
        if mat_nombre not in materias_notas:
            materias_notas[mat_nombre] = []
        materias_notas[mat_nombre].append(cal)

    promedios = {}
    for mat_nombre, cals in materias_notas.items():
        prom_obj = next((c for c in cals if c.tipo == 'Promedio'), None)
        if prom_obj:
            promedios[mat_nombre] = prom_obj.nota
        else:
            notas_reg = [c.nota for c in cals if c.tipo != 'Promedio' and c.nota is not None]
            promedios[mat_nombre] = sum(notas_reg) / len(notas_reg) if notas_reg else 0

    promedio_general = sum(promedios.values()) / len(promedios) if promedios else 0

    return render_template('calificaciones/reporte.html',
                           estudiante=estudiante,
                           materias_notas=materias_notas,
                           promedios=promedios,
                           promedio_general=promedio_general)

# =========================================================================
# API: OBTENER ESTUDIANTES POR CURSO
# =========================================================================
@calificaciones_bp.route('/api/estudiantes_por_curso')
def api_estudiantes_por_curso():
    """API para obtener estudiantes de un curso específico."""
    curso = request.args.get('curso', '')
    if not curso:
        return jsonify({'results': []})

    estudiantes = Estudiante.query.filter_by(
        curso=curso, estado='Activo'
    ).order_by(Estudiante.apellidos).all()

    data = [{
        'id': e.id,
        'rude': e.rude,
        'nombre': f"{e.apellidos}, {e.nombres}",
        'curso': e.curso
    } for e in estudiantes]

    return jsonify({'results': data})

# =========================================================================
# API: OBTENER MATERIAS POR CURSO
# =========================================================================
@calificaciones_bp.route('/api/materias_por_curso')
def api_materias_por_curso():
    """API para obtener materias de un curso específico."""
    curso = request.args.get('curso', '')
    if not curso:
        return jsonify({'results': []})

    materias = Materia.query.filter_by(curso_id=curso).order_by(Materia.nombre).all()

    if not materias:
        materias = Materia.query.order_by(Materia.nombre).all()

    data = [{
        'id': m.id,
        'nombre': m.nombre,
        'curso_id': m.curso_id
    } for m in materias]

    return jsonify({'results': data})

# =========================================================================
# VERIFICACIÓN DE BOLETÍN POR QR (Ruta Pública - Solo C.I.)
# =========================================================================
@calificaciones_bp.route('/verificar-boletin')
def verificar_boletin():
    """Ruta pública para verificar la autenticidad de un boletín escaneando el QR usando C.I."""
    ci = request.args.get('ci')
    anio = request.args.get('anio', type=int)

    if not ci or not anio:
        return render_template('calificaciones/verificacion_error.html',
                               mensaje="Parámetros de verificación inválidos. "
                                       "Se requiere C.I. y año de gestión."), 400

    estudiante = Estudiante.query.filter_by(ci=ci).first()

    if not estudiante:
        egresado = Egresado.query.filter_by(ci=ci).first()
        if egresado:
            estudiante_id = egresado.estudiante_id_original
            nombre_estudiante = f"{egresado.apellidos}, {egresado.nombres}"
        else:
            return render_template('calificaciones/verificacion_error.html',
                                   mensaje=f"No se encontró ningún estudiante con C.I. {ci} "
                                           f"en los registros del colegio."), 404
    else:
        estudiante_id = estudiante.id
        nombre_estudiante = f"{estudiante.apellidos}, {estudiante.nombres}"

    # Buscar el archivo PDF exacto con la estructura con la que se genera: boletin_id_año_ci.pdf
    nombre_archivo = f"boletin_{estudiante_id}_{anio}_{ci}.pdf"
    filepath = os.path.join(os.getcwd(), 'static', 'boletines', nombre_archivo)

    if not os.path.exists(filepath):
        return render_template('calificaciones/verificacion_error.html',
                               mensaje=f"El boletín del estudiante {nombre_estudiante} "
                                       f"(C.I.: {ci}) para la gestión {anio} "
                                       f"aún no ha sido generado o no se encuentra disponible."), 404

    return send_file(
        filepath,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"Boletin_Verificado_{ci}_{anio}.pdf"
    )

# =========================================================================
# VERIFICACIÓN MANUAL DE BOLETÍN
# =========================================================================
@calificaciones_bp.route('/verificar')
def verificar_manual():
    """Página para verificar boletines manualmente ingresando RUDE y año."""
    rude = request.args.get('rude', '', type=str)
    anio = request.args.get('anio', '', type=str)
    resultado = None
    error = None

    if rude and anio:
        try:
            rude_int = int(rude)
            anio_int = int(anio)

            estudiante = Estudiante.query.filter_by(rude=rude_int).first()
            if not estudiante:
                egresado = Egresado.query.filter_by(rude=rude_int).first()
                if egresado:
                    estudiante_id = egresado.estudiante_id_original
                    nombre = f"{egresado.apellidos}, {egresado.nombres}"
                    curso = egresado.curso_final
                else:
                    error = f"No se encontró estudiante con RUDE {rude_int}"
            else:
                estudiante_id = estudiante.id
                nombre = f"{estudiante.apellidos}, {estudiante.nombres}"
                curso = estudiante.curso

            if not error:
                nombre_archivo = f"boletin_{estudiante_id}_{anio_int}_{rude_int}.pdf"
                filepath = os.path.join(os.getcwd(), 'static', 'boletines', nombre_archivo)

                if os.path.exists(filepath):
                    resultado = {
                        'nombre': nombre,
                        'rude': rude_int,
                        'curso': curso,
                        'anio': anio_int,
                        'archivo': nombre_archivo,
                        'estado': 'VÁLIDO',
                        'fecha_verificacion': ahora_bolivia().strftime('%d/%m/%Y %H:%M:%S')
                    }
                else:
                    error = f"El boletín para la gestión {anio_int} no ha sido generado aún."

        except ValueError:
            error = "El RUDE y el año deben ser números válidos."

    return render_template('calificaciones/verificar.html',
                           resultado=resultado,
                           error=error,
                           rude=rude,
                           anio=anio,
                           anio_actual=ahora_bolivia().year)



# =========================================================================
# GENERAR BOLETINES MASIVOS POR CURSO
# =========================================================================
@calificaciones_bp.route('/generar_boletines_curso/<curso>')
def generar_boletines_curso(curso):
    """Genera boletines PDF para todos los estudiantes de un curso."""
    try:
        from utils.boletin_generator import generar_boletin_pdf

        estudiantes = Estudiante.query.filter_by(
            curso=curso, estado='Activo'
        ).order_by(Estudiante.apellidos).all()
        materias = Materia.query.all()

        try:
            tunnel_url = current_app.config.get('TUNNEL_URL', '')
            if not tunnel_url:
                tunnel_url = request.host_url.rstrip('/')
        except:
            tunnel_url = 'http://localhost:5000'

        boletines_dir = os.path.join(os.getcwd(), 'static', 'boletines')
        os.makedirs(boletines_dir, exist_ok=True)

        count = 0
        errores = []

        for est in estudiantes:
            calificaciones = Calificacion.query.filter_by(estudiante_id=est.id).all()
            if not calificaciones:
                errores.append(f"{est.apellidos}, {est.nombres} (sin calificaciones)")
                continue

            try:
                url_verificacion = f"{tunnel_url}/calificaciones/verificar-boletin?rude={est.rude}&anio={ahora_bolivia().year}"

                bytes_pdf = generar_boletin_pdf(
                    est, calificaciones, materias, cloudinary_url=url_verificacion
                )

                filename = f"boletin_{est.id}_{ahora_bolivia().year}_{est.rude}.pdf"
                filepath = os.path.join(boletines_dir, filename)

                with open(filepath, 'wb') as f:
                    f.write(bytes_pdf)

                count += 1

            except Exception as e:
                errores.append(f"{est.apellidos}, {est.nombres}: {str(e)}")

        if count > 0:
            flash(f'✅ {count} boletines generados exitosamente para el curso {curso}', 'success')
        if errores:
            flash(f'⚠️ {len(errores)} boletines no pudieron generarse. Revise el log.', 'warning')

    except Exception as e:
        print(f"Error en generación masiva: {e}")
        flash(f'❌ Error: {str(e)}', 'danger')

    return redirect(url_for('calificaciones.libro_notas', curso=curso))

# =========================================================================
# NORMALIZACIÓN Y LLENADO ALEATORIO DE PRUEBA
# =========================================================================
@calificaciones_bp.route('/normalizar_base', methods=['GET'])
def normalizar_base_datos():
    """
    Limpia y rellena la base de datos con notas variadas y aleatorias 
    para cada estudiante, materia y evaluación, calculando sus promedios reales.
    """
    try:
        estudiantes = Estudiante.query.filter_by(estado='Activo').all()
        
        Calificacion.query.delete()
        db.session.commit()

        tipos_eval = ['Parcial 1', 'Parcial 2', 'Parcial 3', 'Examen Final']
        contador = 0

        for est in estudiantes:
            materias = Materia.query.filter_by(curso_id=est.curso).all()
            if not materias:
                materias = Materia.query.all()

            for mat in materias:
                notas_materia = []
                for tipo in tipos_eval:
                    # Generar una nota aleatoria independiente y realista entre 45 y 98
                    nota_valor = float(random.randint(45, 98))
                    
                    nueva_cal = Calificacion(
                        estudiante_id=est.id,
                        materia_id=mat.id,
                        tipo=tipo,
                        nota=nota_valor,
                        fecha=ahora_bolivia()
                    )
                    db.session.add(nueva_cal)
                    notas_materia.append(nota_valor)
                    contador += 1

                # Calcular y guardar el promedio independiente para esta materia y estudiante
                if notas_materia:
                    promedio_mat = round(sum(notas_materia) / len(notas_materia), 2)
                    cal_prom = Calificacion(
                        estudiante_id=est.id,
                        materia_id=mat.id,
                        tipo='Promedio',
                        nota=promedio_mat,
                        fecha=ahora_bolivia()
                    )
                    db.session.add(cal_prom)

        db.session.commit()
        flash(f'Base de datos normalizada con éxito. Se generaron {contador} registros con notas variadas por alumno y materia.', 'success')
        return redirect(url_for('calificaciones.libro_notas'))

    except Exception as e:
        db.session.rollback()
        return f"Error al normalizar la base de datos: {str(e)}", 500
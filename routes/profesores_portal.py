# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/profesores_portal.py
Proyecto: ASestud-Konetz - Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Portal docente integral:
             - Motor de precedencia de rúbricas (específica y general).
             - Control financiero con distinción entre sueldos íntegros y adelantos.
             - Gestión de tareas y seguimiento para la Pizarra Escolar.
             - Módulo de asistencia y galería de respaldos documentales.
==============================================================================
"""

import os
import json
from functools import wraps
from datetime import datetime, date

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, abort, current_app, send_from_directory
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

# Modelos centralizados del sistema (incluyendo Falta para asistencia unificada)
from models import (
    db, Profesor, Materia, Estudiante, Calificacion,
    CriterioEvaluacion, nivel_de_curso, Pago, PagoPersonal,
    Tarea, EntregaTarea, Falta
)

# Importación segura de RespaldoEstudiante si existe en models
try:
    from models import RespaldoEstudiante
except ImportError:
    RespaldoEstudiante = None

# Importación segura de comunicados
try:
    from routes.admin_profesores_chat import MensajeProfesor
except ImportError:
    try:
        from models import MensajeProfesor
    except ImportError:
        class MensajeProfesor(db.Model):
            __tablename__ = 'mensajes_profesores'
            __table_args__ = {'extend_existing': True}
            id = db.Column(db.Integer, primary_key=True)
            asunto = db.Column(db.String(150), nullable=False)
            contenido = db.Column(db.Text, nullable=False)
            tipo = db.Column(db.String(20), default='privado')
            profesor_id = db.Column(db.Integer, db.ForeignKey('profesores.id'), nullable=True)
            fecha_envio = db.Column(db.DateTime, default=datetime.now)

# Modelo seguro de asistencia (respaldo si fuera necesario)
try:
    from models import AsistenciaEstudiante
except ImportError:
    class AsistenciaEstudiante(db.Model):
        __tablename__ = 'asistencias_estudiantes'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.Integer, primary_key=True)
        estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
        materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=False)
        fecha = db.Column(db.Date, nullable=False)
        estado = db.Column(db.String(20), default='Presente')

profesores_portal_bp = Blueprint(
    'profesores_portal',
    __name__
)

# Carpeta independiente para los respaldos documentales y fotográficos de los profesores
UPLOAD_FOLDER_RESPALDOS = 'static/uploads/respaldos_docentes'

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'profesor_id' not in session:
            flash('Debe iniciar sesión para acceder al portal.', 'danger')
            return redirect(url_for('profesores_portal.login'))
        return f(*args, **kwargs)
    return decorated_function


def obtener_criterios_materia(materia_id):
    """
    Motor de precedencia de evaluación institucional:
    - Nivel 1: Criterios específicos asignados directamente a la materia.
    - Nivel 2: Criterios generales configurados para el nivel.
    """
    materia = Materia.query.get(materia_id)
    if not materia:
        return [], 'general', False, 'Primaria'

    nivel = nivel_de_curso(materia.curso_id)
    if not nivel:
        c_low = (materia.curso_id or '').lower()
        if 'nidito' in c_low:
            nivel = 'Nidito'
        elif 'secundaria' in c_low:
            nivel = 'Secundaria'
        else:
            nivel = 'Primaria'

    criterios_especificos = CriterioEvaluacion.query.filter_by(
        materia_id=materia_id,
        activo=True
    ).order_by(CriterioEvaluacion.orden.asc()).all()

    if criterios_especificos:
        origen = 'especifico'
        criterios = criterios_especificos
    else:
        origen = 'general'
        criterios = CriterioEvaluacion.query.filter_by(
            nivel=nivel,
            materia_id=None,
            activo=True
        ).order_by(CriterioEvaluacion.orden.asc()).all()

        if not criterios:
            if nivel == 'Nidito':
                base = [
                    CriterioEvaluacion(nombre='Desarrollo Psicomotriz', nivel='Nidito', tipo_evaluacion='CUALITATIVA', opciones_cualitativas='Logrado,En Proceso,En Inicio', es_descriptivo=False, orden=1, activo=True),
                    CriterioEvaluacion(nombre='Lenguaje y Comunicación', nivel='Nidito', tipo_evaluacion='CUALITATIVA', opciones_cualitativas='Logrado,En Proceso,En Inicio', es_descriptivo=False, orden=2, activo=True),
                    CriterioEvaluacion(nombre='Autonomía y Convivencia', nivel='Nidito', tipo_evaluacion='CUALITATIVA', opciones_cualitativas='Logrado,En Proceso,En Inicio', es_descriptivo=False, orden=3, activo=True),
                    CriterioEvaluacion(nombre='Informe Pedagógico y Recomendaciones', nivel='Nidito', tipo_evaluacion='CUALITATIVA', opciones_cualitativas=None, es_descriptivo=True, orden=4, activo=True)
                ]
            else:
                base = [
                    CriterioEvaluacion(nombre='Asistencia', nivel=nivel, tipo_evaluacion='NUMERICA', puntaje_maximo=10, permite_decimales=False, paso_step=1.0, orden=1, activo=True),
                    CriterioEvaluacion(nombre='Participación / Exposición', nivel=nivel, tipo_evaluacion='NUMERICA', puntaje_maximo=20, permite_decimales=False, paso_step=1.0, orden=2, activo=True),
                    CriterioEvaluacion(nombre='Evaluaciones y Trabajos', nivel=nivel, tipo_evaluacion='NUMERICA', puntaje_maximo=70, permite_decimales=True, paso_step=0.5, orden=3, activo=True)
                ]
            db.session.add_all(base)
            db.session.commit()
            criterios = CriterioEvaluacion.query.filter_by(nivel=nivel, materia_id=None, activo=True).order_by(CriterioEvaluacion.orden.asc()).all()

    es_nidito = (nivel == 'Nidito') or all(c.tipo_evaluacion == 'CUALITATIVA' for c in criterios)
    return criterios, origen, es_nidito, nivel


def recalcular_nota_final(materia_id, periodo='1er Trimestre'):
    """
    Calcula la sumatoria sobre 100 puntos y genera el desglose JSON.
    Se omite en régimen cualitativo.
    """
    criterios, origen, es_nidito, nivel = obtener_criterios_materia(materia_id)
    if es_nidito:
        return

    materia = Materia.query.get(materia_id)
    if not materia:
        return

    if materia.curso_id == 'Nidito':
        estudiantes = Estudiante.query.filter(
            Estudiante.curso.in_(['Nidito 1', 'Nidito 2']),
            Estudiante.estado == 'Activo'
        ).all()
    else:
        estudiantes = Estudiante.query.filter_by(curso=materia.curso_id, estado='Activo').all()

    nombres_criterios = [c.nombre for c in criterios if c.tipo_evaluacion == 'NUMERICA']

    for est in estudiantes:
        notas_criterios = Calificacion.query.filter(
            Calificacion.estudiante_id == est.id,
            Calificacion.materia_id == materia_id,
            Calificacion.periodo == periodo,
            Calificacion.tipo.in_(nombres_criterios)
        ).all()

        desglose = {}
        total = 0.0
        for cal in notas_criterios:
            val = float(cal.nota or 0.0)
            desglose[cal.tipo] = val
            total += val

        total = min(100.0, max(0.0, total))

        cal_final = Calificacion.query.filter_by(
            estudiante_id=est.id,
            materia_id=materia_id,
            periodo=periodo,
            tipo='Nota Final'
        ).first()

        if cal_final:
            cal_final.nota = round(total, 1)
            cal_final.desglose_json = json.dumps(desglose, ensure_ascii=False)
            cal_final.fecha = datetime.now().date()
        else:
            nueva_final = Calificacion(
                estudiante_id=est.id,
                ci_estudiante=est.ci,
                rude_estudiante=est.rude,
                materia_id=materia_id,
                periodo=periodo,
                tipo='Nota Final',
                nota=round(total, 1),
                desglose_json=json.dumps(desglose, ensure_ascii=False),
                fecha=datetime.now().date()
            )
            db.session.add(nueva_final)

    db.session.commit()


# =========================================================================
# RUTAS DEL PORTAL DOCENTE
# =========================================================================

@profesores_portal_bp.route('/')
@login_requerido
def index():
    profesor_id = int(session['profesor_id'])
    profesor = Profesor.query.get(profesor_id)
    mis_materias = Materia.query.filter_by(profesor_id=profesor_id).all()

    try:
        mensajes_recibidos = MensajeProfesor.query.filter(
            (MensajeProfesor.profesor_id == profesor_id) | (MensajeProfesor.tipo == 'general')
        ).order_by(MensajeProfesor.fecha_envio.desc()).limit(10).all()
    except Exception:
        mensajes_recibidos = []

    cursos_set = {m.curso_id for m in mis_materias if m.curso_id}

    return render_template(
        ['profesores_portal/index.html', 'index.html'],
        profesor=profesor,
        materias=mis_materias,
        mensajes_recibidos=mensajes_recibidos,
        total_materias=len(mis_materias),
        total_cursos=len(cursos_set)
    )


@profesores_portal_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        contrasena = request.form.get('contrasena', '').strip()
        profesor = Profesor.query.filter_by(usuario=usuario, estado='Activo').first()

        if profesor and check_password_hash(profesor.contrasena_hash, contrasena):
            session['profesor_id'] = profesor.id
            session['profesor_nombre'] = f"{profesor.apellidos}, {profesor.nombres}"
            flash(f"Bienvenido/a Prof. {profesor.nombres}", 'success')
            return redirect(url_for('profesores_portal.index'))
        flash('Credenciales incorrectas.', 'danger')
    return render_template(['profesores_portal/login.html', 'login.html'])


@profesores_portal_bp.route('/logout')
def logout():
    session.pop('profesor_id', None)
    session.pop('profesor_nombre', None)
    return redirect(url_for('profesores_portal.login'))


# --- HISTORIAL FINANCIERO: DISTINCIÓN ENTRE SUELDO CANCELADO Y RETENCIONES ---
@profesores_portal_bp.route('/mis-pagos')
@login_requerido
def mis_pagos():
    profesor_id = int(session['profesor_id'])
    profesor = Profesor.query.get_or_404(profesor_id)

    meses_disponibles = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre', 'Todos'
    ]

    mes_actual = datetime.now().strftime('%B')
    traduccion_meses = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
        'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
        'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
        'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }
    mes_por_defecto = traduccion_meses.get(mes_actual, 'Septiembre')
    mes_filtro = request.args.get('mes', mes_por_defecto).strip()
    anio_filtro = datetime.now().year

    # Traer todos los pagos del profesor
    query = PagoPersonal.query.filter(
        (PagoPersonal.persona_id == profesor.id) | 
        (PagoPersonal.ci_persona == profesor.ci)
    )

    if mes_filtro and mes_filtro.lower() != 'todos':
        query = query.filter(db.func.trim(db.func.lower(PagoPersonal.mes)) == mes_filtro.lower())

    pagos_lista = query.order_by(PagoPersonal.fecha_pago.desc(), PagoPersonal.id.desc()).all()

    sueldo_base = float(profesor.salario_base or 0.0)

    items_procesados = []
    total_sueldos_pagados = 0.0
    total_retenciones = 0.0

    for p in pagos_lista:
        monto = float(p.monto_neto_pagado or p.monto_adelanto or 0.0)
        es_sueldo_completo = (sueldo_base > 0 and monto >= sueldo_base) or ('sueldo' in (p.motivo or '').lower() and monto >= sueldo_base)
        
        if es_sueldo_completo:
            tipo_movimiento = 'Sueldo Íntegro Cancelado'
            total_sueldos_pagados += monto
        else:
            tipo_movimiento = 'Retención / Adelanto Parcial'
            total_retenciones += monto

        items_procesados.append({
            'registro': p,
            'monto': monto,
            'es_sueldo': es_sueldo_completo,
            'tipo_movimiento': tipo_movimiento
        })

    if mes_filtro.lower() != 'todos':
        if total_sueldos_pagados >= sueldo_base and sueldo_base > 0:
            estado_mes = 'PAGADO_TOTAL'
            saldo_pendiente = 0.0
        elif total_retenciones > 0:
            estado_mes = 'CON_RETENCION'
            saldo_pendiente = max(0.0, sueldo_base - total_retenciones)
        else:
            estado_mes = 'PENDIENTE'
            saldo_pendiente = sueldo_base
    else:
        estado_mes = 'HISTORICO_GLOBAL'
        saldo_pendiente = float(getattr(profesor, 'salario_neto', 0.0) or (sueldo_base - float(profesor.adelanto or 0.0)))

    return render_template(
        ['profesores_portal/mis_pagos.html', 'mis_pagos.html'],
        profesor=profesor,
        items=items_procesados,
        mes_filtro=mes_filtro,
        anio_filtro=anio_filtro,
        meses_disponibles=meses_disponibles,
        total_sueldos_pagados=total_sueldos_pagados,
        total_retenciones=total_retenciones,
        sueldo_base=sueldo_base,
        saldo_pendiente=saldo_pendiente,
        estado_mes=estado_mes
    )


# --- LISTA DE ALUMNOS MOROSOS ---
@profesores_portal_bp.route('/alumnos-morosos')
@login_requerido
def alumnos_morosos():
    profesor_id = int(session['profesor_id'])
    profesor = Profesor.query.get_or_404(profesor_id)
    mis_materias = Materia.query.filter_by(profesor_id=profesor_id).all()

    cursos_docente = list({m.curso_id.strip() for m in mis_materias if m.curso_id})

    cursos_busqueda = []
    for c in cursos_docente:
        cursos_busqueda.append(c)
        if 'nidito' in c.lower():
            cursos_busqueda.extend(['Nidito 1', 'Nidito 2', 'Nidito'])

    estudiantes = Estudiante.query.filter(
        Estudiante.curso.in_(cursos_busqueda),
        Estudiante.estado == 'Activo'
    ).order_by(Estudiante.curso.asc(), Estudiante.apellidos.asc()).all()

    meses_evaluados = ['Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre']
    anio_actual = datetime.now().year

    lista_morosos = []
    for est in estudiantes:
        pagos_est = Pago.query.filter(
            ((Pago.estudiante_id == est.id) | (Pago.ci_estudiante == est.ci)),
            Pago.anio == anio_actual,
            Pago.estado == 'Pagado'
        ).all()

        meses_pagados_set = {p.mes.strip().capitalize() for p in pagos_est if p.mes}
        meses_en_mora = [m for m in meses_evaluados if m not in meses_pagados_set]

        cuota = 0.0
        for attr in ['pension', 'monto_mensualidad', 'mensualidad', 'costo_mensual']:
            val = getattr(est, attr, None)
            if val is not None and float(val or 0.0) > 0:
                cuota = float(val)
                break
        if cuota <= 0:
            cuota = 250.0

        saldo_cardex = float(getattr(est, 'saldo_deuda', 0.0) or 0.0)

        if len(meses_en_mora) > 0:
            monto_deuda = (len(meses_en_mora) * cuota) if saldo_cardex <= 0 else saldo_cardex
            lista_morosos.append({
                'id': est.id,
                'apellidos': est.apellidos,
                'nombres': est.nombres,
                'curso': est.curso,
                'ci': est.ci or 'S/C',
                'deuda': monto_deuda,
                'meses_deuda': len(meses_en_mora),
                'detalle_meses': ', '.join(meses_en_mora),
                'tutor': getattr(est, 'nombre_padre', '') or getattr(est, 'tutor', 'N/D'),
                'telefono': getattr(est, 'telefono_tutor', '') or getattr(est, 'celular', 'S/N')
            })
        elif saldo_cardex > 0:
            lista_morosos.append({
                'id': est.id,
                'apellidos': est.apellidos,
                'nombres': est.nombres,
                'curso': est.curso,
                'ci': est.ci or 'S/C',
                'deuda': saldo_cardex,
                'meses_deuda': 1,
                'detalle_meses': 'Saldo pendiente acumulado',
                'tutor': getattr(est, 'nombre_padre', '') or getattr(est, 'tutor', 'N/D'),
                'telefono': getattr(est, 'telefono_tutor', '') or getattr(est, 'celular', 'S/N')
            })

    return render_template(
        ['profesores_portal/morosos.html', 'morosos.html'],
        profesor=profesor,
        morosos=lista_morosos,
        cursos=cursos_docente
    )


# --- ASISTENCIA DIARIA (UNIFICADA Y BLINDADA) ---
@profesores_portal_bp.route('/asistencia/<int:materia_id>', methods=['GET', 'POST'])
@login_requerido
def registrar_asistencia(materia_id):
    profesor_id = int(session['profesor_id'])
    materia = Materia.query.get_or_404(materia_id)

    if materia.profesor_id != profesor_id:
        abort(403)

    fecha_sel_str = request.values.get('fecha') or request.values.get('fecha_asistencia')
    if fecha_sel_str:
        try:
            fecha_sel = datetime.strptime(fecha_sel_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_sel = date.today()
    else:
        fecha_sel = date.today()

    if materia.curso_id == 'Nidito':
        estudiantes = Estudiante.query.filter(
            Estudiante.curso.in_(['Nidito 1', 'Nidito 2']),
            Estudiante.estado == 'Activo'
        ).order_by(Estudiante.curso.asc(), Estudiante.apellidos.asc()).all()
    else:
        estudiantes = Estudiante.query.filter_by(
            curso=materia.curso_id,
            estado='Activo'
        ).order_by(Estudiante.apellidos.asc(), Estudiante.nombres.asc()).all()

    # Verificar registros previos en el modelo unificado Falta
    registros_previos = Falta.query.filter(
        Falta.tipo_sujeto == 'Estudiante',
        Falta.fecha == fecha_sel,
        Falta.sujeto_id.in_([e.id for e in estudiantes]) if estudiantes else False
    ).all()

    bloqueado_para_docente = len(registros_previos) > 0

    if request.method == 'POST':
        if bloqueado_para_docente:
            flash('❌ Esta asistencia ya fue enviada y registrada. Los profesores no pueden alterarla; comuníquese con administración para cualquier modificación.', 'danger')
            return redirect(url_for('profesores_portal.registrar_asistencia', materia_id=materia.id, fecha=fecha_sel.strftime('%Y-%m-%d')))

        try:
            for est in estudiantes:
                estado_ingresado = request.form.get(f'asistencia_{est.id}', 'Presente')
                tipo_estado = 'Presente' if estado_ingresado == 'Presente' else 'Falta Injustificada'

                nuevo_registro = Falta(
                    tipo_sujeto='Estudiante',
                    sujeto_id=est.id,
                    ci_sujeto=est.ci,
                    rude_estudiante=est.rude,
                    fecha=fecha_sel,
                    tipo_falta=tipo_estado,
                    estado=tipo_estado
                )
                db.session.add(nuevo_registro)

            db.session.commit()
            flash(f'✅ Asistencia diaria enviada y sincronizada al instante para la fecha {fecha_sel.strftime("%d/%m/%Y")}.', 'success')
            return redirect(url_for('profesores_portal.registrar_asistencia', materia_id=materia.id, fecha=fecha_sel.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al registrar la asistencia: {str(e)}', 'danger')

    asistencias_map = {r.sujeto_id: r.tipo_falta for r in registros_previos}

    return render_template(
        ['profesores_portal/asistencia.html', 'asistencia.html'],
        materia=materia,
        estudiantes=estudiantes,
        fecha_sel=fecha_sel.strftime('%Y-%m-%d'),
        asistencias_map=asistencias_map,
        bloqueado_para_docente=bloqueado_para_docente
    )


@profesores_portal_bp.route('/materia/<int:materia_id>')
@login_requerido
def ver_materia(materia_id):
    profesor_id = int(session['profesor_id'])
    materia = Materia.query.get_or_404(materia_id)

    if materia.profesor_id != profesor_id:
        abort(403)

    periodo_sel = request.args.get('periodo', '1er Trimestre').strip()
    criterios, origen_rubrica, es_nidito, nivel = obtener_criterios_materia(materia_id)

    if not es_nidito:
        recalcular_nota_final(materia_id, periodo_sel)

    if materia.curso_id == 'Nidito':
        estudiantes = Estudiante.query.filter(
            Estudiante.curso.in_(['Nidito 1', 'Nidito 2']),
            Estudiante.estado == 'Activo'
        ).order_by(Estudiante.curso.asc(), Estudiante.apellidos.asc()).all()
    else:
        estudiantes = Estudiante.query.filter_by(
            curso=materia.curso_id,
            estado='Activo'
        ).order_by(Estudiante.apellidos.asc(), Estudiante.nombres.asc()).all()

    calificaciones_periodo = Calificacion.query.filter_by(
        materia_id=materia_id,
        periodo=periodo_sel
    ).all()

    cal_matrix = {}
    notas_finales = {}
    for c in calificaciones_periodo:
        tipo_limpio = c.tipo.strip() if c.tipo else ''
        if tipo_limpio == 'Nota Final':
            notas_finales[c.estudiante_id] = c.nota
        else:
            cal_matrix[(c.estudiante_id, tipo_limpio)] = c

    return render_template(
        ['profesores_portal/materia.html', 'materia.html'],
        materia=materia,
        estudiantes=estudiantes,
        nivel=nivel,
        es_nidito=es_nidito,
        criterios=criterios,
        origen_rubrica=origen_rubrica,
        periodo_sel=periodo_sel,
        cal_matrix=cal_matrix,
        notas_finales=notas_finales,
        periodos=['1er Trimestre', '2do Trimestre', '3er Trimestre'],
        RespaldoEstudiante=RespaldoEstudiante
    )


@profesores_portal_bp.route('/guardar_notas_matriz/<int:materia_id>', methods=['POST'])
@login_requerido
def guardar_notas_matriz(materia_id):
    profesor_id = int(session['profesor_id'])
    materia = Materia.query.get_or_404(materia_id)

    if materia.profesor_id != profesor_id:
        abort(403)

    periodo = request.form.get('periodo', '1er Trimestre').strip()
    criterios, origen_rubrica, es_nidito, nivel = obtener_criterios_materia(materia_id)

    if materia.curso_id == 'Nidito':
        estudiantes = Estudiante.query.filter(
            Estudiante.curso.in_(['Nidito 1', 'Nidito 2']),
            Estudiante.estado == 'Activo'
        ).all()
    else:
        estudiantes = Estudiante.query.filter_by(curso=materia.curso_id, estado='Activo').all()

    contador = 0

    for est in estudiantes:
        desglose_est = {}
        total_est = 0.0

        archivos_respaldo = request.files.getlist(f"respaldo_{est.id}")
        for archivo_respaldo in archivos_respaldo:
            if archivo_respaldo and allowed_file(archivo_respaldo.filename):
                filename = secure_filename(f"respaldo_est_{est.id}_mat_{materia_id}_{int(datetime.now().timestamp())}_{archivo_respaldo.filename}")
                os.makedirs(UPLOAD_FOLDER_RESPALDOS, exist_ok=True)
                path_completo = os.path.join(UPLOAD_FOLDER_RESPALDOS, filename)
                archivo_respaldo.save(path_completo)
                
                nuevo_respaldo = RespaldoEstudiante(
                    estudiante_id=est.id,
                    materia_id=materia_id,
                    periodo=periodo,
                    filename=filename
                )
                db.session.add(nuevo_respaldo)

        for crit in criterios:
            campo_nombre = f"criterio_{est.id}_{crit.id}"

            if es_nidito:
                cal = Calificacion.query.filter_by(
                    estudiante_id=est.id,
                    materia_id=materia_id,
                    periodo=periodo,
                    tipo=crit.nombre
                ).first()

                if not cal:
                    cal = Calificacion(
                        estudiante_id=est.id,
                        ci_estudiante=est.ci,
                        rude_estudiante=est.rude,
                        materia_id=materia_id,
                        periodo=periodo,
                        tipo=crit.nombre,
                        nota=0.0,
                        fecha=datetime.now().date()
                    )
                    db.session.add(cal)
                elif cal.nota is None:
                    cal.nota = 0.0

                if crit.es_descriptivo:
                    cal.informe_descriptivo = request.form.get(campo_nombre, '').strip()
                else:
                    cal.valoracion_cualitativa = request.form.get(campo_nombre, '').strip()

                cal.fecha = datetime.now().date()

            else:
                val_str = request.form.get(campo_nombre, '').strip()
                try:
                    if not crit.permite_decimales:
                        val_num = int(round(float(val_str))) if val_str else 0
                    else:
                        val_num = float(val_str) if val_str else 0.0
                except (ValueError, TypeError):
                    val_num = 0 if not crit.permite_decimales else 0.0

                max_p = float(crit.puntaje_maximo or 100.0)
                val_num = max(0, min(int(max_p), int(val_num))) if not crit.permite_decimales else max(0.0, min(max_p, float(val_num)))

                desglose_est[crit.nombre] = val_num
                total_est += float(val_num)

                cal = Calificacion.query.filter_by(
                    estudiante_id=est.id,
                    materia_id=materia_id,
                    periodo=periodo,
                    tipo=crit.nombre
                ).first()

                if not cal:
                    cal = Calificacion(
                        estudiante_id=est.id,
                        ci_estudiante=est.ci,
                        rude_estudiante=est.rude,
                        materia_id=materia_id,
                        periodo=periodo,
                        tipo=crit.nombre,
                        nota=0.0,
                        fecha=datetime.now().date()
                    )
                    db.session.add(cal)
                elif cal.nota is None:
                    cal.nota = 0.0

                cal.nota = float(val_num)
                cal.fecha = datetime.now().date()

        if not es_nidito:
            total_est = min(100.0, max(0.0, total_est))
            cal_final = Calificacion.query.filter_by(
                estudiante_id=est.id,
                materia_id=materia_id,
                periodo=periodo,
                tipo='Nota Final'
            ).first()

            if not cal_final:
                cal_final = Calificacion(
                    estudiante_id=est.id,
                    ci_estudiante=est.ci,
                    rude_estudiante=est.rude,
                    materia_id=materia_id,
                    periodo=periodo,
                    tipo='Nota Final',
                    fecha=datetime.now().date()
                )
                db.session.add(cal_final)

            cal_final.nota = round(total_est, 1)
            cal_final.desglose_json = json.dumps(desglose_est, ensure_ascii=False)
            cal_final.fecha = datetime.now().date()

        contador += 1

    db.session.commit()
    flash(f'✅ Calificaciones y respaldos guardados correctamente ({contador} estudiantes) para el {periodo}.', 'success')
    return redirect(url_for('profesores_portal.ver_materia', materia_id=materia_id, periodo=periodo))


@profesores_portal_bp.route('/ver_respaldo/<filename>')
@login_requerido
def ver_respaldo(filename):
    """Permite visualizar o descargar de forma segura cualquier archivo adjuntado."""
    return send_from_directory(os.path.join(current_app.root_path, UPLOAD_FOLDER_RESPALDOS), filename)


@profesores_portal_bp.route('/eliminar_respaldo/<int:respaldo_id>', methods=['POST'])
@login_requerido
def eliminar_respaldo(respaldo_id):
    """Elimina un archivo de respaldo individual desde la galería modal del estudiante."""
    respaldo = RespaldoEstudiante.query.get_or_404(respaldo_id)
    materia_id = respaldo.materia_id
    
    try:
        path_completo = os.path.join(current_app.root_path, UPLOAD_FOLDER_RESPALDOS, respaldo.filename)
        if os.path.exists(path_completo):
            os.remove(path_completo)
    except Exception:
        pass
    
    db.session.delete(respaldo)
    db.session.commit()
    flash('🗑️ Archivo de respaldo eliminado correctamente de la galería.', 'info')
    return redirect(url_for('profesores_portal.ver_materia', materia_id=materia_id))


# Bloqueo de mutación de rúbricas desde el portal docente
@profesores_portal_bp.route('/nueva_evaluacion/<int:materia_id>', methods=['POST'])
@login_requerido
def nueva_evaluacion(materia_id):
    flash('❌ Acción restringida: La definición de rúbricas es de competencia exclusiva de la Administración.', 'warning')
    return redirect(url_for('profesores_portal.ver_materia', materia_id=materia_id))


@profesores_portal_bp.route('/eliminar_evaluacion/<int:materia_id>', methods=['POST'])
@login_requerido
def eliminar_evaluacion(materia_id):
    flash('❌ Acción restringida: La eliminación de parámetros evaluativos solo puede ser autorizada por Dirección.', 'warning')
    return redirect(url_for('profesores_portal.ver_materia', materia_id=materia_id))
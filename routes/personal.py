# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/personal.py
Proyecto: ASestud-Konetz - Sistema de Gestión Escolar
Descripción:
    Blueprint para gestión completa de Profesores y Personal Administrativo.
    Incluye listado, alta, edición, eliminación, cardex, pagos, recibos,
    acceso del profesor y gestión de materias.
    DIVISIÓN ACADÉMICA: Nivel (Nidito/Primaria/Secundaria) y Turno
    (Mañana/Tarde). Caja única para todo el colegio.
==============================================================================
"""

import os
import io
from datetime import datetime

from flask import (
    jsonify,
    session,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    send_file
)

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from utils_pdf import cabecera_logo

from models import (
    db,
    Profesor,
    PersonalAdministrativo,
    PagoPersonal,
    Materia,
    NIVELES,
    TURNOS
)


personal_bp = Blueprint(
    'personal',
    __name__,
    template_folder='templates/personal'
)


# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================

def convertir_salario(valor):
    """
    Convierte un valor de formulario a float.
    Acepta coma decimal y campos vacíos.
    """
    try:
        valor = (valor or '').strip().replace(',', '.')
        return float(valor) if valor else 0.0
    except Exception:
        return 0.0


def allowed_file(filename):
    """
    Valida extensiones permitidas para fotos del personal.
    """
    allowed_extensions = {
        'jpg',
        'jpeg',
        'png',
        'tif',
        'tiff',
        'webp',
        'gif'
    }

    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


# ==============================================================================
# RUTA PRINCIPAL
# ==============================================================================

@personal_bp.route('/')
def index():
    """
    Ruta raíz del módulo personal.
    Redirecciona al listado de profesores.
    """
    return redirect(url_for('personal.lista_profesores'))


# ==============================================================================
# LISTADO DE PROFESORES (CON FILTROS DE NIVEL Y TURNO)
# ==============================================================================

@personal_bp.route('/profesores')
def lista_profesores():
    nivel_seleccionado = request.args.get('nivel', '').strip()
    turno_seleccionado = request.args.get('turno', '').strip()

    query = Profesor.query

    # Filtro por NIVEL (Nidito / Primaria / Secundaria)
    if nivel_seleccionado:
        query = query.filter(Profesor.nivel == nivel_seleccionado)

    # Filtro por TURNO (Mañana / Tarde)
    if turno_seleccionado:
        query = query.filter(Profesor.turno == turno_seleccionado)

    profesores = query.order_by(Profesor.apellidos.asc()).all()

    return render_template(
        'personal/profesores.html',
        profesores=profesores,
        nivel_seleccionado=nivel_seleccionado,
        turno_seleccionado=turno_seleccionado
    )


# ==============================================================================
# LISTADO DE PERSONAL ADMINISTRATIVO
# ==============================================================================

@personal_bp.route('/administrativos')
def lista_administrativos():
    administrativos = PersonalAdministrativo.query.order_by(
        PersonalAdministrativo.apellidos.asc()
    ).all()

    return render_template(
        'personal/administrativos.html',
        administrativos=administrativos
    )

# ==============================================================================
# PLANILLA GENERAL CONSOLIDADA DE SUELDOS
# ==============================================================================

@personal_bp.route('/planillas', methods=['GET'])
def planillas():
    MESES_ES = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    
    mes_actual_es = MESES_ES[datetime.now().month - 1]
    mes_seleccionado = request.args.get('mes', mes_actual_es).capitalize()
    
    try:
        anio_seleccionado = int(request.args.get('anio', datetime.now().year))
    except ValueError:
        anio_seleccionado = datetime.now().year

    turno_filtro = request.args.get('turno', '').strip()

    query_profesores = Profesor.query.filter_by(estado='Activo')
    query_admins = PersonalAdministrativo.query.filter_by(estado='Activo')

    if turno_filtro:
        query_profesores = query_profesores.filter(Profesor.turno == turno_filtro)
        if hasattr(PersonalAdministrativo, 'turno'):
            query_admins = query_admins.filter(PersonalAdministrativo.turno == turno_filtro)

    profesores_raw = query_profesores.order_by(Profesor.apellidos.asc()).all()
    administrativos_raw = query_admins.order_by(PersonalAdministrativo.apellidos.asc()).all()

    profesores = []
    tot_prof_base = 0.0
    tot_prof_adelanto = 0.0
    tot_prof_neto = 0.0

    for p in profesores_raw:
        adelanto_mes = db.session.query(db.func.coalesce(db.func.sum(PagoPersonal.monto_neto_pagado), 0.0)).filter(
            PagoPersonal.tipo == 'Adelanto',
            PagoPersonal.persona_id == p.id,
            PagoPersonal.mes == mes_seleccionado,
            PagoPersonal.anio == anio_seleccionado,
            PagoPersonal.estado != 'Anulado',
            PagoPersonal.nombre_persona.ilike(f"{p.apellidos}%")
        ).scalar() or 0.0

        base = float(p.salario_base or 0.0)
        adel = float(adelanto_mes)
        neto = max(0.0, base - adel)

        tot_prof_base += base
        tot_prof_adelanto += adel
        tot_prof_neto += neto

        profesores.append({
            'id': p.id,
            'ci': p.ci,
            'apellidos': p.apellidos,
            'nombres': p.nombres,
            'salario_base': base,
            'adelanto': adel,
            'salario_neto': neto
        })

    administrativos = []
    tot_admin_base = 0.0
    tot_admin_adelanto = 0.0
    tot_admin_neto = 0.0

    for a in administrativos_raw:
        adelanto_mes = db.session.query(db.func.coalesce(db.func.sum(PagoPersonal.monto_neto_pagado), 0.0)).filter(
            PagoPersonal.tipo == 'Adelanto',
            PagoPersonal.persona_id == a.id,
            PagoPersonal.mes == mes_seleccionado,
            PagoPersonal.anio == anio_seleccionado,
            PagoPersonal.estado != 'Anulado',
            PagoPersonal.nombre_persona.ilike(f"{a.apellidos}%")
        ).scalar() or 0.0

        base = float(a.salario_base or 0.0)
        adel = float(adelanto_mes)
        neto = max(0.0, base - adel)

        tot_admin_base += base
        tot_admin_adelanto += adel
        tot_admin_neto += neto

        administrativos.append({
            'id': a.id,
            'ci': a.ci,
            'apellidos': a.apellidos,
            'nombres': a.nombres,
            'salario_base': base,
            'adelanto': adel,
            'salario_neto': neto
        })

    gran_total_base = tot_prof_base + tot_admin_base
    gran_total_adelanto = tot_prof_adelanto + tot_admin_adelanto
    gran_total_neto = tot_prof_neto + tot_admin_neto

    return render_template(
        'personal/planillas.html',
        profesores=profesores,
        administrativos=administrativos,
        mes_seleccionado=mes_seleccionado,
        anio_seleccionado=anio_seleccionado,
        turno_filtro=turno_filtro,
        meses_disponibles=MESES_ES,
        tot_prof_base=tot_prof_base,
        tot_prof_adelanto=tot_prof_adelanto,
        tot_prof_neto=tot_prof_neto,
        tot_admin_base=tot_admin_base,
        tot_admin_adelanto=tot_admin_adelanto,
        tot_admin_neto=tot_admin_neto,
        gran_total_base=gran_total_base,
        gran_total_adelanto=gran_total_adelanto,
        gran_total_neto=gran_total_neto
    )
# ==============================================================================
# NUEVO PROFESOR (CON NIVEL Y TURNO)
# ==============================================================================

@personal_bp.route('/profesores/nuevo', methods=['GET', 'POST'])
def nuevo_profesor():
    if request.method == 'POST':
        apellidos = request.form.get('apellidos', '').strip()
        nombres = request.form.get('nombres', '').strip()
        ci = request.form.get('ci', '').strip() or None
        especialidad = request.form.get('especialidad', '').strip()
        salario_base = convertir_salario(request.form.get('salario_base'))
        estado = request.form.get('estado', 'Activo')
        usuario = request.form.get('usuario', '').strip() or None
        contrasena = request.form.get('contrasena', '').strip()

        nivel = request.form.get('nivel', '').strip() or None
        turno = request.form.get('turno', 'Mañana')

        if not apellidos or not nombres:
            flash('❌ Los apellidos y nombres del profesor son obligatorios.', 'danger')
            return render_template('personal/nuevo_profesor.html')

        if usuario:
            usuario_existente = Profesor.query.filter_by(usuario=usuario).first()
            if usuario_existente:
                flash('❌ Ese nombre de usuario ya está en uso.', 'danger')
                return render_template('personal/nuevo_profesor.html')

        contrasena_hash = None
        if contrasena:
            contrasena_hash = generate_password_hash(contrasena)

        try:
            nuevo = Profesor(
                ci=ci,
                apellidos=apellidos,
                nombres=nombres,
                especialidad=especialidad,
                nivel=nivel,
                turno=turno,
                salario_base=salario_base,
                salario_neto=salario_base,
                estado=estado,
                usuario=usuario,
                contrasena_hash=contrasena_hash
            )

            db.session.add(nuevo)
            db.session.commit()

            flash('✅ Profesor registrado correctamente.', 'success')
            return redirect(url_for('personal.lista_profesores'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al registrar profesor: {str(e)}', 'danger')

    return render_template('personal/nuevo_profesor.html')


# ==============================================================================
# NUEVO PERSONAL ADMINISTRATIVO
# ==============================================================================

@personal_bp.route('/administrativos/nuevo', methods=['GET', 'POST'])
def nuevo_administrativo():
    if request.method == 'POST':
        apellidos = request.form.get('apellidos', '').strip()
        nombres = request.form.get('nombres', '').strip()
        ci = request.form.get('ci', '').strip() or None
        cargo = request.form.get('cargo', '').strip()
        area = request.form.get('area', '').strip()
        salario_base = convertir_salario(request.form.get('salario_base'))
        estado = request.form.get('estado', 'Activo')
        usuario = request.form.get('usuario', '').strip() or None
        contrasena = request.form.get('contrasena', '').strip()

        if not apellidos or not nombres:
            flash('❌ Los apellidos y nombres son obligatorios.', 'danger')
            return render_template('personal/nuevo_administrativo.html')

        if not cargo:
            flash('❌ El cargo del personal administrativo es obligatorio.', 'danger')
            return render_template('personal/nuevo_administrativo.html')

        if usuario:
            usuario_existente = PersonalAdministrativo.query.filter_by(usuario=usuario).first()
            if usuario_existente:
                flash('❌ Ese nombre de usuario ya está en uso.', 'danger')
                return render_template('personal/nuevo_administrativo.html')

        contrasena_hash = None
        if contrasena:
            contrasena_hash = generate_password_hash(contrasena)

        try:
            nuevo = PersonalAdministrativo(
                ci=ci,
                apellidos=apellidos,
                nombres=nombres,
                cargo=cargo,
                area=area,
                salario_base=salario_base,
                salario_neto=salario_base,
                estado=estado,
                usuario=usuario,
                contrasena_hash=contrasena_hash
            )

            db.session.add(nuevo)
            db.session.commit()

            flash('✅ Personal administrativo registrado correctamente.', 'success')
            return redirect(url_for('personal.lista_administrativos'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al registrar personal administrativo: {str(e)}', 'danger')

    return render_template('personal/nuevo_administrativo.html')


# ==============================================================================
# EDITAR PROFESOR (CON NIVEL Y TURNO)
# ==============================================================================

@personal_bp.route('/profesor/<int:id>/editar', methods=['GET', 'POST'])
def editar_profesor(id):
    profesor = Profesor.query.get_or_404(id)

    if request.method == 'POST':
        profesor.ci = request.form.get('ci', '').strip() or None
        profesor.apellidos = request.form.get('apellidos', '').strip()
        profesor.nombres = request.form.get('nombres', '').strip()
        profesor.especialidad = request.form.get('especialidad', '').strip()
        profesor.salario_base = convertir_salario(request.form.get('salario_base'))
        profesor.estado = request.form.get('estado', profesor.estado)

        profesor.nivel = request.form.get('nivel', '').strip() or None
        profesor.turno = request.form.get('turno', profesor.turno or 'Mañana')

        nuevo_usuario = request.form.get('usuario', '').strip()
        contrasena = request.form.get('contrasena', '').strip()

        if not profesor.apellidos or not profesor.nombres:
            flash('❌ Los apellidos y nombres del profesor son obligatorios.', 'danger')
            return render_template('personal/editar_profesor.html', persona=profesor)

        if nuevo_usuario:
            usuario_en_uso = Profesor.query.filter(
                Profesor.usuario == nuevo_usuario,
                Profesor.id != profesor.id
            ).first()

            if usuario_en_uso:
                flash('❌ Ese nombre de usuario ya está en uso.', 'danger')
                return render_template('personal/editar_profesor.html', persona=profesor)

            profesor.usuario = nuevo_usuario
        else:
            profesor.usuario = None

        if contrasena:
            profesor.contrasena_hash = generate_password_hash(contrasena)

        profesor.salario_neto = (profesor.salario_base or 0.0) - (profesor.adelanto or 0.0)

        try:
            db.session.commit()
            flash('✅ Datos del profesor actualizados correctamente.', 'success')
            return redirect(url_for('personal.cardex_personal', tipo='profesor', id=profesor.id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al actualizar profesor: {str(e)}', 'danger')

    return render_template('personal/editar_profesor.html', persona=profesor)


# ==============================================================================
# EDITAR PERSONAL ADMINISTRATIVO
# ==============================================================================

@personal_bp.route('/administrativo/<int:id>/editar', methods=['GET', 'POST'])
def editar_administrativo(id):
    persona = PersonalAdministrativo.query.get_or_404(id)

    if request.method == 'POST':
        persona.ci = request.form.get('ci', '').strip() or None
        persona.apellidos = request.form.get('apellidos', '').strip()
        persona.nombres = request.form.get('nombres', '').strip()
        persona.cargo = request.form.get('cargo', '').strip()
        persona.area = request.form.get('area', '').strip()
        persona.salario_base = convertir_salario(request.form.get('salario_base'))
        persona.estado = request.form.get('estado', persona.estado)

        nuevo_usuario = request.form.get('usuario', '').strip()
        contrasena = request.form.get('contrasena', '').strip()

        if not persona.apellidos or not persona.nombres:
            flash('❌ Los apellidos y nombres son obligatorios.', 'danger')
            return render_template('personal/editar_administrativo.html', persona=persona)

        if not persona.cargo:
            flash('❌ El cargo es obligatorio.', 'danger')
            return render_template('personal/editar_administrativo.html', persona=persona)

        if nuevo_usuario:
            usuario_en_uso = PersonalAdministrativo.query.filter(
                PersonalAdministrativo.usuario == nuevo_usuario,
                PersonalAdministrativo.id != persona.id
            ).first()

            if usuario_en_uso:
                flash('❌ Ese nombre de usuario ya está en uso.', 'danger')
                return render_template('personal/editar_administrativo.html', persona=persona)

            persona.usuario = nuevo_usuario
        else:
            persona.usuario = None

        if contrasena:
            persona.contrasena_hash = generate_password_hash(contrasena)

        persona.salario_neto = (persona.salario_base or 0.0) - (persona.adelanto or 0.0)

        try:
            db.session.commit()
            flash('✅ Datos del personal administrativo actualizados correctamente.', 'success')
            return redirect(url_for('personal.cardex_personal', tipo='admin', id=persona.id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al actualizar personal: {str(e)}', 'danger')

    return render_template('personal/editar_administrativo.html', persona=persona)


# ==============================================================================
# ELIMINAR PROFESOR
# ==============================================================================

@personal_bp.route('/profesor/<int:id>/eliminar', methods=['POST'])
def eliminar_profesor(id):
    profesor = Profesor.query.get_or_404(id)

    try:
        db.session.delete(profesor)
        db.session.commit()

        flash('✅ Profesor eliminado correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar profesor: {str(e)}', 'danger')

    return redirect(url_for('personal.lista_profesores'))


# ==============================================================================
# ELIMINAR PERSONAL ADMINISTRATIVO
# ==============================================================================

@personal_bp.route('/administrativo/<int:id>/eliminar', methods=['POST'])
def eliminar_administrativo(id):
    persona = PersonalAdministrativo.query.get_or_404(id)

    try:
        db.session.delete(persona)
        db.session.commit()

        flash('✅ Personal administrativo eliminado correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar personal administrativo: {str(e)}', 'danger')

    return redirect(url_for('personal.lista_administrativos'))


# ==============================================================================
# GUARDAR USUARIO Y CONTRASEÑA DE ACCESO DEL PROFESOR
# ==============================================================================

@personal_bp.route('/profesor/<int:id>/acceso', methods=['POST'])
def guardar_acceso_profesor(id):
    profesor = Profesor.query.get_or_404(id)

    usuario = request.form.get('usuario', '').strip() or None
    contrasena = request.form.get('contrasena', '').strip()

    if usuario:
        usuario_en_uso = Profesor.query.filter(
            Profesor.usuario == usuario,
            Profesor.id != profesor.id
        ).first()

        if usuario_en_uso:
            flash('❌ Ese nombre de usuario ya está en uso.', 'danger')
            return redirect(url_for('personal.cardex_personal', tipo='profesor', id=id))

        profesor.usuario = usuario

    if contrasena:
        profesor.contrasena_hash = generate_password_hash(contrasena)

    try:
        db.session.commit()
        flash('✅ Datos de acceso del profesor actualizados correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al guardar acceso: {str(e)}', 'danger')

    return redirect(url_for('personal.cardex_personal', tipo='profesor', id=id))


# ==============================================================================
# CREAR MATERIA DIRECTAMENTE PARA UN PROFESOR
# ==============================================================================

@personal_bp.route('/profesor/<int:id>/crear_materia', methods=['POST'])
def crear_materia_profesor(id):
    profesor = Profesor.query.get_or_404(id)

    nombre = request.form.get('nombre', '').strip()
    curso_id = request.form.get('curso_id', '').strip()

    if not nombre or not curso_id:
        flash('❌ Debe escribir el nombre de la materia y el curso.', 'danger')
        return redirect(url_for('personal.cardex_personal', tipo='profesor', id=id))

    try:
        materia = Materia(
            nombre=nombre,
            curso_id=curso_id,
            profesor_id=profesor.id
        )

        db.session.add(materia)
        db.session.commit()

        flash(f'✅ Materia "{nombre}" agregada correctamente al profesor.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al crear materia: {str(e)}', 'danger')

    return redirect(url_for('personal.cardex_personal', tipo='profesor', id=id))


# ==============================================================================
# CREAR MATERIA NUEVA, CON O SIN PROFESOR
# ==============================================================================

@personal_bp.route('/materias/nueva', methods=['POST'])
def nueva_materia():
    nombre = request.form.get('nombre', '').strip()
    curso_id = request.form.get('curso_id', '').strip()
    profesor_id = request.form.get('profesor_id', '').strip()

    if not nombre or not curso_id:
        flash('❌ Debe escribir el nombre de la materia y el curso.', 'danger')
        return redirect(request.referrer or url_for('personal.lista_profesores'))

    profesor_id_valor = None

    if profesor_id:
        try:
            profesor_id_valor = int(profesor_id)
        except ValueError:
            profesor_id_valor = None

    if profesor_id_valor:
        profesor = Profesor.query.get(profesor_id_valor)
        if not profesor:
            flash('❌ Profesor no encontrado.', 'danger')
            return redirect(request.referrer or url_for('personal.lista_profesores'))

    try:
        materia = Materia(
            nombre=nombre,
            curso_id=curso_id,
            profesor_id=profesor_id_valor
        )

        db.session.add(materia)
        db.session.commit()

        flash(f'✅ Materia "{nombre}" creada correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al crear materia: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('personal.lista_profesores'))


# ==============================================================================
# PAGAR AL PERSONAL Y GENERAR RECIBO
# ==============================================================================

@personal_bp.route('/pagar/<tipo>/<int:id>', methods=['GET', 'POST'])
def pagar_personal(tipo, id):
    if tipo == 'profesor':
        persona = Profesor.query.get_or_404(id)
        tipo_db = 'Profesor'
    else:
        persona = PersonalAdministrativo.query.get_or_404(id)
        tipo_db = 'Administrativo'

    if request.method == 'POST':
        mes = request.form.get('mes')
        anio = int(request.form.get('anio', datetime.now().year))

        try:
            monto_base = float(request.form.get('monto_base', persona.salario_base or 0) or 0)
            adelanto = float(request.form.get('adelanto', 0) or 0)
        except ValueError:
            flash('❌ Montos inválidos', 'danger')
            return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

        pago_previo = PagoPersonal.query.filter(
            PagoPersonal.tipo == tipo_db,
            PagoPersonal.persona_id == id,
            PagoPersonal.mes == mes,
            PagoPersonal.anio == anio,
            PagoPersonal.estado == 'Pagado'
        ).first()

        if pago_previo:
            fecha_reg = pago_previo.fecha_pago.strftime('%d/%m/%Y') if pago_previo.fecha_pago else 'fecha previa'
            flash(f"❌ OPERACIÓN DENEGADA: El sueldo correspondiente a {mes} / {anio} ya fue liquidado y pagado el {fecha_reg} (Recibo N° {pago_previo.id}). No se permiten duplicados del mismo mes.", "danger")
            return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

        monto_neto = max(0.0, monto_base - adelanto)

        nuevo_pago = PagoPersonal(
            tipo=tipo_db,
            persona_id=id,
            nombre_persona=f"{persona.apellidos}, {persona.nombres}",
            mes=mes,
            anio=anio,
            monto_base=monto_base,
            monto_adelanto=adelanto,
            monto_neto_pagado=monto_neto,
            fecha_pago=datetime.now().date(),
            motivo=f"Sueldo - {mes} {anio}",
            estado='Pagado'
        )

        db.session.add(nuevo_pago)

        if adelanto > 0:
            adelanto_actual = persona.adelanto or 0.0
            persona.adelanto = max(0.0, adelanto_actual - adelanto)
            persona.salario_neto = (persona.salario_base or 0.0) - (persona.adelanto or 0.0)

        db.session.commit()

        try:
            bytes_pdf = generar_recibo_personal_pdf(
                pago=nuevo_pago,
                persona=persona,
                tipo_db=tipo_db
            )

            recibos_dir = os.path.join(os.getcwd(), 'static', 'recibos_personal')
            os.makedirs(recibos_dir, exist_ok=True)

            recibo_filename = f"recibo_personal_{id}_{datetime.now().year}_{int(datetime.now().timestamp())}.pdf"
            recibo_filepath = os.path.join(recibos_dir, recibo_filename)

            with open(recibo_filepath, 'wb') as f:
                f.write(bytes_pdf)

            flash('✅ Pago registrado y recibo generado exitosamente.', 'success')

            return redirect(
                url_for(
                    'personal.ver_recibo_oficial_personal',
                    tipo=tipo,
                    id=id,
                    recibo=recibo_filename
                )
            )

        except Exception as _e:
            flash('✅ Pago registrado, pero hubo un error al generar el recibo.', 'warning')
            return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

    MESES_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    
    mes_actual_es = MESES_ES[datetime.now().month - 1]
    mes = request.args.get('mes', mes_actual_es)
    
    try:
        anio = request.args.get('anio')
        anio_actual_calc = int(anio) if anio else datetime.now().year
    except ValueError:
        anio_actual_calc = datetime.now().year

    total_adelantos = db.session.query(
        db.func.coalesce(db.func.sum(PagoPersonal.monto_neto_pagado), 0.0)
    ).filter(
        PagoPersonal.persona_id == id,
        PagoPersonal.tipo == 'Adelanto',
        PagoPersonal.mes == mes,
        PagoPersonal.anio == anio_actual_calc,
        PagoPersonal.nombre_persona.ilike(f"{persona.apellidos}%")
    ).scalar() or 0.0

    total_adelantos = float(total_adelantos)

    adelantos_detalle = PagoPersonal.query.filter(
        PagoPersonal.persona_id == id,
        PagoPersonal.tipo == 'Adelanto',
        PagoPersonal.mes == mes,
        PagoPersonal.anio == anio_actual_calc,
        PagoPersonal.nombre_persona.ilike(f"{persona.apellidos}%")
    ).order_by(PagoPersonal.fecha_pago.desc()).limit(10).all()

    return render_template(
        'personal/pagar.html',
        persona=persona,
        tipo=tipo,
        total_adelantos=total_adelantos,
        adelantos_detalle=adelantos_detalle,
        mes_seleccionado=mes,
        anio_seleccionado=anio_actual_calc,
        anio_actual=datetime.now().year
    )

# ==============================================================================
# REGISTRAR PAGO GENERAL DEL PERSONAL
# ==============================================================================

@personal_bp.route('/registrar_pago', methods=['POST'])
def registrar_pago():
    turno_activo = session.get('turno_activo')
    if not turno_activo or str(turno_activo).strip().lower() in ['none', '', 'false']:
        flash('❌ ACCESO DENEGADO: Apertura de Turno requerida. Nadie puede registrar pagos de sueldo sin un turno de caja activo.', 'danger')
        return redirect(url_for('personal.pagos_personal'))

    persona_id_str = request.form.get('persona_id', '').strip()
    mes = request.form.get('mes', '').strip()
    anio = int(request.form.get('anio', datetime.now().year))

    try:
        monto_base = float(request.form.get('monto_base', 0) or 0)
        monto_adelanto = float(request.form.get('monto_adelanto', 0) or 0)
    except ValueError:
        flash('❌ Montos inválidos', 'danger')
        return redirect(url_for('personal.pagos_personal'))

    if not persona_id_str or not persona_id_str.startswith(('P-', 'A-')):
        flash('Por favor, seleccione una persona válida de la lista', 'danger')
        return redirect(url_for('personal.pagos_personal'))

    tipo_persona = persona_id_str[0]
    real_id = int(persona_id_str[2:])

    nombre = ""
    tipo_db = ""

    if tipo_persona == 'P':
        p = Profesor.query.get(real_id)
        if p:
            nombre = f"{p.apellidos}, {p.nombres}"
            tipo_db = "Profesor"
    else:
        a = PersonalAdministrativo.query.get(real_id)
        if a:
            nombre = f"{a.apellidos}, {a.nombres}"
            tipo_db = "Administrativo"

    if not nombre:
        flash('Persona no encontrada en la base de datos', 'danger')
        return redirect(url_for('personal.pagos_personal'))

    pago_existente = PagoPersonal.query.filter_by(
        tipo=tipo_db,
        persona_id=real_id,
        mes=mes,
        anio=anio
    ).first()

    if pago_existente:
        flash(f'❌ BLOQUEO DE SEGURIDAD: El sueldo de {nombre} correspondiente a {mes} {anio} YA FUE PAGADO. No se permite doble pago.', 'danger')
        return redirect(url_for('personal.pagos_personal'))

    monto_neto_pagado = max(0.0, monto_base - monto_adelanto)

    nuevo_pago = PagoPersonal(
        tipo=tipo_db,
        persona_id=real_id,
        nombre_persona=nombre,
        mes=mes,
        anio=anio,
        monto_base=monto_base,
        monto_adelanto=monto_adelanto,
        monto_neto_pagado=monto_neto_pagado,
        fecha_pago=datetime.now().date(),
        motivo=f"Sueldo - {mes} {anio}",
        estado='Pagado'
    )

    db.session.add(nuevo_pago)

    if tipo_persona == 'P':
        persona = Profesor.query.get(real_id)
    else:
        persona = PersonalAdministrativo.query.get(real_id)

    if persona and monto_adelanto > 0:
        adelanto_actual = persona.adelanto or 0.0
        persona.adelanto = max(0.0, adelanto_actual - monto_adelanto)
        persona.salario_neto = (persona.salario_base or 0.0) - (persona.adelanto or 0.0)

    db.session.commit()

    flash('✅ Pago registrado exitosamente', 'success')
    return redirect(url_for('personal.pagos_personal'))


# ==============================================================================
# CÁRDEX DEL PERSONAL (CONSOLIDADO SIN DUPLICAR ADELANTOS)
# ==============================================================================

@personal_bp.route('/cardex/<tipo>/<int:id>')
def cardex_personal(tipo, id):
    if tipo == 'profesor':
        persona = Profesor.query.get_or_404(id)
        materias = Materia.query.filter_by(
            profesor_id=id
        ).order_by(Materia.nombre.asc()).all()
        materias_disponibles = Materia.query.filter_by(
            profesor_id=None
        ).order_by(Materia.nombre.asc()).all()
        tipo_db = 'Profesor'
    else:
        persona = PersonalAdministrativo.query.get_or_404(id)
        materias = []
        materias_disponibles = []
        tipo_db = 'Administrativo'

    raw_pagos = PagoPersonal.query.filter(
        PagoPersonal.persona_id == id,
        PagoPersonal.tipo.in_([tipo_db, 'Adelanto']),
        PagoPersonal.nombre_persona.ilike(f"{persona.apellidos}%")
    ).order_by(PagoPersonal.fecha_pago.desc(), PagoPersonal.id.desc()).all()

    class PagoConsolidado:
        def __init__(self, id, tipo, mes, anio, monto_base, monto_adelanto, monto_neto_pagado, fecha_pago, estado):
            self.id = id
            self.tipo = tipo
            self.mes = mes
            self.anio = anio
            self.monto_base = monto_base
            self.monto_adelanto = monto_adelanto
            self.monto_neto_pagado = monto_neto_pagado
            self.fecha_pago = fecha_pago
            self.estado = estado

    periodos_dict = {}
    adelantos_sueltos = []

    for p in raw_pagos:
        clave = (p.mes, p.anio)
        if p.tipo == tipo_db:
            if clave not in periodos_dict:
                # Si ya se pagó el sueldo, el monto_adelanto registrado en ese pago es la verdad financiera del mes
                periodos_dict[clave] = {
                    'id': p.id,
                    'tipo': tipo_db,
                    'mes': p.mes,
                    'anio': p.anio,
                    'monto_base': float(p.monto_base or 0.0),
                    'monto_adelanto': float(p.monto_adelanto or 0.0),
                    'monto_neto_pagado': float(p.monto_neto_pagado or 0.0),
                    'fecha_pago': p.fecha_pago,
                    'estado': p.estado
                }
        elif p.tipo == 'Adelanto':
            # Solo mostramos el adelanto como fila independiente si el sueldo de ese mes AÚN NO ha sido pagado
            if clave not in periodos_dict:
                adelantos_sueltos.append({
                    'id': p.id,
                    'tipo': 'Adelanto',
                    'mes': p.mes,
                    'anio': p.anio,
                    'monto_base': 0.0,
                    'monto_adelanto': float(p.monto_neto_pagado or 0.0),
                    'monto_neto_pagado': float(p.monto_neto_pagado or 0.0),
                    'fecha_pago': p.fecha_pago,
                    'estado': p.estado
                })

    pagos_lista = list(periodos_dict.values()) + adelantos_sueltos
    pagos_consolidados = [
        PagoConsolidado(
            id=item['id'],
            tipo=item['tipo'],
            mes=item['mes'],
            anio=item['anio'],
            monto_base=item['monto_base'],
            monto_adelanto=item['monto_adelanto'],
            monto_neto_pagado=item['monto_neto_pagado'],
            fecha_pago=item['fecha_pago'],
            estado=item['estado']
        )
        for item in pagos_lista
    ]

    pagos_consolidados.sort(key=lambda x: (x.fecha_pago or datetime.min.date(), x.id), reverse=True)

    return render_template(
        'personal/cardex.html',
        persona=persona,
        tipo=tipo,
        materias=materias,
        materias_disponibles=materias_disponibles,
        pagos=pagos_consolidados
    )

# ==============================================================================
# ASIGNAR O DESASIGNAR MATERIA A PROFESOR
# ==============================================================================

@personal_bp.route('/profesor/<int:id>/gestionar_materia', methods=['POST'])
def gestionar_materia_profesor(id):
    profesor = Profesor.query.get_or_404(id)

    materia_id = request.form.get('materia_id')
    accion = request.form.get('accion')

    if materia_id:
        materia = Materia.query.get_or_404(materia_id)

        try:
            if accion == 'asignar':
                materia.profesor_id = profesor.id
                flash(
                    f'✅ Materia "{materia.nombre}" ({materia.curso_id}) asignada correctamente.',
                    'success'
                )

            elif accion == 'desasignar':
                materia.profesor_id = None
                flash(
                    f'ℹ️ Materia "{materia.nombre}" ({materia.curso_id}) desasignada. Queda disponible.',
                    'info'
                )

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al gestionar materia: {str(e)}', 'danger')

    return redirect(url_for('personal.cardex_personal', tipo='profesor', id=id))


# ==============================================================================
# SUBIR FOTO DEL PERSONAL
# ==============================================================================

@personal_bp.route('/subir_foto/<tipo>/<int:id>', methods=['POST'])
def subir_foto_personal(tipo, id):
    if tipo == 'profesor':
        persona = Profesor.query.get_or_404(id)
    else:
        persona = PersonalAdministrativo.query.get_or_404(id)

    if 'foto' not in request.files:
        flash('No se seleccionó archivo', 'danger')
        return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

    file = request.files['foto']

    if file.filename == '':
        flash('No se seleccionó archivo', 'danger')
        return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        extension = filename.rsplit('.', 1)[1].lower()
        nuevo_nombre = f"{tipo}_{persona.id}.{extension}"
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'personal')
        os.makedirs(upload_folder, exist_ok=True)

        filepath = os.path.join(upload_folder, nuevo_nombre)
        file.save(filepath)

        persona.foto_path = f"uploads/personal/{nuevo_nombre}"
        db.session.commit()

        flash('Foto actualizada exitosamente', 'success')
    else:
        flash('Formato no permitido. Use: jpg, jpeg, png, tif, tiff, webp, gif', 'danger')

    return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))


# ==============================================================================
# RECIBO SIMPLE DEL PERSONAL
# ==============================================================================

@personal_bp.route('/recibo/<tipo>/<int:id>')
def ver_recibo_personal(tipo, id):
    if tipo == 'profesor':
        persona = Profesor.query.get_or_404(id)
        tipo_db = 'Profesor'
    else:
        persona = PersonalAdministrativo.query.get_or_404(id)
        tipo_db = 'Administrativo'

    ultimo_pago = PagoPersonal.query.filter_by(
        persona_id=id,
        tipo=tipo_db
    ).order_by(PagoPersonal.id.desc()).first()

    if not ultimo_pago:
        flash('No hay pagos registrados para esta persona.', 'warning')
        return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

    try:
        bytes_pdf = generar_recibo_personal_pdf(
            pago=ultimo_pago,
            persona=persona,
            tipo_db=tipo_db
        )
        recibos_dir = os.path.join(os.getcwd(), 'static', 'recibos_personal')
        os.makedirs(recibos_dir, exist_ok=True)
        recibo_filename = f"recibo_personal_{id}_{ultimo_pago.id}_{int(datetime.now().timestamp())}.pdf"
        recibo_filepath = os.path.join(recibos_dir, recibo_filename)
        with open(recibo_filepath, 'wb') as f:
            f.write(bytes_pdf)

        return redirect(url_for('personal.ver_recibo_oficial_personal', tipo=tipo, id=id, recibo=recibo_filename))
    except Exception as e:
        print(f"Error al generar recibo: {e}")
        flash('Hubo un error al generar el recibo.', 'danger')
        return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))


# ==============================================================================
# SISTEMA DE ADELANTOS AL PERSONAL (CON CANDADO DE MESES YA PAGADOS)
# ==============================================================================

@personal_bp.route('/registrar_adelanto/<tipo>/<int:id>', methods=['GET', 'POST'])
def registrar_adelanto(tipo, id):
    turno_activo = session.get('turno_activo')
    if not turno_activo or str(turno_activo).strip().lower() in ['none', '', 'false']:
        flash('❌ ACCESO DENEGADO: Debe iniciar un turno de caja para registrar y entregar adelantos de dinero.', 'danger')
        return redirect(url_for('auth.login_turno'))

    if tipo == 'profesor':
        persona = Profesor.query.get_or_404(id)
        tipo_db = 'Profesor'
    else:
        persona = PersonalAdministrativo.query.get_or_404(id)
        tipo_db = 'Administrativo'

    MESES_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    mes_actual_es = MESES_ES[datetime.now().month - 1]

    if request.method == 'POST':
        try:
            monto = float(request.form.get('monto', 0) or 0)
        except ValueError:
            flash('Monto inválido', 'danger')
            return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

        if monto <= 0:
            flash('El monto del adelanto debe ser mayor a 0', 'danger')
            return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

        mes_adelanto = request.form.get('mes', mes_actual_es)
        anio_adelanto = int(request.form.get('anio', datetime.now().year))
        motivo_adelanto = request.form.get('motivo', 'Adelanto de Sueldo').strip() or 'Adelanto de Sueldo'

        # CANDADO CONTABLE: Bloquear adelantos si el sueldo de ese mes ya fue pagado
        pago_ya_realizado = PagoPersonal.query.filter_by(
            tipo=tipo_db,
            persona_id=id,
            mes=mes_adelanto,
            anio=anio_adelanto,
            estado='Pagado'
        ).first()

        if pago_ya_realizado:
            flash(f'❌ BLOQUEO CONTABLE: El sueldo correspondiente a {mes_adelanto} {anio_adelanto} ya fue liquidado y pagado. No se pueden otorgar adelantos para un periodo cerrado.', 'danger')
            return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

        nuevo_adelanto = PagoPersonal(
            tipo='Adelanto',
            persona_id=id,
            ci_persona=getattr(persona, 'ci', None),
            nombre_persona=f"{persona.apellidos}, {persona.nombres}",
            mes=mes_adelanto,
            anio=anio_adelanto,
            monto_base=0.0,
            monto_adelanto=0.0,
            monto_neto_pagado=monto,
            fecha_pago=datetime.now().date(),
            motivo=motivo_adelanto,
            estado='Pagado'
        )
        db.session.add(nuevo_adelanto)

        persona.adelanto = (persona.adelanto or 0.0) + monto
        persona.salario_neto = (persona.salario_base or 0.0) - (persona.adelanto or 0.0)

        db.session.commit()

        try:
            bytes_pdf = generar_recibo_adelanto_pdf(
                pago=nuevo_adelanto,
                persona=persona,
                tipo_db=tipo_db
            )
            recibos_dir = os.path.join(os.getcwd(), 'static', 'recibos_personal')
            os.makedirs(recibos_dir, exist_ok=True)
            recibo_filename = f"recibo_adelanto_{id}_{int(datetime.now().timestamp())}.pdf"
            recibo_filepath = os.path.join(recibos_dir, recibo_filename)
            with open(recibo_filepath, 'wb') as f:
                f.write(bytes_pdf)

            flash('Adelanto registrado con recibo oficial. Se descontará en el próximo pago.', 'success')
            return redirect(url_for('personal.ver_recibo_oficial_personal', tipo=tipo, id=id, recibo=recibo_filename))
        except Exception as e:
            print(f"Error al generar recibo de adelanto: {e}")
            flash('Adelanto registrado, pero hubo un error al generar el recibo.', 'warning')
            return redirect(url_for('personal.cardex_personal', tipo=tipo, id=id))

    return render_template(
        'personal/registrar_adelanto.html',
        persona=persona,
        tipo=tipo,
        anio_actual=datetime.now().year
    )


# ==============================================================================
# RECIBO OFICIAL DEL PERSONAL
# ==============================================================================

@personal_bp.route('/recibo_oficial/<tipo>/<int:id>')
def ver_recibo_oficial_personal(tipo, id):
    if tipo == 'profesor':
        persona = Profesor.query.get_or_404(id)
        tipo_db = 'Profesor'
    else:
        persona = PersonalAdministrativo.query.get_or_404(id)
        tipo_db = 'Administrativo'

    recibo_filename = request.args.get('recibo', '')

    pagos_recientes = PagoPersonal.query.filter(
        PagoPersonal.persona_id == id,
        PagoPersonal.tipo.in_([tipo_db, 'Adelanto']),
        PagoPersonal.nombre_persona.ilike(f"{persona.apellidos}%")
    ).order_by(PagoPersonal.id.desc()).limit(10).all()

    return render_template(
        'personal/recibo_oficial.html',
        persona=persona,
        tipo=tipo,
        tipo_db=tipo_db,
        pagos=pagos_recientes,
        recibo_filename=recibo_filename
    )


# ==============================================================================
# DESCARGAR RECIBO DEL PERSONAL
# ==============================================================================

@personal_bp.route('/ver_recibo_pdf/<filename>')
def ver_recibo_pdf(filename):
    filepath = os.path.join(os.getcwd(), 'static', 'recibos_personal', filename)
    if not os.path.exists(filepath):
        flash('El recibo no existe', 'danger')
        return redirect(url_for('personal.pagos_personal'))
    return send_file(filepath, as_attachment=False, mimetype='application/pdf')


@personal_bp.route('/descargar_recibo_personal/<filename>')
def descargar_recibo_personal(filename):
    filepath = os.path.join(os.getcwd(), 'static', 'recibos_personal', filename)

    if not os.path.exists(filepath):
        flash('El recibo no existe', 'danger')
        return redirect(url_for('personal.pagos_personal'))

    return send_file(filepath, as_attachment=True, download_name=filename)


# ==============================================================================
# GENERAR RECIBO PDF DEL PERSONAL (FILTRADO ESTRICTO POR MES Y AÑO)
# ==============================================================================

def generar_recibo_personal_pdf(pago, persona, tipo_db):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.3 * inch,
        bottomMargin=0.3 * inch
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=4,
        spaceBefore=0,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        spaceAfter=1,
        spaceBefore=0
    )

    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#333333'),
        spaceAfter=2,
        spaceBefore=0,
        leading=10
    )

    small_style = ParagraphStyle(
        'SmallStyle',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#555555'),
        alignment=TA_CENTER,
        spaceAfter=1,
        spaceBefore=0,
        leading=9
    )

    elements = []

    logo = cabecera_logo()
    if logo:
        elements.append(logo)
        elements.append(Spacer(1, 0.05 * inch))

    elements.append(Paragraph("COLEGIO DR. ANTONIO VACA DÍEZ", title_style))
    elements.append(Paragraph(
        "Dirección Administrativa y Académica - Riberalta, Beni, Bolivia",
        header_style
    ))
    elements.append(Spacer(1, 0.08 * inch))

    elements.append(Paragraph(
        "<b>RECIBO OFICIAL DE PAGO AL PERSONAL</b>",
        ParagraphStyle(
            'SubTitle',
            parent=title_style,
            fontSize=11,
            spaceAfter=4
        )
    ))

    elements.append(Spacer(1, 0.05 * inch))

    elements.append(Table([['']], colWidths=[7.5 * inch], rowHeights=[1]))
    elements[-1].setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#1a237e'))
    ]))

    elements.append(Spacer(1, 0.08 * inch))

    pago_id = pago.id or 0
    numero_recibo = f"REC-PER-{datetime.now().year}-{pago_id:04d}"
    fecha_str = pago.fecha_pago.strftime('%d/%m/%Y')

    info_data = [[
        Paragraph(f"<b>N° Recibo:</b> {numero_recibo}", normal_style),
        Paragraph(f"<b>Fecha:</b> {fecha_str}", normal_style)
    ]]

    info_table = Table(info_data, colWidths=[3.75 * inch, 3.75 * inch])

    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(info_table)
    elements.append(Spacer(1, 0.1 * inch))

    if tipo_db == 'Profesor':
        cargo_o_especialidad = getattr(persona, 'especialidad', '') or 'No registrado'
        label_cargo = 'Especialidad'
    else:
        cargo_o_especialidad = getattr(persona, 'cargo', '') or 'No registrado'
        label_cargo = 'Cargo'

    trabajador_data = [
        [Paragraph("<b>DATOS DEL TRABAJADOR</b>", normal_style), '', '', ''],
        [
            Paragraph(f"<b>Nombre:</b> {persona.apellidos}, {persona.nombres}", normal_style),
            Paragraph(f"<b>Tipo:</b> {tipo_db}", normal_style),
            Paragraph(f"<b>CI:</b> {persona.ci or 'N/R'}", normal_style),
            Paragraph(f"<b>{label_cargo}:</b> {cargo_o_especialidad}", normal_style)
        ]
    ]

    trabajador_table = Table(
        trabajador_data,
        colWidths=[2.2 * inch, 1.5 * inch, 1.3 * inch, 2.5 * inch]
    )

    trabajador_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f5f5f5')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 1), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    elements.append(trabajador_table)
    elements.append(Spacer(1, 0.1 * inch))

    # ⭐ FILTRADO ESTRICTO: Solo adelantos del mes y año exactos que se están pagando
    adelantos_persona = PagoPersonal.query.filter(
        PagoPersonal.persona_id == pago.persona_id,
        PagoPersonal.tipo == 'Adelanto',
        PagoPersonal.mes == pago.mes,
        PagoPersonal.anio == pago.anio,
        PagoPersonal.nombre_persona.ilike(f"{persona.apellidos}%")
    ).order_by(PagoPersonal.fecha_pago.asc()).all()

    adelantos_descontados = []
    suma_acumulada = 0.0
    for ad in adelantos_persona:
        if suma_acumulada < (pago.monto_adelanto or 0.0):
            adelantos_descontados.append(ad)
            suma_acumulada += ad.monto_neto_pagado or 0.0

    pago_data = [
        [Paragraph("<b>DETALLE FINANCIERO</b>", normal_style), '', ''],
        [
            Paragraph("<b>Concepto</b>", normal_style),
            Paragraph("<b>Fecha</b>", normal_style),
            Paragraph("<b>Monto (Bs.)</b>", normal_style)
        ],
        [
            Paragraph("Sueldo Neto", normal_style),
            Paragraph(f"{pago.mes} / {pago.anio}", normal_style),
            Paragraph(f"{pago.monto_base:.2f}", normal_style)
        ],
    ]

    red_style = ParagraphStyle('RedText', parent=normal_style, textColor=colors.red)

    for ad in adelantos_descontados:
        motivo_txt = f"(-) Adelanto ({ad.motivo or 'Sueldo'})"
        pago_data.append([
            Paragraph(motivo_txt, red_style),
            Paragraph(ad.fecha_pago.strftime('%d/%m/%Y') if ad.fecha_pago else '-', red_style),
            Paragraph(f"- {ad.monto_neto_pagado:.2f}", red_style)
        ])

    pago_data.append([
        Paragraph("<b>TOTAL LIQUIDO PAGABLE:</b>", normal_style),
        Paragraph("", normal_style),
        Paragraph(
            f"<b>Bs. {pago.monto_neto_pagado:.2f}</b>",
            ParagraphStyle(
                'GreenBold',
                parent=normal_style,
                textColor=colors.HexColor('#155724'),
                fontSize=10
            )
        )
    ])

    pago_table = Table(
        pago_data,
        colWidths=[3.5 * inch, 1.5 * inch, 2.5 * inch]
    )

    estilo_pago = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#4a4a4a')),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.whitesmoke),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 1), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    ultima_fila = len(pago_data) - 1
    estilo_pago.add('BACKGROUND', (0, ultima_fila), (-1, ultima_fila), colors.HexColor('#d4edda'))

    pago_table.setStyle(estilo_pago)

    elements.append(pago_table)
    elements.append(Spacer(1, 0.25 * inch))

    firmas_data = [
        [
            Paragraph("_____________________________", small_style),
            Paragraph("_____________________________", small_style)
        ],
        [
            Paragraph("Firma del Trabajador", small_style),
            Paragraph("Firma y Sello de Administración", small_style)
        ],
        [
            Paragraph(f"C.I. {persona.ci or '__________'}", small_style),
            Paragraph("Autorizado por Dirección", small_style)
        ]
    ]

    firmas_table = Table(firmas_data, colWidths=[3.75 * inch, 3.75 * inch])

    firmas_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    elements.append(firmas_table)
    elements.append(Spacer(1, 0.15 * inch))

    footer_text = Paragraph(
        f"<i>Este documento es un comprobante oficial de pago. Conserve este registro. "
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - Colegio Dr. Antonio Vaca Díez.</i>",
        small_style
    )

    elements.append(footer_text)

    doc.build(elements)
    buffer.seek(0)

    return buffer.getvalue()


# ==============================================================================
# GENERADOR DE RECIBO DE ADELANTO
# ==============================================================================

def generar_recibo_adelanto_pdf(pago, persona, tipo_db):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    adelantos_mes = PagoPersonal.query.filter(
        PagoPersonal.persona_id == pago.persona_id,
        PagoPersonal.tipo == 'Adelanto',
        PagoPersonal.mes == pago.mes,
        PagoPersonal.anio == pago.anio,
        PagoPersonal.nombre_persona.ilike(f"{persona.apellidos}%")
    ).order_by(PagoPersonal.fecha_pago.asc()).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#1a237e'),
        alignment=TA_CENTER,
        spaceAfter=2,
        spaceBefore=2,
        fontName='Helvetica-Bold'
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        spaceAfter=1,
        spaceBefore=0
    )

    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=2,
        spaceBefore=0,
        leading=15
    )

    elements = []

    logo = cabecera_logo()
    if logo:
        elements.append(logo)
        elements.append(Spacer(1, 0.05 * inch))

    elements.append(Paragraph("COLEGIO DR. ANTONIO VACA DÍEZ", title_style))
    elements.append(Paragraph(
        "Dirección Administrativa y Académica - Riberalta, Beni, Bolivia",
        header_style
    ))
    elements.append(Spacer(1, 0.08 * inch))

    elements.append(Paragraph(
        "<b>RECIBO DE ADELANTO DE SUELDO</b>",
        ParagraphStyle(
            'SubTitle',
            parent=title_style,
            fontSize=11,
            spaceAfter=4
        )
    ))

    elements.append(Spacer(1, 0.05 * inch))

    cargo = getattr(persona, 'especialidad', None) or getattr(persona, 'cargo', '-') or '-'
    ci = getattr(persona, 'ci', '-') or '-'

    datos_data = [
        [Paragraph("<b>Nombre:</b>", normal_style),
         Paragraph(f"{persona.apellidos}, {persona.nombres}", normal_style)],
        [Paragraph("<b>C.I.:</b>", normal_style), Paragraph(str(ci), normal_style)],
        [Paragraph("<b>Cargo/Especialidad:</b>", normal_style), Paragraph(str(cargo), normal_style)],
    ]

    datos_table = Table(datos_data, colWidths=[2.2 * inch, 5.3 * inch])
    datos_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8eaf6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(datos_table)
    elements.append(Spacer(1, 0.15 * inch))

    cell_center = ParagraphStyle('CellCenter', parent=normal_style, fontSize=12, alignment=TA_CENTER)

    tabla_data = [[
        Paragraph("<b>MOTIVO / RAZÓN</b>", cell_center),
        Paragraph("<b>FECHA</b>", cell_center),
        Paragraph("<b>PERIODO</b>", cell_center),
        Paragraph("<b>MONTO (Bs.)</b>", cell_center)
    ]]

    total_adelantos = 0.0
    for ad in adelantos_mes:
        total_adelantos += ad.monto_neto_pagado or 0.0
        tabla_data.append([
            Paragraph(ad.motivo or 'Adelanto de Sueldo', cell_center),
            Paragraph(ad.fecha_pago.strftime('%d/%m/%Y') if ad.fecha_pago else '-', cell_center),
            Paragraph(f"{ad.mes} / {ad.anio}", cell_center),
            Paragraph(f"{(ad.monto_neto_pagado or 0.0):.2f}", cell_center)
        ])

    tabla_data.append([
        Paragraph("", normal_style),
        Paragraph("", normal_style),
        Paragraph("<b>TOTAL ADELANTOS</b>", cell_center),
        Paragraph(f"<b>{total_adelantos:.2f}</b>", cell_center)
    ])

    tabla = Table(tabla_data, colWidths=[1.6 * inch, 1.6 * inch, 2.0 * inch, 1.8 * inch])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fff8e1')),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#1a237e')),
    ]))
    elements.append(tabla)

    elements.append(Spacer(1, 0.5 * inch))

    firmas_data = [
        ["", ""],
        ["____________________________", "____________________________"],
        ["Entregado por (Administración)", "Recibido por (Trabajador)"]
    ]

    firmas_table = Table(firmas_data, colWidths=[3.75 * inch, 3.75 * inch])
    firmas_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, 1), 8),
    ]))
    elements.append(firmas_table)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# ==============================================================================
# FUNCIÓN AUXILIAR DE VALIDACIÓN DE BÓVEDA (FLEXIBLE)
# ==============================================================================

def validar_boveda(password_ingresada):
    """
    Valida la contraseña de la bóveda comprobando contra sesión,
    configuraciones de la app o claves maestras del sistema.
    """
    if not password_ingresada:
        return False

    if session.get('boveda_autorizada') is True or session.get('superadmin_boveda') is True:
        return True

    clave_config = current_app.config.get('BOVEDA_PASSWORD') or current_app.config.get('CLAVE_BOVEDA')
    if clave_config and str(password_ingresada).strip() == str(clave_config).strip():
        return True

    claves_maestras = ['1234', 'boveda2026', 'admin123', 'admin']
    if str(password_ingresada).strip() in claves_maestras:
        return True

    return False


# ==============================================================================
# ANULACIÓN DE PAGOS / ADELANTOS (ÚNICA VÍA PERMITIDA - PROTEGIDO CON BÓVEDA)
# ==============================================================================

@personal_bp.route('/pago/eliminar/<int:pago_id>', methods=['POST'])
def eliminar_pago_personal(pago_id):
    pago = PagoPersonal.query.get_or_404(pago_id)
    tipo_persona = 'profesor' if pago.tipo == 'Profesor' else ('admin' if pago.tipo == 'Administrativo' else 'profesor')
    persona_id = pago.persona_id

    password_ingresada = request.form.get('boveda_password', '').strip()

    if not validar_boveda(password_ingresada):
        flash('❌ Contraseña de Bóveda incorrecta. No se autorizó la anulación.', 'danger')
        return redirect(url_for('personal.cardex_personal', tipo=tipo_persona, id=persona_id))

    try:
        if pago.estado == 'Anulado':
            flash('⚠️ Este registro ya se encontraba anulado.', 'warning')
            return redirect(url_for('personal.cardex_personal', tipo=tipo_persona, id=persona_id))

        # Si el registro anulado era un Adelanto, descontarlo del acumulado de la persona
        if pago.tipo == 'Adelanto':
            persona = Profesor.query.get(persona_id) if tipo_persona == 'profesor' else PersonalAdministrativo.query.get(persona_id)
            if persona:
                adelanto_actual = persona.adelanto or 0.0
                monto_anulado = pago.monto_neto_pagado or 0.0
                persona.adelanto = max(0.0, adelanto_actual - monto_anulado)
                persona.salario_neto = (persona.salario_base or 0.0) - persona.adelanto

        # Cambiar el estado a Anulado sin borrar físicamente el registro de la base de datos
        pago.estado = 'Anulado'
        pago.motivo = f"[ANULADA] {pago.motivo or ''}".strip()
        
        db.session.commit()
        db.session.expire_all()

        flash('✅ Transacción económica anulada correctamente. Queda constancia en el cárdex y se excluyó de los informes.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al anular la transacción: {str(e)}', 'danger')

    return redirect(url_for('personal.cardex_personal', tipo=tipo_persona, id=persona_id))

# ==============================================================================
# API PARA OBTENER ADELANTOS DE UN PERIODO (UTILIZADO EN PANTALLA DE PAGO)
# ==============================================================================

@personal_bp.route('/api/adelantos_periodo/<tipo>/<int:id>')
def api_adelantos_periodo(tipo, id):
    mes = request.args.get('mes', '').strip()
    try:
        anio = int(request.args.get('anio', datetime.now().year))
    except ValueError:
        anio = datetime.now().year

    if tipo == 'profesor':
        persona = Profesor.query.get(id)
    else:
        persona = PersonalAdministrativo.query.get(id)

    adelantos = PagoPersonal.query.filter(
        PagoPersonal.persona_id == id,
        PagoPersonal.tipo == 'Adelanto',
        PagoPersonal.mes == mes,
        PagoPersonal.anio == anio,
        PagoPersonal.nombre_persona.ilike(f"{persona.apellidos}%") if persona else True
    ).order_by(PagoPersonal.fecha_pago.desc(), PagoPersonal.id.desc()).all()

    total = sum(float(a.monto_neto_pagado or 0.0) for a in adelantos)
    detalle = []
    for a in adelantos:
        detalle.append({
            'fecha': a.fecha_pago.strftime('%d/%m/%Y') if a.fecha_pago else '-',
            'motivo': a.motivo or 'Adelanto de Sueldo',
            'monto': float(a.monto_neto_pagado or 0.0)
        })

    return jsonify({
        'status': 'success',
        'mes': mes,
        'anio': anio,
        'total': total,
        'detalle': detalle
    })
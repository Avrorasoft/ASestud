# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: routes/reportes.py
Proyecto: Sistema de Gestión Escolar
Desarrollado por: Avrora Soft - Vibola LLC
Descripción: Módulo de reportes económicos por turno (Mañana/Tarde) y 
consolidado general para caja única. Incluye Panel de Control, Monitor Mural y Ceremonia.
==============================================================================
"""

import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, make_response
from werkzeug.utils import secure_filename
from models import db, Pago, Gasto, PagoPersonal, Falta, Estudiante, Asistencia, ahora_bolivia
from sqlalchemy import func, or_, and_

# ⭐ BLUEPRINT DEFINIDO PRIMERO PARA EVITAR ERRORES DE REFERENCIA
reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes', template_folder='templates/reportes')

# =========================================================================
# CONFIGURACIÓN DEL MONITOR MURAL (JSON Básico)
# =========================================================================
CONFIG_FILE = 'monitor_config.json'

def cargar_configuracion_monitor():
    default_config = {
        'velocidad_ticker': 150,        
        'velocidad_aeropuerto': 40,     
        'intervalo_carrusel': 4000,     
        'texto_ticker': '🔴 AVISO: Inscripciones abiertas para las Olimpiadas. 🟢 DEPORTES: Final de Futsal el sábado a las 10:00 AM.',
        'agenda_1': 'Viernes Cívico: Acto a las 08:00 AM.',
        'agenda_2': 'Reunión Padres: Secundaria, martes 19:00 hrs.',
        'album_titulo': 'Galería Institucional',
        'album_subtitulo': 'Momentos destacados de nuestra comunidad educativa'
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for k, v in default_config.items():
                    if k not in config:
                        config[k] = v
                return config
    except Exception:
        pass
    return default_config

def guardar_configuracion_monitor(config_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error guardando config del monitor: {e}")
        return False

# =========================================================================
# REPORTES ECONÓMICOS
# =========================================================================
@reportes_bp.route('/economico/manana')
def economico_manana():
    try:
        pagos = [p for p in Pago.query.filter(Pago.turno_responsable == 'Mañana', Pago.monto_pagado > 0).order_by(Pago.fecha_pago.desc()).all() if getattr(p, 'estado', 'Pagado') != 'Anulado']
    except Exception:
        pagos = [p for p in Pago.query.filter(Pago.turno_responsable == 'Mañana', Pago.monto_pagado > 0).all()]
    
    total = sum(p.monto_pagado for p in pagos)

    try:
        todos_gastos = Gasto.query.all()
    except Exception:
        todos_gastos = []
    
    gastos = [g for g in todos_gastos if getattr(g, 'estado', 'Activo') != 'Anulado']
    total_gastos = sum(g.monto for g in gastos)

    try:
        todos_personal = PagoPersonal.query.all()
    except Exception:
        todos_personal = []

    pagos_personal = [p for p in todos_personal if getattr(p, 'estado', 'Pagado') != 'Anulado']
    
    sueldos = [p for p in pagos_personal if getattr(p, 'tipo', 'Profesor') != 'Adelanto']
    adelantos = [p for p in pagos_personal if getattr(p, 'tipo', 'Profesor') == 'Adelanto']

    total_personal = sum(p.monto_neto_pagado for p in pagos_personal)
    total_egresos = total_gastos + total_personal
    balance_neto = total - total_egresos

    return render_template('reportes/economico.html', 
                           pagos=pagos,
                           gastos=gastos,
                           pagos_personal=pagos_personal,
                           sueldos=sueldos,
                           adelantos=adelantos,
                           total=total,
                           total_gastos=total_gastos,
                           total_personal=total_personal,
                           total_egresos=total_egresos,
                           balance_neto=balance_neto,
                           titulo='Reporte Económico - Turno Mañana',
                           turno='Mañana')

@reportes_bp.route('/economico/tarde')
def economico_tarde():
    try:
        pagos = [p for p in Pago.query.filter(Pago.turno_responsable == 'Tarde', Pago.monto_pagado > 0).order_by(Pago.fecha_pago.desc()).all() if getattr(p, 'estado', 'Pagado') != 'Anulado']
    except Exception:
        pagos = [p for p in Pago.query.filter(Pago.turno_responsable == 'Tarde', Pago.monto_pagado > 0).all()]
    
    total = sum(p.monto_pagado for p in pagos)

    try:
        todos_gastos = Gasto.query.all()
    except Exception:
        todos_gastos = []

    gastos = [g for g in todos_gastos if getattr(g, 'estado', 'Activo') != 'Anulado']
    total_gastos = sum(g.monto for g in gastos)

    try:
        todos_personal = PagoPersonal.query.all()
    except Exception:
        todos_personal = []

    pagos_personal = [p for p in todos_personal if getattr(p, 'estado', 'Pagado') != 'Anulado']
    
    sueldos = [p for p in pagos_personal if getattr(p, 'tipo', 'Profesor') != 'Adelanto']
    adelantos = [p for p in pagos_personal if getattr(p, 'tipo', 'Profesor') == 'Adelanto']

    total_personal = sum(p.monto_neto_pagado for p in pagos_personal)
    total_egresos = total_gastos + total_personal
    balance_neto = total - total_egresos

    return render_template('reportes/economico.html', 
                           pagos=pagos,
                           gastos=gastos,
                           pagos_personal=pagos_personal, 
                           sueldos=sueldos,
                           adelantos=adelantos,
                           total=total,
                           total_gastos=total_gastos,
                           total_personal=total_personal,
                           total_egresos=total_egresos,
                           balance_neto=balance_neto,
                           titulo='Reporte Económico - Turno Tarde',
                           turno='Tarde')

@reportes_bp.route('/economico/general')
def economico_general():
    try:
        pagos = [p for p in Pago.query.filter(Pago.monto_pagado > 0).order_by(Pago.fecha_pago.desc()).all() if getattr(p, 'estado', 'Pagado') != 'Anulado']
    except Exception:
        pagos = [p for p in Pago.query.filter(Pago.monto_pagado > 0).all()]

    total_general = sum(p.monto_pagado for p in pagos)
    
    total_manana = sum(p.monto_pagado for p in pagos if p.turno_responsable == 'Mañana')
    total_tarde = sum(p.monto_pagado for p in pagos if p.turno_responsable == 'Tarde')

    try:
        todos_gastos = Gasto.query.all()
    except Exception:
        todos_gastos = []

    gastos = [g for g in todos_gastos if getattr(g, 'estado', 'Activo') != 'Anulado']
    total_gastos = sum(g.monto for g in gastos)

    try:
        todos_personal = PagoPersonal.query.all()
    except Exception:
        todos_personal = []

    pagos_personal = [p for p in todos_personal if getattr(p, 'estado', 'Pagado') != 'Anulado']
    
    sueldos = [p for p in pagos_personal if getattr(p, 'tipo', 'Profesor') != 'Adelanto']
    adelantos = [p for p in pagos_personal if getattr(p, 'tipo', 'Profesor') == 'Adelanto']

    total_personal = sum(p.monto_neto_pagado for p in pagos_personal)
    total_egresos = total_gastos + total_personal
    balance_general_neto = total_general - total_egresos
    
    return render_template('reportes/economico_general.html', 
                           pagos=pagos,
                           gastos=gastos,
                           pagos_personal=pagos_personal, 
                           sueldos=sueldos,
                           adelantos=adelantos,
                           total_general=total_general,
                           total_manana=total_manana,
                           total_tarde=total_tarde,
                           total_gastos=total_gastos,
                           total_personal=total_personal,
                           total_egresos=total_egresos,
                           balance_general_neto=balance_general_neto,
                           titulo='Reporte Económico General')


# =========================================================================
# PANEL DE CONTROL DEL MONITOR MURAL
# =========================================================================
@reportes_bp.route('/monitor-config', methods=['GET', 'POST'])
def monitor_config():
    config_actual = cargar_configuracion_monitor()
    
    base_upload = current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads")
    upload_folder = os.path.join(base_upload, 'monitor_album')
    os.makedirs(upload_folder, exist_ok=True)

    if request.method == 'POST':
        try:
            nueva_config = {
                'velocidad_ticker': int(request.form.get('velocidad_ticker', 150)),
                'velocidad_aeropuerto': int(request.form.get('velocidad_aeropuerto', 40)),
                'intervalo_carrusel': int(request.form.get('intervalo_carrusel', 4000)),
                'texto_ticker': request.form.get('texto_ticker', ''),
                'agenda_1': request.form.get('agenda_1', ''),
                'agenda_2': request.form.get('agenda_2', ''),
                'album_titulo': request.form.get('album_titulo', 'Galería Institucional'),
                'album_subtitulo': request.form.get('album_subtitulo', 'Momentos destacados')
            }
            guardar_configuracion_monitor(nueva_config)

            fotos_a_eliminar = request.form.getlist('eliminar_fotos')
            for foto in fotos_a_eliminar:
                try:
                    os.remove(os.path.join(upload_folder, foto))
                except Exception as e:
                    print(f"Error eliminando foto {foto}: {e}")

            if 'fotos_album' in request.files:
                for file in request.files.getlist('fotos_album'):
                    if file and file.filename != '':
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(upload_folder, filename))

            if 'fotos_excelencia' in request.files:
                for file in request.files.getlist('fotos_excelencia'):
                    if file and file.filename != '':
                        filename = secure_filename("excelencia_" + file.filename)
                        file.save(os.path.join(upload_folder, filename))

            if 'fotos_valores' in request.files:
                for file in request.files.getlist('fotos_valores'):
                    if file and file.filename != '':
                        filename = secure_filename("valores_" + file.filename)
                        file.save(os.path.join(upload_folder, filename))

            flash('✅ Configuración y carruseles de reconocimiento actualizados con éxito.', 'success')
            return redirect(url_for('reportes.monitor_config'))
            
        except ValueError:
            flash('❌ Error: Asegúrese de ingresar números válidos para las velocidades.', 'danger')

    todas_fotos = [f for f in os.listdir(upload_folder) if os.path.isfile(os.path.join(upload_folder, f))]
    
    fotos_album = [f for f in todas_fotos if not f.startswith('excelencia_') and not f.startswith('valores_')]
    fotos_excelencia = [f for f in todas_fotos if f.startswith('excelencia_')]
    fotos_valores = [f for f in todas_fotos if f.startswith('valores_')]
    
    return render_template('reportes/monitor_config.html', 
                           configuracion=config_actual, 
                           fotos_actuales=todas_fotos,
                           fotos_album=fotos_album,
                           fotos_excelencia=fotos_excelencia,
                           fotos_valores=fotos_valores)


@reportes_bp.route('/album/<path:filename>')
def imagen_album(filename):
    base_upload = current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads")
    upload_folder = os.path.join(base_upload, 'monitor_album')
    return send_from_directory(upload_folder, filename)


# =========================================================================
# PANTALLA PÚBLICA: MONITOR EXTERNO DE DIRECCIÓN (CON FILTRO ESTRICTO DE TURNO)
# =========================================================================
@reportes_bp.route('/monitor-direccion')
def monitor_direccion():
    """Pantalla pública en tiempo real filtrada estrictamente por el turno del estudiante."""
    
    ahora_local = ahora_bolivia()
    hoy = ahora_local.date()
    
    # 1. Detección automática del turno según la hora (Antes de las 13:00 = Mañana, desde las 13:00 = Tarde)
    turno_por_defecto = 'Tarde' if ahora_local.hour >= 13 else 'Mañana'
    
    # Permite forzar el turno mediante parámetro en la URL si se desea (ej: /reportes/monitor-direccion?turno=Tarde)
    turno_activo = request.args.get('turno', turno_por_defecto).capitalize()
    if turno_activo not in ['Mañana', 'Tarde']:
        turno_activo = turno_por_defecto

    configuracion = cargar_configuracion_monitor()
    
    base_upload = current_app.config.get('UPLOAD_FOLDER', r"C:\ASestud\uploads")
    upload_folder = os.path.join(base_upload, 'monitor_album')
    os.makedirs(upload_folder, exist_ok=True)
    todas_fotos = [f for f in os.listdir(upload_folder) if os.path.isfile(os.path.join(upload_folder, f))]
    
    fotos_album = [f for f in todas_fotos if not f.startswith('excelencia_') and not f.startswith('valores_')]
    fotos_excelencia = [f for f in todas_fotos if f.startswith('excelencia_')]
    fotos_valores = [f for f in todas_fotos if f.startswith('valores_')]
    
    # 2. CONSULTA BLINDADA CON JOIN: Filtra estrictamente por la fecha, estado Falta Y el turno del Estudiante
    ausencias_hoy = db.session.query(Asistencia, Estudiante).join(
        Estudiante, Asistencia.estudiante_id == Estudiante.id
    ).filter(
        db.func.date(Asistencia.fecha) == hoy,
        Asistencia.estado == 'Falta',
        db.func.trim(db.func.lower(Estudiante.turno)) == turno_activo.lower()
    ).all()
    
    lista_ausentes = []
    for aus, est in ausencias_hoy:
        if est:
            lista_ausentes.append({
                'apellidos': est.apellidos,
                'nombres': est.nombres,
                'curso': aus.curso
            })

    lista_ausentes = sorted(lista_ausentes, key=lambda x: (x['curso'], x['apellidos']))

    respuesta = make_response(render_template(
        'reportes/monitor.html',
        ausentes=lista_ausentes,
        fecha_hoy=hoy.strftime('%d/%m/%Y'),
        turno_activo=turno_activo,
        configuracion=configuracion,
        fotos_album=fotos_album,
        fotos_excelencia=fotos_excelencia,
        fotos_valores=fotos_valores
    ))
    
    respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    respuesta.headers['Pragma'] = 'no-cache'
    respuesta.headers['Expires'] = '-1'
    
    return respuesta


# =========================================================================
# CEREMONIA DE PROMOCIÓN Y CLAUSURA
# =========================================================================
@reportes_bp.route('/ceremonia/curso/<curso_nombre>', methods=['GET', 'POST'])
def ceremonia_curso(curso_nombre):
    try:
        curso_actual = curso_nombre.strip()
        
        estudiantes_curso = Estudiante.query.filter(
            db.func.trim(Estudiante.curso) == curso_actual,
            Estudiante.estado != 'Egresado',
            Estudiante.estado != 'Retirado'
        ).all()

        if request.method == 'POST':
            secuencia_cursos_invertida = {
                'NIDITO 1': 'NIDITO 2',
                'NIDITO 2': 'PRE-KINDER',
                'PRE-KINDER': 'KINDER',
                'KINDER': '1RO PRIMARIA',
                '1RO PRIMARIA': '2DO PRIMARIA',
                '2DO PRIMARIA': '3RO PRIMARIA',
                '3RO PRIMARIA': '4TO PRIMARIA',
                '4TO PRIMARIA': '5TO PRIMARIA',
                '5TO PRIMARIA': '6TO PRIMARIA',
                '6TO PRIMARIA': '1RO SECUNDARIA',
                '1RO SECUNDARIA': '2DO SECUNDARIA',
                '2DO SECUNDARIA': '3RO SECUNDARIA',
                '3RO SECUNDARIA': '4TO SECUNDARIA',
                '4TO SECUNDARIA': '5TO SECUNDARIA',
                '5TO SECUNDARIA': '6TO SECUNDARIA',
                '6TO SECUNDARIA': 'Egresados',
                
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
                '6TO DE SECUNDARIA': 'Egresados',
            }

            promovidos_count = 0
            repitentes_count = 0

            for est in estudiantes_curso:
                es_aprobado = getattr(est, 'aprobado', True)
                
                if es_aprobado:
                    curso_upper = curso_actual.upper()
                    if curso_upper in ['6TO SECUNDARIA', '6TO DE SECUNDARIA', 'SEXTO SECUNDARIA', 'SEXTO DE SECUNDARIA']:
                        est.estado = 'Egresado'
                        est.curso = 'Egresados'
                    elif curso_upper in secuencia_cursos_invertida:
                        est.curso = secuencia_cursos_invertida[curso_upper]
                    promovidos_count += 1
                else:
                    repitentes_count += 1

            db.session.commit()
            flash(f"🎉 Promoción del curso {curso_actual} completada con éxito. Promovidos: {promovidos_count}, Repitentes: {repitentes_count}.", "success")
            return redirect(url_for('reportes.ceremonia_curso', curso_nombre=curso_actual))

        lista_ceremonia = []
        for index, est in enumerate(estudiantes_curso):
            if hasattr(est, 'aprobado'):
                aprobado = est.aprobado
            else:
                aprobado = True if index % 5 != 0 else False
                
            lista_ceremonia.append({
                'id': est.id,
                'nombres': est.nombres,
                'apellidos': est.apellidos,
                'aprobado': aprobado,
                'estado_texto': 'APROBADO (Promovido)' if aprobado else 'REITERANTE (Repite)'
            })

        return render_template('reportes/ceremonia_curso.html', 
                               curso_actual=curso_actual, 
                               estudiantes=lista_ceremonia)

    except Exception as e:
        db.session.rollback()
        flash(f"Error al procesar la ceremonia del curso: {str(e)}", "danger")
        return redirect(url_for('reportes.monitor_config'))
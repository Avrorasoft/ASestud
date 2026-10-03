# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: models.py
Proyecto: ASestud-Konetz / Sistema de Gestión Escolar Genérico
Descripción:
    Modelos SQLAlchemy del sistema de gestión escolar.
    IDENTIFICADOR PRINCIPAL: CARNET DE IDENTIDAD (CI)
    El RUDE se mantiene solo como dato informativo.
    DIVISIÓN ACADÉMICA: Niveles (Nidito/Primaria/Secundaria) y Turnos
    (Mañana/Tarde). La Caja es única para toda la institución.
    SISTEMA DE CALIFICACIONES: Paramétrico y dinámico (Cuantitativo para
    Primaria/Secundaria y Cualitativo/Descriptivo para Nidito).
    PORTAL FAMILIAR (PWA): Autenticación segura para tutores con C.I.
    y contraseña personalizable (por defecto '1234').
==============================================================================
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ==============================================================================
# ZONA HORARIA BOLIVIA (UTC-4)
# ==============================================================================

BOLIVIA_TZ = timezone(timedelta(hours=-4))


def ahora_bolivia():
    """
    Devuelve la fecha/hora actual en zona horaria Bolivia (UTC-4).
    """
    return datetime.now(BOLIVIA_TZ)


# ==============================================================================
# NIVELES, TURNOS Y CURSOS (DIVISIÓN ACADÉMICA)
# ==============================================================================

NIVELES = ['Nidito', 'Primaria', 'Secundaria']
TURNOS = ['Mañana', 'Tarde']

CURSOS_POR_NIVEL = {
    'Nidito': ['Nidito 1', 'Nidito 2'],
    'Primaria': [
        '1ro Primaria', '2do Primaria', '3ro Primaria',
        '4to Primaria', '5to Primaria', '6to Primaria'
    ],
    'Secundaria': [
        '1ro Secundaria', '2do Secundaria', '3ro Secundaria',
        '4to Secundaria', '5to Secundaria', '6to Secundaria'
    ],
}


def nivel_de_curso(curso):
    """
    Devuelve el nivel (Nidito/Primaria/Secundaria) al que pertenece un curso.
    """
    if not curso:
        return ''

    for nivel, cursos in CURSOS_POR_NIVEL.items():
        if curso in cursos:
            return nivel

    c = curso.lower()
    if 'nidito' in c:
        return 'Nidito'
    if 'primaria' in c:
        return 'Primaria'
    if 'secundaria' in c:
        return 'Secundaria'

    return ''


# ==============================================================================
# ESTUDIANTE (IDENTIFICADO POR C.I.)
# ==============================================================================

class Estudiante(db.Model):
    __tablename__ = 'estudiantes'

    id = db.Column(db.Integer, primary_key=True)

    # ⭐ C.I. como identificador principal único obligatorio
    ci = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # RUDE queda solo como dato informativo (opcional)
    rude = db.Column(db.String(20), nullable=True, index=True)

    apellidos = db.Column(db.String(100), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    curso = db.Column(db.String(50), nullable=False)

    turno = db.Column(db.String(20), default='Mañana')
    estado = db.Column(db.String(20), default='Activo')
    pension = db.Column(db.Float, nullable=True)

    direccion = db.Column(db.String(200), nullable=True)
    zona = db.Column(db.String(100), nullable=True)
    ciudad = db.Column(db.String(100), nullable=True)
    foto_path = db.Column(db.String(255), default='default.png')

    # Cardex de Salud
    tipo_sangre = db.Column(db.String(10), nullable=True)
    alergias = db.Column(db.Text, nullable=True)
    enfermedades_cronicas = db.Column(db.Text, nullable=True)
    medicamentos_actuales = db.Column(db.String(255), nullable=True)
    medico_nombre = db.Column(db.String(150), nullable=True)
    medico_telefono = db.Column(db.String(20), nullable=True)
    clinica_habitual = db.Column(db.String(150), nullable=True)
    seguro_medico = db.Column(db.String(150), nullable=True)
    observaciones_salud = db.Column(db.Text, nullable=True)
    fecha_actualizacion_salud = db.Column(db.Date, nullable=True)

    # Relaciones con eliminación en cascada
    calificaciones = db.relationship(
        'Calificacion',
        backref='estudiante',
        lazy=True,
        cascade="all, delete-orphan"
    )

    pagos = db.relationship(
        'Pago',
        backref='estudiante',
        lazy=True,
        cascade="all, delete-orphan"
    )

    padres = db.relationship(
        'Padre',
        backref='estudiante',
        lazy=True,
        cascade="all, delete-orphan"
    )

    mensajes = db.relationship(
        'Mensaje',
        backref='estudiante',
        lazy=True,
        cascade="all, delete-orphan"
    )

    respaldos = db.relationship(
        'RespaldoEstudiante',
        backref='estudiante',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Estudiante CI:{self.ci} - {self.apellidos}, {self.nombres}>"


# ==============================================================================
# PADRE / TUTOR (AUTENTICACIÓN PWA CON CONTRASEÑA ASIGNABLE)
# ==============================================================================

class Padre(db.Model):
    __tablename__ = 'padres'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)

    # ⭐ C.I. del tutor como identificador único para el login
    ci = db.Column(db.String(20), unique=True, nullable=False, index=True)

    ci_estudiante = db.Column(db.String(20), nullable=True)
    rude_estudiante = db.Column(db.String(20), nullable=True)

    parentesco = db.Column(db.String(50), nullable=False)
    nombres = db.Column(db.String(150), nullable=False)

    telefono1 = db.Column(db.String(20), nullable=True)
    telefono2 = db.Column(db.String(20), nullable=True)
    telefono3 = db.Column(db.String(20), nullable=True)
    telefono4 = db.Column(db.String(20), nullable=True)

    email = db.Column(db.String(100), nullable=True)
    ocupacion = db.Column(db.String(100), nullable=True)
    foto_path = db.Column(db.String(255), default='default.png')

    # ⭐ Hash de contraseña. Si es NULL, el tutor ingresa con la clave universal '1234'
    contrasena_hash = db.Column(db.String(255), nullable=True)

    def verificar_clave(self, clave_candidata):
        """
        Valida la contraseña:
        - Si aún no tiene contrasena_hash personalizada, valida contra '1234'.
        - Si ya definió su propia clave, verifica el hash criptográfico.
        """
        if not self.contrasena_hash:
            return clave_candidata == '1234'
        return check_password_hash(self.contrasena_hash, clave_candidata)

    def establecer_clave(self, nueva_clave):
        """Asigna un hash criptográfico seguro para la nueva clave personal."""
        self.contrasena_hash = generate_password_hash(nueva_clave)

    def restablecer_clave_universal(self):
        """Vuelve la contraseña al valor universal '1234'."""
        self.contrasena_hash = None

    def __repr__(self):
        return f"<Padre CI:{self.ci} - {self.nombres}>"


# ==============================================================================
# PERSONAL ADMINISTRATIVO (IDENTIFICADO POR C.I.)
# ==============================================================================

class PersonalAdministrativo(db.Model):
    __tablename__ = 'personal_administrativo'

    id = db.Column(db.Integer, primary_key=True)

    ci = db.Column(db.String(20), unique=True, nullable=False, index=True)
    apellidos = db.Column(db.String(100), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)

    cargo = db.Column(db.String(100), nullable=False)
    area = db.Column(db.String(100), nullable=True)

    salario_base = db.Column(db.Float, nullable=True)
    estado = db.Column(db.String(20), default='Activo')

    telefono = db.Column(db.String(50), nullable=True)
    correo = db.Column(db.String(100), nullable=True)
    foto_path = db.Column(db.String(255), default='default.png')

    usuario = db.Column(db.String(50), unique=True, nullable=True)
    contrasena_hash = db.Column(db.String(255), nullable=True)

    adelanto = db.Column(db.Float, default=0.0)
    salario_neto = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f"<PersonalAdministrativo CI:{self.ci} - {self.apellidos}, {self.nombres}>"


# ==============================================================================
# MATERIA
# ==============================================================================

class Materia(db.Model):
    __tablename__ = 'materias'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    curso_id = db.Column(db.String(50), nullable=False)

    profesor_id = db.Column(
        db.Integer,
        db.ForeignKey('profesores.id'),
        nullable=True
    )

    profesor_ref = db.relationship(
        'Profesor',
        backref=db.backref('materias')
    )

    respaldos = db.relationship(
        'RespaldoEstudiante',
        backref='materia',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Materia {self.nombre} - {self.curso_id}>"


# ==============================================================================
# CRITERIOS DE EVALUACIÓN CONFIGURABLES (RÚBRICA DINÁMICA)
# ==============================================================================

class CriterioEvaluacion(db.Model):
    __tablename__ = 'criterios_evaluacion'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    nivel = db.Column(db.String(20), nullable=False)                             # 'Nidito', 'Primaria', 'Secundaria'
    tipo_evaluacion = db.Column(db.String(20), default='NUMERICA')    # 'NUMERICA' o 'CUALITATIVA'

    # Parámetros Cuantitativos (Primaria / Secundaria)
    puntaje_maximo = db.Column(db.Integer, default=0)                           # Asistencia: 10, Participación: 20, etc.
    permite_decimales = db.Column(db.Boolean, default=False)          # False para Asistencia y Participación
    paso_step = db.Column(db.Float, default=1.0)                        # 1.0 (enteros) o 0.1/0.5 (decimales)

    # Parámetros Cualitativos (Nidito / Nivel Inicial)
    opciones_cualitativas = db.Column(db.String(255), nullable=True)
    es_descriptivo = db.Column(db.Boolean, default=False)

    orden = db.Column(db.Integer, default=1)
    activo = db.Column(db.Boolean, default=True)

    materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=True)
    materia = db.relationship('Materia', backref=db.backref('criterios_personalizados', lazy=True))

    def __repr__(self):
        return f"<CriterioEvaluacion {self.nombre} ({self.nivel}) - {self.tipo_evaluacion}>"


# ==============================================================================
# CALIFICACIÓN (HÍBRIDA: CUANTITATIVA Y CUALITATIVA / ASOCIADA POR C.I.)
# ==============================================================================

class Calificacion(db.Model):
    __tablename__ = 'calificaciones'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)

    ci_estudiante = db.Column(db.String(20), nullable=False, index=True)
    rude_estudiante = db.Column(db.String(20), nullable=True)

    materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=False)
    materia = db.relationship(
        'Materia',
        backref=db.backref('calificaciones', cascade='all, delete-orphan')
    )

    periodo = db.Column(db.String(50), nullable=False, default='1er Trimestre')
    fecha = db.Column(db.Date, nullable=False, default=datetime.now().date)
    tipo = db.Column(db.String(50), nullable=True)
    tipo_evaluacion_id = db.Column(db.Integer, nullable=True)

    # Componente Cuantitativo (Primaria / Secundaria - Total sobre 100)
    nota = db.Column(db.Float, nullable=True)
    desglose_json = db.Column(db.Text, nullable=True)

    # Componente Cualitativo / Descriptivo (Nidito)
    valoracion_cualitativa = db.Column(db.String(100), nullable=True)
    informe_descriptivo = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Calificacion CI:{self.ci_estudiante} - {self.periodo}: {self.nota or self.valoracion_cualitativa}>"


# ==============================================================================
# RESPALDO ESTUDIANTE (GALERÍA DE MÚLTIPLES ARCHIVOS DOCUMENTALES Y FOTOGRÁFICOS)
# ==============================================================================

class RespaldoEstudiante(db.Model):
    __tablename__ = 'respaldo_estudiante'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=False)
    periodo = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=ahora_bolivia)

    def __repr__(self):
        return f"<RespaldoEstudiante EstID:{self.estudiante_id} - {self.filename}>"


# ==============================================================================
# PROFESOR Y PERSONAL (UNIFICADO)
# ==============================================================================

class Profesor(db.Model):
    __tablename__ = 'profesores'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    ci = db.Column(db.String(20), unique=True, nullable=False, index=True)
    apellidos = db.Column(db.String(100), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    especialidad = db.Column(db.String(100), nullable=True)
    nivel = db.Column(db.String(20), nullable=True)
    turno = db.Column(db.String(20), default='Mañana')
    salario_base = db.Column(db.Float, nullable=True)
    estado = db.Column(db.String(20), default='Activo')
    telefono = db.Column(db.String(50), nullable=True)
    correo = db.Column(db.String(100), nullable=True)
    foto_path = db.Column(db.String(255), default='default.png')
    usuario = db.Column(db.String(50), unique=True, nullable=True)
    contrasena_hash = db.Column(db.String(255), nullable=True)
    adelanto = db.Column(db.Float, default=0.0)
    salario_neto = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f"<Profesor - CI:{self.ci} {self.apellidos}, {self.nombres}>"


# ==============================================================================
# PAGO DE PERSONAL (ASOCIADO POR C.I.)
# ==============================================================================

class PagoPersonal(db.Model):
    __tablename__ = 'pago_personal'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    persona_id = db.Column(db.Integer, nullable=False)
    ci_persona = db.Column(db.String(20), nullable=True, index=True)
    nombre_persona = db.Column(db.String(150), nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    monto_base = db.Column(db.Float, nullable=False)
    monto_adelanto = db.Column(db.Float, default=0.0)
    monto_neto_pagado = db.Column(db.Float, nullable=False)
    motivo = db.Column(db.String(200), default='Adelanto de Sueldo')
    fecha_pago = db.Column(db.Date, nullable=False)
    metodo_pago = db.Column(db.String(20), default='Efectivo')
    estado = db.Column(db.String(20), default='Pagado')

    def __repr__(self):
        return f"<PagoPersonal - CI:{self.ci_persona} {self.nombre_persona}>"


# ==============================================================================
# PAGO DE ESTUDIANTE (ASOCIADO POR C.I.)
# ==============================================================================

class Pago(db.Model):
    __tablename__ = 'pagos'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)

    ci_estudiante = db.Column(db.String(20), nullable=False, index=True)
    rude_estudiante = db.Column(db.String(20), nullable=True)

    mes = db.Column(db.String(20), nullable=False)
    anio = db.Column(db.Integer, nullable=False)

    monto_total = db.Column(db.Float, nullable=False)
    descuento = db.Column(db.Float, nullable=True)
    monto_pagado = db.Column(db.Float, nullable=False)

    fecha_pago = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(20), default='Pendiente')
    metodo_pago = db.Column(db.String(20), default='Efectivo')
    turno_responsable = db.Column(db.String(20), nullable=False, default='Mañana')
    tipo_concepto = db.Column(db.String(50), default='Pensión')
    detalle_concepto = db.Column(db.String(150), default='')

    def __repr__(self):
        return f"<Pago - CI:{self.ci_estudiante} Turno:{self.turno_responsable} {self.mes}/{self.anio}>"


# ==============================================================================
# FALTA (ASOCIADA POR C.I.)
# ==============================================================================

class Falta(db.Model):
    __tablename__ = 'faltas'

    id = db.Column(db.Integer, primary_key=True)
    tipo_sujeto = db.Column(db.String(20), nullable=False)
    sujeto_id = db.Column(db.Integer, nullable=False)

    ci_sujeto = db.Column(db.String(20), nullable=True, index=True)
    rude_estudiante = db.Column(db.String(20), nullable=True)

    fecha = db.Column(db.Date, nullable=False)
    tipo_falta = db.Column(db.String(50), nullable=False)
    observaciones = db.Column(db.Text, nullable=True)

    estado = db.Column(db.String(20), default='Pendiente')
    archivo_adjunto = db.Column(db.String(255), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=ahora_bolivia)

    def __repr__(self):
        return f"<Falta {self.tipo_sujeto} CI:{self.ci_sujeto}>"


class Gasto(db.Model):
    __tablename__ = 'gastos'

    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, nullable=False)

    proveedor = db.Column(db.String(100), nullable=True)
    responsable = db.Column(db.String(100), nullable=True)
    metodo_pago = db.Column(db.String(20), default='Efectivo')
    archivo = db.Column(db.String(255), nullable=True)
    
    # Definido con nullable=True para que las consultas antiguas no fallen antes de la migración automática
    estado = db.Column(db.String(20), nullable=True, default='Activo')

    def __repr__(self):
        return f"<Gasto {self.categoria}>"


# ==============================================================================
# MENSAJE / CHAT
# ==============================================================================

class Mensaje(db.Model):
    __tablename__ = 'mensajes'

    id = db.Column(db.Integer, primary_key=True)
    destinatario = db.Column(db.String(100), nullable=False)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=True)
    telefono = db.Column(db.String(20), nullable=False)

    tipo_mensaje = db.Column(db.String(50), nullable=False)
    contenido = db.Column(db.Text, nullable=True)

    fecha_envio = db.Column(db.DateTime, default=ahora_bolivia)
    remitente = db.Column(db.String(20), default='Institución')
    leido = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Mensaje {self.tipo_mensaje}>"


# ==============================================================================
# EGRESADO (IDENTIFICADO POR C.I.)
# ==============================================================================

class Egresado(db.Model):
    __tablename__ = 'egresados'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id_original = db.Column(db.Integer, unique=True, nullable=False)

    ci = db.Column(db.String(20), nullable=True, index=True)
    rude = db.Column(db.String(20), unique=True, nullable=False, index=True)

    apellidos = db.Column(db.String(100), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=True)

    curso_final = db.Column(db.String(50), nullable=False)
    anio_egreso = db.Column(db.Integer, nullable=False)
    estado_egreso = db.Column(db.String(20), nullable=False)

    nombre_tutor = db.Column(db.String(150), nullable=True)
    telefono_tutor = db.Column(db.String(20), nullable=True)

    fecha_archivo = db.Column(db.DateTime, default=ahora_bolivia)

    historial_notas = db.relationship(
        'HistorialCalificacion',
        backref='egresado',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Egresado CI:{self.ci} - {self.apellidos}, {self.nombres}>"


# ==============================================================================
# HISTORIAL DE CALIFICACIONES DE EGRESADOS (POR C.I.)
# ==============================================================================

class HistorialCalificacion(db.Model):
    __tablename__ = 'historial_calificaciones'

    id = db.Column(db.Integer, primary_key=True)
    egresado_id = db.Column(db.Integer, db.ForeignKey('egresados.id'), nullable=False)

    ci_egresado = db.Column(db.String(20), nullable=True, index=True)
    rude_egresado = db.Column(db.String(20), nullable=True)

    gestion = db.Column(db.Integer, nullable=False)
    materia = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    periodo = db.Column(db.String(20), nullable=True)
    nota = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<HistorialCalificacion {self.materia}>"


# ==============================================================================
# PORTAL DEL PROFESOR: TAREAS Y SEGUIMIENTO PEDAGÓGICO (PIZARRA ESCOLAR)
# ==============================================================================

class Tarea(db.Model):
    __tablename__ = 'tareas'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=False)

    titulo = db.Column(db.String(150), nullable=False)
    indicaciones = db.Column(db.Text, nullable=False)

    fecha_asignacion = db.Column(db.DateTime, default=ahora_bolivia)
    fecha_entrega = db.Column(db.DateTime, nullable=False)
    puntaje_maximo = db.Column(db.Float, default=100.0)
    archivo_adjunto = db.Column(db.String(255), nullable=True)

    # Relación bidireccional con Materia
    materia = db.relationship(
        'Materia',
        backref=db.backref('tareas', lazy=True, cascade='all, delete-orphan')
    )

    def __repr__(self):
        return f"<Tarea {self.id}: {self.titulo} - Materia ID: {self.materia_id}>"


# ==============================================================================
# PORTAL DEL PROFESOR: ASISTENCIAS (POR C.I.)
# ==============================================================================

class Asistencia(db.Model):
    __tablename__ = 'asistencias'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=False)

    ci_estudiante = db.Column(db.String(20), nullable=False, index=True)
    rude_estudiante = db.Column(db.String(20), nullable=True)

    fecha = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(20), default='Presente')
    observacion = db.Column(db.Text, nullable=True)
    fecha_registro = db.Column(db.DateTime, default=ahora_bolivia)

    estudiante = db.relationship(
        'Estudiante',
        backref=db.backref('asistencias', cascade='all, delete-orphan')
    )

    materia = db.relationship(
        'Materia',
        backref=db.backref('asistencias', cascade='all, delete-orphan')
    )

    def __repr__(self):
        return f"<Asistencia {self.fecha}>"


# ==============================================================================
# PORTAL DEL PROFESOR: REPORTES PEDAGÓGICOS
# ==============================================================================

class ReportePedagogico(db.Model):
    __tablename__ = 'reportes_pedagogicos'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    profesor_id = db.Column(db.Integer, db.ForeignKey('profesores.id'), nullable=True)
    materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=True)

    asunto = db.Column(db.String(150), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)

    fecha = db.Column(db.DateTime, default=ahora_bolivia)
    leido = db.Column(db.Boolean, default=False)

    estudiante = db.relationship(
        'Estudiante',
        backref=db.backref('reportes_pedagogicos', cascade='all, delete-orphan')
    )

    profesor = db.relationship(
        'Profesor',
        backref=db.backref('reportes_pedagogicos', cascade='all, delete-orphan')
    )

    materia = db.relationship(
        'Materia',
        backref=db.backref('reportes_pedagogicos', cascade='all, delete-orphan')
    )

    def __repr__(self):
        return f"<ReportePedagogico {self.asunto}>"


# ==============================================================================
# INFORME ECONÓMICO CONFIDENCIAL
# ==============================================================================

class InformeEconomico(db.Model):
    __tablename__ = 'informes_economicos'

    id = db.Column(db.Integer, primary_key=True)

    tipo_informe = db.Column(db.String(20), nullable=False)
    fecha_generacion = db.Column(db.DateTime, default=ahora_bolivia)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)

    ingresos_efectivo = db.Column(db.Float, default=0.0)
    ingresos_bancario = db.Column(db.Float, default=0.0)
    total_ingresos = db.Column(db.Float, default=0.0)

    gastos_efectivo = db.Column(db.Float, default=0.0)
    gastos_bancario = db.Column(db.Float, default=0.0)
    total_gastos = db.Column(db.Float, default=0.0)

    saldo_efectivo = db.Column(db.Float, default=0.0)
    saldo_bancario = db.Column(db.Float, default=0.0)
    saldo_total = db.Column(db.Float, default=0.0)

    detalle_json = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<InformeEconomico {self.tipo_informe} {self.fecha_inicio} - {self.fecha_fin}>"


# ==============================================================================
# CONFIGURACIÓN SUPERADMIN E INSTITUCIÓN
# ==============================================================================

class ConfiguracionSuperadmin(db.Model):
    __tablename__ = 'configuracion_superadmin'

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=True)
    descripcion = db.Column(db.String(255), nullable=True)


class ConfiguracionInstitucion(db.Model):
    __tablename__ = 'configuracion_institucion'

    id = db.Column(db.Integer, primary_key=True)
    institucion_linea1 = db.Column(db.String(150), default='Sistema de Gestión Escolar')
    institucion_linea2 = db.Column(db.String(150), default='')
    institucion_linea3 = db.Column(db.String(150), default='')
    institucion_logo = db.Column(db.String(255), default='uploads/logo_institucion.png')


# ==============================================================================
# INTERCEPTORES DE EVENTOS PARA EVITAR REGISTROS HUÉRFANOS
# ==============================================================================

@event.listens_for(Estudiante, 'before_delete')
def interceptar_eliminacion_estudiante(mapper, connection, target):
    """Elimina faltas asociadas al estudiante antes de borrarlo."""
    connection.execute(
        Falta.__table__.delete().where(
            (Falta.__table__.c.tipo_sujeto == 'Estudiante') &
            (Falta.__table__.c.sujeto_id == target.id)
        )
    )


@event.listens_for(Profesor, 'before_delete')
def interceptar_eliminacion_profesor(mapper, connection, target):
    """
    Antes de eliminar un profesor:
    1. Deja sus materias disponibles (profesor_id = NULL).
    2. Elimina sus faltas.
    3. Elimina sus pagos de personal.
    """
    connection.execute(
        Materia.__table__.update().where(
            Materia.__table__.c.profesor_id == target.id
        ).values(profesor_id=None)
    )

    connection.execute(
        Falta.__table__.delete().where(
            (Falta.__table__.c.tipo_sujeto == 'Profesor') &
            (Falta.__table__.c.sujeto_id == target.id)
        )
    )

    connection.execute(
        PagoPersonal.__table__.delete().where(
            (PagoPersonal.__table__.c.tipo == 'Profesor') &
            (PagoPersonal.__table__.c.persona_id == target.id)
        )
    )


@event.listens_for(PersonalAdministrativo, 'before_delete')
def interceptar_eliminacion_personal(mapper, connection, target):
    """Elimina faltas y pagos asociados al personal administrativo antes de borrarlo."""
    connection.execute(
        Falta.__table__.delete().where(
            Falta.__table__.c.tipo_sujeto.in_(['Personal', 'PersonalAdministrativo', 'Administrativo']) &
            (Falta.__table__.c.sujeto_id == target.id)
        )
    )

    connection.execute(
        PagoPersonal.__table__.delete().where(
            PagoPersonal.__table__.c.tipo.in_(['Personal', 'PersonalAdministrativo', 'Administrativo']) &
            (PagoPersonal.__table__.c.persona_id == target.id)
        )
    )


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    
    # ⭐ AUTOCORRECCIÓN AUTOMÁTICA DE ESQUEMA PARA LA TABLA GASTOS
    try:
        cursor.execute("PRAGMA table_info(gastos);")
        columnas = [col[1] for col in cursor.fetchall()]
        if columnas and 'estado' not in columnas:
            cursor.execute("ALTER TABLE gastos ADD COLUMN estado TEXT DEFAULT 'Activo';")
            dbapi_connection.commit()
    except Exception:
        pass

    cursor.close()


# ==============================================================================
# SEGUIMIENTO PEDAGÓGICO: ENTREGAS DE TAREAS
# ==============================================================================

class EntregaTarea(db.Model):
    __tablename__ = 'entregas_tareas'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    tarea_id = db.Column(db.Integer, db.ForeignKey('tareas.id'), nullable=False)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    fecha_presentacion = db.Column(db.DateTime, default=datetime.now)
    archivo_respuesta = db.Column(db.String(255), nullable=True)
    comentario_alumno = db.Column(db.Text, nullable=True)
    calificacion = db.Column(db.Float, nullable=True)
    retroalimentacion = db.Column(db.Text, nullable=True)

    # Relaciones bidireccionales con Tarea y Estudiante
    tarea = db.relationship('Tarea', backref=db.backref('entregas', lazy=True, cascade='all, delete-orphan'))
    estudiante = db.relationship('Estudiante', backref=db.backref('entregas_tareas', lazy=True))

    def __repr__(self):
        return f"<EntregaTarea {self.tarea_id} - Estudiante ID: {self.estudiante_id}>"
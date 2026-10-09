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
import sqlite3

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
# NIVELES, TURNOS Y CURSOS (DIVISIÓN ACADÉMICA DINÁMICA)
# ==============================================================================

NIVELES = ['Nidito', 'Primaria', 'Secundaria']
TURNOS = ['Mañana', 'Tarde']

CURSOS_POR_NIVEL = {
    'Nidito': ['Nidito 1', 'Nidito 2', 'Nidito 3'],
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
    Devuelve el nivel (Nidito/Primaria/Secundaria) al que pertenece un curso,
    incluso si contiene paralelos agregados (ej: '3ro Primaria A', 'Nidito 2 B').
    """
    if not curso:
        return ''

    c = str(curso).strip().lower()

    # Detección para Nidito / Nivel Inicial
    if any(k in c for k in ['nidito', 'inicial', 'kinder', 'kínder', 'pre-kinder', 'prekinder']):
        return 'Nidito'

    # Detección para Primaria
    if any(k in c for k in ['primaria', 'prim.']) or ('1ro' in c and 'secundaria' not in c and 'sec' not in c and 'nidito' not in c):
        if 'secundaria' not in c and 'sec' not in c:
            return 'Primaria'

    # Detección para Secundaria
    if any(k in c for k in ['secundaria', 'sec.', 'bachillerato']):
        return 'Secundaria'

    # Búsqueda en listas base predefinidas
    for nivel, cursos in CURSOS_POR_NIVEL.items():
        for base in cursos:
            if base.lower() in c:
                return nivel

    return 'Primaria'


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
    
    # ⭐ CAMPO TURNO AGREGADO PARA CONTROL Y AUDITORÍA
    turno = db.Column(db.String(20), nullable=True, default='Mañana')

    def __repr__(self):
        return f"<PagoPersonal - CI:{self.ci_persona} {self.nombre_persona} Turno:{self.turno}>"


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


# ==============================================================================
# GASTO OPERATIVO
# ==============================================================================

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
    
    estado = db.Column(db.String(20), nullable=True, default='Activo')

    # ⭐ CAMPO TURNO AGREGADO PARA CONTROL Y AUDITORÍA
    turno = db.Column(db.String(20), nullable=True, default='Mañana')

    def __repr__(self):
        return f"<Gasto {self.categoria} Turno:{self.turno}>"


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

    materia = db.relationship(
        'Materia',
        backref=db.backref('tareas', lazy=True, cascade='all, delete-orphan')
    )

    def __repr__(self):
        return f"<Tarea {self.id}: {self.titulo} - Materia ID: {self.materia_id}>"


# ==============================================================================
# SISTEMA DE ASISTENCIAS (AHORA EXCLUSIVO PARA LA REGENTE)
# ==============================================================================

class Asistencia(db.Model):
    __tablename__ = 'asistencias'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    
    # Este campo originó el error. Al crearse la BD antes, seguía exigiendo que no sea Nulo.
    # En el pragma de abajo aplicamos la cirugía automática.
    materia_id = db.Column(db.Integer, db.ForeignKey('materias.id'), nullable=True)

    ci_estudiante = db.Column(db.String(20), nullable=False, index=True)
    rude_estudiante = db.Column(db.String(20), nullable=True)

    curso = db.Column(db.String(50), nullable=True)
    fecha = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(20), default='Presente')
    observacion = db.Column(db.Text, nullable=True)
    
    # ⭐ NUEVO CAMPO AÑADIDO: Documento para justificar faltas
    archivo_adjunto = db.Column(db.String(255), nullable=True)
    
    notificado_padre = db.Column(db.Boolean, default=False)
    
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
        return f"<Asistencia {self.fecha} - Estudiante CI: {self.ci_estudiante}>"


# ==============================================================================
# CONTROL DIARIO DE ASISTENCIA (BLOQUEO DE REGISTRO PARA LA REGENTE)
# ==============================================================================

class ControlAsistenciaDiaria(db.Model):
    __tablename__ = 'control_asistencia_diaria'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    curso = db.Column(db.String(50), nullable=False)
    bloqueado = db.Column(db.Boolean, default=True)
    registrado_por = db.Column(db.String(100), default='Regente')
    fecha_registro = db.Column(db.DateTime, default=ahora_bolivia)

    def __repr__(self):
        return f"<ControlAsistenciaDiaria {self.curso} - {self.fecha} (Bloqueado:{self.bloqueado})>"


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
    
    modalidad_descuento_faltas = db.Column(db.String(20), default='Proporcional') 
    puntaje_base_asistencia = db.Column(db.Float, default=10.0)
    descuento_fijo_por_falta = db.Column(db.Float, default=2.0)
    dias_habiles_trimestre = db.Column(db.Integer, default=60)


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
    
    try:
        cursor.execute("PRAGMA table_info(gastos);")
        columnas = [col[1] for col in cursor.fetchall()]
        if columnas:
            if 'estado' not in columnas:
                cursor.execute("ALTER TABLE gastos ADD COLUMN estado TEXT DEFAULT 'Activo';")
            if 'turno' not in columnas:
                cursor.execute("ALTER TABLE gastos ADD COLUMN turno VARCHAR(20) DEFAULT 'Mañana';")
            dbapi_connection.commit()
    except Exception:
        pass

    try:
        cursor.execute("PRAGMA table_info(pago_personal);")
        columnas_pago = [col[1] for col in cursor.fetchall()]
        if columnas_pago and 'turno' not in columnas_pago:
            cursor.execute("ALTER TABLE pago_personal ADD COLUMN turno VARCHAR(20) DEFAULT 'Mañana';")
            dbapi_connection.commit()
    except Exception:
        pass
        
    try:
        cursor.execute("PRAGMA table_info(configuracion_institucion);")
        columnas = [col[1] for col in cursor.fetchall()]
        if columnas and 'modalidad_descuento_faltas' not in columnas:
            cursor.execute("ALTER TABLE configuracion_institucion ADD COLUMN modalidad_descuento_faltas TEXT DEFAULT 'Proporcional';")
            cursor.execute("ALTER TABLE configuracion_institucion ADD COLUMN puntaje_base_asistencia REAL DEFAULT 10.0;")
            cursor.execute("ALTER TABLE configuracion_institucion ADD COLUMN descuento_fijo_por_falta REAL DEFAULT 2.0;")
            cursor.execute("ALTER TABLE configuracion_institucion ADD COLUMN dias_habiles_trimestre INTEGER DEFAULT 60;")
            dbapi_connection.commit()
    except Exception:
        pass

    # ⭐ AUTOCORRECCIÓN PARA ASISTENCIAS CON MAPEO EXACTO DE COLUMNAS
    try:
        cursor.execute("PRAGMA table_info(asistencias);")
        columnas_asis = cursor.fetchall()
        columnas = [col[1] for col in columnas_asis]
        
        # 1. Agregar las nuevas columnas si no existen
        if columnas and 'curso' not in columnas:
            cursor.execute("ALTER TABLE asistencias ADD COLUMN curso TEXT;")
            cursor.execute("ALTER TABLE asistencias ADD COLUMN notificado_padre BOOLEAN DEFAULT 0;")
            dbapi_connection.commit()
            
        # 2. Agregar columna archivo_adjunto
        if columnas and 'archivo_adjunto' not in columnas:
            cursor.execute("ALTER TABLE asistencias ADD COLUMN archivo_adjunto TEXT;")
            dbapi_connection.commit()
            
        # Refrescar info de columnas para la reconstrucción final
        cursor.execute("PRAGMA table_info(asistencias);")
        columnas_asis = cursor.fetchall()

        # 3. Cirugía reconstructiva para eliminar el bloqueo de materia_id (NOT NULL)
        # Identificar si materia_id exige ser NO NULO (col[3] es la bandera notnull)
        for col in columnas_asis:
            if col[1] == 'materia_id' and col[3] == 1:
                cursor.execute("CREATE TABLE asistencias_temporal AS SELECT * FROM asistencias;")
                cursor.execute("DROP TABLE asistencias;")
                
                cursor.execute("""
                    CREATE TABLE asistencias (
                        id INTEGER NOT NULL, 
                        estudiante_id INTEGER NOT NULL, 
                        materia_id INTEGER, 
                        ci_estudiante VARCHAR(20) NOT NULL, 
                        rude_estudiante VARCHAR(20), 
                        curso TEXT, 
                        fecha DATE NOT NULL, 
                        estado VARCHAR(20), 
                        observacion TEXT, 
                        archivo_adjunto TEXT,
                        notificado_padre BOOLEAN DEFAULT 0, 
                        fecha_registro DATETIME, 
                        PRIMARY KEY (id), 
                        FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
                        FOREIGN KEY(materia_id) REFERENCES materias (id)
                    );
                """)
                
                # Inserción con mapeo explícito para evitar mezclas de datos por alteraciones previas
                cursor.execute("""
                    INSERT INTO asistencias (id, estudiante_id, materia_id, ci_estudiante, rude_estudiante, curso, fecha, estado, observacion, archivo_adjunto, notificado_padre, fecha_registro)
                    SELECT id, estudiante_id, materia_id, ci_estudiante, rude_estudiante, curso, fecha, estado, observacion, archivo_adjunto, notificado_padre, fecha_registro 
                    FROM asistencias_temporal;
                """)
                cursor.execute("DROP TABLE asistencias_temporal;")
                cursor.execute("CREATE INDEX ix_asistencias_ci_estudiante ON asistencias (ci_estudiante);")
                dbapi_connection.commit()
                break
    except Exception as e:
        print(f"Error en Pragma Asistencias: {e}")

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

    tarea = db.relationship(
        'Tarea',
        backref=db.backref('entregas', lazy=True, cascade='all, delete-orphan')
    )
    estudiante = db.relationship(
        'Estudiante',
        backref=db.backref('entregas_tareas', lazy=True)
    )

    def __repr__(self):
        return f"<EntregaTarea {self.tarea_id} - Estudiante ID: {self.estudiante_id}>"
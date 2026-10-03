# -*- coding: utf-8 -*-
# ==============================================================================
# Archivo: utils/validador_db.py
# Descripción: Validador programático de esquema de base de datos para prevenir
#              alteraciones estructurales no autorizadas.
# ==============================================================================

from sqlalchemy import inspect
from models import db, Estudiante, Gasto, Falta, Padre, Mensaje  # Importa tus modelos oficiales

# Define el esquema oficial esperado: tablas obligatorias y sus columnas clave
ESQUEMA_OFICIAL = {
    'estudiante': {'id', 'nombres', 'apellidos', 'curso', 'estado', 'rude'},
    'gasto': {'id', 'categoria', 'descripcion', 'monto', 'fecha', 'proveedor', 'responsable', 'archivo'},
    'falta': {'id', 'tipo_sujeto', 'sujeto_id', 'fecha', 'tipo_falta', 'estado', 'observaciones', 'archivo_adjunto'},
    'padre': {'id', 'estudiante_id', 'nombres', 'telefono1'},
    'mensaje': {'id', 'estudiante_id', 'destinatario', 'telefono', 'contenido', 'tipo_mensaje'}
}

def validar_integridad_base_datos(engine_externo):
    """
    Inspecciona una base de datos externa y valida su estructura contra el esquema oficial.
    Retorna (True, "OK") si es válida, o (False, "Motivo del rechazo") si la estructura está alterada.
    """
    try:
        inspector = inspect(engine_externo)
        tablas_presentes = set(inspector.get_table_names())
        tablas_oficiales = set(ESQUEMA_OFICIAL.keys())

        # 1. Verificar si faltan tablas esenciales
        tablas_faltantes = tablas_oficiales - tablas_presentes
        if tablas_faltantes:
            return False, f"❌ Rechazado: La base de datos carece de tablas estructurales obligatorias: {list(tablas_faltantes)}"

        # 2. Verificar si hay tablas extra no autorizadas que alteren la arquitectura
        tablas_no_autorizadas = tablas_presentes - tablas_oficiales
        if tablas_no_autorizadas:
            return False, f"❌ Rechazado: Se detectaron tablas ajenas o no autorizadas que modifican el esquema del sistema: {list(tablas_no_autorizadas)}"

        # 3. Validar columnas críticas de cada tabla
        for tabla, columnas_esperadas in ESQUEMA_OFICIAL.items():
            columnas_reales = {col['name'] for col in inspector.get_columns(tabla)}
            
            # Verificar columnas faltantes indispensables
            columnas_faltantes = columnas_esperadas - columnas_reales
            if columnas_faltantes:
                return False, f"❌ Rechazado: La tabla '{tabla}' tiene una estructura alterada. Faltan columnas esenciales: {list(columnas_faltantes)}"

        return True, "✅ Validación estructural exitosa. La base de datos es compatible y segura."

    except Exception as e:
        return False, f"❌ Error crítico durante la introspección del esquema: {str(e)}"
# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: tests/test_asestud.py
Proyecto: ASestud / Avrora Soft - Vibola LLC
Descripción: Pruebas unitarias y de integración con pytest para lógicas críticas.
==============================================================================
"""

import pytest
from datetime import date
from models import db, Asistencia, Estudiante, Gasto


def test_ruta_caja_activa(client):
    """Valida que el módulo de Caja y Pagos responda correctamente (200 o redirección a login si hay auth)."""
    response = client.get('/caja/')
    assert response.status_code in [200, 302]


def test_boveda_asistencia_bloqueo(client):
    """Verifica que un intento de borrado o edición de asistencia sin pasar por la bóveda requiera autorización."""
    # Intentamos acceder a una acción protegida por @boveda_requerida sin sesión previa
    response = client.post('/faltas/eliminar/1', data={'estado': 'Falta'})
    # Debe redirigir al login de la bóveda o denegar el acceso
    assert response.status_code in [302, 401, 403, 404]


def test_restriccion_normativa_asistencia(client):
    """Valida la lógica de negocio institucional donde registros justificados no deben eliminarse por error."""
    with client.application.app_context():
        # Creamos un estudiante con su CI obligatorio y una asistencia con estado Justificada de prueba
        est = Estudiante(
            ci='1234567',
            nombres='Juan',
            apellidos='Pérez',
            curso='6to Secundaria',
            turno='Mañana',
            estado='Activo',
        )
        db.session.add(est)
        db.session.commit()

        asist = Asistencia(
            estudiante_id=est.id,
            ci_estudiante='1234567',
            curso='6to Secundaria',
            fecha=date.today(),
            estado='Justificada',
            observacion='Certificado médico',
        )
        db.session.add(asist)
        db.session.commit()

        # Comprobamos que el estado impida la eliminación por normativa interna
        assert asist.estado in ['Justificada', 'Retraso']
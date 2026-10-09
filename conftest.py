# -*- coding: utf-8 -*-
"""
==============================================================================
Archivo: conftest.py
Proyecto: ASestud / Avrora Soft - Vibola LLC
Descripción: Configuración y fixtures globales para pytest en Flask.
==============================================================================
"""

import pytest
from app import app, db


@pytest.fixture
def client():
  """Configura un cliente de prueba para la aplicación Flask con BD en memoria."""
  app.config['TESTING'] = True
  app.config['WTF_CSRF_ENABLED'] = False  # Desactiva CSRF para facilitar pruebas POST
  app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

  with app.test_client() as client:
    with app.app_context():
      db.create_all()
      yield client
      db.session.remove()
      db.drop_all()
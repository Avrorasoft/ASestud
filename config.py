# -*- coding: utf-8 -*-
import os

# RUTA DIRECTA Y ABSOLUTA EN LA RAÍZ DEL DISCO C:\
BASE_SYSTEM_DIR = r"C:\ASestud"

# Asegurar que la estructura principal exista en C:\ASestud
if not os.path.exists(BASE_SYSTEM_DIR):
    try:
        os.makedirs(BASE_SYSTEM_DIR, exist_ok=True)
    except Exception:
        pass

# Definir la carpeta de subidas de archivos (fotos, PDFs, comprobantes)
UPLOAD_FOLDER = os.path.join(BASE_SYSTEM_DIR, "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Directorio de datos / base de datos dentro de C:\ASestud
DATA_DIR = BASE_SYSTEM_DIR
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

import cloudinary

cloudinary.config(
    cloud_name="tu_cloud_name",
    api_key="tu_api_key",
    api_secret="tu_api_secret",
    secure=True
)

class Config:
    BASE_DIR = BASE_SYSTEM_DIR
    DATA_DIR = DATA_DIR
    UPLOAD_FOLDER = UPLOAD_FOLDER
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-por-defecto'
    DB_NAME = 'colegio_vaca_diez.db'
    DB_PATH = os.path.join(DATA_DIR, DB_NAME)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + DB_PATH.replace('\\', '/')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
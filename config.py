import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'instance')
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
    BASE_DIR = BASE_DIR
    DATA_DIR = DATA_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-por-defecto'
    DB_NAME = 'colegio_vaca_diez.db'
    DB_PATH = os.path.join(DATA_DIR, DB_NAME)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + DB_PATH.replace('\\', '/')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

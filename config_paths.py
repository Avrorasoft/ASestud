import os
import sys

# Identificadores de la empresa y aplicación
COMPANY_NAME = "AvroraSoft"
APP_NAME = "ASestud"

def get_base_dir():
    """
    Devuelve la ruta base del proyecto.
    Si está empaquetado con PyInstaller, usa la carpeta temporal _MEIPASS.
    Si está en desarrollo, usa la ruta del script.
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))

def get_appdata_dir():
    """
    Obtiene la ruta %APPDATA% del usuario en Windows y crea 
    la estructura de carpetas segura para Avrora Soft.
    """
    if sys.platform.startswith('win'):
        appdata = os.environ.get('APPDATA')
        if not appdata:
            appdata = os.path.expanduser('~')
    else:
        # Fallback de seguridad en caso de ejecución en Linux/Mac
        appdata = os.path.expanduser('~/.config')
    
    # Ruta final: C:\Users\Usuario\AppData\Roaming\AvroraSoft\ASestud
    path = os.path.join(appdata, COMPANY_NAME, APP_NAME)
    
    # Crear carpetas de persistencia si no existen
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(path, 'database'), exist_ok=True)
    
    return path

# Variables globales para importar en todo el proyecto
BASE_DIR = get_base_dir()
APPDATA_DIR = get_appdata_dir()

# Rutas críticas predefinidas
DB_PATH = os.path.join(APPDATA_DIR, 'database', 'asestud.db')
UPLOAD_FOLDER = os.path.join(APPDATA_DIR, 'uploads')
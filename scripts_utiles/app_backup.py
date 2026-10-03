import os
import zipfile
from datetime import datetime
from flask import Flask, render_template_string, send_file, redirect, url_for

app = Flask(__name__)

# Ruta correcta de tu proyecto y carpeta de respaldos
PROYECTO_DIR = r"D:\colegio_vaca_diez"
BACKUP_DIR = r"D:\colegio_vaca_diez_backups"

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# Elementos y directorios temporales que se excluirán del respaldo
ELEMENTOS_EXCLUIDOS = {
    'build',
    '.dart_tool',
    '.idea',
    '.vscode',
    'ios/Pods',
    'ios/.symlinks',
    'android/.gradle',
    'windows/flutter/ephemeral',
    'linux/flutter/ephemeral',
    'macos/flutter/ephemeral',
    '.pub'
}

@app.route('/')
def index():
    respaldos = []
    if os.path.exists(BACKUP_DIR):
        for f in os.listdir(BACKUP_DIR):
            if f.endswith('.zip'):
                ruta_completa = os.path.join(BACKUP_DIR, f)
                tamano = os.path.getsize(ruta_completa) / (1024 * 1024)
                respaldos.append({'nombre': f, 'tamano': round(tamano, 2)})
    
    html_template = '''
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <title>Respaldo Optimizado - Colegio Vaca Diez</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }
            .container { max-width: 850px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
            h1 { color: #333; font-size: 22px; }
            p { color: #666; }
            .btn { display: inline-block; background: #0038ff; color: white; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 10px; }
            .btn:hover { background: #002db3; }
            table { width: 100%; border-collapse: collapse; margin-top: 25px; }
            th, td { padding: 12px; border-bottom: 1px solid #ddd; text-align: left; }
            th { background-color: #f8f9fa; color: #333; }
            .download-link { color: #0038ff; font-weight: bold; text-decoration: none; }
            .download-link:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Panel de Respaldo Limpio - Colegio Vaca Diez</h1>
            <p>Directorio analizado: <code>D:\\colegio_vaca_diez</code></p>
            <a href="/crear" class="btn">Generar Respaldo Optimizado Ahora</a>
            
            <h2>Historial de Respaldos</h2>
            <table>
                <thead>
                    <tr>
                        <th>Nombre del Archivo ZIP</th>
                        <th>Tamaño</th>
                        <th>Acción</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in respaldos %}
                    <tr>
                        <td>{{ r.nombre }}</td>
                        <td>{{ r.tamano }} MB</td>
                        <td><a href="/descargar/{{ r.nombre }}" class="download-link">Descargar</a></td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="3" style="text-align: center; color: #777;">No hay respaldos generados todavía.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html_template, respaldos=respaldos)

@app.route('/crear')
def crear_respaldo():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_zip = f"backup_colegio_vaca_diez_{timestamp}.zip"
    ruta_zip_salida = os.path.join(BACKUP_DIR, nombre_zip)
    
    try:
        with zipfile.ZipFile(ruta_zip_salida, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(PROYECTO_DIR):
                dirs[:] = [d for d in dirs if not any(
                    os.path.relpath(os.path.join(root, d), PROYECTO_DIR).replace('\\', '/').startswith(exc) 
                    for exc in ELEMENTOS_EXCLUIDOS
                )]
                
                for file in files:
                    ruta_completa = os.path.join(root, file)
                    ruta_relativa = os.path.relpath(ruta_completa, PROYECTO_DIR)
                    ruta_relativa_unix = ruta_relativa.replace('\\', '/')
                    
                    if any(ruta_relativa_unix.startswith(exc) for exc in ELEMENTOS_EXCLUIDOS):
                        continue
                        
                    zipf.write(ruta_completa, ruta_relativa)
    except Exception as e:
        print(f"Error al generar el respaldo: {e}")
        
    return redirect(url_for('index'))

@app.route('/descargar/<nombre_archivo>')
def descargar(nombre_archivo):
    ruta_archivo = os.path.join(BACKUP_DIR, nombre_archivo)
    if os.path.exists(ruta_archivo):
        return send_file(ruta_archivo, as_attachment=True)
    return "Archivo de respaldo no encontrado", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
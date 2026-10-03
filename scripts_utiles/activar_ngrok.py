import os
import time
import requests
import subprocess

def automatizar_ngrok():
    print("Iniciando túnel Ngrok en el puerto 5000...")
    
    # 1. Abre Ngrok en una nueva ventana de consola
    subprocess.Popen(['start', 'cmd', '/c', 'ngrok http 5000'], shell=True)
    
    # 2. Espera 4 segundos para darle tiempo a Ngrok de conectarse a internet
    time.sleep(4)
    
    # 3. Consulta la API interna de Ngrok para robar la URL generada
    try:
        respuesta = requests.get('http://127.0.0.1:4040/api/tunnels')
        datos = respuesta.json()
        
        url_publica = None
        for tunel in datos['tunnels']:
            if tunel['proto'] == 'https':
                url_publica = tunel['public_url']
                break
                
        if url_publica:
            print(f"✅ Enlace capturado: {url_publica}")
            actualizar_env(url_publica)
        else:
            print("❌ No se pudo encontrar el enlace HTTPS de Ngrok.")
            
    except Exception as e:
        print(f"❌ Error al intentar leer Ngrok: {e}")
        print("Asegúrate de tener instalada la librería 'requests' (pip install requests)")

def actualizar_env(nueva_url):
    ruta_env = '.env'
    lineas = []
    
    # Leer el .env actual si existe
    if os.path.exists(ruta_env):
        with open(ruta_env, 'r', encoding='utf-8') as archivo:
            lineas = archivo.readlines()
            
    # Sobrescribir el archivo actualizando solo la línea de TUNNEL_URL
    with open(ruta_env, 'w', encoding='utf-8') as archivo:
        actualizado = False
        for linea in lineas:
            if linea.startswith('TUNNEL_URL='):
                archivo.write(f"TUNNEL_URL={nueva_url}\n")
                actualizado = True
            else:
                archivo.write(linea)
                
        # Si la variable no existía, la crea al final
        if not actualizado:
            archivo.write(f"\nTUNNEL_URL={nueva_url}\n")
            
    print("✅ Archivo .env actualizado exitosamente. Ya puedes iniciar tu sistema (app.py).")

if __name__ == '__main__':
    automatizar_ngrok()
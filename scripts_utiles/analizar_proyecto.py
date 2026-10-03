import os
import json
import datetime
from pathlib import Path
import sys
import subprocess
from collections import defaultdict

class ProyectoAnalyzer:
    def __init__(self, ruta_proyecto):
        self.ruta_proyecto = Path(ruta_proyecto)
        self.analisis = {
            'nombre_proyecto': 'Colegio Vaca Díez',
            'desarrollador': 'Avrora Soft - Vibola LLC',
            'ruta': str(self.ruta_proyecto),
            'fecha_analisis': datetime.datetime.now().isoformat(),
            'estadisticas': {},
            'estructura': {},
            'archivos_por_tipo': defaultdict(list),
            'posibles_problemas': [],
            'dependencias': [],
            'recursos': []
        }
        
    def analizar(self):
        """Método principal para ejecutar el análisis completo"""
        print(f"🔍 Iniciando análisis del proyecto: {self.analisis['nombre_proyecto']}")
        print(f"📁 Ruta: {self.ruta_proyecto}")
        print("=" * 60)
        
        if not self.ruta_proyecto.exists():
            print("❌ La ruta del proyecto no existe")
            return False
            
        self._recorrer_proyecto()
        self._analizar_estructura()
        self._generar_reporte()
        self._guardar_analisis()
        
        print("✅ Análisis completado exitosamente")
        return True
    
    def _recorrer_proyecto(self):
        """Recorre recursivamente todos los archivos y carpetas"""
        print("\n📂 Recorriendo estructura del proyecto...")
        
        total_archivos = 0
        total_carpetas = 0
        tamaño_total = 0
        
        # Ignorar carpetas comunes de sistema y dependencias
        ignorar = {'.git', '__pycache__', 'node_modules', 'venv', 'env', '.idea', '.vscode', 'dist', 'build'}
        
        for root, dirs, files in os.walk(self.ruta_proyecto):
            # Filtrar carpetas a ignorar
            dirs[:] = [d for d in dirs if d not in ignorar]
            
            carpeta_actual = Path(root).relative_to(self.ruta_proyecto)
            self.analisis['estructura'][str(carpeta_actual)] = {
                'archivos': len(files),
                'subcarpetas': len(dirs)
            }
            
            for archivo in files:
                ruta_completa = Path(root) / archivo
                try:
                    tamaño = ruta_completa.stat().st_size
                    tamaño_total += tamaño
                except:
                    tamaño = 0
                    
                # Obtener extensión - CORREGIDO
                nombre, extension = os.path.splitext(archivo)
                extension = extension.lower()
                if extension.startswith('.'):
                    extension = extension[1:]
                if not extension:
                    extension = 'sin_extension'
                    
                self.analisis['archivos_por_tipo'][extension].append({
                    'nombre': archivo,
                    'ruta': str(ruta_completa.relative_to(self.ruta_proyecto)),
                    'tamaño': tamaño
                })
                
                total_archivos += 1
                
                # Analizar contenido de archivos de código
                self._analizar_archivo(ruta_completa, extension)
                
            total_carpetas += len(dirs)
            
        self.analisis['estadisticas'] = {
            'total_archivos': total_archivos,
            'total_carpetas': total_carpetas,
            'tamaño_total_bytes': tamaño_total,
            'tamaño_total_mb': round(tamaño_total / (1024 * 1024), 2)
        }
        
        print(f"📊 Encontrados: {total_archivos} archivos en {total_carpetas} carpetas")
        print(f"💾 Tamaño total: {self.analisis['estadisticas']['tamaño_total_mb']} MB")
    
    def _analizar_archivo(self, ruta, extension):
        """Analiza el contenido de archivos específicos"""
        # Extensiones de archivos de texto que podemos leer
        extensiones_texto = ['py', 'js', 'jsx', 'ts', 'tsx', 'java', 'php', 'rb', 'html', 'css', 'scss', 'json', 'xml', 'txt', 'md']
        
        if extension not in extensiones_texto:
            return  # Saltar archivos binarios
            
        try:
            with open(ruta, 'r', encoding='utf-8', errors='ignore') as f:
                contenido = f.read()
                
            # Detectar posibles problemas o patrones importantes
            if 'TODO' in contenido or 'FIXME' in contenido or 'HACK' in contenido:
                self.analisis['posibles_problemas'].append({
                    'archivo': str(ruta.relative_to(self.ruta_proyecto)),
                    'tipo': 'pendiente',
                    'descripcion': 'Contiene marcadores TODO/FIXME/HACK'
                })
                
            # Detectar dependencias en diferentes lenguajes
            if extension in ['py', 'js', 'jsx', 'ts', 'tsx', 'java', 'php', 'rb']:
                self._detectar_dependencias(contenido, extension)
                
            # Detectar recursos (imágenes, estilos, etc.)
            if extension in ['css', 'scss', 'html']:
                self.analisis['recursos'].append({
                    'archivo': str(ruta.relative_to(self.ruta_proyecto)),
                    'tipo': extension
                })
                
        except Exception as e:
            pass  # Si no se puede leer el archivo, continuar
    
    def _detectar_dependencias(self, contenido, extension):
        """Detecta dependencias en archivos de código"""
        dependencias = []
        
        if extension == 'py':
            # Buscar importaciones en Python
            lineas = contenido.split('\n')
            for linea in lineas:
                linea_clean = linea.strip()
                if linea_clean.startswith('import ') or linea_clean.startswith('from '):
                    # Extraer solo el nombre del módulo
                    if linea_clean.startswith('import '):
                        modulo = linea_clean.replace('import ', '').split()[0]
                        dependencias.append(modulo)
                    else:  # from ... import ...
                        partes = linea_clean.split()
                        if len(partes) > 1:
                            dependencias.append(partes[1])
        elif extension in ['js', 'jsx', 'ts', 'tsx']:
            # Buscar importaciones en JavaScript/TypeScript
            lineas = contenido.split('\n')
            for linea in lineas:
                linea_clean = linea.strip()
                if linea_clean.startswith('import ') or linea_clean.startswith('require('):
                    # Simplificar la extracción
                    if 'from' in linea_clean:
                        partes = linea_clean.split('from')
                        if len(partes) > 1:
                            dependencias.append(partes[1].strip().strip('\'"'))
                    elif linea_clean.startswith('require('):
                        import re
                        match = re.search(r'require\([\'"]([^\'"]+)[\'"]\)', linea_clean)
                        if match:
                            dependencias.append(match.group(1))
        
        if dependencias:
            # Limitar dependencias duplicadas
            for dep in dependencias:
                if dep and dep not in self.analisis['dependencias']:
                    self.analisis['dependencias'].append(dep)
    
    def _analizar_estructura(self):
        """Analiza la estructura del proyecto y genera insights"""
        print("\n🏗️ Analizando estructura del proyecto...")
        
        # Identificar tipo de proyecto
        tipos_proyecto = []
        
        # Buscar archivos de configuración
        archivos_config = []
        for archivo in os.listdir(self.ruta_proyecto):
            archivos_config.append(archivo.lower())
        
        if 'requirements.txt' in archivos_config:
            tipos_proyecto.append('Python')
        if 'package.json' in archivos_config:
            tipos_proyecto.append('Node.js')
        if 'pom.xml' in archivos_config:
            tipos_proyecto.append('Java/Maven')
        if 'web.config' in archivos_config:
            tipos_proyecto.append('.NET')
        if 'composer.json' in archivos_config:
            tipos_proyecto.append('PHP')
        if 'Cargo.toml' in archivos_config:
            tipos_proyecto.append('Rust')
        if 'go.mod' in archivos_config:
            tipos_proyecto.append('Go')
            
        # Detectar por extensiones comunes
        if self.analisis['archivos_por_tipo'].get('html'):
            tipos_proyecto.append('Web (HTML)')
        if self.analisis['archivos_por_tipo'].get('php'):
            tipos_proyecto.append('PHP')
        if self.analisis['archivos_por_tipo'].get('py'):
            if 'Python' not in tipos_proyecto:
                tipos_proyecto.append('Python')
                
        self.analisis['tipo_proyecto'] = list(set(tipos_proyecto)) if tipos_proyecto else ['No identificado']
        
        # Identificar archivos principales
        principales = ['index', 'main', 'app', 'server', 'init', 'setup', 'run']
        archivos_principales = []
        
        for ext, archivos in self.analisis['archivos_por_tipo'].items():
            for archivo in archivos:
                nombre_base = Path(archivo['nombre']).stem.lower()
                if nombre_base in principales:
                    archivos_principales.append(archivo['ruta'])
                    
        self.analisis['archivos_principales'] = archivos_principales[:10]  # Limitar a 10
    
    def _generar_reporte(self):
        """Genera un reporte legible del análisis"""
        print("\n📋 GENERANDO REPORTE")
        print("=" * 60)
        print(f"🏫 Proyecto: {self.analisis['nombre_proyecto']}")
        print(f"👨‍💻 Desarrollador: {self.analisis['desarrollador']}")
        print(f"📅 Análisis: {self.analisis['fecha_analisis']}")
        print("-" * 60)
        
        # Estadísticas
        est = self.analisis['estadisticas']
        print("\n📊 ESTADÍSTICAS:")
        print(f"  • Total archivos: {est.get('total_archivos', 0):,}")
        print(f"  • Total carpetas: {est.get('total_carpetas', 0):,}")
        print(f"  • Tamaño total: {est.get('tamaño_total_mb', 0):.2f} MB")
        print(f"  • Tamaño en bytes: {est.get('tamaño_total_bytes', 0):,}")
        
        # Tipos de archivos
        print("\n📁 TIPOS DE ARCHIVOS:")
        tipos = self.analisis['archivos_por_tipo']
        tipos_ordenados = sorted(tipos.items(), key=lambda x: len(x[1]), reverse=True)
        for tipo, archivos in tipos_ordenados[:10]:
            print(f"  • .{tipo}: {len(archivos)} archivos")
        if len(tipos_ordenados) > 10:
            print(f"  • ... y {len(tipos_ordenados) - 10} tipos más")
        
        # Tipo de proyecto
        print("\n🏗️ TIPO DE PROYECTO:")
        if self.analisis.get('tipo_proyecto'):
            for tipo in self.analisis['tipo_proyecto']:
                print(f"  • {tipo}")
        
        # Archivos principales
        if self.analisis.get('archivos_principales'):
            print("\n📄 ARCHIVOS PRINCIPALES:")
            for archivo in self.analisis['archivos_principales'][:5]:
                print(f"  • {archivo}")
        
        # Dependencias
        if self.analisis.get('dependencias'):
            print(f"\n📦 DEPENDENCIAS DETECTADAS ({len(self.analisis['dependencias'])}):")
            for dep in self.analisis['dependencias'][:10]:
                print(f"  • {dep}")
            if len(self.analisis['dependencias']) > 10:
                print(f"  • ... y {len(self.analisis['dependencias']) - 10} más")
        
        # Problemas encontrados
        if self.analisis.get('posibles_problemas'):
            print(f"\n⚠️ PROBLEMAS POTENCIALES ({len(self.analisis['posibles_problemas'])}):")
            for problema in self.analisis['posibles_problemas'][:5]:
                print(f"  • {problema['archivo']}: {problema['descripcion']}")
        
        # Recursos
        if self.analisis.get('recursos'):
            print(f"\n🎨 RECURSOS ENCONTRADOS ({len(self.analisis['recursos'])}):")
            for recurso in self.analisis['recursos'][:5]:
                print(f"  • {recurso['archivo']} (.{recurso['tipo']})")
        
        print("=" * 60)
    
    def _guardar_analisis(self):
        """Guarda el análisis en un archivo JSON"""
        try:
            archivo_salida = self.ruta_proyecto / 'analisis_proyecto.json'
            
            # Preparar datos para JSON (convertir Path a string)
            datos_json = self.analisis.copy()
            
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                json.dump(datos_json, f, indent=2, ensure_ascii=False, default=str)
                
            print(f"\n💾 Análisis guardado en: {archivo_salida}")
            
            # También guardar un reporte en texto
            reporte_txt = self.ruta_proyecto / 'reporte_proyecto.txt'
            with open(reporte_txt, 'w', encoding='utf-8') as f:
                f.write(f"REPORTE DE ANÁLISIS - {self.analisis['nombre_proyecto']}\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Desarrollador: {self.analisis['desarrollador']}\n")
                f.write(f"Fecha: {self.analisis['fecha_analisis']}\n\n")
                
                est = self.analisis['estadisticas']
                f.write("ESTADÍSTICAS:\n")
                f.write(f"- Total archivos: {est.get('total_archivos', 0):,}\n")
                f.write(f"- Total carpetas: {est.get('total_carpetas', 0):,}\n")
                f.write(f"- Tamaño total: {est.get('tamaño_total_mb', 0):.2f} MB\n\n")
                
                f.write("TIPOS DE ARCHIVOS:\n")
                tipos_ordenados = sorted(self.analisis['archivos_por_tipo'].items(), key=lambda x: len(x[1]), reverse=True)
                for tipo, archivos in tipos_ordenados:
                    f.write(f"- .{tipo}: {len(archivos)} archivos\n")
                    
                if self.analisis.get('tipo_proyecto'):
                    f.write("\nTIPO DE PROYECTO:\n")
                    for tipo in self.analisis['tipo_proyecto']:
                        f.write(f"- {tipo}\n")
                        
                if self.analisis.get('archivos_principales'):
                    f.write("\nARCHIVOS PRINCIPALES:\n")
                    for archivo in self.analisis['archivos_principales']:
                        f.write(f"- {archivo}\n")
                        
                if self.analisis.get('dependencias'):
                    f.write("\nDEPENDENCIAS DETECTADAS:\n")
                    for dep in self.analisis['dependencias']:
                        f.write(f"- {dep}\n")
                        
                if self.analisis.get('posibles_problemas'):
                    f.write("\nPROBLEMAS POTENCIALES:\n")
                    for problema in self.analisis['posibles_problemas']:
                        f.write(f"- {problema['archivo']}: {problema['descripcion']}\n")
                        
            print(f"📝 Reporte guardado en: {reporte_txt}")
            
        except Exception as e:
            print(f"❌ Error al guardar el análisis: {e}")

def main():
    # Ruta del proyecto
    ruta_proyecto = r"D:\colegio_vaca_diez"
    
    print("=" * 60)
    print("🔧 ANALIZADOR DE PROYECTOS")
    print("=" * 60)
    print(f"📁 Proyecto: Colegio Vaca Díez")
    print(f"👨‍💻 Desarrollador: Avrora Soft - Vibola LLC")
    print(f"📍 Ruta: {ruta_proyecto}")
    print("=" * 60)
    
    # Crear y ejecutar el analizador
    analyzer = ProyectoAnalyzer(ruta_proyecto)
    
    try:
        analyzer.analizar()
    except KeyboardInterrupt:
        print("\n⏹️ Análisis interrumpido por el usuario")
    except Exception as e:
        print(f"❌ Error durante el análisis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
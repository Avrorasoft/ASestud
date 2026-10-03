import os
import io
import zipfile
import random
from datetime import datetime, date
from app import create_app

app = create_app()

with app.app_context():
    from models import (
        db, Estudiante, Egresado, Calificacion, Pago, Gasto,
        Materia, Profesor, PersonalAdministrativo, Padre
    )
    from flask import current_app

    nombres_m = [
        'Carlos', 'Miguel', 'Jose', 'Juan', 'Pedro', 'Luis', 'Fernando', 'Roberto', 'Diego', 'Andres',
        'Daniel', 'Gabriel', 'Ricardo', 'Eduardo', 'Javier', 'Mario', 'Hugo', 'Raul', 'Marcelo', 'Alvaro',
        'Rodrigo', 'Sebastian', 'Matias', 'Nicolas', 'Alejandro', 'Santiago', 'Emiliano', 'Tomas', 'Lucas', 'Martin',
        'Bruno', 'Facundo', 'Joaquin', 'Thiago', 'Dylan', 'Ian', 'Liam', 'Mateo', 'Santino', 'Bautista',
        'Cristian', 'Felipe', 'Gonzalo', 'Hector', 'Ignacio', 'Jesus', 'Kevin', 'Leonardo', 'Manuel', 'Oscar'
    ]
    nombres_f = [
        'Maria', 'Ana', 'Carmen', 'Rosa', 'Lucia', 'Isabella', 'Valentina', 'Camila', 'Sofia', 'Martina',
        'Victoria', 'Valeria', 'Antonia', 'Julieta', 'Catalina', 'Emma', 'Regina', 'Renata', 'Mia', 'Abril',
        'Emilia', 'Olivia', 'Ambar', 'Salome', 'Guadalupe', 'Fernanda', 'Daniela', 'Paola', 'Andrea', 'Claudia',
        'Patricia', 'Silvia', 'Veronica', 'Gabriela', 'Alejandra', 'Natalia', 'Carolina', 'Teresa', 'Elena', 'Beatriz',
        'Liliana', 'Sandra', 'Martha', 'Monica', 'Lorena', 'Carla', 'Yessica', 'Karla', 'Wendy', 'Elizabeth'
    ]
    apellidos = [
        'Garcia', 'Rodriguez', 'Martinez', 'Lopez', 'Gonzalez', 'Hernandez', 'Perez', 'Sanchez', 'Ramirez', 'Torres',
        'Flores', 'Rivera', 'Gomez', 'Diaz', 'Cruz', 'Morales', 'Reyes', 'Gutierrez', 'Ortiz', 'Chavez',
        'Ramos', 'Vargas', 'Castillo', 'Mendoza', 'Alvarez', 'Romero', 'Ruiz', 'Aguilar', 'Molina', 'Delgado',
        'Medina', 'Castro', 'Vega', 'Herrera', 'Marquez', 'Pena', 'Cabrera', 'Rojas', 'Salazar', 'Campos',
        'Suarez', 'Ibanez', 'Maldonado', 'Acosta', 'Paredes', 'Bravo', 'Cordero', 'Quispe', 'Mamani', 'Condori'
    ]

    # =========================================================================
    # COMPLETAR 500 EGRESADOS (usando estudiante_id_original de los existentes)
    # =========================================================================
    print("Limpiando egresados anteriores...")
    Egresado.query.delete()
    db.session.commit()

    # Obtener IDs de estudiantes existentes
    ids_estudiantes = [e.id for e in Estudiante.query.with_entities(Estudiante.id).all()]
    print(f"Estudiantes disponibles: {len(ids_estudiantes)}")

    # Pools unicos
    cis_usados = set()
    def obtener_ci():
        while True:
            ci = str(random.randint(1000000, 99999999))
            if ci not in cis_usados:
                cis_usados.add(ci)
                return ci

    rudes_usados = set()
    def obtener_rude():
        while True:
            anio = random.randint(2010, 2025)
            rude = f'R{anio}{random.randint(100000, 999999)}'
            if rude not in rudes_usados:
                rudes_usados.add(rude)
                return rude

    anio_actual = 2026
    print("Creando 500 egresados con estudiante_id_original asignado...")

    for i in range(500):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido1 = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
        anio_egreso = anio_actual - random.randint(1, 15)
        genero_tutor = random.choice(['M', 'F'])
        nombre_tutor = random.choice(nombres_m if genero_tutor == 'M' else nombres_f)

        egresado = Egresado(
            estudiante_id_original=random.choice(ids_estudiantes),
            ci=obtener_ci(),
            rude=obtener_rude(),
            apellidos=f'{apellido1} {apellido2}',
            nombres=nombre,
            fecha_nacimiento=date(anio_egreso - 17, random.randint(1, 12), random.randint(1, 28)),
            curso_final='6 Secundaria',
            anio_egreso=anio_egreso,
            estado_egreso='Egresado',
            nombre_tutor=f'{nombre_tutor} {random.choice(apellidos)} {random.choice(apellidos)}',
            telefono_tutor=f'7{random.randint(10000000, 99999999)}',
            fecha_archivo=datetime(anio_egreso, 12, 15)
        )
        db.session.add(egresado)
        if (i + 1) % 100 == 0:
            db.session.commit()
            print(f"  {i+1}/500 egresados")

    db.session.commit()
    print(f"OK: {Egresado.query.count()} egresados creados")

    # =========================================================================
    # CREAR ARCHIVO .avr
    # =========================================================================
    print()
    print("=" * 70)
    print("CREANDO ARCHIVO .avr DE RESPALDO...")
    print("=" * 70)

    root_path = current_app.root_path
    nombre_avr = f"BD_Prueba_200est_30prof_500egr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avr"

    db.session.commit()
    db.engine.dispose()

    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = db_uri.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(root_path, db_path)

    carpetas_datos = [
        'static/uploads', 'static/recibos', 'static/boletines',
        'static/recibos_personal', 'templates', 'routes',
        'models.py', 'app.py', 'config.py', 'utils_pdf.py'
    ]

    memory_buffer = io.BytesIO()
    with zipfile.ZipFile(memory_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(db_path):
            zipf.write(db_path, "colegio_vaca_diez.db")
            print(f"  [OK] BD agregada: {os.path.getsize(db_path) / 1024:.1f} KB")

        for item in carpetas_datos:
            ruta_abs = os.path.join(root_path, item)
            if os.path.isfile(ruta_abs):
                zipf.write(ruta_abs, item)
            elif os.path.isdir(ruta_abs):
                count = 0
                for raiz, dirs, archivos in os.walk(ruta_abs):
                    dirs[:] = [d for d in dirs if d not in ['__pycache__', '.pytest_cache']]
                    for archivo in archivos:
                        if not archivo.endswith(('.pyc', '.db')):
                            arch_abs = os.path.join(raiz, archivo)
                            arcname = os.path.relpath(arch_abs, root_path)
                            zipf.write(arch_abs, arcname)
                            count += 1
                print(f"  [OK] {item}: {count} archivos")

    backups_dir = os.path.join(root_path, 'static', 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    backup_path = os.path.join(backups_dir, nombre_avr)

    memory_buffer.seek(0)
    with open(backup_path, 'wb') as f:
        f.write(memory_buffer.getvalue())

    tamano_mb = os.path.getsize(backup_path) / (1024 * 1024)

    print()
    print("=" * 70)
    print("ARCHIVO .avr CREADO EXITOSAMENTE")
    print("=" * 70)
    print(f"  Nombre: {nombre_avr}")
    print(f"  Ubicacion: static/backups/{nombre_avr}")
    print(f"  Tamano: {tamano_mb:.2f} MB")
    print()
    print("RESUMEN DE LA BASE DE DATOS:")
    print(f"  Estudiantes: {Estudiante.query.count()} (Kardex completo)")
    print(f"  Padres: {Padre.query.count()} (apellidos coincidentes)")
    print(f"  Profesores: {Profesor.query.count()} (30)")
    print(f"  Administrativos: {PersonalAdministrativo.query.count()} (10)")
    print(f"  Materias: {Materia.query.count()}")
    print(f"  Calificaciones: {Calificacion.query.count()} (E1,P1,P2,P3,EF,NF x 2 tri)")
    print(f"  Pagos: {Pago.query.count()} (93% hasta julio)")
    print(f"  Gastos: {Gasto.query.count()} (9 categorias x 7 meses)")
    print(f"  Egresados: {Egresado.query.count()} (500)")
    print(f"  Pension: 605 Bs")
    print("=" * 70)
    print()
    print("Para restaurar desde la Boveda:")
    print(f"  1. Ir a la Boveda del Superadmin")
    print(f"  2. Subir el archivo: static/backups/{nombre_avr}")
    print("=" * 70)

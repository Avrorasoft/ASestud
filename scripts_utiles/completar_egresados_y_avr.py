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
            estudiante_id_original=random.choice(ids_estudiantes) if ids_estudiantes else None,
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
    # CREAR ARCHIVO .avr EN LA RUTA ABSOLUTA DEL DISCO C (C:\ASestud\uploads)
    # =========================================================================
    print()
    print("=" * 70)
    print("CREANDO ARCHIVO .avr DE RESPALDO EN C:\\ASestud\\uploads...")
    print("=" * 70)

    root_path = r"C:\ASestud"
    base_upload = r"C:\ASestud\uploads"
    nombre_avr = f"BD_Prueba_200est_30prof_500egr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avr"

    db.session.commit()
    db.engine.dispose()

    db_path = os.path.join(root_path, 'colegio_vaca_diez.db')

    memory_buffer = io.BytesIO()
    with zipfile.ZipFile(memory_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(db_path):
            zipf.write(db_path, "colegio_vaca_diez.db")
            print(f"  [OK] BD agregada: {os.path.getsize(db_path) / 1024:.1f} KB")

        carpetas_datos = [
            base_upload,
            os.path.join(root_path, 'templates'),
            os.path.join(root_path, 'routes'),
            os.path.join(root_path, 'models.py'),
            os.path.join(root_path, 'app.py'),
            os.path.join(root_path, 'config.py')
        ]

        for item in carpetas_datos:
            if os.path.isfile(item):
                zipf.write(item, os.path.relpath(item, root_path))
            elif os.path.isdir(item):
                count = 0
                for raiz, dirs, archivos in os.walk(item):
                    dirs[:] = [d for d in dirs if d not in ['__pycache__', '.pytest_cache']]
                    for archivo in archivos:
                        if not archivo.endswith(('.pyc', '.db')):
                            arch_abs = os.path.join(raiz, archivo)
                            arcname = os.path.relpath(arch_abs, root_path)
                            zipf.write(arch_abs, arcname)
                            count += 1
                print(f"  [OK] {os.path.basename(item)}: {count} archivos")

    backups_dir = os.path.join(base_upload, 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    backup_path = os.path.join(backups_dir, nombre_avr)

    memory_buffer.seek(0)
    with open(backup_path, 'wb') as f:
        f.write(memory_buffer.getvalue())

    tamano_mb = os.path.getsize(backup_path) / (1024 * 1024)

    print()
    print("=" * 70)
    print("ARCHIVO .avr CREADO EXITOSAMENTE EN EL DISCO C")
    print("=" * 70)
    print(f"  Nombre: {nombre_avr}")
    print(f"  Ubicacion: {backup_path}")
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
    print(f"  2. Subir el archivo: {backup_path}")
    print("=" * 70)
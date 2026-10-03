import random
import os
import io
import zipfile
from datetime import datetime, date
from app import create_app

app = create_app()

with app.app_context():
    from models import (
        db, Estudiante, Padre, Calificacion, Profesor, PersonalAdministrativo,
        Egresado, Materia, Pago, Gasto
    )
    from flask import current_app

    # =========================================================================
    # POOL DE IDENTIFICADORES UNICOS
    # =========================================================================
    def generar_pool_cis(n=1500):
        cis = set()
        while len(cis) < n:
            cis.add(str(random.randint(1000000, 99999999)))
        return list(cis)

    POOL_CIS = generar_pool_cis(1500)
    POOL_INDEX = 0
    def obtener_ci():
        global POOL_INDEX
        ci = POOL_CIS[POOL_INDEX]
        POOL_INDEX += 1
        return ci

    def generar_pool_rudes(n=1000, anio_base=2026):
        rudes = set()
        while len(rudes) < n:
            anio = anio_base - random.randint(0, 15)
            rudes.add(f'R{anio}{random.randint(100000, 999999)}')
        return list(rudes)

    POOL_RUDES = generar_pool_rudes(1000)
    RUDE_INDEX = 0
    def obtener_rude():
        global RUDE_INDEX
        rude = POOL_RUDES[RUDE_INDEX]
        RUDE_INDEX += 1
        return rude

    # =========================================================================
    # DATOS BASE
    # =========================================================================
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
    zonas = ['Central', 'Norte', 'Sur', 'Este', 'Oeste', 'Barrio Universitario', 'Villa Fatima', 'Alto Miraflores', 'Bajo San Antonio', 'Miraflores']
    calles = ['Av. Beni', 'Calle Comercio', 'Av. Riberalta', 'Calle Bolivar', 'Av. Amazonas', 'Calle Sucre', 'Av. del Estudiante', 'Calle Cochabamba']
    cursos_primaria = ['1 Primaria', '2 Primaria', '3 Primaria', '4 Primaria', '5 Primaria', '6 Primaria']
    cursos_secundaria = ['1 Secundaria', '2 Secundaria', '3 Secundaria', '4 Secundaria', '5 Secundaria', '6 Secundaria']
    cursos_nidito = ['Nidito', 'Pre-Kinder', 'Kinder']
    turnos = ['Manana', 'Tarde']
    tipos_sangre = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-']
    materias_primaria = ['Matematicas', 'Lenguaje', 'Ciencias Naturales', 'Estudios Sociales', 'Artes Plasticas', 'Musica', 'Educacion Fisica', 'Ingles', 'Religion', 'Computacion']
    materias_secundaria = ['Matematicas', 'Fisica', 'Quimica', 'Biologia', 'Literatura', 'Historia', 'Geografia', 'Ingles', 'Filosofia', 'Educacion Fisica', 'Artes', 'Computacion']
    materias_nidito = ['Motricidad', 'Lenguaje Inicial', 'Matematica Inicial', 'Artes', 'Musica', 'Juegos']
    TIPOS_EVALUACION = ['E1', 'P1', 'P2', 'P3', 'EF', 'NF']
    MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    PENSION = 605.0
    anio_actual = 2026

    print("=" * 70)
    print("GENERANDO BASE DE DATOS DE PRUEBA + ARCHIVO .avr")
    print("=" * 70)
    print(f"Pension: {PENSION} Bs | 93% al dia hasta julio | 7% con mora")
    print(f"Notas: E1, P1, P2, P3, EF, NF (1er y 2do trimestre)")
    print("=" * 70)
    print()

    # =========================================================================
    # LIMPIAR DATOS
    # =========================================================================
    print("[1/8] Limpiando datos anteriores...")
    Pago.query.delete()
    Calificacion.query.delete()
    Gasto.query.delete()
    Padre.query.delete()
    Egresado.query.delete()
    Materia.query.delete()
    Estudiante.query.delete()
    Profesor.query.delete()
    PersonalAdministrativo.query.delete()
    db.session.commit()
    print("  OK")

    # =========================================================================
    # 30 PROFESORES
    # =========================================================================
    print("[2/8] Creando 30 profesores...")
    profesores = []
    especialidades = ['Matematicas', 'Fisica', 'Quimica', 'Biologia', 'Literatura', 'Historia',
                      'Ingles', 'Artes', 'Educacion Fisica', 'Computacion', 'Musica', 'Religion',
                      'Filosofia', 'Geografia', 'Psicologia']
    niveles_prof = ['Primaria', 'Secundaria', 'Nidito']

    for i in range(30):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido1 = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
        prof = Profesor(
            ci=obtener_ci(),
            apellidos=f'{apellido1} {apellido2}',
            nombres=nombre,
            especialidad=random.choice(especialidades),
            nivel=random.choice(niveles_prof),
            turno=random.choice(turnos),
            salario_base=random.choice([2500, 3000, 3500, 4000, 4500, 5000]),
            estado='Activo',
            telefono=f'7{random.randint(10000000, 99999999)}',
            correo=f'{nombre.lower()}.{apellido1.lower()}{i}@colegio.edu.bo'
        )
        db.session.add(prof)
        profesores.append(prof)
    db.session.commit()
    print("  OK: 30 profesores")

    # =========================================================================
    # 10 ADMINISTRATIVOS
    # =========================================================================
    print("[3/8] Creando 10 administrativos...")
    cargos_admin = ['Director', 'Secretaria General', 'Contador', 'Psicologo',
                    'Bibliotecario', 'Inspector General', 'Auxiliar Administrativo',
                    'Encargado de Sistemas', 'Orientador Vocacional', 'Tesorero']
    areas = ['Direccion', 'Secretaria', 'Contabilidad', 'Psicologia',
             'Biblioteca', 'Inspectoría', 'Administracion', 'Sistemas', 'Orientacion', 'Tesoreria']

    for i in range(10):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido1 = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
        admin = PersonalAdministrativo(
            ci=obtener_ci(),
            apellidos=f'{apellido1} {apellido2}',
            nombres=nombre,
            cargo=cargos_admin[i],
            area=areas[i],
            salario_base=random.choice([2500, 3000, 3500, 4000, 5000, 6000, 7000]),
            estado='Activo',
            telefono=f'7{random.randint(10000000, 99999999)}',
            correo=f'{nombre.lower()}.{apellido1.lower()}{i}@colegio.edu.bo'
        )
        db.session.add(admin)
    db.session.commit()
    print("  OK: 10 administrativos")

    # =========================================================================
    # MATERIAS
    # =========================================================================
    print("[4/8] Creando materias...")
    materias_por_curso = {}
    for curso in cursos_nidito:
        materias_por_curso[curso] = []
        for mat in materias_nidito:
            m = Materia(nombre=mat, curso_id=curso, profesor_id=random.choice(profesores).id)
            db.session.add(m)
            materias_por_curso[curso].append(m)
    for curso in cursos_primaria:
        materias_por_curso[curso] = []
        for mat in materias_primaria:
            m = Materia(nombre=mat, curso_id=curso, profesor_id=random.choice(profesores).id)
            db.session.add(m)
            materias_por_curso[curso].append(m)
    for curso in cursos_secundaria:
        materias_por_curso[curso] = []
        for mat in materias_secundaria:
            m = Materia(nombre=mat, curso_id=curso, profesor_id=random.choice(profesores).id)
            db.session.add(m)
            materias_por_curso[curso].append(m)
    db.session.commit()
    print(f"  OK: {sum(len(v) for v in materias_por_curso.values())} materias")

    # =========================================================================
    # 200 ESTUDIANTES CON PADRES (APELLIDOS COINCIDENTES) + KARDEX
    # =========================================================================
    print("[5/8] Creando 200 estudiantes con padres y Kardex...")
    estudiantes_creados = []
    estudiantes_morosos = set(random.sample(range(200), 14))  # 7% morosos

    for i in range(200):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido_paterno = random.choice(apellidos)
        apellido_materno = random.choice(apellidos)
        curso = random.choice(cursos_nidito + cursos_primaria + cursos_secundaria)
        turno = random.choice(turnos)

        if curso in cursos_nidito:
            edad = random.randint(3, 5)
        elif curso in cursos_primaria:
            edad = random.randint(6, 11)
        else:
            edad = random.randint(12, 17)

        fecha_nac = date(anio_actual - edad, random.randint(1, 12), random.randint(1, 28))
        ci_est = obtener_ci()
        rude_est = obtener_rude()

        est = Estudiante(
            ci=ci_est, rude=rude_est,
            apellidos=f'{apellido_paterno} {apellido_materno}',
            nombres=nombre,
            fecha_nacimiento=fecha_nac,
            curso=curso, turno=turno, estado='Activo', pension=PENSION,
            direccion=f'{random.choice(calles)} N {random.randint(100, 9999)}',
            zona=random.choice(zonas), ciudad='Riberalta', foto_path='default.png',
            tipo_sangre=random.choice(tipos_sangre),
            alergias=random.choice(['Ninguna', 'Polvo', 'Acaros', 'Penicilina', 'Ninguna', 'Ninguna']),
            enfermedades_cronicas=random.choice(['Ninguna', 'Asma', 'Ninguna', 'Ninguna', 'Rinitis']),
            medicamentos_actuales=random.choice(['Ninguno', 'Ninguno', 'Ninguno', 'Ventolin (asma)']),
            medico_nombre=f'Dr. {random.choice(nombres_m)} {random.choice(apellidos)}',
            medico_telefono=f'7{random.randint(10000000, 99999999)}',
            clinica_habitual=random.choice(['Clinica Riberalta', 'Clinica del Norte', 'Centro de Salud Municipal', 'Clinica San Rafael']),
            seguro_medico=random.choice(['SUS', 'Seguro Privado', 'Ninguno', 'SUS', 'SUS']),
            observaciones_salud=random.choice(['Sin observaciones', 'Requiere control anual', 'Sin observaciones']),
            fecha_actualizacion_salud=date(anio_actual, 1, random.randint(15, 30))
        )
        db.session.add(est)
        db.session.flush()
        estudiantes_creados.append((est, i in estudiantes_morosos))

        # PADRE (apellido paterno coincide)
        nombre_padre = random.choice(nombres_m)
        ap_padre = f'{apellido_paterno} {random.choice(apellidos)}'
        padre = Padre(
            estudiante_id=est.id, ci=obtener_ci(),
            ci_estudiante=ci_est, rude_estudiante=rude_est,
            parentesco='Padre',
            nombres=f'{nombre_padre} {ap_padre}',
            telefono1=f'7{random.randint(10000000, 99999999)}',
            telefono2=f'7{random.randint(10000000, 99999999)}' if random.random() > 0.5 else None,
            email=f'{nombre_padre.lower()}.{apellido_paterno.lower()}@gmail.com' if random.random() > 0.3 else None,
            ocupacion=random.choice(['Comerciante', 'Profesional Independiente', 'Empleado Publico', 'Empleado Privado', 'Agricultor', 'Transportista', 'Docente', 'Medico', 'Ingeniero'])
        )
        db.session.add(padre)

        # MADRE (apellido diferente)
        if random.random() > 0.15:  # 85% tienen ambos padres
            nombre_madre = random.choice(nombres_f)
            ap_madre = f'{random.choice(apellidos)} {random.choice(apellidos)}'
            madre = Padre(
                estudiante_id=est.id, ci=obtener_ci(),
                ci_estudiante=ci_est, rude_estudiante=rude_est,
                parentesco='Madre',
                nombres=f'{nombre_madre} {ap_madre}',
                telefono1=f'7{random.randint(10000000, 99999999)}',
                email=f'{nombre_madre.lower()}.{ap_madre.split()[0].lower()}@gmail.com' if random.random() > 0.4 else None,
                ocupacion=random.choice(['Comerciante', 'Profesional Independiente', 'Empleado Publico', 'Empleado Privado', 'Docente', 'Ama de casa', 'Enfermera', 'Contadora'])
            )
            db.session.add(madre)

        db.session.commit()
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/200 estudiantes")

    print("  OK: 200 estudiantes con padres")

    # =========================================================================
    # PAGOS: 93% hasta julio, 7% con mora
    # =========================================================================
    print("[6/8] Generando pagos (93% al dia, 7% con mora)...")
    for est, es_moroso in estudiantes_creados:
        if es_moroso:
            meses_pagados = random.randint(3, 5)
            meses_a_pagar = MESES[:meses_pagados]
        else:
            meses_a_pagar = MESES[:7]  # Enero a Julio

        for mes in meses_a_pagar:
            mes_num = MESES.index(mes) + 1
            descuento = random.choice([0, 0, 0, 0, 10, 20])
            pago = Pago(
                estudiante_id=est.id, ci_estudiante=est.ci, rude_estudiante=est.rude,
                mes=mes, anio=anio_actual,
                monto_total=PENSION, descuento=float(descuento),
                monto_pagado=PENSION - descuento,
                fecha_pago=datetime(anio_actual, mes_num, random.randint(1, 10)),
                estado='Pagado',
                metodo_pago=random.choice(['Efectivo', 'Transferencia', 'QR'])
            )
            db.session.add(pago)
        db.session.commit()

    print(f"  OK: {Pago.query.count()} pagos")

    # =========================================================================
    # CALIFICACIONES E1, P1, P2, P3, EF, NF (1er y 2do trimestre)
    # =========================================================================
    print("[7/8] Generando calificaciones (E1,P1,P2,P3,EF,NF x 2 trimestres)...")
    total_calif = 0
    for est, _ in estudiantes_creados:
        materias_curso = materias_por_curso.get(est.curso, [])
        for materia in materias_curso:
            # 1er trimestre (feb-abr)
            for tipo in TIPOS_EVALUACION:
                nota = round(random.uniform(50, 100) if tipo in ['EF', 'NF'] else random.uniform(45, 100), 0)
                calif = Calificacion(
                    estudiante_id=est.id, ci_estudiante=est.ci, rude_estudiante=est.rude,
                    materia_id=materia.id, tipo=tipo,
                    fecha=date(anio_actual, random.choice([2, 3, 4]), random.randint(1, 28)),
                    nota=nota
                )
                db.session.add(calif)
                total_calif += 1
            # 2do trimestre (may-jul)
            for tipo in TIPOS_EVALUACION:
                nota = round(random.uniform(50, 100) if tipo in ['EF', 'NF'] else random.uniform(45, 100), 0)
                calif = Calificacion(
                    estudiante_id=est.id, ci_estudiante=est.ci, rude_estudiante=est.rude,
                    materia_id=materia.id, tipo=tipo,
                    fecha=date(anio_actual, random.choice([5, 6, 7]), random.randint(1, 28)),
                    nota=nota
                )
                db.session.add(calif)
                total_calif += 1
        db.session.commit()

    print(f"  OK: {total_calif} calificaciones")

    # =========================================================================
    # GASTOS HASTA JULIO 2026
    # =========================================================================
    print("[8/8] Generando gastos mensuales hasta julio...")
    categorias_gastos = [
        ('Luz', 'Pago de electricidad', 1200, 1800, 'CRE', 'Contador', 'Transferencia'),
        ('Agua', 'Pago de agua potable', 300, 600, 'SAP', 'Contador', 'Transferencia'),
        ('Internet', 'Servicio de internet institucional', 500, 800, 'Cotas', 'Contador', 'Transferencia'),
        ('Mantenimiento', 'Mantenimiento de instalaciones', 1500, 3500, 'Tecnico Externo', 'Director', 'Efectivo'),
        ('Transporte', 'Transporte de personal y materiales', 800, 1500, 'Transporte Riberalta', 'Administrativo', 'Efectivo'),
        ('Material Didactico', 'Compra de materiales para clases', 500, 1200, 'Papeleria Central', 'Director', 'Efectivo'),
        ('Limpieza', 'Servicios de limpieza', 600, 1000, 'Servicios Generales', 'Administrativo', 'Efectivo'),
        ('Telefono', 'Servicio telefonico', 200, 400, 'Entel', 'Contador', 'Transferencia'),
        ('Combustible', 'Combustible para transporte escolar', 400, 900, 'Estacion de Servicio', 'Administrativo', 'Efectivo'),
    ]

    for mes_num in range(1, 8):
        for cat, desc, mmin, mmax, prov, resp, metodo in categorias_gastos:
            gasto = Gasto(
                categoria=cat,
                descripcion=f'{desc} - {MESES[mes_num-1]} {anio_actual}',
                monto=round(random.uniform(mmin, mmax), 2),
                fecha=date(anio_actual, mes_num, random.randint(1, 28)),
                proveedor=prov, responsable=resp, metodo_pago=metodo
            )
            db.session.add(gasto)
        db.session.commit()

    print(f"  OK: {Gasto.query.count()} gastos")

    # =========================================================================
    # 500 EGRESADOS
    # =========================================================================
    print("[+] Creando 500 egresados...")
    for i in range(500):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido1 = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
        anio_egreso = anio_actual - random.randint(1, 15)
        genero_tutor = random.choice(['M', 'F'])
        nombre_tutor = random.choice(nombres_m if genero_tutor == 'M' else nombres_f)

        egresado = Egresado(
            ci=obtener_ci(), rude=obtener_rude(),
            apellidos=f'{apellido1} {apellido2}', nombres=nombre,
            fecha_nacimiento=date(anio_egreso - 17, random.randint(1, 12), random.randint(1, 28)),
            curso_final='6 Secundaria', anio_egreso=anio_egreso, estado_egreso='Egresado',
            nombre_tutor=f'{nombre_tutor} {random.choice(apellidos)} {random.choice(apellidos)}',
            telefono_tutor=f'7{random.randint(10000000, 99999999)}',
            fecha_archivo=datetime(anio_egreso, 12, 15)
        )
        db.session.add(egresado)
        if (i + 1) % 100 == 0:
            db.session.commit()
    db.session.commit()
    print(f"  OK: {Egresado.query.count()} egresados")

    # =========================================================================
    # CREAR ARCHIVO .avr (ZIP con BD + archivos del proyecto)
    # =========================================================================
    print()
    print("=" * 70)
    print("CREANDO ARCHIVO .avr DE RESPALDO...")
    print("=" * 70)

    root_path = current_app.root_path
    nombre_avr = f"BD_Prueba_200est_30prof_500egr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avr"

    # Cerrar la conexion SQLite antes de copiar el archivo
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
        # Base de datos
        if os.path.exists(db_path):
            zipf.write(db_path, "colegio_vaca_diez.db")
            print(f"  [OK] BD agregada: {os.path.getsize(db_path) / 1024:.1f} KB")

        # Archivos del proyecto
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

    # Guardar en static/backups/
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
    print(f"  Estudiantes: 200 (Kardex completo)")
    print(f"  Padres: ~370 (apellidos coincidentes)")
    print(f"  Profesores: 30 (todos los turnos)")
    print(f"  Administrativos: 10")
    print(f"  Materias: {Materia.query.count()}")
    print(f"  Calificaciones: {Calificacion.query.count()} (E1,P1,P2,P3,EF,NF x 2 tri)")
    print(f"  Pagos: {Pago.query.count()} (93% hasta julio)")
    print(f"  Gastos: {Gasto.query.count()} (9 categorias x 7 meses)")
    print(f"  Egresados: 500")
    print(f"  Pension: {PENSION} Bs")
    print("=" * 70)
    print()
    print("Para restaurar desde la Boveda:")
    print(f"  1. Ir a la Boveda del Superadmin")
    print(f"  2. Seleccionar 'Restaurar Sistema'")
    print(f"  3. Subir el archivo: static/backups/{nombre_avr}")
    print("=" * 70)

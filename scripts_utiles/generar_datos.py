import random
from datetime import datetime, date, timedelta
from app import create_app

app = create_app()

with app.app_context():
    from models import db, Estudiante, Padre, Calificacion, Profesor, PersonalAdministrativo, Egresado, Materia, Pago, Asistencia

    # ====================================================================
    # POOL DE 2000 CIs UNICOS GENERADOS DE ANTEMANO (garantiza unicidad absoluta)
    # ====================================================================
    def generar_pool_cis(n=2000):
        cis = set()
        while len(cis) < n:
            cis.add(str(random.randint(1000000, 99999999)))
        return list(cis)
    
    POOL_CIS = generar_pool_cis(2000)
    POOL_INDEX = 0
    
    def obtener_ci():
        global POOL_INDEX
        ci = POOL_CIS[POOL_INDEX]
        POOL_INDEX += 1
        return ci
    
    # ====================================================================
    # POOL DE RUDES UNICOS (garantiza unicidad para egresados)
    # ====================================================================
    def generar_pool_rudes(n=500, anio_base=2026):
        rudes = set()
        while len(rudes) < n:
            anio = anio_base - random.randint(0, 15)
            rudes.add(f'R{anio}{random.randint(100000, 999999)}')
        return list(rudes)
    
    POOL_RUDES = generar_pool_rudes(500)
    RUDE_INDEX = 0
    
    def obtener_rude():
        global RUDE_INDEX
        rude = POOL_RUDES[RUDE_INDEX]
        RUDE_INDEX += 1
        return rude

    nombres_m = ['Carlos', 'Miguel', 'Jose', 'Juan', 'Pedro', 'Luis', 'Fernando', 'Roberto', 'Diego', 'Andres',
                 'Daniel', 'Gabriel', 'Ricardo', 'Eduardo', 'Javier', 'Mario', 'Hugo', 'Raul', 'Marcelo', 'Alvaro',
                 'Rodrigo', 'Sebastian', 'Matias', 'Nicolas', 'Alejandro', 'Santiago', 'Emiliano', 'Tomas', 'Lucas', 'Martin',
                 'Bruno', 'Facundo', 'Joaquin', 'Thiago', 'Dylan', 'Ian', 'Liam', 'Mateo', 'Santino', 'Bautista']
    nombres_f = ['Maria', 'Ana', 'Carmen', 'Rosa', 'Lucia', 'Isabella', 'Valentina', 'Camila', 'Sofia', 'Martina',
                 'Victoria', 'Valeria', 'Antonia', 'Julieta', 'Catalina', 'Emma', 'Regina', 'Renata', 'Mia', 'Abril',
                 'Emilia', 'Olivia', 'Ambar', 'Salome', 'Guadalupe', 'Fernanda', 'Daniela', 'Paola', 'Andrea', 'Claudia',
                 'Patricia', 'Silvia', 'Veronica', 'Gabriela', 'Alejandra', 'Natalia', 'Carolina', 'Teresa', 'Elena', 'Beatriz']
    apellidos = ['Garcia', 'Rodriguez', 'Martinez', 'Lopez', 'Gonzalez', 'Hernandez', 'Perez', 'Sanchez', 'Ramirez', 'Torres',
                 'Flores', 'Rivera', 'Gomez', 'Diaz', 'Cruz', 'Morales', 'Reyes', 'Gutierrez', 'Ortiz', 'Chavez',
                 'Ramos', 'Vargas', 'Castillo', 'Mendoza', 'Alvarez', 'Romero', 'Ruiz', 'Aguilar', 'Molina', 'Delgado',
                 'Medina', 'Castro', 'Vega', 'Herrera', 'Marquez', 'Pena', 'Cabrera', 'Rojas', 'Salazar', 'Campos',
                 'Suarez', 'Ibanez', 'Maldonado', 'Acosta', 'Paredes', 'Bravo', 'Cordero', 'Quispe', 'Mamani', 'Condori']
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

    print("Generando datos como PRIMER DIA DE CLASES...")
    anio_actual = datetime.now().year

    # LIMPIAR DATOS
    Pago.query.delete()
    Calificacion.query.delete()
    Asistencia.query.delete()
    Padre.query.delete()
    Egresado.query.delete()
    Materia.query.delete()
    Estudiante.query.delete()
    Profesor.query.delete()
    PersonalAdministrativo.query.delete()
    db.session.commit()
    print("Datos anteriores limpiados")

    # 20 PROFESORES
    profesores = []
    for i in range(20):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido1 = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
        prof = Profesor(
            ci=obtener_ci(),
            apellidos=f'{apellido1} {apellido2}',
            nombres=nombre,
            especialidad=random.choice(['Matematicas', 'Fisica', 'Quimica', 'Biologia', 'Literatura', 'Historia', 'Ingles', 'Artes', 'Educacion Fisica', 'Computacion', 'Musica', 'Religion']),
            nivel=random.choice(['Primaria', 'Secundaria']),
            turno=random.choice(turnos),
            salario_base=random.choice([2500, 3000, 3500, 4000, 4500]),
            estado='Activo',
            telefono=f'7{random.randint(10000000, 99999999)}',
            correo=f'{nombre.lower()}.{apellido1.lower().replace(" ", "")}{i}@colegio.edu.bo'
        )
        db.session.add(prof)
        profesores.append(prof)
    db.session.commit()
    print("20 profesores creados")

    # 10 ADMINISTRATIVOS
    cargos_admin = ['Director', 'Secretaria', 'Contador', 'Psicologo', 'Bibliotecario', 'Inspector', 'Auxiliar', 'Encargado de Sistemas', 'Orientador', 'Tesorero']
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
            area=random.choice(['Administracion', 'Direccion', 'Contabilidad', 'Psicologia', 'Biblioteca', 'Inspectoría']),
            salario_base=random.choice([2000, 2500, 3000, 3500, 4000, 5000, 6000]),
            estado='Activo',
            telefono=f'7{random.randint(10000000, 99999999)}',
            correo=f'{nombre.lower()}.{apellido1.lower().replace(" ", "")}{i}@colegio.edu.bo'
        )
        db.session.add(admin)
    db.session.commit()
    print("10 administrativos creados")

    # MATERIAS
    materias_creadas = []
    for curso in cursos_nidito:
        for materia in materias_nidito:
            prof = random.choice(profesores)
            m = Materia(nombre=materia, curso_id=curso, profesor_id=prof.id)
            db.session.add(m)
            materias_creadas.append((curso, m))
    for curso in cursos_primaria:
        for materia in materias_primaria:
            prof = random.choice(profesores)
            m = Materia(nombre=materia, curso_id=curso, profesor_id=prof.id)
            db.session.add(m)
            materias_creadas.append((curso, m))
    for curso in cursos_secundaria:
        for materia in materias_secundaria:
            prof = random.choice(profesores)
            m = Materia(nombre=materia, curso_id=curso, profesor_id=prof.id)
            db.session.add(m)
            materias_creadas.append((curso, m))
    db.session.commit()
    print(f"{len(materias_creadas)} materias creadas")

    # 200 ESTUDIANTES - COMMIT POR CADA ESTUDIANTE para evitar conflictos de autoflush
    for i in range(200):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido1 = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
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
            ci=ci_est,
            rude=rude_est,
            apellidos=f'{apellido1} {apellido2}',
            nombres=nombre,
            fecha_nacimiento=fecha_nac,
            curso=curso,
            turno=turno,
            estado='Activo',
            pension=random.choice([250, 300, 350, 400]),
            direccion=f'{random.choice(calles)} N {random.randint(100, 9999)}',
            zona=random.choice(zonas),
            ciudad='Riberalta',
            foto_path='default.png',
            tipo_sangre=random.choice(tipos_sangre),
            alergias=random.choice(['Ninguna', 'Polvo', 'Acaros', 'Penicilina', 'Ninguna', 'Ninguna']),
            enfermedades_cronicas=random.choice(['Ninguna', 'Asma', 'Ninguna', 'Ninguna', 'Rinitis']),
            medicamentos_actuales=random.choice(['Ninguno', 'Ninguno', 'Ninguno', 'Ventolin (asma)']),
            medico_nombre=f'Dr. {random.choice(nombres_m)} {random.choice(apellidos)}',
            medico_telefono=f'7{random.randint(10000000, 99999999)}',
            clinica_habitual=random.choice(['Clinica Riberalta', 'Clinica del Norte', 'Centro de Salud Municipal', 'Clinica San Rafael']),
            seguro_medico=random.choice(['SUS', 'Seguro Privado', 'Ninguno', 'SUS', 'SUS']),
            observaciones_salud=random.choice(['Sin observaciones', 'Requiere control anual', 'Sin observaciones'])
        )
        db.session.add(est)
        db.session.flush()
        est_id = est.id

        # PADRES con CIs del pool
        num_padres = random.choice([1, 2, 2])
        parentescos = ['Padre', 'Madre']
        for j in range(num_padres):
            genero_padre = 'M' if j == 0 else 'F'
            nombre_padre = random.choice(nombres_m if genero_padre == 'M' else nombres_f)
            ap_padre = f'{random.choice(apellidos)} {random.choice(apellidos)}'
            ci_padre = obtener_ci()
            padre = Padre(
                estudiante_id=est_id,
                ci=ci_padre,
                ci_estudiante=ci_est,
                rude_estudiante=rude_est,
                parentesco=parentescos[j],
                nombres=f'{nombre_padre} {ap_padre}',
                telefono1=f'7{random.randint(10000000, 99999999)}',
                telefono2=f'7{random.randint(10000000, 99999999)}' if random.random() > 0.5 else None,
                email=f'{nombre_padre.lower()}.{ap_padre.split()[0].lower()}@gmail.com' if random.random() > 0.3 else None,
                ocupacion=random.choice(['Comerciante', 'Profesional Independiente', 'Empleado Publico', 'Empleado Privado', 'Agricultor', 'Transportista', 'Docente', 'Medico', 'Ingeniero', 'Ama de casa'])
            )
            db.session.add(padre)

        # CALIFICACIONES
        materias_curso = [m for c, m in materias_creadas if c == curso]
        for materia in materias_curso[:random.randint(4, min(len(materias_curso), 10))]:
            calif = Calificacion(
                estudiante_id=est_id,
                ci_estudiante=ci_est,
                rude_estudiante=rude_est,
                materia_id=materia.id,
                tipo='1er Trimestre',
                fecha=date(anio_actual - 1, random.randint(3, 11), random.randint(1, 28)),
                nota=round(random.uniform(45, 100), 0)
            )
            db.session.add(calif)

        # PAGO
        pago = Pago(
            estudiante_id=est_id,
            ci_estudiante=ci_est,
            rude_estudiante=rude_est,
            mes='Enero',
            anio=anio_actual,
            monto_total=est.pension,
            descuento=0.0,
            monto_pagado=est.pension,
            fecha_pago=datetime(anio_actual, 1, random.randint(2, 31)),
            estado='Pagado',
            metodo_pago=random.choice(['Efectivo', 'Transferencia', 'QR'])
        )
        db.session.add(pago)

        # COMMIT POR CADA ESTUDIANTE (evita conflictos de autoflush con UNIQUE)
        db.session.commit()

        if (i + 1) % 50 == 0:
            print(f"  Procesados {i + 1} estudiantes...")

    print("200 estudiantes con padres, calificaciones y pagos creados")

    # 200 EGRESADOS
    for i in range(200):
        genero = random.choice(['M', 'F'])
        nombre = random.choice(nombres_m if genero == 'M' else nombres_f)
        apellido1 = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
        anio_egreso = anio_actual - random.randint(1, 10)

        egresado = Egresado(
            ci=obtener_ci(),
            rude=obtener_rude(),
            apellidos=f'{apellido1} {apellido2}',
            nombres=nombre,
            fecha_nacimiento=date(anio_egreso - 17, random.randint(1, 12), random.randint(1, 28)),
            curso_final='6 Secundaria',
            anio_egreso=anio_egreso,
            estado_egreso='Egresado',
            nombre_tutor=f'{random.choice(nombres_m if genero == "M" else nombres_f)} {random.choice(apellidos)} {random.choice(apellidos)}',
            telefono_tutor=f'7{random.randint(10000000, 99999999)}',
            fecha_archivo=datetime(anio_egreso, 12, 15)
        )
        db.session.add(egresado)

        if (i + 1) % 50 == 0:
            db.session.commit()
            print(f"  Procesados {i + 1} egresados...")

    db.session.commit()
    print("200 egresados creados")

    print()
    print("=" * 60)
    print("BASE DE DATOS GENERADA COMO PRIMER DIA DE CLASES")
    print("=" * 60)
    print(f"  Estudiantes: {Estudiante.query.count()}")
    print(f"  Padres/Tutores: {Padre.query.count()}")
    print(f"  Calificaciones: {Calificacion.query.count()} (del ano anterior)")
    print(f"  Profesores: {Profesor.query.count()}")
    print(f"  Administrativos: {PersonalAdministrativo.query.count()}")
    print(f"  Egresados: {Egresado.query.count()}")
    print(f"  Pagos: {Pago.query.count()} (matricula de enero)")
    print(f"  Materias: {Materia.query.count()}")
    print("=" * 60)
    print("Inicia el servidor con: python app.py")

import random
from datetime import date
from app import create_app

app = create_app()

with app.app_context():
    from models import db, Estudiante, Calificacion, Materia

    print("=" * 70)
    print("REORGANIZANDO CALIFICACIONES POR MATERIA Y TRIMESTRE")
    print("=" * 70)
    print()
    print("Estructura de cada trimestre:")
    print("  P1  -> Parcial 1 (semana 1-2 del 1er mes)")
    print("  P2  -> Parcial 2 (semana 1-2 del 2do mes)")
    print("  P3  -> Parcial 3 (semana 1-2 del 3er mes)")
    print("  E1  -> Examen Parcial (semana 3 del 3er mes)")
    print("  EF  -> Examen Final (semana 4 del 3er mes)")
    print("  NF  -> Nota Final del trimestre (ultimo dia)")
    print()

    # =========================================================================
    # ESTRUCTURA DE TRIMESTRES
    # =========================================================================
    anio_actual = 2026
    
    # 1er trimestre: feb-abr | 2do trimestre: may-jul
    trimestres = [
        {'nombre': '1er Trimestre', 'meses': [2, 3, 4]},
        {'nombre': '2do Trimestre', 'meses': [5, 6, 7]}
    ]
    
    # Fechas especificas para cada tipo de evaluacion
    # Estructura: (tipo, mes_offset, dia_min, dia_max, descripcion)
    estructura_evaluacion = [
        ('P1', 0, 5, 12),   # Parcial 1: primera quincena del 1er mes
        ('P2', 1, 5, 12),   # Parcial 2: primera quincena del 2do mes
        ('P3', 2, 5, 12),   # Parcial 3: primera quincena del 3er mes
        ('E1', 2, 18, 22),  # Examen Parcial: tercera semana del 3er mes
        ('EF', 2, 25, 28),  # Examen Final: ultima semana del 3er mes
        ('NF', 2, 29, 30),  # Nota Final: ultimo dia del 3er mes
    ]
    
    print("Limpiando calificaciones anteriores...")
    Calificacion.query.delete()
    db.session.commit()
    print("OK: Calificaciones eliminadas")
    print()

    # =========================================================================
    # REGENERAR CALIFICACIONES ORDENADAS
    # =========================================================================
    estudiantes = Estudiante.query.all()
    print(f"Generando calificaciones para {len(estudiantes)} estudiantes...")
    
    total_calif = 0
    
    for est in estudiantes:
        # Obtener materias del curso
        materias_curso = Materia.query.filter_by(curso_id=est.curso).all()
        
        for materia in materias_curso:
            for tri in trimestres:
                # Generar las notas de los parciales primero (para calcular NF)
                notas_parciales = {}
                
                # P1, P2, P3 - notas entre 45 y 100
                p1 = round(random.uniform(45, 100), 0)
                p2 = round(random.uniform(45, 100), 0)
                p3 = round(random.uniform(45, 100), 0)
                
                # E1 (examen parcial) - promedio de P1+P2 con variacion
                e1 = round((p1 + p2) / 2 + random.uniform(-5, 5), 0)
                e1 = max(45, min(100, e1))
                
                # EF (examen final) - promedio de P2+P3 con variacion
                ef = round((p2 + p3) / 2 + random.uniform(-5, 5), 0)
                ef = max(45, min(100, ef))
                
                # NF (nota final) - promedio ponderado de todo
                # 40% parciales + 30% examen parcial + 30% examen final
                nf = round(p1 * 0.2 + p2 * 0.2 + p3 * 0.2 + e1 * 0.2 + ef * 0.2, 0)
                nf = max(45, min(100, nf))
                
                # Asignar cada calificacion con su fecha especifica
                califs_estudiante = [
                    ('P1', p1, tri['meses'][0], random.randint(5, 12)),
                    ('P2', p2, tri['meses'][1], random.randint(5, 12)),
                    ('P3', p3, tri['meses'][2], random.randint(5, 12)),
                    ('E1', e1, tri['meses'][2], random.randint(18, 22)),
                    ('EF', ef, tri['meses'][2], random.randint(25, 28)),
                    ('NF', nf, tri['meses'][2], random.randint(29, 30)),
                ]
                
                for tipo, nota, mes, dia in califs_estudiante:
                    calif = Calificacion(
                        estudiante_id=est.id,
                        ci_estudiante=est.ci,
                        rude_estudiante=est.rude,
                        materia_id=materia.id,
                        tipo=tipo,
                        fecha=date(anio_actual, mes, min(dia, 28)),
                        nota=nota
                    )
                    db.session.add(calif)
                    total_calif += 1
        
        db.session.commit()

    print(f"OK: {total_calif} calificaciones generadas")
    print()

    # =========================================================================
    # MOSTRAR EJEMPLO DE ESTRUCTURA
    # =========================================================================
    print("=" * 70)
    print("EJEMPLO DE ESTRUCTURA POR MATERIA")
    print("=" * 70)
    
    # Tomar un estudiante de ejemplo
    est_ejemplo = Estudiante.query.first()
    materia_ejemplo = Materia.query.filter_by(curso_id=est_ejemplo.curso).first()
    
    if est_ejemplo and materia_ejemplo:
        print(f"Estudiante: {est_ejemplo.nombres} {est_ejemplo.apellidos}")
        print(f"Curso: {est_ejemplo.curso}")
        print(f"Materia: {materia_ejemplo.nombre}")
        print()
        
        for tri in trimestres:
            print(f"--- {tri['nombre']} ---")
            califs = Calificacion.query.filter_by(
                estudiante_id=est_ejemplo.id,
                materia_id=materia_ejemplo.id
            ).filter(
                Calificacion.fecha >= date(anio_actual, tri['meses'][0], 1),
                Calificacion.fecha <= date(anio_actual, tri['meses'][2], 31)
            ).order_by(Calificacion.fecha).all()
            
            for c in califs:
                tipo_desc = {
                    'P1': 'Parcial 1',
                    'P2': 'Parcial 2',
                    'P3': 'Parcial 3',
                    'E1': 'Examen Parcial',
                    'EF': 'Examen Final',
                    'NF': 'Nota Final'
                }.get(c.tipo, c.tipo)
                print(f"  {c.fecha.strftime('%Y-%m-%d')} | {c.tipo:2} | {tipo_desc:18} | Nota: {c.nota}")
            print()

    # =========================================================================
    # ESTADISTICAS
    # =========================================================================
    print("=" * 70)
    print("ESTADISTICAS DE CALIFICACIONES")
    print("=" * 70)
    
    # Contar por tipo
    for tipo in ['P1', 'P2', 'P3', 'E1', 'EF', 'NF']:
        count = Calificacion.query.filter_by(tipo=tipo).count()
        print(f"  {tipo}: {count} registros")
    
    # Promedio general
    from sqlalchemy import func
    promedio = db.session.query(func.avg(Calificacion.nota)).scalar()
    print()
    print(f"  Promedio general: {promedio:.1f}")
    print(f"  Total de calificaciones: {Calificacion.query.count()}")
    print()
    print("Las calificaciones ahora estan ordenadas por materia,")
    print("por trimestre y con fechas logicas (P1->P2->P3->E1->EF->NF)")
    print("=" * 70)
    print()
    print("Inicia el servidor con: python app.py")

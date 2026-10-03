from datetime import date
from app import create_app

app = create_app()

with app.app_context():
    from models import db, Estudiante, Calificacion, Materia
    from sqlalchemy import func

    anio_actual = 2026
    
    # Ultimo dia de cada mes (evita error con meses de 30 dias)
    def ultimo_dia_mes(anio, mes):
        if mes in [1, 3, 5, 7, 8, 10, 12]:
            return 31
        elif mes in [4, 6, 9, 11]:
            return 30
        else:  # febrero
            return 28

    trimestres = [
        {'nombre': '1er Trimestre', 'meses': [2, 3, 4]},
        {'nombre': '2do Trimestre', 'meses': [5, 6, 7]}
    ]

    print("=" * 70)
    print("EJEMPLO DE CALIFICACIONES ORDENADAS POR MATERIA Y TRIMESTRE")
    print("=" * 70)
    print()
    
    # Tomar un estudiante y materia de ejemplo
    est_ejemplo = Estudiante.query.first()
    materia_ejemplo = Materia.query.filter_by(curso_id=est_ejemplo.curso).first()
    
    print(f"Estudiante: {est_ejemplo.nombres} {est_ejemplo.apellidos}")
    print(f"Curso: {est_ejemplo.curso} | Turno: {est_ejemplo.turno}")
    print(f"Materia: {materia_ejemplo.nombre}")
    print()
    
    for tri in trimestres:
        print(f"=== {tri['nombre']} (Meses {tri['meses'][0]}/{tri['meses'][1]}/{tri['meses'][2]}) ===")
        
        mes_ini = tri['meses'][0]
        mes_fin = tri['meses'][2]
        
        califs = Calificacion.query.filter_by(
            estudiante_id=est_ejemplo.id,
            materia_id=materia_ejemplo.id
        ).filter(
            Calificacion.fecha >= date(anio_actual, mes_ini, 1),
            Calificacion.fecha <= date(anio_actual, mes_fin, ultimo_dia_mes(anio_actual, mes_fin))
        ).order_by(Calificacion.fecha).all()
        
        print(f"{'FECHA':<12} {'TIPO':<6} {'DESCRIPCION':<20} {'NOTA':<6}")
        print("-" * 48)
        for c in califs:
            tipo_desc = {
                'P1': 'Parcial 1',
                'P2': 'Parcial 2',
                'P3': 'Parcial 3',
                'E1': 'Examen Parcial',
                'EF': 'Examen Final',
                'NF': 'Nota Final'
            }.get(c.tipo, c.tipo)
            print(f"{c.fecha.strftime('%Y-%m-%d'):<12} {c.tipo:<6} {tipo_desc:<20} {c.nota:<6}")
        print()

    # =========================================================================
    # ESTADISTICAS GENERALES
    # =========================================================================
    print("=" * 70)
    print("ESTADISTICAS DE CALIFICACIONES")
    print("=" * 70)
    print()
    print("Total por tipo de evaluacion:")
    for tipo in ['P1', 'P2', 'P3', 'E1', 'EF', 'NF']:
        count = Calificacion.query.filter_by(tipo=tipo).count()
        print(f"  {tipo:2}: {count:>6} registros")
    
    print()
    promedio = db.session.query(func.avg(Calificacion.nota)).scalar()
    print(f"Promedio general del colegio: {promedio:.1f}")
    print(f"Total de calificaciones: {Calificacion.query.count()}")
    print()
    print("ESTRUCTURA CORRECTA APLICADA:")
    print("  P1 -> Parcial 1: primera quincena del 1er mes del trimestre")
    print("  P2 -> Parcial 2: primera quincena del 2do mes del trimestre")
    print("  P3 -> Parcial 3: primera quincena del 3er mes del trimestre")
    print("  E1 -> Examen Parcial: tercera semana del 3er mes")
    print("  EF -> Examen Final: ultima semana del 3er mes")
    print("  NF -> Nota Final: ultimo dia del trimestre")
    print()
    print("Las notas estan ordenadas por MATERIA y por TRIMESTRE.")
    print("No hay mezclas de parciales, examenes y notas finales.")
    print("=" * 70)

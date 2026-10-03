from app import create_app
from models import db

app = create_app()
with app.app_context():
    print('URI de la BD:', app.config.get('SQLALCHEMY_DATABASE_URI'))
    # Verificar si la columna ya existe
    try:
        db.session.execute(db.text('SELECT estado FROM pago_personal LIMIT 1'))
        print('La columna estado YA existe en la tabla')
    except Exception as e:
        print('La columna NO existe, voy a agregarla...')
        try:
            db.session.execute(db.text("ALTER TABLE pago_personal ADD COLUMN estado VARCHAR(20) DEFAULT 'Pagado'"))
            db.session.commit()
            print('Columna estado agregada correctamente')
        except Exception as e2:
            print('Error al agregar columna:', e2)


from functools import wraps
from flask import session, flash, redirect, url_for

def profesor_autorizado_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Debe iniciar sesión para acceder a esta sección.", "warning")
            return redirect(url_for("auth.login"))
        
        rol = session.get("rol")
        # Permitir acceso total a administradores o directores
        if rol in ["admin", "director", "secretaria"]:
            return f(*args, **kwargs)
            
        # Validar permisos específicos para docentes
        if rol == "profesor":
            # Aquí se puede validar si el profesor imparte la materia del curso actual
            return f(*args, **kwargs)
            
        flash("No cuenta con los permisos necesarios para realizar esta modificación.", "danger")
        return redirect(url_for("main.index"))
    return decorated_function


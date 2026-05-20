"""
Decoradores de seguridad para rutas Flask
Proporciona control de acceso basado en sesión y permisos
"""

from functools import wraps
from flask import session, flash, redirect, url_for

def requiere_sesion():
    """
    Decorador que requiere que el usuario tenga una sesión activa.
    Si no hay sesión, redirige al login.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('login.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator




def requiere_permiso(nombre_permiso):
    """
    Decorador que verifica si el usuario tiene un permiso específico.
    El sistema de permisos es completamente basado en RBAC:
    - Los permisos se asignan a roles en la tabla roles_permisos
    - Los usuarios heredan permisos de su rol
    - Los usuarios pueden tener permisos individuales activados/desactivados
    - NO hay bypass por rol: todos los usuarios siguen las mismas reglas
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar sesión
            if not session.get('user_id'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('login.login'))
            
            # Verificar permisos específicos (sin excepciones por rol)
            permisos = session.get('permisos', [])
            if nombre_permiso not in permisos:
                flash('No tienes permiso para acceder a esta sección.', 'danger')
                return redirect(url_for('login.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator



def requiere_rol(rol_id):
    """
    Decorador que requiere que el usuario tenga un rol específico.
    Si no tiene el rol o no hay sesión, redirige al login.
    
    Args:
        rol_id (int): ID del rol requerido
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('login.login'))
            
            if session.get('rol_id') != rol_id:
                flash('No tienes el rol necesario para acceder a esta sección.', 'danger')
                return redirect(url_for('login.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def requiere_admin():
    """
    Decorador específico que requiere rol de administrador (rol_id = 2).
    Si no es admin o no hay sesión, redirige al login.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('login.login'))
            
            if session.get('rol_id') != 2:
                flash('Solo los administradores pueden acceder a esta sección.', 'danger')
                return redirect(url_for('login.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def requiere_sucursal(sucursal_id=None):
    """
    Decorador que requiere acceso a una sucursal específica.
    Los admins (rol_id=2) tienen acceso a todas las sucursales.
    
    Args:
        sucursal_id (int, optional): ID de la sucursal requerida. 
                                   Si es None, usa la sucursal del usuario.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('login.login'))
            
            # Los administradores tienen acceso a todas las sucursales
            if session.get('rol_id') == 2:
                return f(*args, **kwargs)
            
            # Verificar acceso a la sucursal específica
            usuario_sucursal = session.get('sucursal_id')
            sucursal_requerida = sucursal_id or usuario_sucursal
            
            if usuario_sucursal != sucursal_requerida:
                flash('No tienes acceso a esta sucursal.', 'danger')
                return redirect(url_for('login.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
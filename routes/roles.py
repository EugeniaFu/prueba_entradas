from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso

roles_bp = Blueprint('roles', __name__, url_prefix='/roles')

@roles_bp.route('/')
@requiere_sesion()
@requiere_permiso('gestionar_roles_permisos')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Obtener todos los roles (Puedes omitir el rol 1 si es 'cliente' u otro que no necesite login al sistema)
    # Por ahora los mostramos todos.
    cursor.execute("SELECT * FROM roles ORDER BY id")
    roles = cursor.fetchall()
    
    # Obtener todos los permisos
    cursor.execute("SELECT * FROM permisos ORDER BY nombre")
    permisos = cursor.fetchall()
    
    # Obtener la asignación actual de permisos a roles
    cursor.execute("SELECT rol_id, permiso_id FROM roles_permisos WHERE permitido = 1")
    relaciones = cursor.fetchall()
    
    # Agrupar en un diccionario para poder checar rápido en la vista HTML
    # Formato: roles_permisos[rol_id] = [lista de permiso_id]
    roles_permisos = {r['id']: [] for r in roles}
    
    for rel in relaciones:
        if rel['rol_id'] in roles_permisos:
            roles_permisos[rel['rol_id']].append(rel['permiso_id'])
            
    cursor.close()
    conn.close()
    
    return render_template('roles/index.html', roles=roles, permisos=permisos, roles_permisos=roles_permisos)

@roles_bp.route('/guardar', methods=['POST'])
@requiere_sesion()
@requiere_permiso('gestionar_roles_permisos')
def guardar():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Limpiamos por completo la tabla de permisos de roles temporalmente
        # para luego insertar solo los que vienen marcados en los checkboxes
        cursor.execute("DELETE FROM roles_permisos")
        
        # 2. Recorremos lo que envió el administrador desde el formulario (checkboxes seleccionados)
        for key in request.form:
            if key.startswith('permiso_'):
                # El "name" del checkbox viene como: permiso_3_15 (rol 3, permiso 15)
                partes = key.split('_')
                if len(partes) == 3:
                    _, rol_id, permiso_id = partes
                    # Insertamos el nuevo registro
                    cursor.execute(
                        "INSERT INTO roles_permisos (rol_id, permiso_id, permitido) VALUES (%s, %s, 1)",
                        (rol_id, permiso_id)
                    )
        
        conn.commit()
        flash('¡Permisos por Rol actualizados y guardados correctamente!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ocurrió un error al guardar los permisos: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('roles.index'))
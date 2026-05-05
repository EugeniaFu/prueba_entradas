from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso

sucursales_bp = Blueprint('sucursales', __name__, url_prefix='/sucursales')

@sucursales_bp.route('/')
@requiere_sesion()
@requiere_permiso('ver_sucursales') # Asumiendo que quisieras un permiso para esto, o puedes usar 'ver_empleados' / validarlo para superadmin
def sucursales():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, direccion FROM sucursales ORDER BY id ASC")
    lista_sucursales = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('sucursales/index.html', sucursales=lista_sucursales)

@sucursales_bp.route('/nueva', methods=['POST'])
@requiere_sesion()
@requiere_permiso('ver_sucursales') # O el permiso de crear_sucursal
def nueva_sucursal():
    nombre = request.form.get('nombre')
    direccion = request.form.get('direccion')
    
    if not nombre or not direccion:
        flash('El nombre y la dirección son obligatorios.', 'danger')
        return redirect(url_for('sucursales.sucursales'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sucursales (nombre, direccion) VALUES (%s, %s)", (nombre, direccion))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Sucursal creada exitosamente.', 'success')
    return redirect(url_for('sucursales.sucursales'))

@sucursales_bp.route('/editar/<int:id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('ver_sucursales') 
def editar_sucursal(id):
    nombre = request.form.get('nombre')
    direccion = request.form.get('direccion')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sucursales SET nombre = %s, direccion = %s WHERE id = %s", (nombre, direccion, id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Sucursal actualizada correctamente.', 'success')
    return redirect(url_for('sucursales.sucursales'))

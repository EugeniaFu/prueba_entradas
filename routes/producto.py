from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso

bp_producto = Blueprint('producto', __name__, url_prefix='/producto')



# Mostrar productos
@bp_producto.route('/productos')
@requiere_sesion()
@requiere_permiso('ver_productos')
def productos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Traer productos y precios (incluye precio_dia)
    cursor.execute("""
        SELECT p.*, pr.precio_dia, pr.precio_14_dias, pr.precio_29_dias, pr.precio_30_dias
        FROM productos p
        LEFT JOIN producto_precios pr ON p.id_producto = pr.id_producto
        ORDER BY p.estatus DESC, p.nombre
    """)
    productos = cursor.fetchall()
    # Traer piezas asociadas a cada producto
    for producto in productos:
        cursor.execute("""
                       SELECT pp.id_pieza, pp.cantidad, pi.nombre_pieza, pi.descripcion
                       FROM producto_piezas pp
                       JOIN piezas pi ON pp.id_pieza = pi.id_pieza
                       WHERE pp.id_producto = %s
                       """, (producto['id_producto'],))
        producto['piezas'] = cursor.fetchall()

    # Traer piezas para el modal de alta/edición (solo activas)
    cursor.execute("SELECT * FROM piezas WHERE COALESCE(estatus, 'activo') = 'activo' ORDER BY nombre_pieza")
    piezas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventario/productos.html', productos=productos, piezas=piezas)

# Crear producto
@bp_producto.route('/crear', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_producto')
def crear_producto():
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion', '')
    tipo = request.form['tipo']
    precio_unico = 1 if request.form.get('precio_unico') == '1' else 0
    precio_dia = request.form.get('precio_dia') or 0
    
    # Si es precio único, usar precio_dia para todos los rangos
    if precio_unico:
        precio_14_dias = precio_dia
        precio_29_dias = precio_dia
        precio_30_dias = precio_dia
    else:
        # Si no es precio único, usar los valores del formulario o 0
        precio_14_dias = request.form.get('precio_14_dias') or 0
        precio_29_dias = request.form.get('precio_29_dias') or 0
        precio_30_dias = request.form.get('precio_30_dias') or 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
                   INSERT INTO productos (nombre, descripcion, tipo, estatus, precio_unico)
                   VALUES (%s, %s, %s, 'activo', %s)
                   """, (nombre, descripcion, tipo, precio_unico))
    id_producto = cursor.lastrowid
    cursor.execute("""
                   INSERT INTO producto_precios (id_producto, precio_dia, precio_14_dias, precio_29_dias, precio_30_dias)
                   VALUES (%s, %s, %s, %s, %s)
                   """, (id_producto, precio_dia, precio_14_dias, precio_29_dias, precio_30_dias))

    # Insertar piezas asociadas
    if tipo == 'individual':
        id_pieza = request.form['pieza_individual']
        cursor.execute("""
            INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
            VALUES (%s, %s, 1)
        """, (id_producto, id_pieza))
    elif tipo == 'conjunto':
        piezas_kit = request.form.getlist('pieza_kit[]')
        cantidades_kit = request.form.getlist('cantidad_kit[]')
        for id_pieza, cantidad in zip(piezas_kit, cantidades_kit):
            cursor.execute("""
                INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
                VALUES (%s, %s, %s)
            """, (id_producto, id_pieza, cantidad))

    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto guardado correctamente.', 'success')
    return redirect(url_for('producto.productos'))




# Editar producto
@bp_producto.route('/editar/<int:id_producto>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('editar_producto')
def editar_producto(id_producto):
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion', '')
    tipo = request.form['tipo']  
    precio_unico = 1 if request.form.get('precio_unico') == '1' else 0
    precio_dia = request.form.get('precio_dia') or 0
    
    # Si es precio único, usar precio_dia para todos los rangos
    if precio_unico:
        precio_14_dias = precio_dia
        precio_29_dias = precio_dia
        precio_30_dias = precio_dia
    else:
        # Si no es precio único, usar los valores del formulario o 0
        precio_14_dias = request.form.get('precio_14_dias') or 0
        precio_29_dias = request.form.get('precio_29_dias') or 0
        precio_30_dias = request.form.get('precio_30_dias') or 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(""" 
                   UPDATE productos SET nombre=%s, descripcion=%s, tipo=%s, precio_unico=%s WHERE id_producto=%s
                   """, (nombre, descripcion, tipo, precio_unico, id_producto))
    cursor.execute("""
                   UPDATE producto_precios SET precio_dia=%s, precio_14_dias=%s, precio_29_dias=%s, precio_30_dias=%s
                   WHERE id_producto=%s
                   """, (precio_dia, precio_14_dias, precio_29_dias, precio_30_dias, id_producto))
    # Elimina piezas asociadas actuales
    cursor.execute("DELETE FROM producto_piezas WHERE id_producto=%s", (id_producto,))
    # Inserta nuevas piezas asociadas según el tipo actualizado
    if tipo == 'individual':
        id_pieza = request.form['pieza_individual']
        cursor.execute("""
            INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
            VALUES (%s, %s, 1)
        """, (id_producto, id_pieza))
    elif tipo == 'conjunto':
        piezas_kit = request.form.getlist('pieza_kit[]')
        cantidades_kit = request.form.getlist('cantidad_kit[]')
        for id_pieza, cantidad in zip(piezas_kit, cantidades_kit):
            cursor.execute("""
                INSERT INTO producto_piezas (id_producto, id_pieza, cantidad)
                VALUES (%s, %s, %s)
            """, (id_producto, id_pieza, cantidad))

    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto guardado correctamente.', 'success')
    return redirect(url_for('producto.productos'))




# Dar de baja producto (descontinuar)
@bp_producto.route('/baja/<int:id_producto>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('baja_producto')
def dar_baja_producto(id_producto):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE productos SET estatus='descontinuado' WHERE id_producto=%s
    """, (id_producto,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto descontinuado correctamente.', 'warning')
    return redirect(url_for('producto.productos'))

# Dar de alta producto (activar)
@bp_producto.route('/alta/<int:id_producto>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('alta_producto')
def dar_alta_producto(id_producto):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE productos SET estatus='activo' WHERE id_producto=%s
    """, (id_producto,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Producto activado correctamente.', 'success')
    return redirect(url_for('producto.productos'))
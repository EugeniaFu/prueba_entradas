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
    cursor.execute("SELECT id, nombre, direccion, plantilla_renta, plantilla_cotizacion FROM sucursales ORDER BY id ASC")
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
    plantilla_renta = None
    plantilla_cotizacion = None

    if not nombre or not direccion:
        flash('El nombre y la dirección son obligatorios.', 'danger')
        return redirect(url_for('sucursales.sucursales'))

    # Insertar primero para obtener el id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sucursales (nombre, direccion) VALUES (%s, %s)", (nombre, direccion))
    sucursal_id = cursor.lastrowid

    # Manejar archivos PDF
    carpeta_destino = 'static/notas/'
    renta_file = request.files.get('plantilla_renta')
    cotizacion_file = request.files.get('plantilla_cotizacion')
    if renta_file and renta_file.filename.endswith('.pdf'):
        renta_filename = f"sucursal_{sucursal_id}_renta.pdf"
        renta_path = carpeta_destino + renta_filename
        renta_file.save(renta_path)
        plantilla_renta = renta_path
    if cotizacion_file and cotizacion_file.filename.endswith('.pdf'):
        cotizacion_filename = f"sucursal_{sucursal_id}_cotizacion.pdf"
        cotizacion_path = carpeta_destino + cotizacion_filename
        cotizacion_file.save(cotizacion_path)
        plantilla_cotizacion = cotizacion_path

    # Actualizar sucursal con rutas de plantillas si existen
    cursor.execute(
        "UPDATE sucursales SET plantilla_renta=%s, plantilla_cotizacion=%s WHERE id=%s",
        (plantilla_renta, plantilla_cotizacion, sucursal_id)
    )
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
    plantilla_renta = None
    plantilla_cotizacion = None

    conn = get_db_connection()
    cursor = conn.cursor()

    # Manejar archivos PDF
    carpeta_destino = 'static/notas/'
    renta_file = request.files.get('plantilla_renta')
    cotizacion_file = request.files.get('plantilla_cotizacion')
    if renta_file and renta_file.filename.endswith('.pdf'):
        renta_filename = f"sucursal_{id}_renta.pdf"
        renta_path = carpeta_destino + renta_filename
        renta_file.save(renta_path)
        plantilla_renta = renta_path
    if cotizacion_file and cotizacion_file.filename.endswith('.pdf'):
        cotizacion_filename = f"sucursal_{id}_cotizacion.pdf"
        cotizacion_path = carpeta_destino + cotizacion_filename
        cotizacion_file.save(cotizacion_path)
        plantilla_cotizacion = cotizacion_path

    # Actualizar campos
    update_query = "UPDATE sucursales SET nombre = %s, direccion = %s"
    params = [nombre, direccion]
    if plantilla_renta:
        update_query += ", plantilla_renta = %s"
        params.append(plantilla_renta)
    if plantilla_cotizacion:
        update_query += ", plantilla_cotizacion = %s"
        params.append(plantilla_cotizacion)
    update_query += " WHERE id = %s"
    params.append(id)
    cursor.execute(update_query, tuple(params))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Sucursal actualizada correctamente.', 'success')
    return redirect(url_for('sucursales.sucursales'))

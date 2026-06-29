import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso

sucursales_bp = Blueprint('sucursales', __name__, url_prefix='/sucursales')

# Estados de renta que cuentan como "actividad en curso" -- si una sucursal
# tiene alguna renta en uno de estos estados, no se permite darla de baja
# (igual que el resto del sistema ya considera "activas" estas rentas).
ESTADOS_RENTA_ACTIVOS = (
    'en curso', 'activo', 'activa renovacion', 'programada',
    'en recolección', 'entrega parcial'
)


def _asegurar_columna_activo(cursor):
    """Agrega la columna 'activo' a sucursales si todavía no existe (migración
    perezosa, mismo patrón que dashboard_notas/cortes_caja)."""
    try:
        cursor.execute("SELECT activo FROM sucursales LIMIT 1")
        cursor.fetchall()
    except Exception:
        cursor.execute("ALTER TABLE sucursales ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1")


@sucursales_bp.route('/')
@requiere_sesion()
@requiere_permiso('ver_sucursales') # Asumiendo que quisieras un permiso para esto, o puedes usar 'ver_empleados' / validarlo para superadmin
def sucursales():
    ver_bajas = request.args.get('ver_bajas', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    _asegurar_columna_activo(cursor)
    conn.commit()

    filtro_activo = 0 if ver_bajas == '1' else 1
    cursor.execute("""
        SELECT id, nombre, direccion, plantilla_renta, plantilla_cotizacion, activo
        FROM sucursales WHERE activo = %s ORDER BY id ASC
    """, (filtro_activo,))
    lista_sucursales = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('sucursales/index.html', sucursales=lista_sucursales, ver_bajas=ver_bajas)

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


@sucursales_bp.route('/baja/<int:id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('baja_sucursal')
def baja_sucursal(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    _asegurar_columna_activo(cursor)

    placeholders = ', '.join(['%s'] * len(ESTADOS_RENTA_ACTIVOS))
    cursor.execute(f"""
        SELECT COUNT(*) AS total FROM rentas
        WHERE id_sucursal = %s AND LOWER(TRIM(estado_renta)) IN ({placeholders})
    """, (id, *ESTADOS_RENTA_ACTIVOS))
    rentas_activas = cursor.fetchone()['total']

    if rentas_activas > 0:
        cursor.close()
        conn.close()
        flash(
            f'No se puede dar de baja: esta sucursal tiene {rentas_activas} renta(s) activa(s). '
            'Espera a que finalicen o cancélalas antes de dar de baja la sucursal.',
            'danger'
        )
        return redirect(url_for('sucursales.sucursales'))

    cursor.execute("UPDATE sucursales SET activo = 0 WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Sucursal dada de baja. Su historial (rentas, clientes, inventario) sigue disponible; '
          'solo deja de aparecer para operaciones nuevas.', 'success')
    return redirect(url_for('sucursales.sucursales'))


@sucursales_bp.route('/reactivar/<int:id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('baja_sucursal')
def reactivar_sucursal(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    _asegurar_columna_activo(cursor)
    cursor.execute("UPDATE sucursales SET activo = 1 WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Sucursal reactivada correctamente.', 'success')
    return redirect(url_for('sucursales.sucursales', ver_bajas='1'))


@sucursales_bp.route('/eliminar/<int:id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('eliminar_sucursal')
def eliminar_sucursal(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    _asegurar_columna_activo(cursor)

    # Solo se permite eliminar definitivamente si la sucursal nunca tuvo
    # ninguna actividad real -- de lo contrario se rompería el historial
    # (rentas, clientes, inventario, caja) que depende de este id.
    cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM rentas WHERE id_sucursal = %s) AS rentas,
            (SELECT COUNT(*) FROM clientes WHERE sucursal_id = %s) AS clientes,
            (SELECT COUNT(*) FROM inventario_sucursal WHERE id_sucursal = %s) AS inventario,
            (SELECT COUNT(*) FROM movimientos_caja WHERE sucursal_id = %s) AS movimientos_caja,
            (SELECT COUNT(*) FROM usuarios WHERE sucursal_id = %s) AS usuarios
    """, (id, id, id, id, id))
    conteos = cursor.fetchone()

    if any(conteos.values()):
        cursor.close()
        conn.close()
        detalle = ', '.join(f"{k}: {v}" for k, v in conteos.items() if v)
        flash(
            f'No se puede eliminar definitivamente: esta sucursal tiene registros asociados ({detalle}). '
            'Solo se puede eliminar una sucursal que nunca haya tenido actividad. Usa "dar de baja" en su lugar.',
            'danger'
        )
        return redirect(url_for('sucursales.sucursales', ver_bajas='1'))

    cursor.execute("SELECT plantilla_renta, plantilla_cotizacion FROM sucursales WHERE id = %s", (id,))
    sucursal = cursor.fetchone()
    if sucursal:
        for ruta in (sucursal.get('plantilla_renta'), sucursal.get('plantilla_cotizacion')):
            if ruta and os.path.exists(ruta):
                try:
                    os.remove(ruta)
                except OSError:
                    pass

    cursor.execute("DELETE FROM sucursales WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Sucursal eliminada definitivamente.', 'success')
    return redirect(url_for('sucursales.sucursales', ver_bajas='1'))



# ======================= IMPORTS =======================
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, time, timedelta
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso
from itertools import zip_longest
from utils.datetime_utils import get_local_now, get_local_now_naive
# PDF/Reportlab imports (usados en otras rutas, mantener agrupados)
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from services.renta_service import RentasService

# ======================= BLUEPRINT =======================
rentas_bp = Blueprint('rentas', __name__, url_prefix='/rentas')



###########################################################
# ======================= ELIMINACIÓN DE RENTAS =======================
@rentas_bp.route('/info_eliminar/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def info_eliminar_renta(renta_id):
    mensaje = RentasService.info_eliminar_renta(renta_id)
    return jsonify({"status": "ok", "mensaje": mensaje})



@rentas_bp.route('/eliminar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('eliminar_renta')
def eliminar_renta(renta_id):
    success, msg = RentasService.eliminar_renta(renta_id)
    if success:
        return jsonify({"status": "ok", "mensaje": msg})
    else:
        return jsonify({"status": "error", "mensaje": msg})






###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
# ======================= CANCELACIÓN DE RENTAS =======================
@rentas_bp.route('/cancelar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('cancelar_renta')
def cancelar_renta(renta_id):
    motivo = request.form.get('motivo_cancelacion', '')
    monto_reembolso = request.form.get('monto_reembolso', None)
    
    success, msg = RentasService.cancelar_renta(renta_id, motivo, monto_reembolso)
    if success:
        return jsonify({"status": "ok", "mensaje": msg})
    else:
        return jsonify({"status": "error", "mensaje": msg})




###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
# ======================= LISTADO Y CREACIÓN DE RENTAS =======================
@rentas_bp.route('/')
@rentas_bp.route('/<sucursal_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def modulo_rentas(sucursal_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    sucursal_id_usuario = session.get('sucursal_id')
    
    sucursales = RentasService.obtener_sucursales() if sucursal_id_usuario is None else []
    
    if sucursal_id:
        request.args = request.args.copy()
        sucursal_filtro = str(sucursal_id)
    else:
        sucursal_filtro = request.args.get('sucursal_id')
        
    sucursal_actual = None
    
    if sucursal_id_usuario is None:
        if sucursal_filtro and sucursal_filtro != 'todas':
            try:
                sucursal_filtro = int(sucursal_filtro)
                cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_filtro,))
                row = cursor.fetchone()
                sucursal_actual = {'id': sucursal_filtro, 'nombre': row[0] if row else 'Desconocida'}
            except (ValueError, TypeError):
                sucursal_filtro = None
                
        elif sucursal_filtro == 'todas':
            sucursal_actual = {'id': 'todas', 'nombre': 'Todas las Sucursales'}
        
        # Si el admin entra a /rentas/ sin especificar sucursal, lo redirigimos a su sucursal base
        if not sucursal_filtro:
            cursor.close()
            conn.close()
            return redirect(url_for('rentas.modulo_rentas', sucursal_id=sucursal_id_usuario))
    else:
        sucursal_filtro = sucursal_id_usuario
        cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_id_usuario,))
        row = cursor.fetchone()
        sucursal_actual = {'id': sucursal_id_usuario, 'nombre': row[0] if row else 'Mi Sucursal'}

    # Si no se especifica sucursal_id para un usuario normal, redirigirlo a la url con ID
    if not sucursal_filtro and sucursal_id_usuario is not None:
        cursor.close()
        conn.close()
        return redirect(url_for('rentas.modulo_rentas', sucursal_id=sucursal_id_usuario))

    # ---- OBTENER RENTAS A TRAVÉS DEL SERVICE ----
    sucursal_para_servicio = sucursal_actual['id'] if sucursal_actual['id'] != 'todas' else 'todas'
    es_admin = (sucursal_id_usuario is None)
    rentas_crudas = RentasService.obtener_rentas_por_sucursal_y_estado(sucursal_para_servicio, es_admin, 'activas')
    rentas_pagadas_crudas = RentasService.obtener_rentas_por_sucursal_y_estado(sucursal_para_servicio, es_admin, 'pagadas')

    rentas = rentas_crudas
    rentas_pagadas = rentas_pagadas_crudas

    detalles = []
    productos_por_renta = {}
    rentas_con_productos = rentas + rentas_pagadas
    
    if rentas_con_productos:
        renta_ids = [str(renta[0]) for renta in rentas_con_productos]
        if renta_ids:
            format_strings = ','.join(['%s'] * len(renta_ids))
            cursor.execute(f"""
                SELECT d.renta_id, p.nombre, d.cantidad, d.id_producto, p.tipo
                FROM renta_detalle d
                JOIN productos p ON d.id_producto = p.id_producto
                WHERE d.renta_id IN ({format_strings})
            """, tuple(renta_ids))
            detalles = cursor.fetchall()
            for renta_id, nombre, cantidad, id_producto, tipo in detalles:
                productos_por_renta.setdefault(renta_id, []).append(f"{nombre} x{cantidad}")

    # Clientes activos
    cursor.execute("SELECT id, nombre, apellido1 FROM clientes WHERE activo = 1")
    clientes = cursor.fetchall()

    # Productos y precios
    cursor.execute("""
        SELECT p.id_producto, p.nombre, 
               pp.precio_dia, pp.precio_14_dias, pp.precio_29_dias, pp.precio_30_dias, p.precio_unico
        FROM productos p
        JOIN producto_precios pp ON p.id_producto = pp.id_producto
        WHERE p.estatus = 'activo'
        ORDER BY p.nombre
    """)
    productos = cursor.fetchall()

    precios_productos = {
        prod[0]: {
            "precio_dia": float(prod[2]),
            "precio_14_dias": float(prod[3]),
            "precio_29_dias": float(prod[4]),
            "precio_30_dias": float(prod[5]),
            "precio_unico": int(prod[6])
        } for prod in productos
    }

    def calcular_estado_entrega(renta):
        if not renta[3]: return None
        if renta[15]: return None
        if renta[4] is None or renta[4].lower() not in ['activo', 'activa renovacion']: return None
        
        fecha_entrada = renta[3]  
        fecha_limite = renta[16]  
        ahora_naive = get_local_now_naive()
        
        if fecha_limite:
            fecha_limite_con_hora = datetime.combine(fecha_limite, time(10,0))
            if ahora_naive > fecha_limite_con_hora:
                return {'estado': 'vencida', 'clase': 'badge-vencida', 'texto': 'Vencida'}
            elif ahora_naive.date() >= fecha_entrada:
                return {'estado': 'por_regresar', 'clase': 'badge-por-regresar', 'texto': 'Por regresar'}
        return None

    # Aplicar la función a todas las rentas
    rentas_con_estado = []
    for renta in rentas:
        estado_entrega = calcular_estado_entrega(renta)
        rentas_con_estado.append(list(renta) + [estado_entrega])

    cursor.close()
    conn.close()

    return render_template(
        'rentas/index.html',
        rentas=rentas_con_estado,
        clientes=clientes,
        productos=productos,
        productos_por_renta=productos_por_renta,
        sucursal_nombre=sucursal_actual['nombre'],
        precios_productos=precios_productos,
        sucursal_id=sucursal_id_usuario,
        sucursales=sucursales,
        sucursal_actual=sucursal_actual,
        es_admin=(sucursal_id_usuario is None),
        rentas_pagadas=rentas_pagadas
    )



# ======================= UTILIDADES =======================
def obtener_siguiente_folio_sucursal(cursor, sucursal_id):
    """
    Obtiene el siguiente folio consecutivo para una sucursal específica
    """
    cursor.execute("""
        SELECT COALESCE(MAX(
            (SELECT COUNT(*) FROM rentas r2 WHERE r2.id_sucursal = %s AND r2.id <= r.id)
        ), 0) + 1 
        FROM rentas r 
        WHERE r.id_sucursal = %s
    """, (sucursal_id, sucursal_id))
    resultado = cursor.fetchone()
    return resultado[0] if resultado else 1

def generar_folio_display(sucursal_id, folio_numero):
    """
    Genera el folio formateado para mostrar
    Formato: SUC1-0001, SUC2-0001, etc.
    """
    return f"SUC{sucursal_id}-{folio_numero:04d}"









###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
# ======================= CREAR RENTA =======================
@rentas_bp.route('/crear', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_renta')
def crear_renta():
    try:
        sucursal_id_usuario = session.get('sucursal_id')
        es_admin = (sucursal_id_usuario is None)
        
        # Determinar la sucursal de destino
        sucursal_para_renta = request.form.get('id_sucursal')
        if not sucursal_para_renta:
            sucursal_para_renta = sucursal_id_usuario
            
        try:
            sucursal_para_renta = int(sucursal_para_renta) if sucursal_para_renta else None
        except (ValueError, TypeError):
            sucursal_para_renta = sucursal_id_usuario

        if not sucursal_para_renta:
            flash("Error: No se pudo determinar la sucursal al crear la renta.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))

        # Embalar los datos del form de forma limpia
        datos_renta = {
            'renta_programada': request.form.get('renta_programada'),
            'cliente_id': request.form['cliente_id'],
            'direccion_obra': request.form['direccion_obra'],
            'fecha_salida': request.form['fecha_salida'],
            'fecha_entrada': request.form.get('fecha_entrada') or None,
            'observaciones': request.form.get('observaciones'),
            'fecha_registro': get_local_now(),
            'fecha_programada': request.form.get('fecha_programada') or None,
            'costo_traslado': float(request.form.get('costo_traslado') or 0),
            'traslado': request.form.get('traslado') or 'ninguno'
        }

        # Arrays de detalles
        productos = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        dias = request.form.getlist('dias_renta[]')
        costos = request.form.getlist('costo_unitario[]')

        # Delegar al servicio
        success, renta_id, su_id_usada, err_msg = RentasService.crear_nueva_renta(
            datos_renta, sucursal_para_renta, es_admin, productos, cantidades, dias, costos
        )

        if success:
            # Reutilizamos las funciones utilitarias que ya tienes en el controlador
            conn = get_db_connection()
            cursor = conn.cursor()
            folio_numero = obtener_siguiente_folio_sucursal(cursor, su_id_usada)
            folio_display = generar_folio_display(su_id_usada, folio_numero)
            cursor.close()
            conn.close()
            
            flash(f"Renta {folio_display} registrada con éxito.", "success")
        else:
            flash(f"Error al guardar la renta: {err_msg}", "danger")
            
    except Exception as e:
        flash(f"Error general en la solicitud: {e}", "danger")

    # Redireccionar a la vista de la sucursal donde se creó la renta (sea admin o empleado)
    return redirect(url_for('rentas.modulo_rentas', sucursal_id=sucursal_para_renta))



############################################################
############################################################
#############################################################
##############################################################|
#############################################################
###########################################################
# ======================= ACTUALIZAR FECHA DE ENTRADA =======================
@rentas_bp.route('/actualizar_fecha_entrada/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('editar_renta')
def actualizar_fecha_entrada(renta_id):
    try:
        nueva_fecha_str = request.json.get('fecha_entrada')
        if not nueva_fecha_str:
            return jsonify({'success': False, 'error': 'Fecha de entrada no proporcionada'}), 400

        # Parsear fecha_entrada enviada
        nueva_fecha = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()

        success, msg = RentasService.actualizar_fecha_entrada(renta_id, nueva_fecha)
        if success:
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'success': False, 'error': msg}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

###########################################################
# ======================= CERRAR RENTA =======================
@rentas_bp.route('/cerrar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('cerrar_renta')
def cerrar_renta(renta_id):
    try:
        fecha_entrada_str = request.form.get('fecha_entrada')
        if not fecha_entrada_str:
            flash("Debes ingresar la fecha de entrada para cerrar la renta.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))

        fecha_entrada = datetime.strptime(fecha_entrada_str, "%Y-%m-%d").date()
        
        success, msg = RentasService.cerrar_renta(renta_id, fecha_entrada)
        if success:
            flash(msg, "success")
        else:
            flash(f"Error al cerrar la renta: {msg}", "danger")

    except Exception as e:
        flash(f"Error parseando fechas o datos: {e}", "danger")

    return redirect(url_for('rentas.modulo_rentas'))





###########################################################
###########################################################
###########################################################
###########################################################
# ======================= DETALLE DE RENTA =======================
@rentas_bp.route('/detalle/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def obtener_detalle_renta(renta_id):
    success, err_msg, renta_dict, cliente_dict, productos = RentasService.obtener_detalle_renta(renta_id, get_local_now_naive)
    
    if not success:
        if err_msg == "Renta no encontrada":
            return jsonify({'error': err_msg}), 404
        return jsonify({'error': err_msg}), 500

    return jsonify({
        'renta': renta_dict,
        'cliente': cliente_dict,
        'productos': productos
    })

###########################################################
# ======================= RENOVAR RENTA =======================
@rentas_bp.route('/renovar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('renovar_renta')
def renovar_renta(renta_id):
    nueva_fecha_salida = request.form.get('nueva_fecha_salida')
    if not nueva_fecha_salida:
        flash("Debes ingresar la nueva fecha de salida para renovar la renta.", "danger")
        return redirect(url_for('rentas.modulo_rentas'))

    fecha_entrada = request.form.get('fecha_entrada') or None
    observaciones = request.form.get('observaciones') or ''
    productos = request.form.getlist('producto_id[]')
    cantidades = request.form.getlist('cantidad[]')
    dias_form = request.form.getlist('dias_renta[]')
    costos = request.form.getlist('costo_unitario[]')

    success, nueva_renta_id, sucursal_id, msg = RentasService.renovar_renta(
        renta_id, nueva_fecha_salida, fecha_entrada, observaciones,
        productos, cantidades, dias_form, costos, get_local_now()
    )

    if success:
        flash(f"{msg} (nueva renta ID {nueva_renta_id}).", "success")
    else:
        flash(f"Error al renovar la renta: {msg}", "danger")

    return redirect(url_for(
        'rentas.modulo_rentas',
        sucursal_id=sucursal_id or session.get('sucursal_id')
    ))

###########################################################
# ======================= API: RENTAS PENDIENTES =======================
@rentas_bp.route('/api/rentas_pendientes/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def api_rentas_pendientes(renta_id):
    """Endpoint para obtener productos pendientes de una renta"""
    success, msg, dir_obra, cl_nombre, pendientes = RentasService.obtener_productos_pendientes(renta_id)
    if success:
        return jsonify({
            'success': True,
            'direccion_obra': dir_obra,
            'cliente_nombre': cl_nombre,
            'pendientes': pendientes
        })
    return jsonify({'success': False, 'error': msg})

###########################################################
# ======================= CREAR RENOVACIÓN DE PENDIENTES =======================
@rentas_bp.route('/renovacion_pendientes/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_renovacion_pendiente')
def crear_renovacion_pendientes(renta_id):
    """Endpoint para crear renovación de productos pendientes"""
    data = request.get_json()
    if not data or not data.get('fecha_salida') or not data.get('fecha_entrada'):
        return jsonify({'success': False, 'error': 'Fechas son requeridas'})

    success, nueva_renta_id, msg = RentasService.crear_renovacion_pendientes(renta_id, data)
    
    if success:
        return jsonify({
            'success': True,
            'nueva_renta_id': nueva_renta_id,
            'message': msg
        })
    return jsonify({'success': False, 'error': msg})
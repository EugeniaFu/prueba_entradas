from flask import Blueprint, jsonify, request
from utils.db import get_db_connection
from datetime import datetime, timedelta




cobro_retraso_bp = Blueprint('cobro_retraso', __name__, url_prefix='/cobros_retraso')

# --- PREVIEW: Obtener datos para el modal de cobro por retraso ---
@cobro_retraso_bp.route('/preview/<int:renta_id>')
def preview_cobro_retraso(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener nota de entrada y días de retraso
    cursor.execute("""
        SELECT ne.id AS nota_entrada_id, ne.estado_retraso, ne.fecha_entrada_real, r.fecha_entrada
        FROM notas_entrada ne
        JOIN rentas r ON ne.renta_id = r.id
        WHERE r.id = %s
        ORDER BY ne.id DESC LIMIT 1
    """, (renta_id,))
    nota = cursor.fetchone()
    if not nota:
        cursor.close()
        conn.close()
        return jsonify({'error': 'No hay nota de entrada para esta renta'}), 404

    # Calcular días de retraso
    fecha_limite = None
    # Calcular días de retraso
    dias_retraso = 0
    if nota['fecha_entrada']:
        fecha_limite_dt = datetime.combine(nota['fecha_entrada'] + timedelta(days=1), datetime.strptime('10:00', '%H:%M').time())
        if nota['fecha_entrada_real']:
            if nota['fecha_entrada_real'] <= fecha_limite_dt:
                dias_retraso = 0
            else:
                delta = nota['fecha_entrada_real'] - fecha_limite_dt
                dias_retraso = delta.days + (1 if delta.seconds > 0 else 0)

    # Obtener productos de la renta con precio original
    cursor.execute("""
        SELECT rd.id_producto, p.nombre, rd.cantidad, rd.costo_unitario
        FROM renta_detalle rd
        JOIN productos p ON rd.id_producto = p.id_producto
        WHERE rd.renta_id = %s
    """, (renta_id,))
    productos = cursor.fetchall()

    # Calcular subtotales por producto
    detalles = []
    for prod in productos:
        subtotal = prod['cantidad'] * prod['costo_unitario'] * dias_retraso
        detalles.append({
            'id_producto': prod['id_producto'],
            'nombre_producto': prod['nombre'],
            'cantidad': prod['cantidad'],
            'precio_unitario': prod['costo_unitario'],
            'dias_retraso': dias_retraso,
            'subtotal': subtotal
        })

    cursor.close()
    conn.close()

    return jsonify({
        'nota_entrada_id': nota['nota_entrada_id'],
        'dias_retraso': dias_retraso,
        'detalles': detalles
    })

# --- GUARDAR COBRO POR RETRASO ---
@cobro_retraso_bp.route('/guardar/<int:renta_id>', methods=['POST'])
def guardar_cobro_retraso(renta_id):
    data = request.get_json()
    nota_entrada_id = data.get('nota_entrada_id')
    detalles = data.get('detalles', [])
    subtotal = data.get('subtotal', 0)
    iva = data.get('iva', 0)
    total = data.get('total', 0)
    metodo_pago = data.get('metodo_pago')
    monto_recibido = data.get('monto_recibido', 0)
    cambio = data.get('cambio', 0)
    observaciones = data.get('observaciones', '')
    facturable = int(data.get('facturable', 0))
    traslado_extra = data.get('traslado_extra', 'ninguno')
    costo_traslado_extra = float(data.get('costo_traslado_extra', 0))
    estado_pago = data.get('estado_pago', 'Retraso Pagado')
    numero_seguimiento = data.get('numero_seguimiento', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Insertar cobro retraso
    cursor.execute("""
        INSERT INTO notas_cobro_retraso (
            nota_entrada_id, fecha, subtotal, iva, total, metodo_pago, monto_recibido, cambio,
            observaciones, facturable, traslado_extra, costo_traslado_extra, estado_pago, numero_seguimiento
        ) VALUES ( %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )
    """, (
        nota_entrada_id, subtotal, iva, total, metodo_pago, monto_recibido, cambio,
        observaciones, facturable, traslado_extra, costo_traslado_extra, estado_pago, numero_seguimiento
    ))
    cobro_retraso_id = cursor.lastrowid

    # Insertar detalles
    for det in detalles:
        cursor.execute("""
            INSERT INTO notas_cobro_retraso_detalle (
                cobro_retraso_id, id_producto, nombre_producto, cantidad, precio_unitario, dias_retraso, subtotal
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            cobro_retraso_id,
            det['id_producto'],
            det['nombre_producto'],
            det['cantidad'],
            det['precio_unitario'],
            det['dias_retraso'],
            det['subtotal']
        ))

    # Actualizar estado de retraso en nota de entrada
    cursor.execute("""
        UPDATE notas_entrada SET estado_retraso = 'Retraso Pagado'
        WHERE id = %s
    """, (nota_entrada_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'cobro_retraso_id': cobro_retraso_id})
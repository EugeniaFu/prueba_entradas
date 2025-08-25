# routes/cobros_extra.py
from flask import Blueprint, jsonify, request
from utils.db import get_db_connection
from datetime import datetime

from flask import send_file
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

bp_extras = Blueprint('cobros_extra', __name__, url_prefix='/cobros_extra')

@bp_extras.route('/detalle/<int:renta_id>', methods=['GET'])
def detalle_cobro_extra(renta_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cobro = None
    detalles = []
    try:
        cursor.execute("""
            SELECT nc.*, ne.id AS nota_entrada_id
            FROM notas_cobro_extra nc
            JOIN notas_entrada ne ON nc.nota_entrada_id = ne.id
            WHERE ne.renta_id = %s
            ORDER BY nc.id DESC LIMIT 1
        """, (renta_id,))
        cobro = cursor.fetchone()
        if cobro:
            cursor.execute("""
                SELECT * FROM notas_cobro_extra_detalle
                WHERE cobro_extra_id = %s
            """, (cobro['id'],))
            detalles = cursor.fetchall()
        return jsonify({
            'cobro': cobro,
            'detalles': detalles
        })
    finally:
        cursor.close()
        db.close()




##############################################
##############################################
##############################################
##############################################

@bp_extras.route('/crear/<int:renta_id>', methods=['POST'])
def crear_cobro_extra(renta_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    data = request.get_json()
    subtotal = float(data.get('subtotal', 0))
    iva = float(data.get('iva', 0))
    total = float(data.get('total', 0))
    metodo_pago = data.get('metodo_pago', '')
    monto_recibido = float(data.get('monto_recibido', total))  # Puedes ajustar esto en el frontend
    cambio = float(data.get('cambio', 0))
    facturable = int(data.get('facturable', 0))
    numero_seguimiento = data.get('numero_seguimiento', '')
    observaciones = data.get('observaciones', '')
    estado_pago = "Extra Pagado" if monto_recibido >= total else "Extra Pendiente"
    tipo = data.get('tipo', 'extra')
    fecha = datetime.now()
    detalles = data.get('detalles', [])

    try:
        # Obtener nota_entrada_id
        cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s ORDER BY id DESC LIMIT 1", (renta_id,))
        nota_entrada = cursor.fetchone()
        if not nota_entrada:
            return jsonify({'success': False, 'error': 'No se encontró la nota de entrada.'}), 400
        nota_entrada_id = nota_entrada['id']

        # Crear cobro extra principal
        cursor.execute("""
            INSERT INTO notas_cobro_extra (
                nota_entrada_id, tipo, subtotal, iva, total, metodo_pago,
                monto_recibido, cambio, fecha, facturable, numero_seguimiento,
                observaciones, estado_pago
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s
            )
        """, (
            nota_entrada_id, tipo, subtotal, iva, total, metodo_pago,
            monto_recibido, cambio, fecha, facturable, numero_seguimiento,
            observaciones, estado_pago
        ))
        cobro_id = cursor.lastrowid

        # Crear detalles
        for det in detalles:
            cursor.execute("""
                INSERT INTO notas_cobro_extra_detalle (
                    cobro_extra_id, id_pieza, tipo_afectacion, cantidad,
                    costo_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                cobro_id,
                det.get('id_pieza'),
                det.get('tipo_afectacion'),
                int(det.get('cantidad', 0)),
                float(det.get('costo_unitario', 0)),
                float(det.get('subtotal', 0))
            ))

            # Después de crear el cobro extra principal y antes de db.commit()
            cursor.execute("""
                UPDATE rentas SET estado_cobro_extra = %s WHERE id = %s
            """, (estado_pago, renta_id))

        db.commit()
        return jsonify({'success': True, 'cobro_id': cobro_id})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        db.close()




##############################################
##############################################
##############################################
##############################################

@bp_extras.route('/sugerencias/<int:renta_id>', methods=['GET'])
def sugerencias_cobro_extra(renta_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # Obtener nota de entrada
        cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s ORDER BY id DESC LIMIT 1", (renta_id,))
        nota_entrada = cursor.fetchone()
        if not nota_entrada:
            return jsonify({'detalles': []})

        nota_entrada_id = nota_entrada['id']
        cursor.execute("""
            SELECT nd.id_pieza, p.nombre_pieza,
                   nd.cantidad_danada, nd.cantidad_sucia, nd.cantidad_perdida
            FROM notas_entrada_detalle nd
            JOIN piezas p ON nd.id_pieza = p.id_pieza
            WHERE nd.nota_entrada_id = %s
        """, (nota_entrada_id,))
        piezas = cursor.fetchall()

        detalles = []
        for pieza in piezas:
            for tipo, campo in [('dañada', 'cantidad_danada'), ('sucia', 'cantidad_sucia'), ('perdida', 'cantidad_perdida')]:
                cantidad = pieza[campo]
                if cantidad > 0:
                    detalles.append({
                        'id_pieza': pieza['id_pieza'],
                        'nombre_pieza': pieza['nombre_pieza'],
                        'tipo_afectacion': tipo,
                        'cantidad': cantidad,
                        'costo_unitario': 0,
                        'subtotal': 0
                    })
        # Agregar traslado extra si aplica
        cursor.execute("""
            SELECT requiere_traslado_extra, costo_traslado_extra
            FROM notas_entrada
            WHERE id = %s
        """, (nota_entrada_id,))
        traslado_row = cursor.fetchone()
        if traslado_row and traslado_row['requiere_traslado_extra'] in ['medio', 'redondo'] and traslado_row['costo_traslado_extra'] > 0:
            detalles.append({
                'id_pieza': None,
                'nombre_pieza': f"Traslado Extra ({traslado_row['requiere_traslado_extra'].capitalize()})",
                'tipo_afectacion': 'traslado_extra',
                'cantidad': 1,
                'costo_unitario': traslado_row['costo_traslado_extra'],
                'subtotal': traslado_row['costo_traslado_extra'],
                'es_traslado_extra': True
            })
        return jsonify({'detalles': detalles})
    finally:
        cursor.close()
        db.close()





##############################################
##############################################
##############################################
##############################################

@bp_extras.route('/pdf/<int:cobro_extra_id>')
def generar_pdf_cobro_extra(cobro_extra_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT nc.*, r.direccion_obra, c.nombre, c.apellido1, c.apellido2
        FROM notas_cobro_extra nc
        JOIN notas_entrada ne ON nc.nota_entrada_id = ne.id
        JOIN rentas r ON ne.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        WHERE nc.id = %s
    """, (cobro_extra_id,))
    cobro = cursor.fetchone()
    cursor.execute("""
        SELECT * FROM notas_cobro_extra_detalle WHERE cobro_extra_id = %s
    """, (cobro_extra_id,))
    detalles = cursor.fetchall()
    cursor.close()
    db.close()

    # Generar PDF sencillo
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont("Helvetica-Bold", 16)
    can.drawString(60, 750, f"Nota de Cobro Extra #{str(cobro['id']).zfill(5)}")
    can.setFont("Helvetica", 10)
    can.drawString(60, 730, f"Fecha: {cobro['fecha'].strftime('%d/%m/%Y %H:%M')}")
    can.drawString(60, 715, f"Cliente: {cobro['nombre']} {cobro['apellido1']} {cobro['apellido2']}")
    can.drawString(60, 700, f"Dirección de Obra: {cobro['direccion_obra']}")
    can.drawString(60, 685, f"Método de pago: {cobro['metodo_pago']}")
    can.drawString(60, 670, f"Total: ${cobro['total']:.2f} (IVA: ${cobro['iva']:.2f})")
    y = 650
    can.setFont("Helvetica-Bold", 11)
    can.drawString(60, y, "Detalles de recargo extra:")
    y -= 15
    can.setFont("Helvetica", 10)
    for det in detalles:
        can.drawString(60, y, f"{det['tipo_afectacion'].title()} - Pieza {det['id_pieza']}: {det['cantidad']} x ${det['costo_unitario']:.2f} = ${det['subtotal']:.2f}")
        y -= 13
        if y < 100:
            can.showPage()
            y = 750
    y -= 10
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y, "Observaciones:")
    y -= 13
    can.setFont("Helvetica", 10)
    can.drawString(60, y, cobro['observaciones'] or "Ninguna")
    can.save()
    packet.seek(0)
    return send_file(
        packet,
        download_name=f"cobro_extra_{str(cobro['id']).zfill(5)}.pdf",
        mimetype='application/pdf'
    )
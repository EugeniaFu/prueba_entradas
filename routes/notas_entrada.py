from flask import Blueprint, jsonify, request, current_app, send_file, redirect, url_for
from datetime import datetime, timedelta
from utils.db import get_db_connection

from flask import send_file
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

notas_entrada_bp = Blueprint('notas_entrada', __name__, url_prefix='/notas_entrada')

# --- PREVIEW: Obtener datos para el modal de entrada ---
@notas_entrada_bp.route('/preview/<int:renta_id>')
def preview_nota_entrada(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Folio consecutivo (igual que salida)
    cursor.execute("""
        SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio
        FROM (
            SELECT folio FROM notas_entrada
            UNION ALL
            SELECT folio FROM notas_salida
        ) AS todos
    """)
    row = cursor.fetchone()
    folio_entrada = str(row['siguiente_folio']).zfill(5) if row and row['siguiente_folio'] is not None else '00001'

    # Datos de la renta y cliente
    cursor.execute("""
        SELECT r.id, r.fecha_entrada, r.direccion_obra, r.traslado, r.costo_traslado,
            c.nombre, c.apellido1, c.apellido2, c.telefono
        FROM rentas r
        JOIN clientes c ON r.cliente_id = c.id
        WHERE r.id = %s
    """, (renta_id,))
    renta = cursor.fetchone()
    if not renta:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Renta no encontrada'}), 404
    
    # Obtener folio de salida desde la nota de salida
    cursor.execute("""
        SELECT folio, id AS nota_salida_id
        FROM notas_salida
        WHERE renta_id = %s
        ORDER BY id DESC LIMIT 1
    """, (renta_id,))
    ns_row = cursor.fetchone()
    folio_salida = str(ns_row['folio']).zfill(5) if ns_row and ns_row['folio'] is not None else '-----'
    nota_salida_id = ns_row['nota_salida_id'] if ns_row else None


    # Fecha y hora actual
    fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Fecha límite (un día después de fecha_entrada)
    fecha_limite = '--/--/---- --:--'
    estado = '---'
    dias_retraso = 0
    if renta['fecha_entrada']:
    # Si renta['fecha_entrada'] es date, conviértelo a datetime
        fecha_base = renta['fecha_entrada']
        if isinstance(fecha_base, datetime):
            fecha_base = fecha_base.date()
        fecha_limite_dt = datetime.combine(fecha_base + timedelta(days=1), datetime.strptime('10:00', '%H:%M').time())
        fecha_limite = f"{fecha_limite_dt.strftime('%d/%m/%Y')} hasta las 10:00 a.m."
        ahora = datetime.now()
        if ahora <= fecha_limite_dt:
            estado = 'A tiempo'
        else:
            estado = 'Retrasada'
            delta = ahora - fecha_limite_dt
            dias_retraso = delta.days + (1 if delta.seconds > 0 else 0)
    # Piezas que salieron (de la nota de salida)
    cursor.execute("""
        SELECT ns.id AS nota_salida_id
        FROM notas_salida ns
        WHERE ns.renta_id = %s
        ORDER BY ns.id DESC LIMIT 1
    """, (renta_id,))
    ns_row = cursor.fetchone()
    nota_salida_id = ns_row['nota_salida_id'] if ns_row else None

    piezas = []
    if nota_salida_id:
        cursor.execute("""
            SELECT nsd.id_pieza, p.nombre_pieza, nsd.cantidad AS cantidad_esperada
            FROM notas_salida_detalle nsd
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE nsd.nota_salida_id = %s
        """, (nota_salida_id,))
        piezas = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        'folio_entrada': folio_entrada,
        'folio_salida': folio_salida,
        'nota_salida_id': nota_salida_id,
        'cliente': f"{renta['nombre']} {renta['apellido1']} {renta['apellido2']}",
        'telefono': renta['telefono'],
        'direccion_obra': renta['direccion_obra'],
        'traslado_original': renta['traslado'],  # tipo de traslado pagado al inicio
        'fecha_hora': fecha_hora,
        'fecha_limite': fecha_limite,
        'estado': estado,
        'dias_retraso': dias_retraso,
        'piezas': piezas
    })




####################################################################
####################################################################
####################################################################
####################################################################


@notas_entrada_bp.route('/crear/<int:renta_id>', methods=['POST'])
def crear_nota_entrada(renta_id):
    data = request.get_json()
    folio = data.get('folio_entrada')
    nota_salida_id = data.get('nota_salida_id')
    requiere_traslado_extra = data.get('traslado_extra', 'ninguno')
    costo_traslado_extra = float(data.get('costo_traslado_extra', 0))
    observaciones = data.get('observaciones', '')
    piezas = data.get('piezas', [])
    accion_devolucion = data.get('accion_devolucion', 'no')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Validación: ya existe nota de entrada para esta renta
    cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s", (renta_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Ya existe una nota de entrada para esta renta.'}), 400

    try:
        cobrar_retraso = data.get('cobrar_retraso', False)
        estado_retraso = 'Retraso Pendiente' if cobrar_retraso else 'Sin Retraso'

        # Insertar nota de entrada (solo una vez)
        cursor.execute("""
            INSERT INTO notas_entrada (
                folio, renta_id, nota_salida_id, fecha_entrada_real,
                requiere_traslado_extra, costo_traslado_extra, observaciones, estado, created_at, estado_retraso, accion_devolucion
            ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, NOW(), %s, %s)
        """, (
            folio, renta_id, nota_salida_id, requiere_traslado_extra,
            costo_traslado_extra, observaciones, 'normal', estado_retraso, accion_devolucion
        ))
        nota_entrada_id = cursor.lastrowid

        # Obtener sucursal de la renta
        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        id_sucursal = row['id_sucursal'] if row else None

        # Insertar detalle y actualizar inventario
        for pieza in piezas:
            id_pieza = pieza['id_pieza']
            cantidad_esperada = pieza['cantidad_esperada']
            cantidad_recibida = pieza['cantidad_recibida']
            cantidad_buena = pieza['cantidad_buena']
            cantidad_danada = pieza['cantidad_danada']
            cantidad_sucia = pieza['cantidad_sucia']
            cantidad_perdida = pieza['cantidad_perdida']
            observaciones_pieza = pieza.get('observaciones_pieza', '')

            cursor.execute("""
                INSERT INTO notas_entrada_detalle (
                    nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                    cantidad_buena, cantidad_danada, cantidad_sucia, cantidad_perdida, observaciones_pieza
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                cantidad_buena, cantidad_danada, cantidad_sucia, cantidad_perdida, observaciones_pieza
            ))

            # Verificar existencia en inventario_sucursal
            cursor.execute("""
                SELECT id_inventario FROM inventario_sucursal
                WHERE id_sucursal = %s AND id_pieza = %s
            """, (id_sucursal, id_pieza))
            inventario_row = cursor.fetchone()
            if not inventario_row:
                continue

            # Buenas: +disponibles, -rentadas
            cursor.execute("""
                UPDATE inventario_sucursal
                SET 
                    disponibles = disponibles + %s,
                    rentadas = rentadas - %s
                WHERE id_sucursal = %s AND id_pieza = %s
            """, (
                cantidad_buena, cantidad_buena, id_sucursal, id_pieza
            ))

            # Dañadas: +daniadas, -rentadas
            if cantidad_danada > 0:
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET 
                        daniadas = daniadas + %s,
                        rentadas = rentadas - %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (
                    cantidad_danada, cantidad_danada, id_sucursal, id_pieza
                ))

            # Perdidas: solo si recibidas == esperadas
            if cantidad_recibida == cantidad_esperada and cantidad_perdida > 0:
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET 
                        perdidas = perdidas + %s,
                        rentadas = rentadas - %s,
                        total = total - %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (
                    cantidad_perdida, cantidad_perdida, cantidad_perdida, id_sucursal, id_pieza
                ))

        # Actualizar renta con id de nota de entrada y estado
        cursor.execute("""
            UPDATE rentas SET nota_entrada_id = %s, estado_renta = 'Finalizada'
            WHERE id = %s
        """, (nota_entrada_id, renta_id))

        # Activar estado de extra pendiente si hay cobros extra
        hay_cobro_extra = any(
            pieza['cantidad_danada'] > 0 or pieza['cantidad_sucia'] > 0 or pieza['cantidad_perdida'] > 0
            for pieza in piezas
        )
        if requiere_traslado_extra in ['medio', 'redondo'] and costo_traslado_extra > 0:
            hay_cobro_extra = True

        if hay_cobro_extra:
            cursor.execute("""
                UPDATE rentas SET estado_cobro_extra = 'Extra Pendiente'
                WHERE id = %s
            """, (renta_id,))
        else:
            cursor.execute("""
                UPDATE rentas SET estado_cobro_extra = NULL
                WHERE id = %s
            """, (renta_id,))

        conn.commit()
        return jsonify({'success': True, 'nota_entrada_id': nota_entrada_id})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()
        




####################################################################
####################################################################
####################################################################
####################################################################

@notas_entrada_bp.route('/pdf/<int:nota_entrada_id>')
def generar_pdf_nota_entrada(nota_entrada_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT ne.folio, ne.fecha_entrada_real, ne.requiere_traslado_extra, ne.costo_traslado_extra, ne.observaciones,
               r.direccion_obra,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.telefono
        FROM notas_entrada ne
        JOIN rentas r ON ne.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        WHERE ne.id = %s
    """, (nota_entrada_id,))
    nota = cursor.fetchone()

    cursor.execute("""
        SELECT ned.cantidad_esperada, ned.cantidad_recibida, ned.cantidad_buena, ned.cantidad_danada, ned.cantidad_sucia, ned.cantidad_perdida, p.nombre_pieza
        FROM notas_entrada_detalle ned
        JOIN piezas p ON ned.id_pieza = p.id_pieza
        WHERE ned.nota_entrada_id = %s
    """, (nota_entrada_id,))
    piezas = cursor.fetchall()

    cursor.close()
    conn.close()

    # --- Generar PDF sencillo ---
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont("Helvetica-Bold", 16)
    can.drawString(60, 750, f"Nota de Entrada #{str(nota['folio']).zfill(5)}")
    can.setFont("Helvetica", 10)
    can.drawString(60, 730, f"Fecha: {nota['fecha_entrada_real'].strftime('%d/%m/%Y %H:%M')}")
    can.drawString(60, 715, f"Cliente: {nota['cliente_nombre']}")
    can.drawString(60, 700, f"Teléfono: {nota['telefono']}")
    can.drawString(60, 685, f"Dirección de Obra: {nota['direccion_obra']}")
    can.drawString(60, 670, f"Traslado Extra: {nota['requiere_traslado_extra']} (${nota['costo_traslado_extra']:.2f})")

    y = 650
    can.setFont("Helvetica-Bold", 11)
    can.drawString(60, y, "Piezas Recibidas:")
    y -= 15
    can.setFont("Helvetica", 10)
    for pieza in piezas:
        can.drawString(60, y, f"{pieza['nombre_pieza']}: Esperadas {pieza['cantidad_esperada']}, Recibidas {pieza['cantidad_recibida']}, Buenas {pieza['cantidad_buena']}, Dañadas {pieza['cantidad_danada']}, Sucias {pieza['cantidad_sucia']}, Perdidas {pieza['cantidad_perdida']}")
        y -= 13
        if y < 100:
            can.showPage()
            y = 750

    y -= 10
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y, "Observaciones:")
    y -= 13
    can.setFont("Helvetica", 10)
    can.drawString(60, y, nota['observaciones'] or "Ninguna")

    can.save()
    packet.seek(0)

    return send_file(
        packet,
        download_name=f"nota_entrada_{str(nota['folio']).zfill(5)}.pdf",
        mimetype='application/pdf'
    )


@notas_entrada_bp.route('/pdf_renta/<int:renta_id>')
def generar_pdf_nota_entrada_por_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id FROM notas_entrada
        WHERE renta_id = %s
        ORDER BY id DESC
        LIMIT 1
    """, (renta_id,))
    nota = cursor.fetchone()
    cursor.close()
    conn.close()
    if not nota:
        return f"No hay nota de entrada para la renta {renta_id}", 404
    return redirect(url_for('notas_entrada.generar_pdf_nota_entrada', nota_entrada_id=nota['id']))
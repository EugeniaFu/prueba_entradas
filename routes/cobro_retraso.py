from flask import Blueprint, jsonify, request, send_file, current_app, url_for, session
from utils.db import get_db_connection
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from num2words import num2words 
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
from utils.datetime_utils import get_local_now
from utils.decorators import requiere_sesion, requiere_permiso

# Importar función para registrar movimientos automáticos de caja
from routes.caja import registrar_movimiento_automatico
import os


def obtener_folio_consecutivo_prefactura(sucursal_id):
    """
    Obtiene el próximo folio consecutivo para una sucursal específica.
    Cada sucursal tiene su propia secuencia (inicia en 1), considerando
    folios de prefacturas, cobros extra y cobros de retraso de esa sucursal.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT COALESCE(MAX(folio), 0) as max_folio FROM (
                SELECT folio FROM prefacturas WHERE id_sucursal = %s
                UNION ALL
                SELECT folio FROM notas_cobro_extra WHERE id_sucursal = %s
                UNION ALL
                SELECT folio FROM notas_cobro_retraso WHERE id_sucursal = %s
            ) AS todos_folios
        """, (sucursal_id, sucursal_id, sucursal_id))
        resultado = cursor.fetchone()
        max_folio = resultado[0] if resultado else 0

        # El próximo folio es el máximo + 1
        return max_folio + 1

    finally:
        cursor.close()
        conn.close()




cobro_retraso_bp = Blueprint('cobro_retraso', __name__, url_prefix='/cobros_retraso')

# --- PREVIEW: Obtener datos para el modal de cobro por retraso ---
@cobro_retraso_bp.route('/preview/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('cobrar_retraso')
def preview_cobro_retraso(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener datos de la renta actual (puede ser una renovación)
        cursor.execute("SELECT id_sucursal, traslado, fecha_entrada FROM rentas WHERE id = %s", (renta_id,))
        renta_actual = cursor.fetchone()
        if not renta_actual:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Renta no encontrada'}), 404

        # Obtener nota de entrada de esta renta (la renovación genera su propia nota de entrada)
        cursor.execute("""
            SELECT ne.id AS nota_entrada_id, ne.estado_retraso, ne.fecha_entrada_real
            FROM notas_entrada ne
            WHERE ne.renta_id = %s
            ORDER BY ne.id DESC LIMIT 1
        """, (renta_id,))
        nota = cursor.fetchone()
        if not nota:
            cursor.close()
            conn.close()
            return jsonify({'error': 'No hay nota de entrada para esta renta'}), 404

        # Usar la fecha de entrada y traslado de la renta que se está cobrando
        # (puede ser la renta original o una renovación con su propia nota de entrada)
        fecha_base = renta_actual['fecha_entrada']
        tipo_traslado = (renta_actual['traslado'] or 'ninguno').lower()

        # Calcular días de retraso desde la fecha de entrada de la renta actual
        dias_retraso = 0
        if fecha_base and nota['fecha_entrada_real']:
            if isinstance(fecha_base, datetime):
                fecha_base = fecha_base.date()
            fecha_limite_dt = datetime.combine(fecha_base + timedelta(days=1), datetime.strptime('10:00', '%H:%M').time())

            if nota['fecha_entrada_real'] > fecha_limite_dt:
                delta = nota['fecha_entrada_real'] - fecha_limite_dt
                dias_retraso = delta.days + (1 if delta.seconds > 0 else 0)

        # Si no hay retraso, no hay nada que cobrar
        if dias_retraso <= 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'No hay días de retraso para cobrar'}), 400

        # Obtener productos de la renta correcta para el cobro
        # Si la llamada viene de una renovación, usar productos de esa renovación
        # Si viene de renta original, usar productos de esa renta
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
            'detalles': detalles,
            'tipo_traslado': tipo_traslado
        })
        
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'error': f'Error al procesar la solicitud: {str(e)}'}), 500

# --- GUARDAR COBRO POR RETRASO ---
@cobro_retraso_bp.route('/guardar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('cobrar_retraso')
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
    numero_seguimiento = data.get('numero_seguimiento', '')

    # VALIDACIONES DE ENTRADA
    if not metodo_pago or metodo_pago.strip() == '':
        return jsonify({'success': False, 'error': 'Método de pago requerido'}), 400
    
    if not nota_entrada_id:
        return jsonify({'success': False, 'error': 'ID de nota de entrada requerido'}), 400
    
    if not detalles or len(detalles) == 0:
        return jsonify({'success': False, 'error': 'Detalles de productos requeridos'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # VALIDACIÓN ADICIONAL: Verificar tipo de traslado y obtener sucursal de la renta
        cursor.execute("""
            SELECT r.traslado, r.id_sucursal
            FROM notas_entrada ne
            JOIN rentas r ON ne.renta_id = r.id
            WHERE ne.id = %s
        """, (nota_entrada_id,))
        renta_info = cursor.fetchone()
        if not renta_info:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Nota de entrada no encontrada'}), 404

        tipo_traslado = (renta_info['traslado'] or 'ninguno').lower()
        sucursal_id = renta_info['id_sucursal'] or session.get('sucursal_id') or 1

        # Sin importar el tipo de traslado, se permite cobrar retraso si el usuario lo decide
        # (El checkbox del frontend controla si se cobra o no)

        # Función para redondear según reglas de efectivo
        def redondear_efectivo(monto):
            entero = int(monto)
            centavos = round((monto - entero) * 100)
            if centavos <= 49:
                return entero
            elif centavos >= 60:
                return entero + 1
            else:
                return entero + 0.5

        # Aplicar redondeo para pagos en efectivo
        if metodo_pago.upper() == 'EFECTIVO':
            total_original = float(total)
            total_redondeado = redondear_efectivo(total_original)
            total = total_redondeado
            
            # Recalcular cambio si es necesario
            if monto_recibido and float(monto_recibido) > total_redondeado:
                cambio = float(monto_recibido) - total_redondeado
        
        # Validaciones específicas por método de pago
        if metodo_pago.upper() == 'EFECTIVO':
            if not monto_recibido or float(monto_recibido) < float(total):
                return jsonify({
                    'success': False, 
                    'error': 'El monto recibido debe ser mayor o igual al total'
                }), 400
        else:
            # Para métodos no efectivo, validar número de seguimiento
            if not numero_seguimiento or numero_seguimiento.strip() == '':
                return jsonify({
                    'success': False, 
                    'error': 'Número de seguimiento requerido para pagos no efectivo'
                }), 400
            # Para no efectivo, el monto recibido es igual al total
            monto_recibido = total
            cambio = 0

        # Asegurar que numero_seguimiento no sea None
        if not numero_seguimiento:
            numero_seguimiento = ''

        # Insertar cobro retraso
        # Obtener el próximo folio (secuencia independiente por sucursal)
        folio = obtener_folio_consecutivo_prefactura(sucursal_id)

        cursor.execute("""
            INSERT INTO notas_cobro_retraso (
                nota_entrada_id, fecha, subtotal, iva, total, metodo_pago, monto_recibido, cambio,
                observaciones, facturable, traslado_extra, costo_traslado_extra, estado_pago, numero_seguimiento, folio, id_sucursal
            ) VALUES ( %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )
        """, (
            nota_entrada_id, subtotal, iva, total, metodo_pago.upper(), monto_recibido, cambio,
            observaciones, facturable, traslado_extra, costo_traslado_extra, 'Retraso Pagado', numero_seguimiento, folio, sucursal_id
        ))
        cobro_retraso_id = cursor.lastrowid

        # Registrar movimiento automático de caja si es pago en efectivo
        if metodo_pago.upper() == 'EFECTIVO':
            concepto = f"Cobro retraso #{folio} - Nota entrada #{nota_entrada_id}"
            usuario_id = session.get('user_id')

            resultado_caja = registrar_movimiento_automatico(
                tipo='ingreso',
                concepto=concepto,
                monto=float(total),
                metodo_pago=metodo_pago.upper(),
                usuario_id=usuario_id,
                sucursal_id=sucursal_id,
                referencia_tabla='notas_cobro_retraso',
                referencia_id=cobro_retraso_id,
                observaciones=f"Generado automáticamente desde cobro retraso"
            )
            
            if resultado_caja['success'] and resultado_caja.get('registered', False):
                print(f"Movimiento de caja registrado automáticamente: ID {resultado_caja['movimiento_id']}")

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
        
        # Verificar que se guardó correctamente
        cursor.execute("""
            SELECT metodo_pago, numero_seguimiento, total 
            FROM notas_cobro_retraso 
            WHERE id = %s
        """, (cobro_retraso_id,))
        verificacion = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'cobro_retraso_id': cobro_retraso_id})
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({'success': False, 'error': f'Error al guardar: {str(e)}'}), 500


#############################################################
#############################################################
#############################################################
#################### --- GENERAR PDF DE COBRO POR RETRASO ---

@cobro_retraso_bp.route('/pdf/<int:cobro_retraso_id>')
@requiere_sesion()
@requiere_permiso('ver_cobro_retraso')
def generar_pdf_cobro_retraso(cobro_retraso_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener datos completos del cobro de retraso
    cursor.execute("""
        SELECT ncr.*, ne.folio as folio_entrada, ne.renta_id,
               r.fecha_entrada, r.fecha_salida, r.direccion_obra, r.iva,
               r.traslado, r.costo_traslado, r.id_sucursal,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.codigo_cliente, c.telefono, c.correo, c.calle, c.numero_exterior, 
               c.numero_interior, c.entre_calles, c.colonia, c.codigo_postal,    
               c.municipio, c.estado, c.rfc
        FROM notas_cobro_retraso ncr
        JOIN notas_entrada ne ON ncr.nota_entrada_id = ne.id
        JOIN rentas r ON ne.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        WHERE ncr.id = %s
    """, (cobro_retraso_id,))
    cobro = cursor.fetchone()

    if not cobro:
        cursor.close()
        conn.close()
        return "Cobro de retraso no encontrado", 404

    # Obtener detalles del cobro de retraso (no de la renta original)
    cursor.execute("""
        SELECT nombre_producto, cantidad, dias_retraso, precio_unitario, subtotal
        FROM notas_cobro_retraso_detalle
        WHERE cobro_retraso_id = %s
    """, (cobro_retraso_id,))
    detalles = cursor.fetchall()

    # Obtener plantilla_renta de la sucursal
    plantilla_renta = None
    if cobro.get('id_sucursal'):
        cursor.execute("SELECT plantilla_renta FROM sucursales WHERE id = %s", (cobro['id_sucursal'],))
        sucursal_row = cursor.fetchone()
        if sucursal_row and sucursal_row.get('plantilla_renta'):
            plantilla_renta = sucursal_row['plantilla_renta']

    # Obtener datos del usuario actual
    usuario_id = session.get('user_id')
    usuario_nombre = "USUARIO NO IDENTIFICADO"
    if usuario_id:
        cursor.execute("""
            SELECT CONCAT(nombre, ' ', apellido1, ' ', apellido2) as nombre_completo
            FROM usuarios 
            WHERE id = %s
        """, (usuario_id,))
        usuario_row = cursor.fetchone()
        if usuario_row:
            usuario_nombre = usuario_row['nombre_completo'].upper()

    cursor.close()
    conn.close()
    
    # --- GENERAR PDF COMPLETO ---
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    # Registrar fuentes
    try:
        font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Carlito', font_path))
    except:
        pass
    
    # === TÍTULO PRINCIPAL ===
    can.setFont("Courier-Bold", 15)
    can.drawString(490, 732, "PREFACTURA")
    
    # === DATOS DEL CLIENTE ===
    y_cliente = 715
    can.setFont("Carlito", 10)
    
    # Código y nombre del cliente
    cliente_codigo_nombre = f"{cobro['codigo_cliente']} - {cobro['cliente_nombre'].upper()}"
    can.drawString(36, y_cliente, f"CLIENTE: {cliente_codigo_nombre}")
    y_cliente -= 13
    
    # Teléfono
    can.drawString(36, y_cliente, f"TELÉFONO: {cobro['telefono'] or 'NO REGISTRADO'}")
    y_cliente -= 13
    
    # Correo
    can.drawString(36, y_cliente, f"CORREO: {cobro['correo'] or 'NO REGISTRADO'}")
    y_cliente -= 13
    
    # Dirección completa
    direccion_completa = cobro['calle'] or ''
    if cobro['numero_exterior']:
        direccion_completa += f" #{cobro['numero_exterior']}"
    if cobro['numero_interior']:
        direccion_completa += f", INT. {cobro['numero_interior']}"
    if cobro['entre_calles']:
        direccion_completa += f" (ENTRE {cobro['entre_calles']})"
    if cobro['colonia']:
        direccion_completa += f", COL. {cobro['colonia']}"
    if cobro['codigo_postal']:
        direccion_completa += f" - C.P. {cobro['codigo_postal']}"

    direccion_texto = f"DIRECCIÓN: {direccion_completa.upper()}"
    
    direccion_lines = simpleSplit(direccion_texto, "Carlito", 10, 530)
    for line in direccion_lines:
        can.drawString(36, y_cliente, line)
        y_cliente -= 13
    
    # Estado y Municipio
    can.drawString(36, y_cliente, f"ESTADO: {(cobro['estado'] or 'NO REGISTRADO').upper()}")
    can.drawString(290, y_cliente, f"MUNICIPIO: {(cobro['municipio'] or 'NO REGISTRADO').upper()}")
    y_cliente -= 13
    
    # RFC y Facturable
    can.drawString(36, y_cliente, f"RFC: {(cobro['rfc'] or 'NO REGISTRADO').upper()}")
    facturable_texto = "SÍ" if cobro['facturable'] else "NO"
    can.drawString(290, y_cliente, f"FACTURABLE: {facturable_texto}")
    y_cliente -= 20
    
    # === FECHA Y HORA DE EMISIÓN ===
    can.setFont("Carlito", 12)
    fecha_emision = cobro['fecha']
    can.drawRightString(575, 715, f"{fecha_emision.strftime('%d/%m/%Y - %H:%M:%S')}")
    
    # Folio (usar el folio guardado en la BD)
    can.setFont("Courier-Bold", 20)
    folio_consecutivo = cobro['folio']  # Usar el folio guardado
    can.drawRightString(575, 690, f"#{str(folio_consecutivo).zfill(4)}")

    # === TABLA DE PRODUCTOS ===
    y_tabla = y_cliente - 5
    
    # Línea superior de encabezados
    can.line(28, y_tabla + 20, 585, y_tabla + 20)
    
    # Encabezados de tabla
    can.setFont("Helvetica-Bold", 9)
    can.drawString(36, y_tabla + 10, "DESCRIPCIÓN")
    can.drawRightString(350, y_tabla + 10, "CANT.")
    can.drawRightString(400, y_tabla + 10, "DÍAS")
    can.drawRightString(490, y_tabla + 10, "PRECIO UNIT.")
    can.drawRightString(570, y_tabla + 10, "SUBTOTAL")
    
    # Línea inferior de encabezados
    can.line(28, y_tabla + 5, 585, y_tabla + 5)
    y_tabla -= 15
    
    # Datos de productos
    can.setFont("Carlito", 10)
    subtotal_general = 0
    
    for item in detalles:
        can.drawString(36, y_tabla + 5, item['nombre_producto'][:35].upper())
        can.drawRightString(350, y_tabla + 5, str(item['cantidad']))
        can.drawRightString(400, y_tabla + 5, str(item['dias_retraso']))
        can.drawRightString(490, y_tabla + 5, f"${item['precio_unitario']:.2f}")
        can.drawRightString(570, y_tabla + 5, f"${item['subtotal']:.2f}")
        
        subtotal_general += float(item['subtotal'])
        y_tabla -= 13
        
        if y_tabla < 300:
            break
    
    y_tabla -= 5

    # === LÍNEA DIVISORA Y TOTALES ===
    can.line(28, y_tabla + 15, 585, y_tabla + 15)  # Línea separadora

    espacio_3mm = 10
    can.setFont("Carlito", 11)
    y_totales = y_tabla + 10 - espacio_3mm  # 3mm debajo de la línea

    # Obtener días de retraso del primer detalle (todos tienen los mismos días)
    dias_retraso = detalles[0]['dias_retraso'] if detalles else 0
    
    # PERÍODO DE RETRASO (AL LADO IZQUIERDO DEL SUBTOTAL)
    if cobro['fecha_entrada'] and dias_retraso > 0:
        # Calcular período de retraso real
        inicio_retraso = cobro['fecha_entrada'] + timedelta(days=1)  # Primer día de retraso
        fin_retraso = inicio_retraso + timedelta(days=dias_retraso - 1)  # Último día de retraso
        periodo_retraso = f"{inicio_retraso.strftime('%d/%m/%Y')} - {fin_retraso.strftime('%d/%m/%Y')}"
        
        can.setFont("Helvetica-Bold", 10)
        can.drawString(36, y_totales, f"PERÍODO DE RENTA: {periodo_retraso}")

    # Subtotal de productos (AL LADO DERECHO) - usar subtotal del cobro retraso
    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, "SUBTOTAL:")
    can.drawRightString(570, y_totales, f"${cobro['subtotal']:.2f}")
    y_totales -= 12

    # Traslado extra (si aplica)
    if cobro.get('traslado_extra') and cobro.get('traslado_extra') != 'ninguno':
        can.setFont("Carlito", 10)
        can.drawString(400, y_totales, f"TRASLADO EXTRA ({cobro['traslado_extra']}):")
        can.drawRightString(570, y_totales, f"${cobro.get('costo_traslado_extra', 0):.2f}")
        y_totales -= 12

    # IVA
    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, "IVA (16%):")
    can.drawRightString(570, y_totales, f"${cobro['iva']:.2f}")
    y_totales -= 12

    # Total del cobro retraso
    can.setFont("Helvetica-Bold", 9)
    can.drawString(400, y_totales, "TOTAL COBRO RETRASO:")
    can.drawRightString(570, y_totales, f"${cobro['total']:.2f}")
    
    # === TOTAL EN LETRAS (AL LADO IZQUIERDO DEL TOTAL COBRO RETRASO) ===
    total_cobro_retraso = float(cobro['total'])
    monto_entero = int(total_cobro_retraso)
    monto_centavos = int(round((total_cobro_retraso - monto_entero) * 100))
    monto_letras = num2words(monto_entero, lang='es').upper()
    if monto_centavos > 0:
        monto_letras = f"SON: {monto_letras} PESOS CON {monto_centavos:02d}/100 M.N."
    else:
        monto_letras = f"SON: {monto_letras} PESOS 00/100 M.N."

    # Usar simpleSplit para manejar texto multilínea si es muy largo
    can.setFont("Carlito", 9)
    monto_letras_lines = simpleSplit(monto_letras, "Carlito", 9, 350)  # Ancho máximo hasta donde empieza TOTAL COBRO RETRASO
    y_letras = y_totales
    for line in monto_letras_lines:
        can.drawString(36, y_letras, line)
        y_letras -= 10
    
    # Ajustar y_totales según cuántas líneas ocupó el texto en letras
    lines_used = len(monto_letras_lines)
    y_totales -= max(12, lines_used * 10)

    # === INFORMACIÓN SIMPLE DE PAGO ===
    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, "MÉTODO/PAGO:")
    can.drawRightString(570, y_totales, f"{cobro['metodo_pago']}")
    y_totales -= 12
    
    # Mostrar información de cambio si es efectivo y hay cambio
    if (cobro.get('monto_recibido') and 
        cobro.get('cambio') and 
        float(cobro['cambio']) > 0):
        
        can.setFont("Carlito", 10)
        can.drawString(400, y_totales, f"RECIBIDO:")
        can.drawRightString(570, y_totales, f"${float(cobro['monto_recibido']):.2f}")
        y_totales -= 12
        
        can.drawString(400, y_totales, f"CAMBIO:")
        can.drawRightString(570, y_totales, f"${float(cobro['cambio']):.2f}")
        y_totales -= 13

    # === AVISOS IMPORTANTES PARA EL CLIENTE ===
    y_avisos = y_totales - 5

    # Línea separadora para los avisos
    can.line(28, y_avisos + 16, 585, y_avisos + 16)
    y_avisos -= 5

    # REQUISITOS DE CLIENTE
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "REQUISITOS DEL CLIENTE:")
    y_avisos -= 12

    can.setFont("Carlito", 8)
    can.drawString(60, y_avisos, "LOS SIGUIENTES DOCUMENTOS PUEDEN SER EN IMAGEN O EN COPIA IMPRESA:")
    y_avisos -= 12

    can.drawString(70, y_avisos, "• IDENTIFICACIÓN OFICIAL.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• LICENCIA DE CONDUCIR.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• CONSTANCIA DE SITUACIÓN FISCAL.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• COMPROBANTE DE DOMICILIO.")
    y_avisos -= 15

    # REQUISITOS DE RENTA
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "REQUISITOS DE RENTA:")
    y_avisos -= 11

    can.setFont("Carlito", 8)
    can.drawString(70, y_avisos, "• SE REQUIERE EL PAGO COMPLETO POR ADELANTADO DE LA RENTA.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• UBICACIÓN EXACTA DE LA OBRA (POR GOOGLE MAPS)")
    y_avisos -= 15

    # ¡IMPORTANTE!
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "¡IMPORTANTE!")
    y_avisos -= 11

    can.setFont("Carlito", 8)
    can.drawString(70, y_avisos, "• EL PERIODO DE RENTA INCLUYE DOMINGOS, DÍAS INHÁBILES Y FESTIVOS.")
    y_avisos -= 10

    can.drawString(70, y_avisos, "• NO SE ARMA, NI SE DESARMA EL EQUIPO.")
    y_avisos -= 10
    
    # === FIRMA DEL USUARIO ===
    can.setFont("Carlito", 10)
    can.line(60, y_avisos, 250, y_avisos)
    y_avisos -= 15
    
    can.drawString(60, y_avisos, f"ATENDIDO POR: {usuario_nombre}")

    # === OBSERVACIONES ===
    if cobro['observaciones']:
        y_avisos -= 20
        can.setFont("Carlito", 13)
        obs_texto = f"OBSERVACIONES: {cobro['observaciones'].upper()}"
        obs_lines = simpleSplit(obs_texto, "Carlito", 13, 550)
        for line in obs_lines:
            if y_avisos < 50:
                can.showPage()
                y_avisos = 750
            can.drawString(36, y_avisos, line)
            y_avisos -= 18

    can.save()
    packet.seek(0)

    # --- COMBINAR CON LA PLANTILLA DE LA SUCURSAL (plantilla_renta) ---
    try:
        plantilla_path = None
        if plantilla_renta:
            plantilla_path = os.path.join(current_app.root_path, plantilla_renta)
            if not os.path.exists(plantilla_path):
                plantilla_path = None
        if not plantilla_path:
            plantilla_path = os.path.join(current_app.root_path, 'static/notas/base.pdf')

        overlay_pdf = PdfReader(packet)
        output = PdfWriter()

        if os.path.exists(plantilla_path):
            plantilla_pdf = PdfReader(plantilla_path)
            # Primera página: plantilla + overlay
            page = plantilla_pdf.pages[0]
            page.merge_page(overlay_pdf.pages[0])
            output.add_page(page)
            # Páginas siguientes: solo overlay (blanco)
            for i in range(1, len(overlay_pdf.pages)):
                output.add_page(overlay_pdf.pages[i])
        else:
            # Si no hay plantilla, agrega todas las páginas del overlay
            for page in overlay_pdf.pages:
                output.add_page(page)
    except Exception as e:
        print(f"Error con plantilla, usando solo overlay: {e}")
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        for page in overlay_pdf.pages:
            output.add_page(page)

    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    
    # Agregar timestamp para evitar caché del navegador
    timestamp = get_local_now().strftime("%Y%m%d_%H%M%S")
    filename = f"cobro_retraso_{str(cobro_retraso_id).zfill(5)}_{timestamp}.pdf"
    
    # Agregar headers para evitar caché del navegador
    response = send_file(
        output_stream, 
        download_name=filename, 
        mimetype='application/pdf'
    )
    
    # Headers para forzar descarga sin caché
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response
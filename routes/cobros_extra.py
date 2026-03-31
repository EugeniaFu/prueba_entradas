# routes/cobros_extra.py
from flask import Blueprint, jsonify, request, send_file, current_app, url_for, session
from utils.db import get_db_connection
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from num2words import num2words 
from reportlab.pdfbase import pdfmetrics
from utils.datetime_utils import get_local_now
from utils.decorators import requiere_sesion, requiere_permiso

# Importar función para registrar movimientos automáticos de caja
from routes.caja import registrar_movimiento_automatico
from reportlab.pdfbase.ttfonts import TTFont
import os

def obtener_folio_consecutivo_prefactura():
    """
    Obtiene el próximo folio consecutivo para cualquier tipo de cobro.
    Considera folios de prefacturas, cobros extra y cobros de retraso.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Obtener el folio más alto de todas las tablas de cobros
        cursor.execute("""
            SELECT COALESCE(MAX(folio), 0) as max_folio FROM (
                SELECT COALESCE(folio, 0) as folio FROM prefacturas
                UNION ALL
                SELECT COALESCE(folio, 0) as folio FROM notas_cobro_extra
                UNION ALL  
                SELECT COALESCE(folio, 0) as folio FROM notas_cobro_retraso
            ) AS todos_folios
        """)
        resultado = cursor.fetchone()
        max_folio = resultado[0] if resultado else 0
        
        # El próximo folio es el máximo + 1
        return max_folio + 1
        
    except Exception as e:
        # Si alguna tabla no tiene el campo folio, usar solo prefacturas
        print(f"Error al obtener folio unificado: {e}")
        cursor.execute("SELECT COALESCE(MAX(folio), 0) + 1 FROM notas_cobro_extra")
        resultado = cursor.fetchone()
        return resultado[0] if resultado else 1
        
    finally:
        cursor.close()
        conn.close()

bp_extras = Blueprint('cobros_extra', __name__, url_prefix='/cobros_extra')

@bp_extras.route('/detalle/<int:renta_id>', methods=['GET'])
@requiere_sesion()
@requiere_permiso('ver_cobro_extra')
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
@requiere_sesion()
@requiere_permiso('cobrar_extra')
def crear_cobro_extra(renta_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    data = request.get_json()
    
    # Obtener valores del frontend (ya calculados correctamente, incluyendo redondeo)
    subtotal = float(data.get('subtotal', 0))
    iva = float(data.get('iva', 0))
    total = float(data.get('total', 0))  # Este ya viene redondeado para efectivo
    metodo_pago = data.get('metodo_pago', '')
    monto_recibido = float(data.get('monto_recibido', total)) 
    cambio = float(data.get('cambio', 0))
    facturable = int(data.get('facturable', 0))
    numero_seguimiento = data.get('numero_seguimiento', '')
    observaciones = data.get('observaciones', '')
    estado_pago = "Extra Pagado" if monto_recibido >= total else "Extra Pendiente"
    tipo = data.get('tipo', 'extra')
    fecha = get_local_now()
    detalles = data.get('detalles', [])

    try:
        # Obtener nota_entrada_id
        cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s ORDER BY id DESC LIMIT 1", (renta_id,))
        nota_entrada = cursor.fetchone()
        if not nota_entrada:
            return jsonify({'success': False, 'error': 'No se encontró la nota de entrada.'}), 400
        nota_entrada_id = nota_entrada['id']

        # Obtener el próximo folio
        folio = obtener_folio_consecutivo_prefactura()
        
        # Crear cobro extra principal
        cursor.execute("""
            INSERT INTO notas_cobro_extra (
                nota_entrada_id, tipo, subtotal, iva, total, metodo_pago,
                monto_recibido, cambio, fecha, facturable, numero_seguimiento,
                observaciones, estado_pago, folio
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        """, (
            nota_entrada_id, tipo, subtotal, iva, total, metodo_pago,
            monto_recibido, cambio, fecha, facturable, numero_seguimiento,
            observaciones, estado_pago, folio
        ))
        cobro_id = cursor.lastrowid

        # Registrar movimiento automático de caja si es pago en efectivo
        if metodo_pago.upper() == 'EFECTIVO':
            concepto = f"Cobro extra #{folio} - Renta #{renta_id} ({tipo})"
            usuario_id = session.get('user_id')
            sucursal_id = session.get('sucursal_id', 1)
            
            # Usar el total que ya viene redondeado del frontend
            resultado_caja = registrar_movimiento_automatico(
                tipo='ingreso',
                concepto=concepto,
                monto=float(total),  # Total ya redondeado para efectivo
                metodo_pago=metodo_pago.upper(),
                usuario_id=usuario_id,
                sucursal_id=sucursal_id,
                referencia_tabla='notas_cobro_extra',
                referencia_id=cobro_id,
                observaciones=f"Generado automáticamente desde cobro extra"
            )
            
            if resultado_caja['success'] and resultado_caja.get('registered', False):
                print(f"Movimiento de caja registrado automáticamente: ID {resultado_caja['movimiento_id']}")

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
@requiere_sesion()
@requiere_permiso('ver_cobro_extra')
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
            AND (nd.cantidad_danada > 0 OR nd.cantidad_sucia > 0 OR nd.cantidad_perdida > 0)
        """, (nota_entrada_id,))
        piezas = cursor.fetchall()

        detalles = []
        for pieza in piezas:
            # Agregar cada tipo de afectación que tenga cantidad > 0
            if pieza['cantidad_danada'] and pieza['cantidad_danada'] > 0:
                detalles.append({
                    'id_pieza': pieza['id_pieza'],
                    'nombre_pieza': pieza['nombre_pieza'],
                    'tipo_afectacion': 'dañada',
                    'cantidad': pieza['cantidad_danada'],
                    'costo_unitario': 0,
                    'subtotal': 0,
                    'es_traslado_extra': False
                })
            
            if pieza['cantidad_sucia'] and pieza['cantidad_sucia'] > 0:
                detalles.append({
                    'id_pieza': pieza['id_pieza'],
                    'nombre_pieza': pieza['nombre_pieza'],
                    'tipo_afectacion': 'sucia',
                    'cantidad': pieza['cantidad_sucia'],
                    'costo_unitario': 0,
                    'subtotal': 0,
                    'es_traslado_extra': False
                })
            
            if pieza['cantidad_perdida'] and pieza['cantidad_perdida'] > 0:
                detalles.append({
                    'id_pieza': pieza['id_pieza'],
                    'nombre_pieza': pieza['nombre_pieza'],
                    'tipo_afectacion': 'perdida',
                    'cantidad': pieza['cantidad_perdida'],
                    'costo_unitario': 0,
                    'subtotal': 0,
                    'es_traslado_extra': False
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
                'costo_unitario': float(traslado_row['costo_traslado_extra']),
                'subtotal': float(traslado_row['costo_traslado_extra']),
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
@requiere_sesion()
@requiere_permiso('ver_cobro_extra')
def generar_pdf_cobro_extra(cobro_extra_id):
    # --- OBTENER DATOS COMPLETOS DEL CLIENTE ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT nc.*, ne.folio as folio_entrada, ne.renta_id,
               r.fecha_entrada, r.fecha_salida, r.direccion_obra, 
               r.traslado, r.costo_traslado,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.codigo_cliente,
               c.telefono,
               c.correo,
               c.calle,
               c.numero_exterior,
               c.numero_interior,
               c.entre_calles,
               c.colonia,
               c.codigo_postal,    
               c.municipio,
               c.estado,
               c.rfc
        FROM notas_cobro_extra nc
        JOIN notas_entrada ne ON nc.nota_entrada_id = ne.id
        JOIN rentas r ON ne.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        WHERE nc.id = %s
    """, (cobro_extra_id,))
    cobro = cursor.fetchone()
    
    if not cobro:
        cursor.close()
        conn.close()
        return "Cobro extra no encontrado", 404
    
    # Obtener detalles del cobro extra
    cursor.execute("""
        SELECT nced.*, p.nombre_pieza
        FROM notas_cobro_extra_detalle nced
        LEFT JOIN piezas p ON nced.id_pieza = p.id_pieza
        WHERE nced.cobro_extra_id = %s
        ORDER BY nced.tipo_afectacion, nced.id_pieza
    """, (cobro_extra_id,))
    detalles = cursor.fetchall()
    
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
    from reportlab.lib.utils import simpleSplit
    direccion_lines = simpleSplit(direccion_texto, "Carlito", 10, 530)
    for line in direccion_lines:
        can.drawString(36, y_cliente, line)
        y_cliente -= 13
    
    # Estado y Municipio
    can.drawString(36, y_cliente, f"ESTADO: {cobro['estado'] or 'NO REGISTRADO'.upper()}")
    can.drawString(290, y_cliente, f"MUNICIPIO: {cobro['municipio'] or 'NO REGISTRADO'.upper()}")
    y_cliente -= 13
    
    # RFC y Facturable
    can.drawString(36, y_cliente, f"RFC: {cobro['rfc'] or 'NO REGISTRADO'.upper()}")
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
    can.drawRightString(320, y_tabla + 10, "TIPO")
    can.drawRightString(380, y_tabla + 10, "CANT.")
    can.drawRightString(460, y_tabla + 10, "PRECIO UNIT.")
    can.drawRightString(570, y_tabla + 10, "SUBTOTAL")
    
    # Línea inferior de encabezados
    can.line(28, y_tabla + 5, 585, y_tabla + 5)
    y_tabla -= 15
    
    # Datos de productos
    can.setFont("Carlito", 10)
    subtotal_general = 0
    
    for item in detalles:
        # Descripción del daño
        if item['nombre_pieza']:
            descripcion = item['nombre_pieza'][:25].upper()
        else:
            descripcion = "TRASLADO EXTRA"
        
        can.drawString(36, y_tabla + 5, descripcion)
        can.drawRightString(320, y_tabla + 5, item['tipo_afectacion'][:8].upper())
        can.drawRightString(380, y_tabla + 5, str(item['cantidad']))
        can.drawRightString(460, y_tabla + 5, f"${item['costo_unitario']:.2f}")
        can.drawRightString(570, y_tabla + 5, f"${item['subtotal']:.2f}")
        
        subtotal_general += float(item['subtotal'])
        y_tabla -= 13
        
        if y_tabla < 300:
            break
    
    y_tabla -= 5

    # === LÍNEA DIVISORA Y TOTALES ===
    can.line(28, y_tabla + 15, 585, y_tabla + 15)
    
    espacio_3mm = 10
    can.setFont("Carlito", 11)
    y_totales = y_tabla + 10 - espacio_3mm

    # PERÍODO DE RENTA (AL LADO IZQUIERDO DEL SUBTOTAL)
    periodo_renta = f"{cobro['fecha_salida'].strftime('%d/%m/%Y')}"
    if cobro['fecha_entrada']:
        periodo_renta += f" - {cobro['fecha_entrada'].strftime('%d/%m/%Y')}"
    else:
        periodo_renta += " - Indefinido"
    can.setFont("Helvetica-Bold", 10)
    can.drawString(36, y_totales, f"PERIODO DE RENTA: {periodo_renta}")

    # Subtotal de productos (AL LADO DERECHO)
    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, "SUBTOTAL:")
    can.drawRightString(570, y_totales, f"${cobro['subtotal']:.2f}")
    y_totales -= 12

    # IVA
    can.drawString(400, y_totales, "IVA (16%):")
    can.drawRightString(570, y_totales, f"${cobro['iva']:.2f}")
    y_totales -= 12

    # Total de la renta
    can.setFont("Helvetica-Bold", 9)
    can.drawString(400, y_totales, "TOTAL RENTA:")
    can.drawRightString(570, y_totales, f"${cobro['total']:.2f}")
    
    # === TOTAL EN LETRAS (AL LADO IZQUIERDO DEL TOTAL RENTA) ===
    total_extra = float(cobro['total'])
    monto_entero = int(total_extra)
    monto_centavos = int(round((total_extra - monto_entero) * 100))
    monto_letras = num2words(monto_entero, lang='es').upper()
    if monto_centavos > 0:
        monto_letras = f"SON: {monto_letras} PESOS CON {monto_centavos:02d}/100 M.N."
    else:
        monto_letras = f"SON: {monto_letras} PESOS 00/100 M.N."

    can.setFont("Carlito", 9)
    monto_letras_lines = simpleSplit(monto_letras, "Carlito", 9, 350)
    y_letras = y_totales
    for line in monto_letras_lines:
        can.drawString(36, y_letras, line)
        y_letras -= 10
    
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
        y_totales -= 12

    # === AVISOS IMPORTANTES PARA EL CLIENTE ===
    y_avisos = y_totales - 15 

    # Línea separadora para los avisos
    can.line(28, y_avisos + 20, 585, y_avisos + 20)
    y_avisos -= 2

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
        can.setFont("Carlito", 9)
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

    # --- COMBINAR CON LA PLANTILLA ---
    try:
        plantilla_path = os.path.join(current_app.root_path, 'static/notas/base.pdf')
        if os.path.exists(plantilla_path):
            plantilla_pdf = PdfReader(plantilla_path)
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()

            page = plantilla_pdf.pages[0]
            page.merge_page(overlay_pdf.pages[0])
            output.add_page(page)
        else:
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            output.add_page(overlay_pdf.pages[0])
    except Exception as e:
        print(f"Error con plantilla, usando solo overlay: {e}")
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        output.add_page(overlay_pdf.pages[0])

    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    
    # Agregar timestamp para evitar caché del navegador
    timestamp = get_local_now().strftime("%Y%m%d_%H%M%S")
    filename = f"cobro_extra_{str(cobro_extra_id).zfill(5)}_{timestamp}.pdf"
    
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


@bp_extras.route('/pendientes/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def obtener_cobros_extra_pendientes(renta_id):
    """Obtiene todos los cobros extra pendientes para una renta"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar cobros extra no pagados o parcialmente pagados
        cursor.execute("""
            SELECT 
                nce.id,
                nce.folio,
                nce.subtotal,
                nce.iva,
                nce.total as monto_total,
                nce.fecha,
                nce.estado_pago as estado,
                ne.renta_id
            FROM notas_cobro_extra nce
            JOIN notas_entrada ne ON nce.nota_entrada_id = ne.id
            WHERE ne.renta_id = %s 
            AND nce.estado_pago IN ('pendiente', 'Extra Pendiente', 'parcial')
            ORDER BY nce.fecha DESC
        """, (renta_id,))
        
        extras = cursor.fetchall()
        
        # Obtener detalles de cada cobro extra para el concepto
        for extra in extras:
            cursor.execute("""
                SELECT 
                    nombre_pieza,
                    tipo_afectacion,
                    cantidad,
                    costo_unitario
                FROM notas_cobro_extra_detalle
                WHERE cobro_extra_id = %s
            """, (extra['id'],))
            detalles = cursor.fetchall()
            
            # Construir concepto y descripción
            conceptos = []
            descripciones = []
            for detalle in detalles:
                if detalle['nombre_pieza']:
                    conceptos.append(f"{detalle['nombre_pieza']} ({detalle['tipo_afectacion']})")
                else:
                    conceptos.append("Traslado Extra")
                descripciones.append(f"Cant: {detalle['cantidad']} - ${detalle['costo_unitario']}")
            
            extra['concepto'] = ', '.join(conceptos)[:50] + ('...' if len(', '.join(conceptos)) > 50 else '')
            extra['descripcion'] = ', '.join(descripciones)[:50] + ('...' if len(', '.join(descripciones)) > 50 else '')
        
        # Convertir fechas para JSON
        for extra in extras:
            if extra['fecha']:
                extra['fecha_emision'] = extra['fecha'].isoformat()
        
        return jsonify({
            'extras': extras,
            'total_pendiente': sum(float(e['monto_total']) for e in extras if e['estado'] == 'pendiente'),
            'hay_pendientes': len(extras) > 0
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al obtener cobros extra pendientes: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
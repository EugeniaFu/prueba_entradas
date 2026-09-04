from flask import Blueprint, jsonify, redirect, request, send_file, current_app, url_for, session
from datetime import datetime, timedelta
from utils.db import get_db_connection
# Importar función de folio centralizada desde utils
from utils.folios import obtener_siguiente_folio_nota_sucursal
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from utils.datetime_utils import get_local_now, format_datetime_local
from utils.decorators import requiere_sesion, requiere_permiso
import os

notas_salida_bp = Blueprint('notas_salida', __name__, url_prefix='/notas_salida')

@notas_salida_bp.route('/preview/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_salida')
def preview_nota_salida(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener sucursal de la renta primero
    cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
    sucursal_row = cursor.fetchone()
    if not sucursal_row:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Renta no encontrada'}), 404

    sucursal_id = sucursal_row['id_sucursal']

    # Verificar si ya existe una nota de salida y si la entrega fue finalizada
    cursor.execute("""
        SELECT id, es_entrega_parcial FROM notas_salida
        WHERE renta_id = %s ORDER BY id DESC LIMIT 1
    """, (renta_id,))
    ultima_nota_salida = cursor.fetchone()

    if ultima_nota_salida is not None and not ultima_nota_salida['es_entrega_parcial']:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Entrega finalizada', 'message': 'No se pueden generar más notas de salida para esta renta.'}), 409

    # Folio consecutivo por sucursal
    folio_siguiente = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)
    folio = str(folio_siguiente).zfill(5)

    # 2. Datos de la renta y cliente
    cursor.execute("""
        SELECT r.fecha_salida, r.fecha_entrada, r.direccion_obra, r.traslado,
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

    # 3. Periodo
    fecha_salida = renta['fecha_salida'].strftime('%d/%m/%Y') if renta['fecha_salida'] else '--/--/----'
    if renta['fecha_entrada']:
        fecha_entrada = renta['fecha_entrada'].strftime('%d/%m/%Y')
        periodo = f"{fecha_salida} a {fecha_entrada}"
    else:
        periodo = f"{fecha_salida} a indefinido"

    # 4. Desglose de piezas a entregar
    cursor.execute("""
        SELECT rd.id_producto, rd.cantidad
        FROM renta_detalle rd
        WHERE rd.renta_id = %s
    """, (renta_id,))
    productos = cursor.fetchall()

    piezas_dict = {}
    for prod in productos:
        id_producto = prod['id_producto']
        cantidad_producto = prod['cantidad']
        # Busca las piezas asociadas a este producto
        cursor.execute("""
            SELECT pp.id_pieza, pz.nombre_pieza, pp.cantidad
            FROM producto_piezas pp
            JOIN piezas pz ON pp.id_pieza = pz.id_pieza
            WHERE pp.id_producto = %s
        """, (id_producto,))
        piezas = cursor.fetchall()
        for pieza in piezas:
            id_pieza = pieza['id_pieza']
            nombre_pieza = pieza['nombre_pieza']
            cantidad_pieza = pieza['cantidad'] * cantidad_producto
            if id_pieza in piezas_dict:
                piezas_dict[id_pieza]['cantidad'] += cantidad_pieza
            else:
                piezas_dict[id_pieza] = {
                    'id_pieza': id_pieza,
                    'nombre_pieza': nombre_pieza,
                    'cantidad': cantidad_pieza
                }

    # 5. Consultar inventario disponible en la sucursal para cada pieza
    for id_pieza in piezas_dict:
        cursor.execute("""
            SELECT IFNULL(disponibles, 0) AS disponibles
            FROM inventario_sucursal
            WHERE id_sucursal = %s AND id_pieza = %s
        """, (sucursal_id, id_pieza))
        inventario_row = cursor.fetchone()
        disponibles = inventario_row['disponibles'] if inventario_row else 0
        piezas_dict[id_pieza]['disponibles'] = disponibles

    # Si hay entregas previas (parciales), mostrar solo la cantidad restante
    if ultima_nota_salida:
        cursor.execute("""
            SELECT nsd.id_pieza, SUM(nsd.cantidad) AS ya_entregado
            FROM notas_salida ns
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            WHERE ns.renta_id = %s
            GROUP BY nsd.id_pieza
        """, (renta_id,))
        for row in cursor.fetchall():
            id_pieza = row['id_pieza']
            if id_pieza in piezas_dict:
                piezas_dict[id_pieza]['cantidad'] -= row['ya_entregado']
        piezas_dict = {k: v for k, v in piezas_dict.items() if v['cantidad'] > 0}
        if not piezas_dict:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Sin piezas pendientes', 'message': 'Todo el equipo de esta renta ya fue entregado.'}), 409

    piezas_list = list(piezas_dict.values())

    cursor.close()
    conn.close()

    return jsonify({
        'folio': folio,
        'fecha': format_datetime_local(get_local_now(), '%d/%m/%Y %H:%M'),
        'cliente': f"{renta['nombre']} {renta['apellido1']} {renta['apellido2']}",
        'celular': renta['telefono'],
        'direccion_obra': renta['direccion_obra'],
        'periodo': periodo,
        'piezas': piezas_list,
        'traslado': renta['traslado']
    })


@notas_salida_bp.route('/cargadores')
@requiere_sesion()
@requiere_permiso('ver_notas_salida')
def listar_cargadores():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.id, CONCAT(u.nombre, ' ', u.apellido1, ' ', u.apellido2) AS nombre_completo,
               s.nombre AS sucursal_nombre
        FROM usuarios u
        LEFT JOIN sucursales s ON u.sucursal_id = s.id
        WHERE u.rol_id = 4 AND u.estado = 'activo'
        ORDER BY u.nombre, u.apellido1
    """)
    cargadores = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(cargadores)


@notas_salida_bp.route('/crear/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_nota_salida')
def crear_nota_salida(renta_id):
    data = request.get_json()
    numero_referencia = data.get('numero_referencia')
    observaciones = data.get('observaciones')
    piezas = data.get('piezas', [])
    chofer_entrega_id = data.get('chofer_id') or None
    es_entrega_parcial = bool(data.get('es_entrega_parcial', False))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener sucursal de la renta primero
        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        sucursal_row = cursor.fetchone()
        if not sucursal_row:
            return jsonify({'success': False, 'error': 'Renta no encontrada'})

        # Gate: bloquear si la entrega ya fue finalizada
        cursor.execute("""
            SELECT id, es_entrega_parcial FROM notas_salida
            WHERE renta_id = %s ORDER BY id DESC LIMIT 1
        """, (renta_id,))
        ultima = cursor.fetchone()
        if ultima and not ultima['es_entrega_parcial']:
            return jsonify({'success': False, 'error': 'La entrega de esta renta ya fue finalizada.'})

        sucursal_id = sucursal_row['id_sucursal']

        # ============================================
        # VALIDACIÓN DE INVENTARIO DISPONIBLE
        # ============================================
        piezas_sin_inventario = []
        
        for pieza in piezas:
            id_pieza = pieza.get('id_pieza')
            cantidad_solicitada = pieza.get('cantidad', 0)
            
            if id_pieza and cantidad_solicitada > 0:
                # Consultar inventario disponible en esta sucursal
                cursor.execute("""
                    SELECT p.nombre_pieza, IFNULL(i.disponibles, 0) AS disponibles
                    FROM piezas p
                    LEFT JOIN inventario_sucursal i 
                        ON p.id_pieza = i.id_pieza AND i.id_sucursal = %s
                    WHERE p.id_pieza = %s
                """, (sucursal_id, id_pieza))
                
                inventario_row = cursor.fetchone()
                
                if not inventario_row:
                    piezas_sin_inventario.append({
                        'nombre': 'Pieza desconocida',
                        'solicitada': cantidad_solicitada,
                        'disponible': 0
                    })
                else:
                    disponibles = inventario_row['disponibles']
                    nombre_pieza = inventario_row['nombre_pieza']
                    
                    if disponibles < cantidad_solicitada:
                        piezas_sin_inventario.append({
                            'nombre': nombre_pieza,
                            'solicitada': cantidad_solicitada,
                            'disponible': disponibles
                        })
        
        # Si hay piezas sin inventario suficiente, rechazar la operación
        if piezas_sin_inventario:
            mensajes_error = []
            for pieza_faltante in piezas_sin_inventario:
                mensajes_error.append(
                    f"{pieza_faltante['nombre']}: se solicitan {pieza_faltante['solicitada']} "
                    f"pero solo hay {pieza_faltante['disponible']} disponibles"
                )
            
            error_completo = "INVENTARIO INSUFICIENTE:\n" + "\n".join(mensajes_error)
            return jsonify({
                'success': False, 
                'error': error_completo,
                'piezas_faltantes': piezas_sin_inventario
            })

        # ============================================
        # CONTINUAR CON LA CREACIÓN DE LA NOTA
        # ============================================
        
        # Obtener siguiente folio por sucursal
        folio_siguiente = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)
        folio = str(folio_siguiente).zfill(5)

        # Insertar nota de salida
        cursor.execute("""
            INSERT INTO notas_salida (folio, renta_id, fecha, numero_referencia, observaciones, chofer_entrega_id, es_entrega_parcial)
            VALUES (%s, %s, NOW(), %s, %s, %s, %s)
                       """, (folio, renta_id, numero_referencia, observaciones, chofer_entrega_id, es_entrega_parcial))
        
        nota_salida_id = cursor.lastrowid

        # Obtener la sucursal de la renta SOLO UNA VEZ
        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        id_sucursal = row['id_sucursal'] if row else None

        # Insertar detalle de piezas y descontar inventario de la sucursal SOLO UNA VEZ POR PIEZA
        for pieza in piezas:
            id_pieza = pieza.get('id_pieza')
            cantidad = pieza.get('cantidad')
            if id_pieza and cantidad:
                print(f"UPDATE inventario_sucursal SET disponibles = disponibles - {cantidad}, rentadas = rentadas + {cantidad} WHERE id_sucursal = {id_sucursal} AND id_pieza = {id_pieza}")
                cursor.execute("""
                    INSERT INTO notas_salida_detalle (nota_salida_id, id_pieza, cantidad)
                    VALUES (%s, %s, %s)
                """, (nota_salida_id, id_pieza, cantidad))
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET disponibles = disponibles - %s,
                        rentadas = rentadas + %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (cantidad, cantidad, id_sucursal, id_pieza))
                print("Filas afectadas:", cursor.rowcount)

        # Estado según si es entrega parcial o definitiva
        nuevo_estado_renta = 'Entrega Parcial' if es_entrega_parcial else 'Activo'
        cursor.execute("""
            UPDATE rentas SET estado_renta = %s WHERE id = %s
        """, (nuevo_estado_renta, renta_id))

        conn.commit()
        return jsonify({'success': True, 'folio': folio, 'nota_salida_id': nota_salida_id})
    except Exception as e:
        conn.rollback()
        print(e)
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()











#############################################
#############################################
#############################################
########## PDF NOTAS DE SALIDA ############


@notas_salida_bp.route('/pdf/<int:nota_salida_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_salida')
def generar_pdf_nota_salida(nota_salida_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener datos completos de la nota de salida, incluyendo la plantilla de la sucursal
        cursor.execute("""
            SELECT ns.folio, ns.fecha, ns.numero_referencia, ns.observaciones,
                   r.fecha_salida, r.fecha_entrada, r.direccion_obra, r.id_sucursal,
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
                   c.codigo_cliente, c.telefono, c.calle, c.numero_exterior,
                   c.numero_interior, c.entre_calles, c.colonia, c.codigo_postal,
                   s.plantilla_renta,
                   CONCAT(uc.nombre, ' ', uc.apellido1, ' ', uc.apellido2) AS chofer_nombre
            FROM notas_salida ns
            JOIN rentas r ON ns.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            JOIN sucursales s ON r.id_sucursal = s.id
            LEFT JOIN usuarios uc ON ns.chofer_entrega_id = uc.id
            WHERE ns.id = %s
        """, (nota_salida_id,))
        nota = cursor.fetchone()

        if not nota:
            return "Nota de salida no encontrada", 404

        # Obtener piezas de la nota de salida
        cursor.execute("""
            SELECT nsd.cantidad, p.nombre_pieza
            FROM notas_salida_detalle nsd
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE nsd.nota_salida_id = %s
            ORDER BY p.nombre_pieza
        """, (nota_salida_id,))
        piezas = cursor.fetchall()

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
        
        # Registrar fuente
        try:
            font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Carlito', font_path))
        except:
            pass
        
        # CONFIGURACIÓN INICIAL 
        page_width, page_height = letter
        y_position = page_height - 100
        
        # Folio
        can.setFont("Courier-Bold", 20)
        can.drawRightString(575, 690, f"#{str(nota['folio']).zfill(5)}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 12)
        fecha_emision = nota['fecha'].strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(575, 715, f"{fecha_emision}")
        

        # === DATOS PRINCIPALES ===
        can.setFont("Courier-Bold", 23)
        can.drawString(496, 732, "SALIDA")
        
        can.setFont("Courier-Bold", 15)
        can.drawString(36, 715, "RENTA DE EQUIPO")

        # Datos del cliente
        can.setFont("Carlito", 10)
        cliente_completo = f"{nota['codigo_cliente']} - {nota['cliente_nombre'].upper()}"
        can.drawString(36, 695, f"CLIENTE: {cliente_completo}")
        
        # Teléfono y Referencia en la misma línea
        can.drawString(36, 680, f"TELÉFONO: {nota['telefono'] or 'NO REGISTRADO'}")
        referencia = nota['numero_referencia'] or 'SIN NÚMERO DE REFERENCIA'
        can.drawString(170, 680, f"REFERENCIA: {referencia.upper()}")
        
        # Dirección del cliente (con ajuste multilínea)
        direccion_completa = nota['calle'] or ''
        if nota['numero_exterior']:
            direccion_completa += f" #{nota['numero_exterior']}"
        if nota['numero_interior']:
            direccion_completa += f", INT. {nota['numero_interior']}"
        if nota['entre_calles']:
            direccion_completa += f" (ENTRE {nota['entre_calles']})"
        if nota['colonia']:
            direccion_completa += f", COL. {nota['colonia']}"
        if nota['codigo_postal']:
            direccion_completa += f" - C.P. {nota['codigo_postal']}"
        
        direccion_texto = f"DIRECCIÓN: {direccion_completa.upper()}"
        
        direccion_lines = simpleSplit(direccion_texto, "Carlito", 10, 530)
        y_direccion = 665
        for line in direccion_lines:
            can.drawString(36, y_direccion, line)
            y_direccion -= 12
        
        # DATOS DE PIEZAS 
        y_position -= 50
        # Texto descriptivo antes de la tabla
        can.setFont("Carlito", 10)
        can.drawString(36, y_position, "RECIBO DE ANDAMIOS COLOSIO")
        y_position -= 15
        can.drawString(36, y_position, "EL SIGUIENTE EQUIPO:")
        y_position -= 25
        
        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 9)
        can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        can.drawString(150, y_position + 5, "DESCRIPCIÓN")
        y_position -= 15
        
        can.setFont("Carlito", 10)
        for pieza in piezas:
            # Verificar si necesitamos nueva página
            if y_position < 200:
                can.showPage()
                can.setFont("Carlito", 10)
                y_position = page_height - 60
            can.drawString(70, y_position + 5, str(pieza['cantidad']))
            can.drawString(150, y_position + 5, pieza['nombre_pieza'].upper())
            y_position -= 13
        y_position -= 5
        
        # Período de renta (en negritas)
        can.setFont("Helvetica-Bold", 9)
        fecha_salida = nota['fecha_salida'].strftime('%d/%m/%Y') if nota['fecha_salida'] else 'NO DEFINIDA'
        if nota['fecha_entrada']:
            fecha_entrada = nota['fecha_entrada'].strftime('%d/%m/%Y')
            periodo = f"{fecha_salida} AL {fecha_entrada}"
        else:
            periodo = f"{fecha_salida} A FECHA INDEFINIDA"
        
        can.drawString(36, y_position, f"PERÍODO DE RENTA: {periodo}")
        y_position -= 15

        # Fecha límite de entrega (en negritas)
        can.setFont("Helvetica-Bold", 9)
        if nota['fecha_entrada']:
            dias_es = ['LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES', 'SÁBADO', 'DOMINGO']
            fecha_entrada_nota = nota['fecha_entrada']
            if fecha_entrada_nota.weekday() == 5:  # sábado: no se labora domingo, el límite no se corre
                fecha_limite = f"{dias_es[5]} {fecha_entrada_nota.strftime('%d/%m/%Y')} ANTES DE LAS 3:00 P.M."
            else:
                fecha_limite_obj = fecha_entrada_nota + timedelta(days=1)
                fecha_limite = f"{dias_es[fecha_limite_obj.weekday()]} {fecha_limite_obj.strftime('%d/%m/%Y')} ANTES DE LAS 9:00 A.M."
            can.drawString(36, y_position, f"FECHA LÍMITE DE ENTREGA: {fecha_limite}")
        else:
            can.drawString(36, y_position, "FECHA LÍMITE DE ENTREGA: INDEFINIDA")
        y_position -= 15

        # Dirección de obra
        can.setFont("Helvetica-Bold", 10)
        direccion_obra_texto = f"DIRECCIÓN DE OBRA: {nota['direccion_obra'].upper()}"
        max_width = 550
        
        obra_lines = simpleSplit(direccion_obra_texto, "Helvetica-Bold", 12, max_width)
        for line in obra_lines:
            can.drawString(36, y_position, line)
            y_position -= 10

        # Mantener espacio antes de términos
        y_position -= max(0, 30 - (len(obra_lines) * 18))
        
        # === TÉRMINOS Y CONDICIONES ===
        can.setFont("Carlito", 11)
        can.drawString(36, y_position, "TÉRMINOS Y CONDICIONES:")
        y_position -= 20

        # Texto de términos (más compacto)
        can.setFont("Carlito", 9)
        terminos_texto = """POR MEDIO DE LA PRESENTE, RECONOZCO HABER RECIBIDO EN PERFECTO ESTADO Y FUNCIONANDO EL EQUIPO DESCRITO ANTERIORMENTE. 
        ME COMPROMETO A: • HACER USO RESPONSABLE DEL EQUIPO • MANTENER EL EQUIPO EN LAS MISMAS CONDICIONES • DEVOLVER EL
        EQUIPO COMPLETO EN LA FECHA ACORDADA • RESPONDER POR DAÑOS, PÉRDIDA O ROBO • CUMPLIR CON TODAS LAS CONDICIONES DEL CONTRATO.

        IMPORTANTE: EN CASO DE NO DEVOLVER EL EQUIPO EN LA FECHA LÍMITE, SE REALIZARÁ EL COBRO POR CADA DÍA DE RETRASO."""

        terminos_lines = simpleSplit(terminos_texto, "Carlito", 9, 520)
        for line in terminos_lines:
            if y_position < 100:
                can.showPage()
                y_position = page_height - 60
            can.drawString(36, y_position, line)
            y_position -= 12
        
        y_position -= 50
        
        # === FIRMAS ===
        can.setFont("Carlito", 10)
        # Líneas para firmas
        can.line(60, y_position, 250, y_position)  # Línea empresa
        can.line(350, y_position, 540, y_position)  # Línea cliente
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, "ENTREGA: ANDAMIOS COLOSIO")
        can.drawString(350, y_position, "NOMBRE Y FIRMA DE QUIEN RECIBE")
        y_position -= 10
        
        nombre_entrega = nota['chofer_nombre'].upper() if nota.get('chofer_nombre') else usuario_nombre
        can.drawString(60, y_position, f"NOMBRE: {nombre_entrega}")
        y_position -= 15

        # Observaciones si existen
        if nota['observaciones']:
            y_position -= 20
            can.setFont("Carlito", 13)
            obs_texto = f"OBSERVACIONES: {nota['observaciones'].upper()}"
            obs_lines = simpleSplit(obs_texto, "Carlito", 13, 550)
            for line in obs_lines:
                if y_position < 50:
                    can.showPage()
                    y_position = page_height - 60
                can.drawString(36, y_position, line)
                y_position -= 18

        # Guardar el canvas
        can.save()
        packet.seek(0)
        

        # --- COMBINAR CON LA PLANTILLA DE LA SUCURSAL ---
        try:
            # Usar plantilla_renta de la sucursal si existe, si no usar base.pdf
            plantilla_path = None
            if nota.get('plantilla_renta'):
                plantilla_path = os.path.join(current_app.root_path, nota['plantilla_renta'])
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
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        filename = f"Salida_{str(nota['folio']).zfill(5)}.pdf"
        output.add_metadata({'/Title': filename})

        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)

        return send_file(
            output_stream,
            download_name=filename,
            mimetype='application/pdf'
        )
    
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return f"Error al generar PDF: {str(e)}", 500


@notas_salida_bp.route('/pdf_renta/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_salida')
def generar_pdf_nota_salida_por_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id FROM notas_salida 
        WHERE renta_id = %s 
        ORDER BY id DESC 
        LIMIT 1
    """, (renta_id,))
    
    nota = cursor.fetchone()
    cursor.close()
    conn.close()

    if not nota:
        return f"No hay nota de salida para la renta {renta_id}", 404

    return redirect(url_for('notas_salida.generar_pdf_nota_salida', nota_salida_id=nota['id']))




@notas_salida_bp.route('/historial/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_salida')
def historial_notas_salida(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, folio, fecha
            FROM notas_salida
            WHERE renta_id = %s
            ORDER BY fecha DESC
        """, (renta_id,))
        notas = cursor.fetchall()
        
        # Convert datetime to string for JSON
        for nota in notas:
            if nota['fecha']:
                nota['fecha_salida_real'] = nota['fecha'].isoformat()
                # Mantener campo original para compatibilidad
                nota['fecha'] = nota['fecha'].isoformat()
        
        return jsonify(notas)
        
    except Exception as e:
        return jsonify({'error': f'Error al obtener historial: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
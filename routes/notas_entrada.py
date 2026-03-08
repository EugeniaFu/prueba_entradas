from flask import Blueprint, jsonify, request, current_app, send_file, redirect, url_for, session
from datetime import datetime, timedelta
from utils.db import get_db_connection
# Importar función de folio centralizada desde inventario
from routes.inventario import obtener_siguiente_folio_nota_sucursal
# Importar funciones de datetime utils
from utils.datetime_utils import get_local_now, format_datetime_local
from utils.decorators import requiere_sesion, requiere_permiso

from flask import send_file
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from PyPDF2 import PdfReader, PdfWriter

from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont



notas_entrada_bp = Blueprint('notas_entrada', __name__, url_prefix='/notas_entrada')


@notas_entrada_bp.route('/preview/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_entrada')
def preview_nota_entrada(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verificar si es una renta asociada (renovación parcial)
    cursor.execute("SELECT id_sucursal, renta_asociada_id, estado_renta FROM rentas WHERE id = %s", (renta_id,))
    sucursal_row = cursor.fetchone()
    if not sucursal_row:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Renta no encontrada'}), 404
    
    # Bloquear nota de entrada para rentas asociadas
    if sucursal_row['renta_asociada_id'] is not None:
        cursor.close()
        conn.close()
        return jsonify({
            'error': 'No se puede crear nota de entrada para rentas asociadas',
            'message': 'Esta es una renovación parcial. No requiere nota de entrada ya que el equipo nunca regresó físicamente.'
        }), 403

    sucursal_id = sucursal_row['id_sucursal']

    # Folio consecutivo por sucursal (en lugar del global)
    folio_siguiente = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)
    folio_entrada = str(folio_siguiente).zfill(5)

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

    # Obtener folio de salida y nota_salida_id (incluir rentas con estado "Renta parcial")
    cursor.execute("""
        SELECT folio, id AS nota_salida_id
        FROM notas_salida
        WHERE renta_id = %s
        ORDER BY id DESC LIMIT 1
    """, (renta_id,))
    ns_row = cursor.fetchone()
    folio_salida = str(ns_row['folio']).zfill(5) if ns_row and ns_row['folio'] is not None else '-----'
    nota_salida_id = ns_row['nota_salida_id'] if ns_row else None

    # Si no hay nota de salida, puede ser porque es una renta con renovaciones
    if not nota_salida_id:
        cursor.close()
        conn.close()
        return jsonify({
            'error': 'No se encontró nota de salida para esta renta',
            'message': 'Esta renta no tiene nota de salida asociada. Verifica que se haya generado correctamente.'
        }), 404

    # Fecha y hora actual
    fecha_hora = format_datetime_local(get_local_now(), '%d/%m/%Y %H:%M')

    # Buscar si existe una renovación activa (total o parcial) para esta renta
    cursor.execute("""
        SELECT r.id, r.fecha_entrada
        FROM rentas r
        WHERE r.renta_asociada_id = %s AND r.estado_renta IN ('activa renovación', 'activo')
        ORDER BY r.fecha_entrada DESC LIMIT 1
    """, (renta_id,))
    renovacion = cursor.fetchone()

    fecha_limite = '--/--/---- --:--'
    estado = '---'
    dias_retraso = 0
    fecha_base = None
    if renovacion and renovacion['fecha_entrada']:
        fecha_base = renovacion['fecha_entrada']
    elif renta['fecha_entrada']:
        fecha_base = renta['fecha_entrada']

    if fecha_base:
        if isinstance(fecha_base, datetime):
            fecha_base = fecha_base.date()
        fecha_limite_dt = datetime.combine(fecha_base + timedelta(days=1), datetime.strptime('10:00', '%H:%M').time())
        fecha_limite = f"{fecha_limite_dt.strftime('%d/%m/%Y')} hasta las 10:00 a.m."
        
        # Convertir ambos datetime a naive para comparación
        ahora = get_local_now()
        if hasattr(ahora, 'replace'):
            ahora_naive = ahora.replace(tzinfo=None)
        else:
            ahora_naive = ahora
            
        if ahora_naive <= fecha_limite_dt:
            estado = 'A tiempo'
        else:
            estado = 'Retrasada'
            delta = ahora_naive - fecha_limite_dt
            dias_retraso = delta.days + (1 if delta.seconds > 0 else 0)

    # Piezas que salieron (de la nota de salida)
    piezas_salida = []
    if nota_salida_id:
        cursor.execute("""
            SELECT nsd.id_pieza, p.nombre_pieza, nsd.cantidad AS cantidad_esperada
            FROM notas_salida_detalle nsd
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE nsd.nota_salida_id = %s
        """, (nota_salida_id,))
        piezas_salida = cursor.fetchall()

    # Verifica si ya existe alguna nota de entrada
    cursor.execute("SELECT COUNT(*) AS total FROM notas_entrada WHERE renta_id = %s", (renta_id,))
    existe_entrada = cursor.fetchone()['total'] > 0

    # Consulta de piezas pendientes mejorada (funciona con cualquier estado de renta)
    cursor.execute("""
        SELECT
            nsd.id_pieza,
            p.nombre_pieza,
            nsd.cantidad AS cantidad_salida,
            IFNULL(SUM(ned.cantidad_recibida), 0) AS cantidad_recibida_total,
            (nsd.cantidad - IFNULL(SUM(ned.cantidad_recibida), 0)) AS cantidad_pendiente
        FROM notas_salida_detalle nsd
        JOIN piezas p ON nsd.id_pieza = p.id_pieza
        LEFT JOIN notas_entrada ne ON ne.renta_id = %s
        LEFT JOIN notas_entrada_detalle ned ON ned.nota_entrada_id = ne.id AND ned.id_pieza = nsd.id_pieza
        WHERE nsd.nota_salida_id = %s
        GROUP BY nsd.id_pieza, p.nombre_pieza, nsd.cantidad
        HAVING cantidad_pendiente > 0
        ORDER BY p.nombre_pieza
    """, (renta_id, nota_salida_id))
    piezas_pendientes = cursor.fetchall()

    # Si hay piezas pendientes, muestra solo esas
    if piezas_pendientes:
        piezas = [
            {
                'id_pieza': p['id_pieza'],
                'nombre_pieza': p['nombre_pieza'],
                'cantidad_esperada': p['cantidad_pendiente']
            }
            for p in piezas_pendientes
        ]
    elif not existe_entrada:
        piezas = piezas_salida
    else:
        piezas = []

    cursor.close()
    conn.close()

    return jsonify({
        'folio_entrada': folio_entrada,
        'folio_salida': folio_salida,
        'nota_salida_id': nota_salida_id,
        'cliente': f"{renta['nombre']} {renta['apellido1']} {renta['apellido2']}",
        'telefono': renta['telefono'],
        'direccion_obra': renta['direccion_obra'],
        'traslado_original': renta['traslado'],
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
@requiere_sesion()
@requiere_permiso('crear_nota_entrada')
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

    try:
        # Verificar si es una renta asociada antes de crear la nota
        cursor.execute("SELECT renta_asociada_id FROM rentas WHERE id = %s", (renta_id,))
        renta_check = cursor.fetchone()
        if renta_check and renta_check['renta_asociada_id'] is not None:
            return jsonify({
                'success': False, 
                'error': 'No se puede crear nota de entrada para rentas asociadas. Esta es una renovación parcial que no requiere devolución física del equipo.'
            }), 403

        # --- Lógica para distinguir renovación total vs parcial ---
        cursor.execute("""
            SELECT COUNT(*) AS total_renovaciones
            FROM rentas
            WHERE renta_asociada_id = %s AND estado_renta IN ('activa renovación', 'activo')
        """, (renta_id,))
        total_renovaciones = cursor.fetchone()['total_renovaciones']

        # Obtener piezas de la nota de salida (todas las piezas que salieron)
        cursor.execute("""
            SELECT nsd.id_pieza, nsd.cantidad AS cantidad_salida
            FROM notas_salida ns
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            WHERE ns.renta_id = %s
        """, (renta_id,))
        piezas_salida = cursor.fetchall()
        total_piezas_salida = sum([p['cantidad_salida'] for p in piezas_salida])
        total_piezas_recibidas = sum([int(p.get('cantidad_recibida', 0)) for p in piezas])

        # Si hay una renovación activa y todas las piezas están siendo renovadas (total), no cobrar retraso
        if total_renovaciones > 0 and total_piezas_recibidas == total_piezas_salida:
            cobrar_retraso = False
        else:
            cobrar_retraso = data.get('cobrar_retraso', False)
        estado_retraso = 'Retraso Pendiente' if cobrar_retraso else 'Sin Retraso'

        # Buscar si ya existe una nota de entrada en recolección para esta renta
        cursor.execute("""
            SELECT ne.id FROM notas_entrada ne
            WHERE ne.renta_id = %s
            AND (
                SELECT COUNT(*) FROM notas_entrada_detalle ned
                WHERE ned.nota_entrada_id = ne.id
                AND (ned.cantidad_recibida IS NULL OR ned.cantidad_recibida = 0)
            ) = (SELECT COUNT(*) FROM notas_entrada_detalle WHERE nota_entrada_id = ne.id)
            LIMIT 1
        """, (renta_id,))
        nota_existente = cursor.fetchone()

        if nota_existente:
            nota_entrada_id = nota_existente['id']
            # Actualizar cabecera
            cursor.execute("""
                UPDATE notas_entrada
                SET requiere_traslado_extra=%s, costo_traslado_extra=%s, observaciones=%s, estado_retraso=%s, accion_devolucion=%s, fecha_entrada_real=NOW()
                WHERE id=%s
            """, (requiere_traslado_extra, costo_traslado_extra, observaciones, estado_retraso, accion_devolucion, nota_entrada_id))
            # Eliminar detalles anteriores
            cursor.execute("DELETE FROM notas_entrada_detalle WHERE nota_entrada_id=%s", (nota_entrada_id,))
        else:
            # Insertar nota de entrada 
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

            def safe_int(val):
                return int(val) if str(val).isdigit() else 0

            cantidad_recibida = safe_int(pieza.get('cantidad_recibida', 0))
            cantidad_buena = safe_int(pieza.get('cantidad_buena', 0))
            cantidad_danada = safe_int(pieza.get('cantidad_danada', 0))
            cantidad_sucia = safe_int(pieza.get('cantidad_sucia', 0))
            cantidad_perdida = safe_int(pieza.get('cantidad_perdida', 0))
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

            # Actualizar inventario solo si hay cantidades recibidas
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

        # --- NUEVO FLUJO DE ESTADO ---
        # Detectar si la nota es de recolección (todas las recibidas en 0)
        es_recoleccion = all(
            (pieza.get('cantidad_recibida', 0) in [0, '', None]) for pieza in piezas
        )

        if es_recoleccion:
            cursor.execute("""
                UPDATE rentas SET estado_renta = 'en recolección'
                WHERE id = %s
            """, (renta_id,))
        else:
            # Verificar si quedan piezas pendientes después de esta nota
            # Usar la misma lógica que el preview para consistencia
            cursor.execute("""
                SELECT
                    nsd.id_pieza,
                    nsd.cantidad AS cantidad_salida,
                    IFNULL(SUM(ned.cantidad_recibida), 0) AS cantidad_recibida_total,
                    (nsd.cantidad - IFNULL(SUM(ned.cantidad_recibida), 0)) AS cantidad_pendiente
                FROM notas_salida_detalle nsd
                LEFT JOIN notas_entrada ne ON ne.renta_id = %s
                LEFT JOIN notas_entrada_detalle ned ON ned.nota_entrada_id = ne.id AND ned.id_pieza = nsd.id_pieza
                WHERE nsd.nota_salida_id = %s
                GROUP BY nsd.id_pieza, nsd.cantidad
                HAVING cantidad_pendiente > 0
            """, (renta_id, nota_salida_id))
            piezas_pendientes = cursor.fetchall()

            if len(piezas_pendientes) == 0:
                cursor.execute("""
                    UPDATE rentas SET estado_renta = 'finalizada'
                    WHERE id = %s
                """, (renta_id,))
                
                # Finalizar también las rentas asociadas (renovaciones)
                cursor.execute("""
                    UPDATE rentas SET estado_renta = 'renovación finalizada'
                    WHERE renta_asociada_id = %s AND estado_renta = 'activa renovación'
                """, (renta_id,))
            else:
                cursor.execute("""
                    UPDATE rentas SET estado_renta = 'activo'
                    WHERE id = %s
                """, (renta_id,))

        # Activar estado de extra pendiente si hay cobros extra
        def safe_int(val):
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        hay_cobro_extra = any(
            safe_int(pieza.get('cantidad_danada', 0)) > 0 or
            safe_int(pieza.get('cantidad_sucia', 0)) > 0 or
            safe_int(pieza.get('cantidad_perdida', 0)) > 0
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


@notas_entrada_bp.route('/historial/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_entrada')
def historial_notas_entrada(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, folio, fecha_entrada_real
        FROM notas_entrada
        WHERE renta_id = %s
        ORDER BY fecha_entrada_real DESC
    """, (renta_id,))
    notas = cursor.fetchall()
    cursor.close()
    conn.close()
    # Convert datetime to string for JSON
    for nota in notas:
        if isinstance(nota['fecha_entrada_real'], datetime):
            nota['fecha_entrada_real'] = nota['fecha_entrada_real'].strftime('%Y-%m-%d %H:%M')
    return jsonify(notas)



####################################################################
####################################################################
####################################################################
####################################################################



@notas_entrada_bp.route('/pdf/<int:nota_entrada_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_entrada')
def generar_pdf_nota_entrada(nota_entrada_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener datos completos de la nota de entrada
    cursor.execute("""
        SELECT ne.folio, ne.fecha_entrada_real, ne.requiere_traslado_extra, ne.costo_traslado_extra, ne.observaciones,
               r.fecha_salida, r.fecha_entrada, r.direccion_obra,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.codigo_cliente, c.telefono, c.calle, c.numero_exterior, 
               c.numero_interior, c.entre_calles, c.colonia, c.codigo_postal
        FROM notas_entrada ne
        JOIN rentas r ON ne.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        WHERE ne.id = %s
    """, (nota_entrada_id,))
    nota = cursor.fetchone()

    if not nota:
        cursor.close()
        conn.close()
        return "Nota de entrada no encontrada", 404

    # Obtener piezas de la nota de entrada
    cursor.execute("""
        SELECT ned.cantidad_esperada, ned.cantidad_recibida, ned.cantidad_buena, ned.cantidad_danada, 
               ned.cantidad_sucia, ned.cantidad_perdida, ned.observaciones_pieza, p.nombre_pieza
        FROM notas_entrada_detalle ned
        JOIN piezas p ON ned.id_pieza = p.id_pieza
        WHERE ned.nota_entrada_id = %s
        ORDER BY p.nombre_pieza
    """, (nota_entrada_id,))
    piezas = cursor.fetchall()

    # Verificar si hay piezas con problemas (dañadas, sucias o perdidas)
    hay_piezas_problematicas = any(
        (pieza['cantidad_danada'] and pieza['cantidad_danada'] > 0) or
        (pieza['cantidad_sucia'] and pieza['cantidad_sucia'] > 0) or
        (pieza['cantidad_perdida'] and pieza['cantidad_perdida'] > 0)
        for pieza in piezas
    )

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
    
    # Fecha y hora de entrada
    can.setFont("Carlito", 12)
    fecha_entrada = nota['fecha_entrada_real'].strftime('%d/%m/%Y - %H:%M:%S')
    can.drawRightString(575, 715, f"{fecha_entrada}")
    

    # === DATOS PRINCIPALES ===
    can.setFont("Courier-Bold", 23)
    can.drawString(480, 732, "ENTRADA")
    
    can.setFont("Courier-Bold", 15)
    can.drawString(36, 715, "RENTA DE EQUIPO")

    # Datos del cliente
    can.setFont("Carlito", 10)
    cliente_completo = f"{nota['codigo_cliente']} - {nota['cliente_nombre'].upper()}"
    can.drawString(36, 695, f"CLIENTE: {cliente_completo}")
    
    # Teléfono
    can.drawString(36, 680, f"TELÉFONO: {nota['telefono'] or 'NO REGISTRADO'}")
    
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
    from reportlab.lib.utils import simpleSplit
    direccion_lines = simpleSplit(direccion_texto, "Carlito", 10, 530)
    y_direccion = 665
    for line in direccion_lines:
        can.drawString(36, y_direccion, line)
        y_direccion -= 12
    
    # DATOS DE PIEZAS 
    y_position -= 50
    # Texto descriptivo antes de la tabla
    can.setFont("Carlito", 10)
    can.drawString(36, y_position, "RECIBÍ DE: ______________________________")
    y_position -= 15
    can.drawString(36, y_position, "EL SIGUIENTE EQUIPO:")
    y_position -= 25
    
    # Encabezado de tabla - condicional según si hay piezas problemáticas
    can.setFont("Helvetica-Bold", 9)
    can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
    can.drawString(150, y_position + 5, "DESCRIPCIÓN")
    can.drawString(350, y_position + 5, "RECIBIDAS")
    
    if hay_piezas_problematicas:
        can.drawString(420, y_position + 5, "BUENAS")
        can.drawString(470, y_position + 5, "DAÑADAS")
        can.drawString(520, y_position + 5, "PERDIDAS")
    
    y_position -= 15
    
    can.setFont("Carlito", 10)
    for pieza in piezas:
        # Verificar si necesitamos nueva página
        if y_position < 200:
            can.showPage()
            can.setFont("Carlito", 10)
            y_position = page_height - 60
        
        def mostrar_vacio_si_cero(val):
            return "" if val == 0 else str(val)
            
        can.drawString(70, y_position + 5, str(pieza['cantidad_esperada']))
        can.drawString(150, y_position + 5, pieza['nombre_pieza'].upper())
        can.drawString(365, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_recibida']))
        
        # Solo mostrar columnas de estado si hay piezas problemáticas
        if hay_piezas_problematicas:
            can.drawString(435, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_buena']))
            can.drawString(485, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_danada']))
            can.drawString(535, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_perdida']))
        
        y_position -= 13

    y_position -= 10

    # Dirección de obra
    can.setFont("Carlito", 10)
    direccion_obra_texto = f"DIRECCIÓN DE OBRA: {nota['direccion_obra'].upper()}"
    max_width = 550
    obra_lines = simpleSplit(direccion_obra_texto, "Carlito", 13, max_width)
    for line in obra_lines:
        can.drawString(36, y_position, line)
        y_position -= 10

    # Mantener espacio antes de términos
    y_position -= max(0, 30 - (len(obra_lines) * 18))
    
    

    # Texto 
    can.setFont("Carlito", 9)
    terminos_texto = """
    IMPORTANTE: CUALQUIER DAÑO, PÉRDIDA O EQUIPO SUCIO SERÁ FACTURADO SEGÚN TARIFAS VIGENTES."""

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
    
    # Etiquetas de firmas (invertidas para entrada)
    can.drawString(60, y_position, "RECIBE: ANDAMIOS COLOSIO")
    can.drawString(350, y_position, "ENTREGA: _______________________")
    y_position -= 10
    
    can.drawString(60, y_position, f"NOMBRE: {usuario_nombre}")
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

    # --- COMBINAR CON LA PLANTILLA ---
    try:
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

    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)

    return send_file(
        output_stream,
        download_name=f"nota_entrada_{str(nota['folio']).zfill(5)}.pdf",
        mimetype='application/pdf'
    )




@notas_entrada_bp.route('/pdf_renta/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_entrada')
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
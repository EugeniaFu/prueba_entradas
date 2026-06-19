# ======================= IMPORTS =======================
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from datetime import timedelta
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso
from utils.datetime_utils import get_local_now, format_datetime_local
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import os
from flask import current_app

# Importar función de folios desde utils
from utils.folios import obtener_siguiente_folio_nota_sucursal

# ======================= BLUEPRINT =======================
salidas_internas_bp = Blueprint('salidas_internas', __name__, url_prefix='/salidas-internas')

# ======================= LISTADO DE SALIDAS INTERNAS =======================
@salidas_internas_bp.route('/')
@requiere_sesion()
@requiere_permiso('ver_salidas_internas')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener sucursal del usuario desde la sesión
    sucursal_id_usuario = session.get('sucursal_id')
    
    # Determinar qué sucursal filtrar
    sucursal_filtro = request.args.get('sucursal_id')
    sucursal_actual = None
    
    # Construir WHERE clause para sucursal
    where_sucursal = ""
    params_sucursal = []
    
    if sucursal_id_usuario is None:  # Usuario multi-sucursal
        if sucursal_filtro and sucursal_filtro != 'todas':
            where_sucursal = "WHERE si.id_sucursal = %s"
            params_sucursal = [sucursal_filtro]
            cursor.execute("SELECT id, nombre FROM sucursales WHERE id = %s", (sucursal_filtro,))
            sucursal_data = cursor.fetchone()
            sucursal_actual = {'id': sucursal_filtro, 'nombre': sucursal_data['nombre']} if sucursal_data else None
        else:
            sucursal_actual = {'id': 'todas', 'nombre': 'Todas las Sucursales'}
        
        # Obtener todas las sucursales para el filtro
        cursor.execute("SELECT id, nombre FROM sucursales ORDER BY nombre")
        sucursales = cursor.fetchall()
    else:
        where_sucursal = "WHERE si.id_sucursal = %s"
        params_sucursal = [sucursal_id_usuario]
        cursor.execute("SELECT id, nombre FROM sucursales WHERE id = %s", (sucursal_id_usuario,))
        sucursal_data = cursor.fetchone()
        sucursal_actual = {'id': sucursal_id_usuario, 'nombre': sucursal_data['nombre']} if sucursal_data else None
        sucursales = []

    # Consulta principal de salidas internas
    cursor.execute(f"""
        SELECT 
            si.id, si.folio_sucursal, si.fecha_salida, si.responsable_entrega,
            si.observaciones, si.estado, si.fecha_finalizacion,
            s.nombre as sucursal_nombre, s.id as id_sucursal,
            COUNT(sid.id) as total_productos,
            SUM(sid.cantidad) as cantidad_total_equipos
        FROM salidas_internas si
        JOIN sucursales s ON si.id_sucursal = s.id
        LEFT JOIN salidas_internas_detalle sid ON si.id = sid.salida_interna_id
        {where_sucursal}
        GROUP BY si.id, si.folio_sucursal, si.fecha_salida, si.responsable_entrega,
                 si.observaciones, si.estado, si.fecha_finalizacion, s.nombre, s.id
        ORDER BY si.fecha_salida DESC, si.folio_sucursal DESC
    """, params_sucursal)
    
    salidas_internas = cursor.fetchall()

    # Obtener productos disponibles en la sucursal para el modal
    sucursal_para_productos = sucursal_filtro if sucursal_filtro and sucursal_filtro != 'todas' else (sucursal_id_usuario or 1)
    if sucursal_para_productos:
        cursor.execute("""
            SELECT p.id_pieza, p.nombre_pieza, 
                   COALESCE(inv.disponibles, 0) as disponibles
            FROM piezas p
            LEFT JOIN inventario_sucursal inv ON p.id_pieza = inv.id_pieza 
                                               AND inv.id_sucursal = %s
            WHERE COALESCE(inv.disponibles, 0) > 0
            ORDER BY p.nombre_pieza
        """, (sucursal_para_productos,))
        productos_disponibles = cursor.fetchall()
    else:
        productos_disponibles = []

    sucursal_nombre = None

    if 'sucursal_id' in session:
        cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (session['sucursal_id'],))
        resultado = cursor.fetchone()
        if resultado:
            sucursal_nombre = resultado['nombre']

    cursor.close()
    conn.close()

    return render_template(
        'salidas_internas/index.html',
        salidas_internas=salidas_internas,
        productos_disponibles=productos_disponibles,
        sucursal_actual=sucursal_actual,
        sucursales=sucursales if sucursal_id_usuario is None else [],
        es_admin=(sucursal_id_usuario is None),
        sucursal_id_usuario=sucursal_id_usuario,
        sucursal_nombre=sucursal_nombre
    )

# ======================= CREAR SALIDA INTERNA =======================
@salidas_internas_bp.route('/crear', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_salida_interna')
def crear_salida_interna():
    try:
        data = request.get_json()
        sucursal_id = data.get('sucursal_id')
        responsable_entrega = data.get('responsable_entrega', '').strip()
        observaciones = data.get('observaciones', '').strip()
        productos = data.get('productos', [])
        usuario_id = session.get('user_id')

        if not sucursal_id or not responsable_entrega or not productos:
            return jsonify({'success': False, 'error': 'Datos incompletos'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Obtener siguiente folio consecutivo del sistema
            folio_sucursal = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)
            # Validar que el folio sea un entero
            try:
                folio_int = int(folio_sucursal)
            except Exception:
                return jsonify({'success': False, 'error': 'Error: El folio generado no es válido.'})

            # Crear salida interna
            cursor.execute("""
                INSERT INTO salidas_internas 
                (id_sucursal, folio_sucursal, fecha_salida, responsable_entrega, observaciones, estado, usuario_creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (sucursal_id, folio_int, get_local_now(), responsable_entrega, observaciones, 'activa', usuario_id))

            salida_id = cursor.lastrowid

            # Procesar cada producto
            for producto in productos:
                id_pieza = producto.get('id_pieza')
                cantidad = producto.get('cantidad')

                if not id_pieza or not cantidad or cantidad <= 0:
                    continue

                # Verificar inventario disponible
                cursor.execute("""
                    SELECT disponibles, rentadas 
                    FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, sucursal_id))

                inventario = cursor.fetchone()
                if not inventario or inventario['disponibles'] < cantidad:
                    conn.rollback()
                    cursor.execute("SELECT nombre_pieza FROM piezas WHERE id_pieza = %s", (id_pieza,))
                    pieza_info = cursor.fetchone()
                    nombre_pieza = pieza_info['nombre_pieza'] if pieza_info else f'ID {id_pieza}'
                    return jsonify({
                        'success': False,
                        'error': f'No hay suficiente inventario disponible de {nombre_pieza}'
                    })

                # Insertar detalle de salida
                cursor.execute("""
                    INSERT INTO salidas_internas_detalle 
                    (salida_interna_id, id_pieza, cantidad)
                    VALUES (%s, %s, %s)
                """, (salida_id, id_pieza, cantidad))

                # Actualizar inventario: mover de disponibles a rentadas
                nuevos_disponibles = inventario['disponibles'] - cantidad
                nuevas_rentadas = inventario['rentadas'] + cantidad

                cursor.execute("""
                    UPDATE inventario_sucursal 
                    SET disponibles = %s, rentadas = %s 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (nuevos_disponibles, nuevas_rentadas, id_pieza, sucursal_id))

                # Registrar movimiento en historial con folio de nota de salida
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario, folio_nota_salida)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_pieza, sucursal_id, 'salida_interna', cantidad,
                    f'Salida interna - Responsable: {responsable_entrega}',
                    usuario_id, str(folio_int)
                ))

            conn.commit()

            return jsonify({
                'success': True,
                'message': f'Salida interna creada correctamente - Folio: SUC{sucursal_id}-{folio_int:04d}',
                'folio': f'SUC{sucursal_id}-{folio_int:04d}',
                'folio_nota_salida': str(folio_int),
                'salida_id': salida_id
            })
            
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': f'Error al crear salida interna: {str(e)}'})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})

# ======================= PIEZAS PENDIENTES DE UNA SALIDA INTERNA =======================
def _obtener_piezas_pendientes(cursor, salida_id):
    """
    Por cada pieza que salió, calcula cuánto sigue pendiente de regresar,
    restando lo que ya se recibió o se dio de baja en entradas anteriores
    (una salida interna puede resolverse en varias visitas).
    """
    cursor.execute("""
        SELECT
            sid.id_pieza, p.nombre_pieza, sid.cantidad AS cantidad_salida,
            IFNULL((
                SELECT SUM(sied.cantidad_recibida)
                FROM salidas_internas_entradas sie
                JOIN salidas_internas_entradas_detalle sied ON sied.entrada_id = sie.id
                WHERE sie.salida_interna_id = sid.salida_interna_id AND sied.id_pieza = sid.id_pieza
            ), 0) AS ya_recibido,
            IFNULL((
                SELECT SUM(sied.cantidad_perdida)
                FROM salidas_internas_entradas sie
                JOIN salidas_internas_entradas_detalle sied ON sied.entrada_id = sie.id
                WHERE sie.salida_interna_id = sid.salida_interna_id AND sied.id_pieza = sid.id_pieza
            ), 0) AS ya_perdido
        FROM salidas_internas_detalle sid
        JOIN piezas p ON sid.id_pieza = p.id_pieza
        WHERE sid.salida_interna_id = %s
    """, (salida_id,))
    piezas = cursor.fetchall()
    for pieza in piezas:
        pieza['cantidad_pendiente'] = pieza['cantidad_salida'] - pieza['ya_recibido'] - pieza['ya_perdido']
    return piezas


@salidas_internas_bp.route('/pendientes/<int:salida_id>')
@requiere_sesion()
@requiere_permiso('ver_salidas_internas')
def obtener_pendientes_salida(salida_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT estado FROM salidas_internas WHERE id = %s", (salida_id,))
        salida = cursor.fetchone()
        if not salida:
            return jsonify({'success': False, 'error': 'Salida interna no encontrada'})
        if salida['estado'] not in ('activa', 'parcial'):
            return jsonify({'success': False, 'error': 'Esta salida interna ya está finalizada.'})

        piezas = _obtener_piezas_pendientes(cursor, salida_id)
        piezas_pendientes = [p for p in piezas if p['cantidad_pendiente'] > 0]

        if not piezas_pendientes:
            return jsonify({'success': False, 'error': 'No quedan piezas pendientes de regresar.'})

        return jsonify({'success': True, 'piezas': piezas_pendientes})
    finally:
        cursor.close()
        conn.close()


# ======================= FINALIZAR (REGISTRAR ENTRADA DE) SALIDA INTERNA =======================
@salidas_internas_bp.route('/finalizar/<int:salida_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('finalizar_salida_interna')
def finalizar_salida_interna(salida_id):
    try:
        data = request.get_json()
        piezas_form = data.get('piezas', [])
        observaciones = data.get('observaciones', '').strip()
        usuario_id = session.get('user_id')

        if not piezas_form:
            return jsonify({'success': False, 'error': 'Debes capturar al menos una pieza.'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT si.*, s.nombre as sucursal_nombre
                FROM salidas_internas si
                JOIN sucursales s ON si.id_sucursal = s.id
                WHERE si.id = %s
            """, (salida_id,))
            salida = cursor.fetchone()
            if not salida:
                return jsonify({'success': False, 'error': 'Salida interna no encontrada'})
            if salida['estado'] not in ('activa', 'parcial'):
                return jsonify({'success': False, 'error': 'Esta salida interna ya está finalizada.'})

            # Recalcular pendientes en servidor (no confiar en lo que mande el navegador)
            piezas_pendientes = {p['id_pieza']: p for p in _obtener_piezas_pendientes(cursor, salida_id)}

            folio = obtener_siguiente_folio_nota_sucursal(cursor, salida['id_sucursal'])

            cursor.execute("""
                INSERT INTO salidas_internas_entradas (salida_interna_id, folio, fecha, observaciones, usuario_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (salida_id, folio, get_local_now(), observaciones, usuario_id))
            entrada_id = cursor.lastrowid

            for item in piezas_form:
                id_pieza = item.get('id_pieza')
                cantidad_recibida = int(item.get('cantidad_recibida') or 0)
                cantidad_perdida = int(item.get('cantidad_perdida') or 0)

                if cantidad_recibida <= 0 and cantidad_perdida <= 0:
                    continue

                pendiente = piezas_pendientes.get(int(id_pieza))
                if not pendiente:
                    conn.rollback()
                    return jsonify({'success': False, 'error': 'Pieza no pertenece a esta salida interna.'})

                if cantidad_recibida + cantidad_perdida > pendiente['cantidad_pendiente']:
                    conn.rollback()
                    return jsonify({
                        'success': False,
                        'error': f"{pendiente['nombre_pieza']}: solo quedan {pendiente['cantidad_pendiente']} pendientes."
                    })

                cursor.execute("""
                    INSERT INTO salidas_internas_entradas_detalle (entrada_id, id_pieza, cantidad_recibida, cantidad_perdida)
                    VALUES (%s, %s, %s, %s)
                """, (entrada_id, id_pieza, cantidad_recibida, cantidad_perdida))

                cursor.execute("""
                    SELECT total, disponibles, rentadas
                    FROM inventario_sucursal WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, salida['id_sucursal']))
                inventario = cursor.fetchone()
                if not inventario:
                    continue

                nuevo_total = max(0, inventario['total'] - cantidad_perdida)
                nuevos_disponibles = inventario['disponibles'] + cantidad_recibida
                nuevas_rentadas = max(0, inventario['rentadas'] - cantidad_recibida - cantidad_perdida)

                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET total = %s, disponibles = %s, rentadas = %s
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (nuevo_total, nuevos_disponibles, nuevas_rentadas, id_pieza, salida['id_sucursal']))

                if cantidad_recibida > 0:
                    cursor.execute("""
                        INSERT INTO movimientos_inventario
                        (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario, folio_nota_entrada)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_pieza, salida['id_sucursal'], 'retorno_salida_interna', cantidad_recibida,
                        f'Entrada de salida interna - {observaciones}', usuario_id, str(folio)
                    ))

                if cantidad_perdida > 0:
                    cursor.execute("""
                        INSERT INTO movimientos_inventario
                        (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario, folio_nota_entrada)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_pieza, salida['id_sucursal'], 'perdida_salida_interna', cantidad_perdida,
                        f'Pérdida de salida interna - {observaciones}', usuario_id, str(folio)
                    ))

            # Recalcular si ya quedó completamente resuelta o sigue pendiente
            piezas_actualizadas = _obtener_piezas_pendientes(cursor, salida_id)
            sigue_pendiente = any(p['cantidad_pendiente'] > 0 for p in piezas_actualizadas)

            if sigue_pendiente:
                cursor.execute("UPDATE salidas_internas SET estado = 'parcial' WHERE id = %s", (salida_id,))
            else:
                cursor.execute("""
                    UPDATE salidas_internas
                    SET estado = 'finalizada', fecha_finalizacion = %s,
                        observaciones_finalizacion = %s, usuario_finalizacion = %s
                    WHERE id = %s
                """, (get_local_now(), observaciones, usuario_id, salida_id))

            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Entrada registrada correctamente' + (' (la salida quedó finalizada).' if not sigue_pendiente else ', aún quedan piezas pendientes.'),
                'folio_nota_entrada': str(folio),
                'entrada_id': entrada_id,
                'estado': 'finalizada' if not sigue_pendiente else 'parcial'
            })

        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': f'Error al finalizar salida interna: {str(e)}'})
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})

# ======================= OBTENER DETALLE DE SALIDA INTERNA =======================
@salidas_internas_bp.route('/detalle/<int:salida_id>')
@requiere_sesion()
@requiere_permiso('ver_salidas_internas')
def obtener_detalle_salida(salida_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener datos de la salida
        cursor.execute("""
            SELECT si.*, s.nombre as sucursal_nombre
            FROM salidas_internas si
            JOIN sucursales s ON si.id_sucursal = s.id
            WHERE si.id = %s
        """, (salida_id,))
        
        salida = cursor.fetchone()
        if not salida:
            return jsonify({'success': False, 'error': 'Salida interna no encontrada'})
        
        # Obtener productos de la salida con su estado acumulado (recibido/perdido/pendiente)
        productos = _obtener_piezas_pendientes(cursor, salida_id)
        for p in productos:
            cursor.execute("SELECT codigo_pieza FROM piezas WHERE id_pieza = %s", (p['id_pieza'],))
            codigo_row = cursor.fetchone()
            p['codigo_pieza'] = codigo_row['codigo_pieza'] if codigo_row else None
            p['cantidad'] = p['cantidad_salida']  # compatibilidad con el render anterior

        # Historial de entradas (visitas) registradas para esta salida
        cursor.execute("""
            SELECT id, folio, fecha, observaciones
            FROM salidas_internas_entradas
            WHERE salida_interna_id = %s
            ORDER BY fecha DESC
        """, (salida_id,))
        entradas = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'salida': salida,
            'productos': productos,
            'entradas': entradas
        })

    except Exception as e:
        return jsonify({'success': False, 'error': f'Error al obtener detalle: {str(e)}'})













# ======================= GENERACIÓN DE PDFs =======================

@salidas_internas_bp.route('/pdf-salida/<folio>')
@requiere_sesion()
@requiere_permiso('ver_salidas_internas')
def generar_pdf_salida_interna(folio):
    """
    Generar PDF de nota de salida para salidas internas
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Primero obtener datos de la salida interna
        cursor.execute("""
            SELECT si.*, s.nombre as sucursal_nombre
            FROM salidas_internas si
            JOIN sucursales s ON si.id_sucursal = s.id
            WHERE si.folio_sucursal = %s
        """, (folio,))
        
        salida_datos = cursor.fetchone()
        
        if not salida_datos:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Salida interna no encontrada'}), 404
        
        # Obtener productos de la salida
        cursor.execute("""
            SELECT sid.cantidad, p.nombre_pieza, p.categoria
            FROM salidas_internas_detalle sid
            JOIN piezas p ON sid.id_pieza = p.id_pieza
            WHERE sid.salida_interna_id = %s
            ORDER BY p.nombre_pieza
        """, (salida_datos['id'],))
        
        productos = cursor.fetchall()
        if not productos:
            cursor.close()
            conn.close()
            return jsonify({'error': 'No hay productos en esta salida interna'}), 404
        
        # === OBTENER PLANTILLA DE LA SUCURSAL ===
        plantilla_renta = None
        try:
            conn2 = get_db_connection()
            cursor2 = conn2.cursor(dictionary=True)
            cursor2.execute("SELECT plantilla_renta FROM sucursales WHERE id = %s", (salida_datos['id_sucursal'],))
            sucursal_row = cursor2.fetchone()
            if sucursal_row and sucursal_row.get('plantilla_renta'):
                plantilla_renta = sucursal_row['plantilla_renta']
            cursor2.close()
            conn2.close()
        except Exception as e:
            print(f"Error obteniendo plantilla_renta: {e}")

        # Crear PDF
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        try:
            # Registrar fuente personalizada
            font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Carlito', font_path))
        except:
            pass

        # CONFIGURACIÓN INICIAL 
        page_width, page_height = letter
        y_position = page_height - 100

        # Folio
        c.setFont("Courier-Bold", 20)
        c.drawRightString(575, 690, f"#{folio}")

        # Fecha y hora de emisión
        c.setFont("Carlito", 12)
        fecha_emision = format_datetime_local(salida_datos['fecha_salida'], '%d/%m/%Y - %H:%M:%S')
        c.drawRightString(575, 715, f"{fecha_emision}")

        # === DATOS PRINCIPALES ===
        c.setFont("Courier-Bold", 23)
        c.drawString(496, 732, "SALIDA")

        c.setFont("Courier-Bold", 15)
        c.drawString(36, 715, "SALIDA INTERNA")

        # Datos del responsable y sucursal
        c.setFont("Carlito", 10)
        c.drawString(36, 695, f"SUCURSAL: {salida_datos['sucursal_nombre'].upper()}")

        # Responsable y fecha en la misma línea
        c.drawString(36, 680, f"RESPONSABLE: {salida_datos['responsable_entrega'].upper()}")
        c.drawString(350, 680, f"FECHA: {format_datetime_local(salida_datos['fecha_salida'], '%d/%m/%Y %H:%M')}")

        # Observaciones si existen
        if salida_datos['observaciones']:
            observaciones_texto = f"OBSERVACIONES: {salida_datos['observaciones'].upper()}"
            from reportlab.lib.utils import simpleSplit
            obs_lines = simpleSplit(observaciones_texto, "Carlito", 10, 530)
            y_obs = 665
            for line in obs_lines:
                c.drawString(36, y_obs, line)
                y_obs -= 12
            y_position = y_obs - 10
        else:
            y_position = 650

        # DATOS DE PIEZAS 
        # Texto descriptivo antes de la tabla
        c.setFont("Carlito", 10)
        c.drawString(36, y_position, "RECIBO DE ANDAMIOS COLOSIO")
        y_position -= 10
        c.drawString(36, y_position, "EL SIGUIENTE EQUIPO:")
        y_position -= 20

        # Encabezado de tabla
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        c.drawString(150, y_position + 5, "DESCRIPCIÓN")
        c.drawString(400, y_position + 5, "CATEGORÍA")
        y_position -= 15

        c.setFont("Carlito", 10)
        total_piezas = 0
        for producto in productos:
            # Verificar si necesitamos nueva página
            if y_position < 200:
                c.showPage()
                c.setFont("Carlito", 10)
                y_position = page_height - 60
                
            c.drawString(70, y_position + 5, str(producto['cantidad']))
            c.drawString(150, y_position + 5, producto['nombre_pieza'].upper())
            c.drawString(400, y_position + 5, (producto['categoria'] or '').upper())
            y_position -= 13
            total_piezas += producto['cantidad']

        y_position -= 5

        # Total de piezas
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y_position, f"TOTAL DE PIEZAS: {total_piezas}")
        y_position -= 20

        # === TÉRMINOS Y CONDICIONES ===
        c.setFont("Carlito", 11)
        c.drawString(36, y_position, "TÉRMINOS Y CONDICIONES:")
        y_position -= 20

        # Texto de términos adaptado para salidas internas
        c.setFont("Carlito", 9)
        terminos_texto = """POR MEDIO DE LA PRESENTE, RECONOZCO HABER RECIBIDO EN PERFECTO ESTADO Y FUNCIONANDO EL EQUIPO DESCRITO ANTERIORMENTE. \n        ME COMPROMETO A: • HACER USO RESPONSABLE DEL EQUIPO • MANTENER EL EQUIPO EN LAS MISMAS CONDICIONES • DEVOLVER EL\n        EQUIPO COMPLETO EN LA FECHA ACORDADA • RESPONDER POR DAÑOS, PÉRDIDA O ROBO • CUMPLIR CON TODAS LAS CONDICIONES ESTABLECIDAS.\n\n        IMPORTANTE: EL EQUIPO DEBE SER DEVUELTO EN LAS MISMAS CONDICIONES EN QUE SE ENTREGÓ."""

        from reportlab.lib.utils import simpleSplit
        terminos_lines = simpleSplit(terminos_texto, "Carlito", 9, 520)
        for line in terminos_lines:
            if y_position < 100:
                c.showPage()
                y_position = page_height - 60
            c.drawString(36, y_position, line)
            y_position -= 12

        y_position -= 30

        # === FIRMAS ===
        c.setFont("Carlito", 10)
        # Líneas para firmas
        c.line(60, y_position, 250, y_position)  # Línea empresa
        c.line(350, y_position, 540, y_position)  # Línea responsable
        y_position -= 15

        # Etiquetas de firmas
        c.drawString(60, y_position, "ENTREGA: ANDAMIOS COLOSIO")
        c.drawString(350, y_position, f"RECIBE: {salida_datos['responsable_entrega'].upper()}")
        y_position -= 10

        # Obtener nombre del usuario actual
        usuario_id = session.get('user_id')
        usuario_nombre = "USUARIO NO IDENTIFICADO"
        if usuario_id:
            conn_user = get_db_connection()
            cursor_user = conn_user.cursor(dictionary=True)
            try:
                cursor_user.execute("""
                    SELECT CONCAT(nombre, ' ', apellido1, ' ', apellido2) as nombre_completo
                    FROM usuarios 
                    WHERE id = %s
                """, (usuario_id,))
                usuario_row = cursor_user.fetchone()
                if usuario_row:
                    usuario_nombre = usuario_row['nombre_completo'].upper()
            finally:
                cursor_user.close()
                conn_user.close()

        c.drawString(60, y_position, f"NOMBRE: {usuario_nombre}")
        y_position -= 15

        # Guardar el canvas
        c.save()
        buffer.seek(0)

        # --- COMBINAR CON LA PLANTILLA PERSONALIZADA O BASE ---
        try:
            from PyPDF2 import PdfReader, PdfWriter
            plantilla_path = None
            if plantilla_renta:
                plantilla_path = os.path.join(current_app.root_path, plantilla_renta)
                if not os.path.exists(plantilla_path):
                    plantilla_path = None
            if not plantilla_path:
                plantilla_path = os.path.join(current_app.root_path, 'static/notas/base.pdf')

            overlay_pdf = PdfReader(buffer)
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
            overlay_pdf = PdfReader(buffer)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)

        return send_file(
            output_stream,
            download_name=f"salida_interna_{folio}.pdf",
            mimetype='application/pdf'
        )
    
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 500







@salidas_internas_bp.route('/pdf-entrada/<int:entrada_id>')
@requiere_sesion()
@requiere_permiso('ver_salidas_internas')
def generar_pdf_entrada_interna(entrada_id):
    """
    Generar PDF de nota de entrada para una visita/entrada específica de una salida
    interna (puede haber varias entradas para la misma salida, cada una con su PDF).
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener datos de la entrada (visita) y de la salida interna asociada
        cursor.execute("""
            SELECT sie.id, sie.folio, sie.fecha, sie.observaciones,
                   si.id_sucursal, si.responsable_entrega,
                   s.nombre AS sucursal_nombre
            FROM salidas_internas_entradas sie
            JOIN salidas_internas si ON sie.salida_interna_id = si.id
            JOIN sucursales s ON si.id_sucursal = s.id
            WHERE sie.id = %s
        """, (entrada_id,))

        entrada = cursor.fetchone()

        if not entrada:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Entrada interna no encontrada'}), 404

        # Piezas recibidas/perdidas en esta visita
        cursor.execute("""
            SELECT sied.cantidad_recibida, sied.cantidad_perdida, p.nombre_pieza, p.categoria
            FROM salidas_internas_entradas_detalle sied
            JOIN piezas p ON sied.id_pieza = p.id_pieza
            WHERE sied.entrada_id = %s
            ORDER BY p.nombre_pieza
        """, (entrada_id,))

        piezas = cursor.fetchall()
        folio = entrada['folio']

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

        # === OBTENER PLANTILLA DE LA SUCURSAL ===
        plantilla_renta = None
        try:
            conn2 = get_db_connection()
            cursor2 = conn2.cursor(dictionary=True)
            cursor2.execute("SELECT plantilla_renta FROM sucursales WHERE id = %s", (entrada['id_sucursal'],))
            sucursal_row = cursor2.fetchone()
            if sucursal_row and sucursal_row.get('plantilla_renta'):
                plantilla_renta = sucursal_row['plantilla_renta']
            cursor2.close()
            conn2.close()
        except Exception as e:
            print(f"Error obteniendo plantilla_renta: {e}")

        # Crear PDF
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        try:
            # Registrar fuente personalizada
            font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Carlito', font_path))
        except:
            pass

        # CONFIGURACIÓN INICIAL 
        page_width, page_height = letter
        y_position = page_height - 100

        # Folio
        c.setFont("Courier-Bold", 20)
        c.drawRightString(575, 690, f"#{folio}")

        # Fecha y hora de entrada
        c.setFont("Carlito", 12)
        fecha_entrada = format_datetime_local(entrada['fecha'], '%d/%m/%Y - %H:%M:%S')
        c.drawRightString(575, 715, f"{fecha_entrada}")

        # === DATOS PRINCIPALES ===
        c.setFont("Courier-Bold", 23)
        c.drawString(480, 732, "ENTRADA")

        c.setFont("Courier-Bold", 15)
        c.drawString(36, 715, "SALIDA INTERNA")

        # Datos de la sucursal y responsable
        c.setFont("Carlito", 10)
        c.drawString(36, 695, f"SUCURSAL: {entrada['sucursal_nombre'].upper()}")

        # Fecha de retorno
        c.drawString(36, 680, f"FECHA DE RETORNO: {format_datetime_local(entrada['fecha'], '%d/%m/%Y %H:%M')}")

        # Observaciones si existen
        if entrada['observaciones']:
            observaciones_texto = f"OBSERVACIONES: {entrada['observaciones'].upper()}"
            from reportlab.lib.utils import simpleSplit
            obs_lines = simpleSplit(observaciones_texto, "Carlito", 10, 530)
            y_obs = 665
            for line in obs_lines:
                c.drawString(36, y_obs, line)
                y_obs -= 12
            y_position = y_obs - 10
        else:
            y_position = 650

        # DATOS DE PIEZAS
        # Texto descriptivo antes de la tabla
        c.setFont("Carlito", 10)
        c.drawString(36, y_position, f"RECIBÍ DE: {entrada['responsable_entrega'].upper()}")
        y_position -= 10
        c.drawString(36, y_position, "EL SIGUIENTE EQUIPO:")
        y_position -= 25

        # Encabezado de tabla (con columnas de recibido/baja)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(150, y_position + 5, "DESCRIPCIÓN")
        c.drawString(380, y_position + 5, "CATEGORÍA")
        c.drawString(460, y_position + 5, "RECIBIDO")
        c.drawString(520, y_position + 5, "BAJA")
        y_position -= 15

        c.setFont("Carlito", 10)
        total_recibido = 0
        total_perdido = 0
        for pieza in piezas:
            # Verificar si necesitamos nueva página
            if y_position < 200:
                c.showPage()
                c.setFont("Carlito", 10)
                y_position = page_height - 60

            c.drawString(150, y_position + 5, pieza['nombre_pieza'].upper())
            c.drawString(380, y_position + 5, (pieza['categoria'] or '').upper())
            c.drawString(470, y_position + 5, str(pieza['cantidad_recibida']))
            c.drawString(530, y_position + 5, str(pieza['cantidad_perdida']))
            y_position -= 13
            total_recibido += pieza['cantidad_recibida']
            total_perdido += pieza['cantidad_perdida']

        y_position -= 5

        # Totales
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y_position, f"TOTAL RECIBIDO: {total_recibido}    TOTAL DADO DE BAJA: {total_perdido}")
        y_position -= 20

        # === PIE DE NOTA ===

        c.setFont("Carlito", 9)
        terminos_texto = "IMPORTANTE: CUALQUIER DAÑO, PÉRDIDA O EQUIPO SUCIO SERÁ FACTURADO SEGÚN TARIFAS VIGENTES"

        from reportlab.lib.utils import simpleSplit
        terminos_lines = simpleSplit(terminos_texto, "Carlito", 9, 520)
        for line in terminos_lines:
            if y_position < 100:
                c.showPage()
                y_position = page_height - 60
            c.drawString(36, y_position, line)
            y_position -= 12

        y_position -= 30

        # === FIRMAS ===
        c.setFont("Carlito", 10)
        # Líneas para firmas (invertidas para entrada)
        c.line(60, y_position, 250, y_position)  # Línea empresa
        c.line(350, y_position, 540, y_position)  # Línea responsable
        y_position -= 15

        # Etiquetas de firmas (invertidas para entrada)
        c.drawString(60, y_position, "RECIBE: ANDAMIOS COLOSIO")
        c.drawString(350, y_position, "ENTREGA: _______________________")
        y_position -= 10

        c.drawString(60, y_position, f"NOMBRE: {usuario_nombre}")
        y_position -= 15

        # Guardar el canvas
        c.save()
        buffer.seek(0)

        # --- COMBINAR CON LA PLANTILLA PERSONALIZADA O BASE ---
        try:
            from PyPDF2 import PdfReader, PdfWriter
            plantilla_path = None
            if plantilla_renta:
                plantilla_path = os.path.join(current_app.root_path, plantilla_renta)
                if not os.path.exists(plantilla_path):
                    plantilla_path = None
            if not plantilla_path:
                plantilla_path = os.path.join(current_app.root_path, 'static/notas/base.pdf')

            overlay_pdf = PdfReader(buffer)
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
            overlay_pdf = PdfReader(buffer)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)

        return send_file(
            output_stream,
            download_name=f"entrada_interna_{folio}.pdf",
            mimetype='application/pdf'
        )
    
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 500
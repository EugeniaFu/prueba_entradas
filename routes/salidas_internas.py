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

# ======================= FINALIZAR SALIDA INTERNA =======================
@salidas_internas_bp.route('/finalizar/<int:salida_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('finalizar_salida_interna')
def finalizar_salida_interna(salida_id):
    try:
        data = request.get_json()
        tipo_finalizacion = data.get('tipo')  # 'regreso' o 'no_regreso'
        observaciones_finalizacion = data.get('observaciones', '').strip()
        usuario_id = session.get('user_id')

        if not tipo_finalizacion or tipo_finalizacion not in ['regreso', 'no_regreso']:
            return jsonify({'success': False, 'error': 'Tipo de finalización inválido'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Obtener datos de la salida interna
            cursor.execute("""
                SELECT si.*, s.nombre as sucursal_nombre
                FROM salidas_internas si
                JOIN sucursales s ON si.id_sucursal = s.id
                WHERE si.id = %s AND si.estado = 'activa'
            """, (salida_id,))
            
            salida = cursor.fetchone()
            if not salida:
                return jsonify({'success': False, 'error': 'Salida interna no encontrada o ya finalizada'})
            
            # Obtener productos de la salida
            cursor.execute("""
                SELECT sid.*, p.nombre_pieza
                FROM salidas_internas_detalle sid
                JOIN piezas p ON sid.id_pieza = p.id_pieza
                WHERE sid.salida_interna_id = %s
            """, (salida_id,))
            
            productos_salida = cursor.fetchall()
            
            # Generar folio de entrada solo si hay regreso
            folio_entrada = None
            if tipo_finalizacion == 'regreso':
                folio_entrada = obtener_siguiente_folio_nota_sucursal(cursor, salida['id_sucursal'])
            
            # Procesar según el tipo de finalización
            for producto in productos_salida:
                id_pieza = producto['id_pieza']
                cantidad = producto['cantidad']
                
                # Obtener inventario actual
                cursor.execute("""
                    SELECT total, disponibles, rentadas 
                    FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, salida['id_sucursal']))
                
                inventario = cursor.fetchone()
                if not inventario:
                    continue
                
                if tipo_finalizacion == 'regreso':
                    # El equipo regresó: mover de rentadas a disponibles
                    nuevas_rentadas = max(0, inventario['rentadas'] - cantidad)
                    nuevos_disponibles = inventario['disponibles'] + cantidad
                    
                    cursor.execute("""
                        UPDATE inventario_sucursal 
                        SET disponibles = %s, rentadas = %s 
                        WHERE id_pieza = %s AND id_sucursal = %s
                    """, (nuevos_disponibles, nuevas_rentadas, id_pieza, salida['id_sucursal']))
                    
                    # Registrar movimiento
                    cursor.execute("""
                        INSERT INTO movimientos_inventario 
                        (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario, folio_nota_entrada)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_pieza, salida['id_sucursal'], 'retorno_salida_interna', cantidad,
                        f'Entrada de salida interna - {observaciones_finalizacion}',
                        usuario_id, str(folio_entrada)
                    ))
                    
                else:  # no_regreso
                    # El equipo no regresó: descontar del total y de rentadas
                    nuevo_total = max(0, inventario['total'] - cantidad)
                    nuevas_rentadas = max(0, inventario['rentadas'] - cantidad)
                    
                    cursor.execute("""
                        UPDATE inventario_sucursal 
                        SET total = %s, rentadas = %s 
                        WHERE id_pieza = %s AND id_sucursal = %s
                    """, (nuevo_total, nuevas_rentadas, id_pieza, salida['id_sucursal']))
                    
                    # Registrar movimiento
                    cursor.execute("""
                        INSERT INTO movimientos_inventario 
                        (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        id_pieza, salida['id_sucursal'], 'perdida_salida_interna', cantidad,
                        f'Pérdida de salida interna - {observaciones_finalizacion}',
                        usuario_id
                    ))
            
            # Actualizar estado de la salida interna
            cursor.execute("""
                UPDATE salidas_internas 
                SET estado = %s, fecha_finalizacion = %s, observaciones_finalizacion = %s, usuario_finalizacion = %s
                WHERE id = %s
            """, (
                'finalizada_regreso' if tipo_finalizacion == 'regreso' else 'finalizada_no_regreso',
                get_local_now(),
                observaciones_finalizacion,
                usuario_id,
                salida_id
            ))
            
            conn.commit()
            
            mensaje_tipo = 'con regreso de equipo' if tipo_finalizacion == 'regreso' else 'sin regreso de equipo'
            result = {
                'success': True,
                'message': f'Salida interna finalizada correctamente ({mensaje_tipo})'
            }
            
            # Agregar folio de entrada solo si hay regreso
            if tipo_finalizacion == 'regreso' and folio_entrada:
                result['folio_nota_entrada'] = str(folio_entrada)
                
            return jsonify(result)
            
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
        
        # Obtener productos de la salida
        cursor.execute("""
            SELECT sid.*, p.nombre_pieza, p.codigo_pieza
            FROM salidas_internas_detalle sid
            JOIN piezas p ON sid.id_pieza = p.id_pieza
            WHERE sid.salida_interna_id = %s
            ORDER BY p.nombre_pieza
        """, (salida_id,))
        
        productos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'salida': salida,
            'productos': productos
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error al obtener detalle: {str(e)}'})


# ======================= OBTENER FOLIO DE ENTRADA =======================
@salidas_internas_bp.route('/folio-entrada/<int:salida_id>')
@requiere_sesion()
@requiere_permiso('ver_salidas_internas')
def obtener_folio_entrada(salida_id):
    """
    Obtener el folio de nota de entrada para una salida interna finalizada con regreso
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Primero obtener la salida interna para verificar que existe y está finalizada con regreso
        cursor.execute("""
            SELECT si.folio_sucursal, si.id_sucursal
            FROM salidas_internas si
            WHERE si.id = %s AND si.estado = 'finalizada_regreso'
        """, (salida_id,))
        
        salida = cursor.fetchone()
        if not salida:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Salida interna no encontrada o no finalizada con regreso'})
        
        # Obtener el folio de nota de entrada desde movimientos_inventario
        cursor.execute("""
            SELECT DISTINCT mi.folio_nota_entrada
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s
            AND mi.tipo_movimiento = 'retorno_salida_interna'
            AND mi.folio_nota_entrada IS NOT NULL
            AND mi.descripcion LIKE %s
            ORDER BY mi.fecha DESC
            LIMIT 1
        """, (salida['id_sucursal'], f"%salida interna%"))
        
        resultado = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if resultado and resultado['folio_nota_entrada']:
            return jsonify({
                'success': True,
                'folio_nota_entrada': resultado['folio_nota_entrada']
            })
        else:
            return jsonify({'success': False, 'error': 'Folio de entrada no encontrado'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error al obtener folio: {str(e)}'})


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
        
        cursor.close()
        conn.close()
        
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
        terminos_texto = """POR MEDIO DE LA PRESENTE, RECONOZCO HABER RECIBIDO EN PERFECTO ESTADO Y FUNCIONANDO EL EQUIPO DESCRITO ANTERIORMENTE. 
        ME COMPROMETO A: • HACER USO RESPONSABLE DEL EQUIPO • MANTENER EL EQUIPO EN LAS MISMAS CONDICIONES • DEVOLVER EL
        EQUIPO COMPLETO EN LA FECHA ACORDADA • RESPONDER POR DAÑOS, PÉRDIDA O ROBO • CUMPLIR CON TODAS LAS CONDICIONES ESTABLECIDAS.

        IMPORTANTE: EL EQUIPO DEBE SER DEVUELTO EN LAS MISMAS CONDICIONES EN QUE SE ENTREGÓ."""

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
        
        # --- COMBINAR CON LA PLANTILLA ---
        try:
            from PyPDF2 import PdfReader, PdfWriter
            
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


@salidas_internas_bp.route('/pdf-entrada/<folio>')
@requiere_sesion()
@requiere_permiso('ver_salidas_internas')
def generar_pdf_entrada_interna(folio):
    """
    Generar PDF de nota de entrada para salidas internas (cuando regresan) con diseño profesional
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener datos del retorno desde movimientos_inventario
        cursor.execute("""
            SELECT mi.*, p.nombre_pieza, p.categoria,
                   s.nombre AS sucursal_nombre
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales s ON mi.id_sucursal = s.id
            WHERE mi.folio_nota_entrada = %s 
            AND mi.tipo_movimiento = 'retorno_salida_interna'
            ORDER BY p.nombre_pieza
        """, (folio,))
        
        movimientos = cursor.fetchall()
        
        if not movimientos:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Entrada interna no encontrada'}), 404
        
        # Datos generales del retorno
        primer_movimiento = movimientos[0]
        
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
        fecha_entrada = format_datetime_local(primer_movimiento['fecha'], '%d/%m/%Y - %H:%M:%S')
        c.drawRightString(575, 715, f"{fecha_entrada}")
        
        # === DATOS PRINCIPALES ===
        c.setFont("Courier-Bold", 23)
        c.drawString(480, 732, "ENTRADA")
        
        c.setFont("Courier-Bold", 15)
        c.drawString(36, 715, "SALIDA INTERNA")

        # Datos de la sucursal y responsable (extraer del primer movimiento)
        c.setFont("Carlito", 10)
        c.drawString(36, 695, f"SUCURSAL: {primer_movimiento['sucursal_nombre'].upper()}")
        
        # Fecha de retorno
        c.drawString(36, 680, f"FECHA DE RETORNO: {format_datetime_local(primer_movimiento['fecha'], '%d/%m/%Y %H:%M')}")
        
        # Observaciones si existen (extraer de la descripción)
        if primer_movimiento['descripcion']:
            observaciones_texto = f"OBSERVACIONES: {primer_movimiento['descripcion'].upper()}"
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
        c.drawString(36, y_position, "RECIBÍ DE: ______________________________")
        y_position -= 10
        c.drawString(36, y_position, "EL SIGUIENTE EQUIPO:")
        y_position -= 25
        
        # Encabezado de tabla (sin columnas de estado)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        c.drawString(150, y_position + 5, "DESCRIPCIÓN")
        c.drawString(400, y_position + 5, "CATEGORÍA")
        y_position -= 15
        
        c.setFont("Carlito", 10)
        total_piezas = 0
        for mov in movimientos:
            # Verificar si necesitamos nueva página
            if y_position < 200:
                c.showPage()
                c.setFont("Carlito", 10)
                y_position = page_height - 60
                
            c.drawString(70, y_position + 5, str(mov['cantidad']))
            c.drawString(150, y_position + 5, mov['nombre_pieza'].upper())
            c.drawString(400, y_position + 5, (mov['categoria'] or '').upper())
            y_position -= 13
            total_piezas += mov['cantidad']
        
        y_position -= 5
        
        # Total de piezas
        c.setFont("Helvetica-Bold", 9)
        c.drawString(36, y_position, f"TOTAL DE PIEZAS: {total_piezas}")
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
        
        # --- COMBINAR CON LA PLANTILLA ---
        try:
            from PyPDF2 import PdfReader, PdfWriter
            
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
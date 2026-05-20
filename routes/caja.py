from flask import Blueprint, render_template, request, jsonify, session, send_file, url_for, flash, redirect
from utils.db import get_db_connection
from datetime import date, datetime
from utils.datetime_utils import get_local_now, format_datetime_local
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
import traceback
import os
from utils.decorators import requiere_sesion, requiere_permiso


caja_bp = Blueprint('caja', __name__, url_prefix='/caja')

def registrar_movimiento_automatico(tipo, concepto, monto, metodo_pago, usuario_id, sucursal_id, 
                                  referencia_tabla, referencia_id, numero_seguimiento=None, observaciones=None):
    try:
        if metodo_pago != 'EFECTIVO':
            return {'success': True, 'registered': False, 'message': f'Pago por {metodo_pago} no se registra en caja'}
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Generar concepto automático para prefacturas
        concepto_final = concepto
        if referencia_tabla == 'prefacturas':
            try:
                cursor.execute("""
                    SELECT p.folio, CONCAT(c.nombre, ' ', c.apellido1) as cliente_nombre
                    FROM prefacturas p
                    JOIN rentas r ON p.renta_id = r.id
                    JOIN clientes c ON r.cliente_id = c.id
                    WHERE p.id = %s
                """, (referencia_id,))
                
                prefactura_info = cursor.fetchone()
                if prefactura_info:
                    concepto_final = f"Prefactura #{prefactura_info['folio']} - {prefactura_info['cliente_nombre']}"
            except Exception as e:
                print(f"Error al generar concepto de prefactura: {e}")
                # Si hay error, usar el concepto original
                pass
        
        cursor.execute("""
            INSERT INTO movimientos_caja (
                fecha_hora, tipo, concepto, monto, metodo_pago, 
                observaciones, tipo_movimiento, 
                referencia_tabla, referencia_id, usuario_id, sucursal_id
            ) VALUES (
                NOW(), %s, %s, %s, 'EFECTIVO', 
                %s, 'automatico', %s, %s, %s, %s
            )
        """, (tipo, concepto_final, monto, observaciones, referencia_tabla, referencia_id, usuario_id, sucursal_id))
        
        movimiento_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        
        return {'success': True, 'movimiento_id': movimiento_id, 'registered': True}
        
    except Exception as e:
        print(f"Error al registrar movimiento automático: {e}")
        return {'success': False, 'error': str(e)}

@caja_bp.route('/')
@requiere_sesion()
@requiere_permiso('ver_movimientos_caja')
def movimientos_caja():
    # Obtener lista de sucursales para el select (si es admin)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM sucursales ORDER BY nombre")
    sucursales = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('caja/movimiento_caja.html', sucursales=sucursales)

@caja_bp.route('/api/movimiento', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_movimiento_caja')
def crear_movimiento_manual():
    try:
        data = request.get_json()
        
        required_fields = ['tipo', 'concepto', 'monto', 'metodo_pago']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Campo {field} es requerido'}), 400
        
        tipo = data.get('tipo')
        concepto = data.get('concepto', '').strip()
        monto = float(data.get('monto', 0))
        metodo_pago = data.get('metodo_pago')
        observaciones = data.get('observaciones', '').strip()
        
        if tipo not in ['ingreso', 'egreso']:
            return jsonify({'success': False, 'error': 'Tipo de movimiento inválido'}), 400
            
        if monto <= 0:
            return jsonify({'success': False, 'error': 'El monto debe ser mayor a 0'}), 400
            
        if metodo_pago != 'EFECTIVO':
            return jsonify({'success': False, 'error': 'Los movimientos de caja solo aceptan EFECTIVO'}), 400
        
        usuario_id = session.get('user_id')
        sucursal_id = data.get('sucursal_id', session.get('sucursal_id'))
        
        if not sucursal_id:
            # Si el admin no seleccionó sucursal (y no tiene una propia), no puede registrar algo "global"
            return jsonify({'success': False, 'error': 'Debe especificar a qué sucursal pertenece el movimiento'}), 400
        
        if not usuario_id:
            return jsonify({'success': False, 'error': 'Usuario no autenticado'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO movimientos_caja (
                fecha_hora, tipo, concepto, monto, metodo_pago, 
                observaciones, tipo_movimiento, usuario_id, sucursal_id
            ) VALUES (
                NOW(), %s, %s, %s, 'EFECTIVO', %s, 'manual', %s, %s
            )
        """, (tipo, concepto, monto, observaciones if observaciones else None, usuario_id, sucursal_id))
        
        movimiento_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Movimiento de {tipo} registrado exitosamente',
            'movimiento_id': movimiento_id
        })
        
    except ValueError:
        return jsonify({'success': False, 'error': 'Monto inválido'}), 400
    except Exception as e:
        print(f"Error al crear movimiento manual: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@caja_bp.route('/api/movimiento/<int:movimiento_id>')
@requiere_sesion()
@requiere_permiso('ver_movimientos_caja')
def obtener_detalle_movimiento(movimiento_id):
    try:
        sucursal_id = session.get('sucursal_id', 1)
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT mc.*, CONCAT(u.nombre, ' ', u.apellido1, ' ', u.apellido2) as usuario_completo,
                   s.nombre as sucursal_nombre
            FROM movimientos_caja mc
            LEFT JOIN usuarios u ON mc.usuario_id = u.id
            LEFT JOIN sucursales s ON mc.sucursal_id = s.id
            WHERE mc.id = %s AND mc.sucursal_id = %s
        """, (movimiento_id, sucursal_id))
        
        movimiento = cursor.fetchone()
        
        if not movimiento:
            return jsonify({'success': False, 'error': 'Movimiento no encontrado'}), 404
        
        referencia_info = None
        if movimiento['tipo_movimiento'] == 'automatico' and movimiento['referencia_tabla']:
            try:
                if movimiento['referencia_tabla'] == 'prefacturas':
                    cursor.execute("""
                        SELECT p.id, p.tipo, p.monto, r.id as renta_id, 
                               CONCAT(c.nombre, ' ', c.apellido1) as cliente_nombre
                        FROM prefacturas p
                        JOIN rentas r ON p.renta_id = r.id
                        JOIN clientes c ON r.cliente_id = c.id
                        WHERE p.id = %s
                    """, (movimiento['referencia_id'],))
                elif movimiento['referencia_tabla'] == 'notas_cobro_extra':
                    cursor.execute("""
                        SELECT nce.id, nce.tipo, nce.total as monto, ne.folio, r.id as renta_id
                        FROM notas_cobro_extra nce
                        JOIN notas_entrada ne ON nce.nota_entrada_id = ne.id
                        JOIN rentas r ON ne.renta_id = r.id
                        WHERE nce.id = %s
                    """, (movimiento['referencia_id'],))
                elif movimiento['referencia_tabla'] == 'notas_cobro_retraso':
                    cursor.execute("""
                        SELECT ncr.id, 'retraso' as tipo, ncr.total as monto, ne.folio, r.id as renta_id
                        FROM notas_cobro_retraso ncr
                        JOIN notas_entrada ne ON ncr.nota_entrada_id = ne.id
                        JOIN rentas r ON ne.renta_id = r.id
                        WHERE ncr.id = %s
                    """, (movimiento['referencia_id'],))
                
                referencia_info = cursor.fetchone()
            except Exception as e:
                print(f"Error al obtener información de referencia: {e}")
        
        cursor.close()
        conn.close()
        
        movimiento['fecha_formateada'] = movimiento['fecha_hora'].strftime('%d/%m/%Y')
        movimiento['hora_formateada'] = movimiento['fecha_hora'].strftime('%H:%M:%S')
        movimiento['monto_formateado'] = f"{float(movimiento['monto']):,.2f}"
        
        return jsonify({
            'success': True,
            'movimiento': movimiento,
            'referencia_info': referencia_info
        })
        
    except Exception as e:
        print(f"Error al obtener detalle del movimiento: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@caja_bp.route('/api/movimientos')
@requiere_sesion()
@requiere_permiso('ver_movimientos_caja')
def obtener_movimientos():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin') 
        tipo = request.args.get('tipo')
        tipo_movimiento = request.args.get('tipo_movimiento')
        metodo_pago = request.args.get('metodo_pago')
        
        sucursal_id = request.args.get('sucursal_id', type=int)
        if sucursal_id is None:
            sucursal_id = session.get('sucursal_id')
        if sucursal_id is None:
            sucursal_id = 1
        
        if not fecha_inicio:
            fecha_inicio = date.today().strftime('%Y-%m-%d')
        if not fecha_fin:
            fecha_fin = fecha_inicio
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        where_clauses = ["mc.sucursal_id = %s", "DATE(mc.fecha_hora) BETWEEN %s AND %s"]
        params = [sucursal_id, fecha_inicio, fecha_fin]
        
        if tipo:
            where_clauses.append("mc.tipo = %s")
            params.append(tipo)
            
        if tipo_movimiento:
            where_clauses.append("mc.tipo_movimiento = %s")
            params.append(tipo_movimiento)
            
        if metodo_pago:
            where_clauses.append("mc.metodo_pago = %s")
            params.append(metodo_pago)
        
        where_sql = " AND ".join(where_clauses)
        
        cursor.execute(f"""
            SELECT mc.id, mc.fecha_hora, mc.tipo, mc.concepto, mc.monto, mc.metodo_pago,
                   mc.numero_seguimiento, mc.observaciones, mc.tipo_movimiento, 
                   mc.referencia_tabla, mc.referencia_id, mc.created_at,
                   CONCAT(u.nombre, ' ', u.apellido1) as usuario_nombre
            FROM movimientos_caja mc
            LEFT JOIN usuarios u ON mc.usuario_id = u.id
            WHERE {where_sql}
            ORDER BY mc.fecha_hora DESC
        """, params)
        
        movimientos = cursor.fetchall()
        
        for mov in movimientos:
            mov['fecha_formateada'] = mov['fecha_hora'].strftime('%d/%m/%Y')
            mov['hora_formateada'] = mov['fecha_hora'].strftime('%H:%M')
            mov['monto_formateado'] = f"{float(mov['monto']):,.2f}"
            
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'movimientos': movimientos})
        
    except Exception as e:
        print(f"Error al obtener movimientos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@caja_bp.route('/api/resumen')
@requiere_sesion()
@requiere_permiso('ver_movimientos_caja')
def obtener_resumen():
    try:
        fecha_inicio = request.args.get('fecha_inicio', date.today().strftime('%Y-%m-%d'))
        fecha_fin = request.args.get('fecha_fin', fecha_inicio)
        
        sucursal_id = request.args.get('sucursal_id', type=int)
        if sucursal_id is None:
            sucursal_id = session.get('sucursal_id')
        if sucursal_id is None:
            sucursal_id = 1
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT tipo, COALESCE(SUM(monto), 0) as total, COUNT(*) as cantidad
            FROM movimientos_caja 
            WHERE sucursal_id = %s AND DATE(fecha_hora) BETWEEN %s AND %s
            GROUP BY tipo
        """, (sucursal_id, fecha_inicio, fecha_fin))
        
        resultados = cursor.fetchall()
        
        total_ingresos = 0.0
        total_egresos = 0.0
        count_ingresos = 0
        count_egresos = 0
        
        for resultado in resultados:
            if resultado['tipo'] == 'ingreso':
                total_ingresos = float(resultado['total'])
                count_ingresos = resultado['cantidad']
            elif resultado['tipo'] == 'egreso':
                total_egresos = float(resultado['total'])
                count_egresos = resultado['cantidad']
        
        saldo_neto = total_ingresos - total_egresos
        
        if fecha_inicio == fecha_fin == date.today().strftime('%Y-%m-%d'):
            cursor.execute("""
                SELECT metodo_pago, tipo, COALESCE(SUM(monto), 0) as total
                FROM movimientos_caja 
                WHERE sucursal_id = %s AND DATE(fecha_hora) = %s
                GROUP BY metodo_pago, tipo
                ORDER BY metodo_pago, tipo
            """, (sucursal_id, fecha_inicio))
            
            desglose_metodos = cursor.fetchall()
        else:
            desglose_metodos = []
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'resumen': {
                'total_ingresos': total_ingresos,
                'total_egresos': total_egresos,
                'saldo_neto': saldo_neto,
                'count_ingresos': count_ingresos,
                'count_egresos': count_egresos,
                'desglose_metodos': desglose_metodos,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin
            }
        })
        
    except Exception as e:
        print(f"Error al obtener resumen: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@caja_bp.route('/api/ingresos-digitales')
@requiere_sesion()
@requiere_permiso('ver_movimientos_caja')
def obtener_ingresos_digitales():
    try:
        fecha_inicio = request.args.get('fecha_inicio', date.today().strftime('%Y-%m-%d'))
        fecha_fin = request.args.get('fecha_fin', fecha_inicio)
        
        sucursal_id = request.args.get('sucursal_id', type=int)
        if sucursal_id is None:
            sucursal_id = session.get('sucursal_id')
        if sucursal_id is None:
            sucursal_id = 1
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 'Prefactura' as tipo_documento, p.id as documento_id, p.folio,
                   p.fecha_emision as fecha, p.metodo_pago, p.monto, p.numero_seguimiento,
                   CONCAT(c.nombre, ' ', c.apellido1) as cliente_nombre,
                   'Sistema' as usuario_nombre
            FROM prefacturas p
            JOIN rentas r ON p.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            WHERE p.metodo_pago IN ('T.DÉBITO', 'T.CRÉDITO', 'TRANSFERENCIA')
            AND DATE(p.fecha_emision) BETWEEN %s AND %s
            AND r.id_sucursal = %s
            
            UNION ALL
            
            SELECT 'Cobro Extra' as tipo_documento, nce.id as documento_id, CONCAT('CE-', nce.id) as folio,
                   nce.fecha as fecha, nce.metodo_pago, nce.total as monto, nce.numero_seguimiento,
                   CONCAT(c.nombre, ' ', c.apellido1) as cliente_nombre,
                   'Sistema' as usuario_nombre
            FROM notas_cobro_extra nce
            JOIN notas_entrada ne ON nce.nota_entrada_id = ne.id
            JOIN rentas r ON ne.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            WHERE (nce.metodo_pago IN ('T.DÉBITO', 'T.CRÉDITO', 'TRANSFERENCIA') 
                   OR nce.metodo_pago IN ('tarjeta_debito', 'tarjeta_credito', 'transferencia'))
            AND DATE(nce.fecha) BETWEEN %s AND %s
            AND r.id_sucursal = %s
            
            UNION ALL
            
            SELECT 'Cobro Retraso' as tipo_documento, ncr.id as documento_id, CONCAT('CR-', ncr.id) as folio,
                   ncr.fecha as fecha, ncr.metodo_pago, ncr.total as monto, ncr.numero_seguimiento,
                   CONCAT(c.nombre, ' ', c.apellido1) as cliente_nombre,
                   'Sistema' as usuario_nombre
            FROM notas_cobro_retraso ncr
            JOIN notas_entrada ne ON ncr.nota_entrada_id = ne.id
            JOIN rentas r ON ne.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            WHERE (ncr.metodo_pago IN ('T.DÉBITO', 'T.CRÉDITO', 'TRANSFERENCIA')
                   OR ncr.metodo_pago IN ('tarjeta_debito', 'tarjeta_credito', 'transferencia'))
            AND DATE(ncr.fecha) BETWEEN %s AND %s
            AND r.id_sucursal = %s
            
            ORDER BY fecha DESC
        """, (fecha_inicio, fecha_fin, sucursal_id, fecha_inicio, fecha_fin, sucursal_id, fecha_inicio, fecha_fin, sucursal_id))
        
        ingresos_digitales = cursor.fetchall()
        
        cursor.execute("""
            SELECT metodo_pago, SUM(total_monto) as total, COUNT(*) as cantidad
            FROM (
                SELECT p.metodo_pago, p.monto as total_monto
                FROM prefacturas p JOIN rentas r ON p.renta_id = r.id
                WHERE p.metodo_pago IN ('T.DÉBITO', 'T.CRÉDITO', 'TRANSFERENCIA')
                AND DATE(p.fecha_emision) BETWEEN %s AND %s AND r.id_sucursal = %s
                
                UNION ALL
                
                SELECT nce.metodo_pago, nce.total as total_monto
                FROM notas_cobro_extra nce 
                JOIN notas_entrada ne ON nce.nota_entrada_id = ne.id
                JOIN rentas r ON ne.renta_id = r.id
                WHERE (nce.metodo_pago IN ('T.DÉBITO', 'T.CRÉDITO', 'TRANSFERENCIA') 
                       OR nce.metodo_pago IN ('tarjeta_debito', 'tarjeta_credito', 'transferencia'))
                AND DATE(nce.fecha) BETWEEN %s AND %s AND r.id_sucursal = %s
                
                UNION ALL
                
                SELECT ncr.metodo_pago, ncr.total as total_monto
                FROM notas_cobro_retraso ncr
                JOIN notas_entrada ne ON ncr.nota_entrada_id = ne.id
                JOIN rentas r ON ne.renta_id = r.id
                WHERE (ncr.metodo_pago IN ('T.DÉBITO', 'T.CRÉDITO', 'TRANSFERENCIA')
                       OR ncr.metodo_pago IN ('tarjeta_debito', 'tarjeta_credito', 'transferencia'))
                AND DATE(ncr.fecha) BETWEEN %s AND %s AND r.id_sucursal = %s
            ) as todos_ingresos
            GROUP BY metodo_pago
        """, (fecha_inicio, fecha_fin, sucursal_id, fecha_inicio, fecha_fin, sucursal_id, fecha_inicio, fecha_fin, sucursal_id))
        
        resumen_digital = cursor.fetchall()
        
        for ingreso in ingresos_digitales:
            ingreso['fecha_formateada'] = ingreso['fecha'].strftime('%d/%m/%Y')
            ingreso['monto_formateado'] = f"{float(ingreso['monto']):,.2f}"
            
        for resumen in resumen_digital:
            resumen['total_formateado'] = f"{float(resumen['total']):,.2f}"
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'ingresos_digitales': ingresos_digitales,
            'resumen_digital': resumen_digital,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        })
        
    except Exception as e:
        print(f"Error al obtener ingresos digitales: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@caja_bp.route('/pdf/movimientos')
@requiere_sesion()
@requiere_permiso('ver_movimientos_caja')
def generar_pdf_movimientos():
    try:
        # Obtener parámetros de filtros de la URL
        fecha_inicio = request.args.get('fecha_inicio', date.today().strftime('%Y-%m-%d'))
        fecha_fin = request.args.get('fecha_fin', fecha_inicio)
        tipo = request.args.get('tipo')
        tipo_movimiento = request.args.get('tipo_movimiento')
        
        sucursal_id = request.args.get('sucursal_id', type=int)
        if sucursal_id is None:
            sucursal_id = session.get('sucursal_id')
        if sucursal_id is None:
            sucursal_id = 1
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener información de la sucursal
        cursor.execute("""
            SELECT nombre, direccion
            FROM sucursales 
            WHERE id = %s
        """, (sucursal_id,))
        sucursal = cursor.fetchone()
        
        # Obtener información del usuario
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
        
        # Construir filtros
        where_clauses = ["mc.sucursal_id = %s", "DATE(mc.fecha_hora) BETWEEN %s AND %s"]
        params = [sucursal_id, fecha_inicio, fecha_fin]
        
        if tipo:
            where_clauses.append("mc.tipo = %s")
            params.append(tipo)
            
        if tipo_movimiento:
            where_clauses.append("mc.tipo_movimiento = %s")
            params.append(tipo_movimiento)
        
        where_sql = " AND ".join(where_clauses)
        
        # Obtener movimientos
        cursor.execute(f"""
            SELECT mc.id, mc.fecha_hora, mc.tipo, mc.concepto, mc.monto, mc.metodo_pago,
                   mc.numero_seguimiento, mc.observaciones, mc.tipo_movimiento,
                   CONCAT(u.nombre, ' ', u.apellido1) as usuario_nombre
            FROM movimientos_caja mc
            LEFT JOIN usuarios u ON mc.usuario_id = u.id
            WHERE {where_sql}
            ORDER BY mc.fecha_hora DESC
        """, params)
        
        movimientos = cursor.fetchall()
        
        # Obtener resumen
        cursor.execute("""
            SELECT tipo, COALESCE(SUM(monto), 0) as total, COUNT(*) as cantidad
            FROM movimientos_caja 
            WHERE sucursal_id = %s AND DATE(fecha_hora) BETWEEN %s AND %s
            GROUP BY tipo
        """, (sucursal_id, fecha_inicio, fecha_fin))
        
        resultados_resumen = cursor.fetchall()
        
        total_ingresos = 0.0
        total_egresos = 0.0
        count_ingresos = 0
        count_egresos = 0
        
        for resultado in resultados_resumen:
            if resultado['tipo'] == 'ingreso':
                total_ingresos = float(resultado['total'])
                count_ingresos = resultado['cantidad']
            elif resultado['tipo'] == 'egreso':
                total_egresos = float(resultado['total'])
                count_egresos = resultado['cantidad']
        
        saldo_neto = total_ingresos - total_egresos
        
        cursor.close()
        conn.close()
        
        # --- GENERAR PDF ---
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        
        # Registrar fuente
        try:
            font_path = os.path.join('static/fonts/Carlito-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Carlito', font_path))
        except:
            pass
        
        # === ENCABEZADO ===
        can.setFont("Courier-Bold", 16)
        titulo = "REPORTE DE MOVIMIENTOS DE CAJA"
        text_width = can.stringWidth(titulo, "Courier-Bold", 16)
        x_centered = (letter[0] - text_width) / 2
        can.drawString(x_centered, letter[1] - 50, titulo)
        
        # Información de la sucursal
        can.setFont("Carlito", 10)
        y_pos = letter[1] - 80
        if sucursal:
            can.drawString(40, y_pos, f"SUCURSAL: {sucursal['nombre'].upper()}")
            y_pos -= 12
            if sucursal['direccion']:
                can.drawString(40, y_pos, f"DIRECCIÓN: {sucursal['direccion'].upper()}")
                y_pos -= 12
        
        # Fechas del reporte
        can.setFont("Helvetica-Bold", 10)
        fecha_inicio_fmt = datetime.strptime(fecha_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
        fecha_fin_fmt = datetime.strptime(fecha_fin, '%Y-%m-%d').strftime('%d/%m/%Y')
        
        if fecha_inicio == fecha_fin:
            can.drawString(40, y_pos, f"FECHA: {fecha_inicio_fmt}")
        else:
            can.drawString(40, y_pos, f"PERÍODO: {fecha_inicio_fmt} AL {fecha_fin_fmt}")
        
        # Fecha y hora de generación
        can.setFont("Carlito", 9)
        fecha_generacion = format_datetime_local(get_local_now(), '%d/%m/%Y %H:%M:%S')
        can.drawRightString(letter[0] - 40, y_pos, f"GENERADO: {fecha_generacion}")
        y_pos -= 25
        
        # === RESUMEN ===
        can.setFont("Helvetica-Bold", 12)
        can.drawString(40, y_pos, "RESUMEN FINANCIERO")
        y_pos -= 20
        
        can.setFont("Carlito", 10)
        can.drawString(60, y_pos, f"TOTAL INGRESOS: ${total_ingresos:,.2f} ({count_ingresos} movimientos)")
        y_pos -= 15
        can.drawString(60, y_pos, f"TOTAL EGRESOS: ${total_egresos:,.2f} ({count_egresos} movimientos)")
        y_pos -= 15
        can.setFont("Helvetica-Bold", 11)
        color_saldo = "green" if saldo_neto >= 0 else "red"
        can.drawString(60, y_pos, f"SALDO NETO: ${saldo_neto:,.2f}")
        y_pos -= 30
        
        # === FILTROS APLICADOS ===
        can.setFont("Helvetica-Bold", 10)
        can.drawString(40, y_pos, "FILTROS APLICADOS:")
        y_pos -= 15
        
        can.setFont("Carlito", 9)
        if tipo:
            tipo_texto = "INGRESOS" if tipo == "ingreso" else "EGRESOS"
            can.drawString(60, y_pos, f"• TIPO DE MOVIMIENTO: {tipo_texto}")
            y_pos -= 12
        
        if tipo_movimiento:
            origen_texto = "MOVIMIENTOS MANUALES" if tipo_movimiento == "manual" else "PAGOS DEL SISTEMA"
            can.drawString(60, y_pos, f"• ORIGEN: {origen_texto}")
            y_pos -= 12
        
        if not tipo and not tipo_movimiento:
            can.drawString(60, y_pos, "• TODOS LOS MOVIMIENTOS")
            y_pos -= 12
        
        y_pos -= 20
        
        # === TABLA DE MOVIMIENTOS ===
        can.setFont("Helvetica-Bold", 10)
        can.drawString(40, y_pos, "DETALLE DE MOVIMIENTOS")
        y_pos -= 20
        
        # Encabezados de tabla
        can.setFont("Helvetica-Bold", 9)
        # Lado izquierdo
        can.drawString(40, y_pos, "FECHA")
        can.drawString(90, y_pos, "HORA")
        can.drawString(130, y_pos, "TIPO")
        can.drawString(180, y_pos, "CONCEPTO")
        # Lado derecho
        can.drawString(450, y_pos, "MONTO")
        can.drawString(520, y_pos, "ORIGEN")
        
        # Línea bajo encabezados
        can.line(40, y_pos - 3, 570, y_pos - 3)
        y_pos -= 20
        
        # Datos de movimientos
        can.setFont("Carlito", 8)
        for movimiento in movimientos:
            # Verificar si necesitamos nueva página
            if y_pos < 120:
                can.showPage()
                can.setFont("Carlito", 8)
                y_pos = letter[1] - 60
                
                # Repetir encabezados en nueva página
                can.setFont("Helvetica-Bold", 9)
                can.drawString(40, y_pos, "FECHA")
                can.drawString(90, y_pos, "HORA")
                can.drawString(130, y_pos, "TIPO")
                can.drawString(180, y_pos, "CONCEPTO")
                can.drawString(450, y_pos, "MONTO")
                can.drawString(520, y_pos, "ORIGEN")
                can.line(40, y_pos - 3, 570, y_pos - 3)
                y_pos -= 20
                can.setFont("Carlito", 8)
            
            # Preparar datos
            fecha_mov = movimiento['fecha_hora'].strftime('%d/%m/%Y')
            hora_mov = movimiento['fecha_hora'].strftime('%H:%M')
            tipo_mov = movimiento['tipo'].upper()
            monto_mov = f"${float(movimiento['monto']):,.2f}"
            origen_mov = "MANUAL" if movimiento['tipo_movimiento'] == "manual" else "SISTEMA"
            
            # Manejar concepto completo con salto de línea si es necesario
            concepto_completo = movimiento['concepto'].upper()
            # Dividir el concepto en líneas que quepan en el espacio disponible (aproximadamente 250 puntos)
            concepto_lines = simpleSplit(concepto_completo, "Carlito", 8, 250)
            
            # Dibujar la primera línea con todos los datos
            can.drawString(40, y_pos, fecha_mov)
            can.drawString(90, y_pos, hora_mov)
            can.drawString(130, y_pos, tipo_mov)
            can.drawString(180, y_pos, concepto_lines[0] if concepto_lines else "")
            can.drawString(450, y_pos, monto_mov)
            can.drawString(520, y_pos, origen_mov)
            
            y_pos -= 12
            
            # Si hay más líneas del concepto, dibujarlas
            if len(concepto_lines) > 1:
                for concepto_line in concepto_lines[1:]:
                    # Verificar espacio antes de continuar
                    if y_pos < 120:
                        can.showPage()
                        can.setFont("Carlito", 8)
                        y_pos = letter[1] - 60
                        
                        # Repetir encabezados en nueva página
                        can.setFont("Helvetica-Bold", 9)
                        can.drawString(40, y_pos, "FECHA")
                        can.drawString(90, y_pos, "HORA")
                        can.drawString(130, y_pos, "TIPO")
                        can.drawString(180, y_pos, "CONCEPTO")
                        can.drawString(450, y_pos, "MONTO")
                        can.drawString(520, y_pos, "ORIGEN")
                        can.line(40, y_pos - 3, 570, y_pos - 3)
                        y_pos -= 20
                        can.setFont("Carlito", 8)
                    
                    can.drawString(180, y_pos, concepto_line)
                    y_pos -= 12
            
            # Espacio adicional entre movimientos
            y_pos -= 3
        
        # === INFORMACIÓN DEL USUARIO ===
        y_pos -= 20
        can.setFont("Carlito", 9)
        can.drawString(40, y_pos, f"REPORTE GENERADO POR: {usuario_nombre}")
        
        can.save()
        packet.seek(0)
        
        # Preparar nombre del archivo
        fecha_archivo = fecha_inicio_fmt.replace('/', '-')
        if fecha_inicio != fecha_fin:
            fecha_fin_archivo = fecha_fin_fmt.replace('/', '-')
            nombre_archivo = f"movimientos_caja_{fecha_archivo}_al_{fecha_fin_archivo}.pdf"
        else:
            nombre_archivo = f"movimientos_caja_{fecha_archivo}.pdf"
        
        return send_file(
            packet, 
            download_name=nombre_archivo,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error al generar PDF de movimientos: {e}")
        return f"Error al generar PDF: {str(e)}", 500
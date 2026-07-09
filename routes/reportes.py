from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for, send_file
from utils.db import get_db_connection
from utils.datetime_utils import get_local_now, format_date_local
from utils.decorators import requiere_sesion, requiere_permiso
from datetime import date, datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
import os

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

@reportes_bp.route('/diario')
@requiere_sesion()
@requiere_permiso('ver_reportes')
def reporte_diario():
    """
    Muestra el reporte de entradas y salidas por fecha y sucursal
    """
    # Detectar si es admin (sin sucursal asignada)
    sucursal_id_usuario = session.get('sucursal_id')
    es_admin = (sucursal_id_usuario is None)
    
    # Si es admin, puede seleccionar cualquier sucursal
    # Si es secretaria, solo ve su sucursal asignada
    if es_admin:
        sucursal_id = request.args.get('sucursal_id', type=int)
        if sucursal_id is None:
            sucursal_id = 1  # Matriz por defecto
    else:
        # Forzar la sucursal del usuario (secretarias)
        sucursal_id = sucursal_id_usuario
        
    fecha_consulta = request.args.get('fecha', date.today().strftime('%Y-%m-%d'))
    
    print(f"DEBUG: Consultando sucursal {sucursal_id}, fecha {fecha_consulta}")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener información de la sucursal
        cursor.execute("SELECT id, nombre FROM sucursales WHERE id = %s", (sucursal_id,))
        sucursal = cursor.fetchone()
        
        if not sucursal:
            sucursal = {'id': 1, 'nombre': 'Matriz'}
        
        # Obtener todas las sucursales para el selector
        cursor.execute("SELECT id, nombre FROM sucursales ORDER BY id")
        sucursales = cursor.fetchall()
        
        # === 1. SALIDAS DE CLIENTES ===
        cursor.execute("""
            SELECT 
                ns.folio,
                ns.fecha,
                CONCAT(c.nombre, ' ', c.apellido1, ' ', IFNULL(c.apellido2, '')) as cliente_nombre,
                r.direccion_obra,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', nsd.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM notas_salida ns
            JOIN rentas r ON ns.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE r.id_sucursal = %s 
            AND DATE(ns.fecha) = %s
            AND ns.renta_id IS NOT NULL
            GROUP BY ns.id, ns.folio, ns.fecha, c.nombre, c.apellido1, c.apellido2, r.direccion_obra
            ORDER BY ns.fecha DESC
        """, (sucursal_id, fecha_consulta))
        salidas_clientes = cursor.fetchall()
        print(f"DEBUG: Salidas clientes encontradas: {len(salidas_clientes)}")
        
        # === 2. ENTRADAS DE CLIENTES ===
        cursor.execute("""
            SELECT 
                ne.folio,
                ne.fecha_entrada_real as fecha,
                CONCAT(c.nombre, ' ', c.apellido1, ' ', IFNULL(c.apellido2, '')) as cliente_nombre,
                r.direccion_obra,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', ned.cantidad_recibida, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM notas_entrada ne
            JOIN rentas r ON ne.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            JOIN notas_entrada_detalle ned ON ne.id = ned.nota_entrada_id
            JOIN piezas p ON ned.id_pieza = p.id_pieza
            WHERE r.id_sucursal = %s 
            AND DATE(ne.fecha_entrada_real) = %s
            AND ne.renta_id IS NOT NULL
            GROUP BY ne.id, ne.folio, ne.fecha_entrada_real, c.nombre, c.apellido1, c.apellido2, r.direccion_obra
            ORDER BY ne.fecha_entrada_real DESC
        """, (sucursal_id, fecha_consulta))
        entradas_clientes = cursor.fetchall()
        print(f"DEBUG: Entradas clientes encontradas: {len(entradas_clientes)}")
        
        # === 3. SALIDAS EXTRAS ===
        salidas_extras = []
        
        # 3.1 Transferencias enviadas
        cursor.execute("""
            SELECT 
                'transferencia' as tipo,
                mi.folio_nota_salida as folio,
                mi.fecha,
                CONCAT('Transferencia a ', sd.nombre) as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales sd ON mi.sucursal_destino = sd.id
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'transferencia_salida'
            AND mi.folio_nota_salida IS NOT NULL
            GROUP BY mi.folio_nota_salida, mi.fecha, sd.nombre
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        salidas_extras.extend(cursor.fetchall())
        
        # 3.2 Equipos enviados a reparación
        cursor.execute("""
            SELECT 
                'reparacion' as tipo,
                mi.folio_nota_salida as folio,
                mi.fecha,
                'Equipos enviados a reparación' as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'reparacion_lote'
            AND mi.folio_nota_salida IS NOT NULL
            GROUP BY mi.folio_nota_salida, mi.fecha
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        salidas_extras.extend(cursor.fetchall())
        
        # 3.3 Salidas internas
        cursor.execute("""
            SELECT 
                'salida_interna' as tipo,
                CONCAT('SUC', si.id_sucursal, '-', LPAD(si.folio_sucursal, 4, '0')) as folio,
                si.fecha_salida as fecha,
                CONCAT('Salida interna - ', si.responsable_entrega) as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', sid.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM salidas_internas si
            JOIN salidas_internas_detalle sid ON si.id = sid.salida_interna_id
            JOIN piezas p ON sid.id_pieza = p.id_pieza
            WHERE si.id_sucursal = %s 
            AND DATE(si.fecha_salida) = %s
            GROUP BY si.id, si.folio_sucursal, si.fecha_salida, si.responsable_entrega, si.id_sucursal
            ORDER BY si.fecha_salida DESC
        """, (sucursal_id, fecha_consulta))
        salidas_extras.extend(cursor.fetchall())
        
        # === 4. ENTRADAS EXTRAS ===
        entradas_extras = []
        
        # 4.1 Transferencias recibidas
        cursor.execute("""
            SELECT 
                'transferencia' as tipo,
                mi.folio_nota_entrada as folio,
                mi.fecha,
                'Transferencia recibida' as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'transferencia_entrada'
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, mi.fecha
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        entradas_extras.extend(cursor.fetchall())
        
        # 4.2 Altas de equipos nuevos
        cursor.execute("""
            SELECT 
                'alta_equipo' as tipo,
                mi.folio_nota_entrada as folio,
                mi.fecha,
                'Alta de equipos nuevos' as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'alta_equipo'
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, mi.fecha
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        entradas_extras.extend(cursor.fetchall())

        # 4.3 Entradas (retornos) de salidas internas
        cursor.execute("""
            SELECT
                'entrada_salida_interna' as tipo,
                sie.folio as folio,
                sie.fecha as fecha,
                CONCAT('Entrada de salida interna - ', si.responsable_entrega) as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', sied.cantidad_recibida, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM salidas_internas_entradas sie
            JOIN salidas_internas si ON sie.salida_interna_id = si.id
            JOIN salidas_internas_entradas_detalle sied ON sied.entrada_id = sie.id
            JOIN piezas p ON sied.id_pieza = p.id_pieza
            WHERE si.id_sucursal = %s
            AND DATE(sie.fecha) = %s
            AND sied.cantidad_recibida > 0
            GROUP BY sie.id, sie.folio, sie.fecha, si.responsable_entrega
            ORDER BY sie.fecha DESC
        """, (sucursal_id, fecha_consulta))
        entradas_extras.extend(cursor.fetchall())

        # Ordenar entradas y salidas extras por fecha
        salidas_extras = sorted(salidas_extras, key=lambda x: x['fecha'], reverse=True)
        entradas_extras = sorted(entradas_extras, key=lambda x: x['fecha'], reverse=True)

        print(f"DEBUG: Total salidas extras: {len(salidas_extras)}")
        print(f"DEBUG: Total entradas extras: {len(entradas_extras)}")
        
        cursor.close()
        conn.close()
        
        return render_template('reportes/reportes.html', 
                             salidas_clientes=salidas_clientes,
                             entradas_clientes=entradas_clientes,
                             salidas_extras=salidas_extras,
                             entradas_extras=entradas_extras,
                             sucursal=sucursal,
                             sucursales=sucursales,
                             fecha_consulta=fecha_consulta,
                             fecha_formato=format_date_local(get_local_now(), '%d/%m/%Y'),
                             es_admin=es_admin)
        
    except Exception as e:
        print(f'Error en reporte diario: {e}')
        return render_template('reportes/reportes.html', 
                             error='Error al generar el reporte',
                             sucursal=sucursal,
                             sucursales=sucursales if 'sucursales' in locals() else [],
                             fecha_consulta=fecha_consulta,
                             fecha_formato=format_date_local(get_local_now(), '%d/%m/%Y'),
                             es_admin=es_admin if 'es_admin' in locals() else False)





@reportes_bp.route('/pdf/diario')
@requiere_sesion()
@requiere_permiso('ver_reportes')
def generar_pdf_reporte_diario():
    """Genera PDF del reporte diario de movimientos"""
    try:
        # Detectar si es admin (sin sucursal asignada)
        sucursal_id_usuario = session.get('sucursal_id')
        es_admin = (sucursal_id_usuario is None)
        
        # Si es admin, puede seleccionar cualquier sucursal
        # Si es secretaria, solo ve su sucursal asignada
        if es_admin:
            sucursal_id = request.args.get('sucursal_id', type=int)
            if sucursal_id is None:
                sucursal_id = 1  # Matriz por defecto
        else:
            # Forzar la sucursal del usuario (secretarias)
            sucursal_id = sucursal_id_usuario
            
        fecha_consulta = request.args.get('fecha', date.today().strftime('%Y-%m-%d'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener información de la sucursal
        cursor.execute("SELECT id, nombre, direccion FROM sucursales WHERE id = %s", (sucursal_id,))
        sucursal = cursor.fetchone()
        
        if not sucursal:
            sucursal = {'id': 1, 'nombre': 'Matriz', 'direccion': 'Sin dirección registrada'}
        
        # Obtener usuario actual
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
        
        # === OBTENER DATOS IGUAL QUE EN LA VISTA ===
        # 1. SALIDAS DE CLIENTES
        cursor.execute("""
            SELECT 
                ns.folio,
                ns.fecha,
                CONCAT(c.nombre, ' ', c.apellido1, ' ', IFNULL(c.apellido2, '')) as cliente_nombre,
                r.direccion_obra,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', nsd.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM notas_salida ns
            JOIN rentas r ON ns.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE r.id_sucursal = %s 
            AND DATE(ns.fecha) = %s
            AND ns.renta_id IS NOT NULL
            GROUP BY ns.id, ns.folio, ns.fecha, c.nombre, c.apellido1, c.apellido2, r.direccion_obra
            ORDER BY ns.fecha DESC
        """, (sucursal_id, fecha_consulta))
        salidas_clientes = cursor.fetchall()
        
        # 2. ENTRADAS DE CLIENTES
        cursor.execute("""
            SELECT 
                ne.folio,
                ne.fecha_entrada_real as fecha,
                CONCAT(c.nombre, ' ', c.apellido1, ' ', IFNULL(c.apellido2, '')) as cliente_nombre,
                r.direccion_obra,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', ned.cantidad_recibida, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM notas_entrada ne
            JOIN rentas r ON ne.renta_id = r.id
            JOIN clientes c ON r.cliente_id = c.id
            JOIN notas_entrada_detalle ned ON ne.id = ned.nota_entrada_id
            JOIN piezas p ON ned.id_pieza = p.id_pieza
            WHERE r.id_sucursal = %s 
            AND DATE(ne.fecha_entrada_real) = %s
            AND ne.renta_id IS NOT NULL
            GROUP BY ne.id, ne.folio, ne.fecha_entrada_real, c.nombre, c.apellido1, c.apellido2, r.direccion_obra
            ORDER BY ne.fecha_entrada_real DESC
        """, (sucursal_id, fecha_consulta))
        entradas_clientes = cursor.fetchall()
        
        # 3. SALIDAS EXTRAS
        salidas_extras = []
        
        # Transferencias enviadas
        cursor.execute("""
            SELECT 
                'transferencia' as tipo,
                mi.folio_nota_salida as folio,
                mi.fecha,
                CONCAT('Transferencia a ', sd.nombre) as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales sd ON mi.sucursal_destino = sd.id
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'transferencia_salida'
            AND mi.folio_nota_salida IS NOT NULL
            GROUP BY mi.folio_nota_salida, mi.fecha, sd.nombre
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        salidas_extras.extend(cursor.fetchall())
        
        # Equipos enviados a reparación
        cursor.execute("""
            SELECT 
                'reparacion' as tipo,
                mi.folio_nota_salida as folio,
                mi.fecha,
                'Equipos enviados a reparación' as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'reparacion_lote'
            AND mi.folio_nota_salida IS NOT NULL
            GROUP BY mi.folio_nota_salida, mi.fecha
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        salidas_extras.extend(cursor.fetchall())
        
        # Salidas internas
        cursor.execute("""
            SELECT 
                'salida_interna' as tipo,
                CONCAT('SUC', si.id_sucursal, '-', LPAD(si.folio_sucursal, 4, '0')) as folio,
                si.fecha_salida as fecha,
                CONCAT('Salida interna - ', si.responsable_entrega) as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', sid.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM salidas_internas si
            JOIN salidas_internas_detalle sid ON si.id = sid.salida_interna_id
            JOIN piezas p ON sid.id_pieza = p.id_pieza
            WHERE si.id_sucursal = %s 
            AND DATE(si.fecha_salida) = %s
            GROUP BY si.id, si.folio_sucursal, si.fecha_salida, si.responsable_entrega, si.id_sucursal
            ORDER BY si.fecha_salida DESC
        """, (sucursal_id, fecha_consulta))
        salidas_extras.extend(cursor.fetchall())
        
        # 4. ENTRADAS EXTRAS
        entradas_extras = []
        
        # Transferencias recibidas
        cursor.execute("""
            SELECT 
                'transferencia' as tipo,
                mi.folio_nota_entrada as folio,
                mi.fecha,
                'Transferencia recibida' as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'transferencia_entrada'
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, mi.fecha
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        entradas_extras.extend(cursor.fetchall())
        
        # Altas de equipos nuevos
        cursor.execute("""
            SELECT 
                'alta_equipo' as tipo,
                mi.folio_nota_entrada as folio,
                mi.fecha,
                'Alta de equipos nuevos' as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', mi.cantidad, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            WHERE mi.id_sucursal = %s 
            AND DATE(mi.fecha) = %s
            AND mi.tipo_movimiento = 'alta_equipo'
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, mi.fecha
            ORDER BY mi.fecha DESC
        """, (sucursal_id, fecha_consulta))
        entradas_extras.extend(cursor.fetchall())

        # Entradas (retornos) de salidas internas
        cursor.execute("""
            SELECT
                'entrada_salida_interna' as tipo,
                sie.folio as folio,
                sie.fecha as fecha,
                CONCAT('Entrada de salida interna - ', si.responsable_entrega) as descripcion,
                GROUP_CONCAT(
                    CONCAT(p.nombre_pieza, ' (', sied.cantidad_recibida, ')')
                    ORDER BY p.nombre_pieza SEPARATOR ', '
                ) as piezas_detalle
            FROM salidas_internas_entradas sie
            JOIN salidas_internas si ON sie.salida_interna_id = si.id
            JOIN salidas_internas_entradas_detalle sied ON sied.entrada_id = sie.id
            JOIN piezas p ON sied.id_pieza = p.id_pieza
            WHERE si.id_sucursal = %s
            AND DATE(sie.fecha) = %s
            AND sied.cantidad_recibida > 0
            GROUP BY sie.id, sie.folio, sie.fecha, si.responsable_entrega
            ORDER BY sie.fecha DESC
        """, (sucursal_id, fecha_consulta))
        entradas_extras.extend(cursor.fetchall())

        # Ordenar por fecha
        salidas_extras = sorted(salidas_extras, key=lambda x: x['fecha'], reverse=True)
        entradas_extras = sorted(entradas_extras, key=lambda x: x['fecha'], reverse=True)

        cursor.close()
        conn.close()

        # === GENERAR PDF ===
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
        titulo = "REPORTE DIARIO DE MOVIMIENTOS"
        text_width = can.stringWidth(titulo, "Courier-Bold", 16)
        x_centered = (letter[0] - text_width) / 2
        can.drawString(x_centered, letter[1] - 50, titulo)
        
        # Información de la sucursal
        can.setFont("Carlito", 10)
        y_pos = letter[1] - 80
        can.drawString(40, y_pos, f"SUCURSAL: {sucursal['nombre'].upper()}")
        y_pos -= 12
        if sucursal.get('direccion'):
            can.drawString(40, y_pos, f"DIRECCIÓN: {sucursal['direccion'].upper()}")
            y_pos -= 12
        
        # Fecha del reporte
        can.setFont("Helvetica-Bold", 10)
        fecha_fmt = datetime.strptime(fecha_consulta, '%Y-%m-%d').strftime('%d/%m/%Y')
        can.drawString(40, y_pos, f"FECHA DEL REPORTE: {fecha_fmt}")
        
        # Fecha y hora de generación
        can.setFont("Carlito", 9)
        fecha_generacion = get_local_now().strftime('%d/%m/%Y %H:%M:%S')
        can.drawRightString(letter[0] - 40, y_pos, f"GENERADO: {fecha_generacion}")
        y_pos -= 30
        
        # === RESUMEN ===
        can.setFont("Helvetica-Bold", 12)
        can.drawString(40, y_pos, "RESUMEN DE MOVIMIENTOS")
        y_pos -= 20
        
        can.setFont("Carlito", 10)
        can.drawString(60, y_pos, f"• Salidas de Clientes: {len(salidas_clientes)} movimientos")
        y_pos -= 15
        can.drawString(60, y_pos, f"• Entradas de Clientes: {len(entradas_clientes)} movimientos")
        y_pos -= 15
        can.drawString(60, y_pos, f"• Salidas Extras: {len(salidas_extras)} movimientos")
        y_pos -= 15
        can.drawString(60, y_pos, f"• Entradas Extras: {len(entradas_extras)} movimientos")
        y_pos -= 30
        
        def dibujar_seccion(titulo, items, color_tipo, y_actual):
            """Función auxiliar para dibujar una sección del reporte"""
            can.setFont("Helvetica-Bold", 11)
            can.drawString(40, y_actual, titulo)
            y_actual -= 20
            
            if not items:
                can.setFont("Carlito", 9)
                can.drawString(60, y_actual, "No hay registros")
                return y_actual - 15
            
            can.setFont("Carlito", 8)
            for item in items:
                # Verificar espacio
                if y_actual < 120:
                    can.showPage()
                    y_actual = letter[1] - 60
                    can.setFont("Carlito", 8)
                
                # Información principal
                if 'cliente_nombre' in item:
                    can.drawString(60, y_actual, f"CLIENTE: {item['cliente_nombre'].upper()}")
                    y_actual -= 12
                    if item.get('direccion_obra'):
                        obra_text = f"OBRA: {item['direccion_obra']}"
                        obra_lines = simpleSplit(obra_text.upper(), "Carlito", 8, 500)
                        for line in obra_lines:
                            can.drawString(80, y_actual, line)
                            y_actual -= 10
                else:
                    can.drawString(60, y_actual, f"DESCRIPCIÓN: {item['descripcion'].upper()}")
                    y_actual -= 12
                
                # Piezas
                piezas_text = f"PIEZAS: {item['piezas_detalle']}"
                piezas_lines = simpleSplit(piezas_text.upper(), "Carlito", 8, 500)
                for line in piezas_lines:
                    can.drawString(80, y_actual, line)
                    y_actual -= 10
                
                # Folio y hora
                fecha_hora = item['fecha'].strftime('%H:%M')
                folio_info = f"FOLIO: {item['folio']} | HORA: {fecha_hora}"
                if 'tipo' in item:
                    folio_info += f" | TIPO: {item['tipo'].upper()}"
                can.drawString(80, y_actual, folio_info)
                y_actual -= 20
            
            return y_actual
        
        # === SECCIONES DEL REPORTE ===
        # SALIDAS DE CLIENTES
        y_pos = dibujar_seccion("1. SALIDAS DE CLIENTES", salidas_clientes, "red", y_pos)
        y_pos -= 10
        
        # ENTRADAS DE CLIENTES
        y_pos = dibujar_seccion("2. ENTRADAS DE CLIENTES", entradas_clientes, "green", y_pos)
        y_pos -= 10
        
        # SALIDAS EXTRAS
        y_pos = dibujar_seccion("3. SALIDAS EXTRAS", salidas_extras, "orange", y_pos)
        y_pos -= 10
        
        # ENTRADAS EXTRAS
        y_pos = dibujar_seccion("4. ENTRADAS EXTRAS", entradas_extras, "blue", y_pos)
        
        # === PIE DE PÁGINA ===
        if y_pos > 80:
            y_pos -= 30
        else:
            can.showPage()
            y_pos = letter[1] - 100
        
        can.setFont("Carlito", 9)
        can.drawString(40, y_pos, f"REPORTE GENERADO POR: {usuario_nombre}")
        
        can.save()
        packet.seek(0)
        
        # Preparar nombre del archivo
        fecha_archivo = fecha_fmt.replace('/', '-')
        sucursal_codigo = sucursal['nombre'].replace(' ', '_').lower()
        nombre_archivo = f"reporte_diario_{sucursal_codigo}_{fecha_archivo}.pdf"
        
        return send_file(
            packet, 
            download_name=nombre_archivo,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error al generar PDF del reporte diario: {e}")
        return f"Error al generar PDF: {str(e)}", 500
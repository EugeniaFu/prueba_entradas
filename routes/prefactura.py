
import os
from io import BytesIO
from datetime import datetime
from flask import Blueprint, redirect, request, jsonify, send_file, current_app, url_for, session
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso

# Importar función para registrar movimientos automáticos de caja
from routes.caja import registrar_movimiento_automatico

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PyPDF2 import PdfReader, PdfWriter
from num2words import num2words 
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit


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


prefactura_bp = Blueprint('prefactura', __name__, url_prefix='/prefactura')

# === Endpoint: Obtener datos de prefactura (AJAX) ===
@prefactura_bp.route('/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_prefactura')
def obtener_prefactura(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Obtener detalle de productos con precios históricos (ya guardados en renta_detalle)
    cursor.execute("""
        SELECT p.nombre, d.cantidad, d.dias_renta, d.costo_unitario, d.subtotal
        FROM renta_detalle d
        JOIN productos p ON d.id_producto = p.id_producto
        WHERE d.renta_id = %s
    """, (renta_id,))
    detalle = cursor.fetchall()
    
    # Totales y traslado
    cursor.execute("""
        SELECT total_con_iva, traslado, costo_traslado, fecha_entrada
        FROM rentas
        WHERE id = %s
    """, (renta_id,))
    total_info = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({
        "detalle": detalle,
        "total_con_iva": total_info['total_con_iva'] if total_info else 0,
        "traslado": total_info['traslado'] if total_info else None,
        "costo_traslado": total_info['costo_traslado'] if total_info else 0
    })




@prefactura_bp.route('/api/pagos/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_prefactura')
def obtener_historial_pagos(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT id, tipo, metodo_pago, monto, folio, id_sucursal,
               DATE_FORMAT(fecha_emision, '%d/%m/%Y %H:%i') as fecha_emision
        FROM prefacturas
        WHERE renta_id = %s AND pagada = 1
        ORDER BY fecha_emision ASC, id ASC
    ''', (renta_id,))
    filas = cursor.fetchall()
    cursor.close()
    conn.close()

    # Agrupar por folio: folios con >1 fila = pago combinado
    grupos = {}
    orden = []
    for f in filas:
        key = f['folio']
        if key not in grupos:
            grupos[key] = []
            orden.append(key)
        grupos[key].append(f)

    resultado = []
    for folio in orden:
        rows = grupos[folio]
        if len(rows) == 1:
            r = dict(rows[0])
            r['pdf_url'] = f"/prefactura/pdf/{r['id']}"
            r['es_combinado'] = False
            resultado.append(r)
        else:
            metodos = ' + '.join(r['metodo_pago'] for r in rows)
            monto_total = sum(float(r['monto']) for r in rows)
            sucursal_id = rows[0]['id_sucursal']
            resultado.append({
                'id': rows[0]['id'],
                'folio': folio,
                'tipo': 'combinado',
                'metodo_pago': metodos,
                'monto': monto_total,
                'fecha_emision': rows[0]['fecha_emision'],
                'id_sucursal': sucursal_id,
                'pdf_url': f"/prefactura/pdf_combinado/{sucursal_id}/{folio}",
                'es_combinado': True,
                'detalle_combinado': [
                    {'metodo_pago': r['metodo_pago'], 'monto': float(r['monto'])}
                    for r in rows
                ]
            })

    return jsonify(resultado)

@prefactura_bp.route('/api/info-redondeo/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_prefactura')
def obtener_info_redondeo(renta_id):
    """Obtiene información sobre redondeo para coincidir con la lógica de Python"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verificar si ya hay abonos y cuál fue el primer método
    cursor.execute("""
        SELECT COUNT(*) as total_abonos,
               COALESCE(SUM(monto), 0) as total_pagado,
               (SELECT metodo_pago FROM prefacturas WHERE renta_id = %s AND tipo = 'abono' AND pagada = 1 ORDER BY fecha_emision ASC LIMIT 1) as primer_metodo
        FROM prefacturas 
        WHERE renta_id = %s AND tipo = 'abono' AND pagada = 1
    """, (renta_id, renta_id))
    abono_info = cursor.fetchone()
    
    # Obtener total de la renta
    cursor.execute("SELECT total_con_iva FROM rentas WHERE id = %s", (renta_id,))
    renta_info = cursor.fetchone()
    total_renta = renta_info['total_con_iva'] if renta_info else 0
    
    # Verificar si hay pagos en efectivo (para lógica de redondeo)
    cursor.execute("""
        SELECT COUNT(*) as pagos_efectivo
        FROM prefacturas
        WHERE renta_id = %s AND pagada = 1 AND metodo_pago = 'EFECTIVO'
    """, (renta_id,))
    hay_pagos_efectivo = cursor.fetchone()['pagos_efectivo'] > 0
    
    cursor.close()
    conn.close()
    
    es_primer_abono = abono_info['total_abonos'] == 0
    total_ya_pagado = float(abono_info['total_pagado']) if abono_info['total_pagado'] is not None else 0.0
    primer_metodo_abono = abono_info['primer_metodo']
    
    # Calcular saldo pendiente considerando redondeo de efectivo
    diferencia = float(total_renta) - total_ya_pagado
    
    # Si hay pagos en efectivo y la diferencia es mínima, considerar saldo = 0
    if total_ya_pagado >= float(total_renta) or (hay_pagos_efectivo and abs(diferencia) < 1.00):
        saldo_pendiente = 0.0
    else:
        saldo_pendiente = diferencia
    
    # Lógica simplificada para el frontend: aplicar redondeo en efectivo si es primer abono O si el primero fue efectivo
    aplicar_redondeo_efectivo = es_primer_abono or (primer_metodo_abono == 'EFECTIVO')
    
    return jsonify({
        'es_primer_abono': es_primer_abono,
        'primer_metodo_abono': primer_metodo_abono,
        'saldo_pendiente': saldo_pendiente,
        'total_renta': total_renta,
        'total_pagado': total_ya_pagado,
        'aplicar_redondeo_efectivo': aplicar_redondeo_efectivo
    })




# === Endpoint: Registrar pago 
@prefactura_bp.route('/pago/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('pagar_prefactura')
def registrar_pago_prefactura(renta_id):
    data = request.get_json()
    tipo = data.get('tipo', 'inicial')
    metodo = data.get('metodo_pago')
    monto = data.get('monto')
    monto_recibido = data.get('monto_recibido')
    cambio = data.get('cambio')
    facturable = data.get('facturable', False)
    numero_seguimiento = data.get('numero_seguimiento')

    # DEBUG: Imprimir todos los datos recibidos
    print(f"=== DEBUG PREFACTURA ===")
    print(f"metodo_pago: '{metodo}' (tipo: {type(metodo)})")
    print(f"monto: {monto}")
    print(f"monto_recibido: {monto_recibido}")
    print(f"cambio: {cambio}")
    print(f"numero_seguimiento: '{numero_seguimiento}'")
    print(f"facturable: {facturable}")
    
    # Validar método de pago
    if not metodo or metodo.strip() == '':
        print("ERROR: Método de pago vacío o None")
        return jsonify({'success': False, 'error': 'Método de pago requerido'}), 400
    
    # Convertir explícitamente a entero para la BD
    facturable_int = 1 if facturable else 0
    
    # Asegurar que cambio no sea None para métodos no efectivo
    if metodo.upper() != 'EFECTIVO':
        cambio = 0.0
        # Asegurar que numero_seguimiento no sea None
        if not numero_seguimiento:
            numero_seguimiento = ''

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

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

        # Aplicar redondeo para pagos iniciales en efectivo
        if tipo == 'inicial' and metodo.upper() == 'EFECTIVO':
            monto_original = float(monto)
            monto_redondeado = redondear_efectivo(monto_original)
            print(f"Pago inicial efectivo - Monto original: {monto_original}, Monto redondeado: {monto_redondeado}")
            monto = monto_redondeado
            # Recalcular cambio si es necesario
            if monto_recibido and float(monto_recibido) > monto_redondeado:
                cambio = float(monto_recibido) - monto_redondeado

        # LÓGICA SIMPLIFICADA DE REDONDEO PARA ABONOS
        if tipo == 'abono':
            # Obtener información de abonos previos
            cursor.execute("""
                SELECT COUNT(*) as total_abonos, 
                       COALESCE(SUM(monto), 0) as total_pagado,
                       (SELECT metodo_pago FROM prefacturas WHERE renta_id = %s AND tipo = 'abono' AND pagada = 1 ORDER BY fecha_emision ASC LIMIT 1) as primer_metodo
                FROM prefacturas 
                WHERE renta_id = %s AND tipo = 'abono' AND pagada = 1
            """, (renta_id, renta_id))
            abono_info = cursor.fetchone()
            es_primer_abono = abono_info[0] == 0
            total_ya_pagado = abono_info[1] or 0
            primer_metodo_abono = abono_info[2]
            
            # Obtener total de la renta
            cursor.execute("SELECT total_con_iva FROM rentas WHERE id = %s", (renta_id,))
            total_renta = cursor.fetchone()[0]
            saldo_pendiente = total_renta - total_ya_pagado
            
            print(f"=== REDONDEO ABONOS ===")
            print(f"es_primer_abono: {es_primer_abono}")
            print(f"primer_metodo_abono: {primer_metodo_abono}")
            print(f"metodo_actual: {metodo}")
            print(f"saldo_pendiente: {saldo_pendiente}")
            print(f"monto_original: {monto}")
            
            # APLICAR REDONDEO SEGÚN LA SITUACIÓN
            if metodo.upper() == 'EFECTIVO':
                if es_primer_abono:
                    # Primer abono en efectivo
                    if float(monto) >= saldo_pendiente:
                        # Es liquidación completa: redondear el saldo total, no el monto original
                        saldo_redondeado = redondear_efectivo(saldo_pendiente)
                        monto = saldo_redondeado
                        print(f"Liquidación completa - Saldo redondeado: {saldo_redondeado}")
                    else:
                        # Es abono parcial: redondear el monto del abono
                        monto_redondeado = redondear_efectivo(float(monto))
                        monto = monto_redondeado
                        print(f"Abono parcial - Monto abono redondeado: {monto_redondeado}")
                    
                    # Recalcular cambio si es necesario
                    if monto_recibido and float(monto_recibido) > float(monto):
                        cambio = float(monto_recibido) - float(monto)
                        
                elif primer_metodo_abono == 'EFECTIVO':
                    # Abono posterior cuando el primero fue efectivo: aplicar redondeo al monto del abono
                    if float(monto) >= saldo_pendiente:
                        # Liquidación del saldo restante
                        saldo_redondeado = redondear_efectivo(saldo_pendiente)
                        monto = saldo_redondeado
                        print(f"Liquidación saldo restante - Saldo redondeado: {saldo_redondeado}")
                    else:
                        # Abono parcial adicional
                        monto_redondeado = redondear_efectivo(float(monto))
                        monto = monto_redondeado
                        print(f"Abono posterior parcial - Monto redondeado: {monto_redondeado}")
                    
                    # Recalcular cambio si es necesario
                    if monto_recibido and float(monto_recibido) > float(monto):
                        cambio = float(monto_recibido) - float(monto)
                else:
                    # Primer abono efectivo sin previos: aplicar redondeo según el tipo
                    if float(monto) >= saldo_pendiente:
                        # Es liquidación completa del saldo
                        saldo_redondeado = redondear_efectivo(saldo_pendiente)
                        monto = saldo_redondeado
                        print(f"Primer efectivo - Liquidación completa - Saldo redondeado: {saldo_redondeado}")
                    else:
                        # Es abono parcial
                        monto_redondeado = redondear_efectivo(float(monto))
                        monto = monto_redondeado  
                        print(f"Primer efectivo - Abono parcial - Monto redondeado: {monto_redondeado}")
                    
                    # Recalcular cambio si es necesario
                    if monto_recibido and float(monto_recibido) > float(monto):
                        cambio = float(monto_recibido) - float(monto)
            
            print(f"monto_final: {monto}")
            print(f"cambio_final: {cambio}")
            print("========================")
                
        # Obtener la sucursal de la renta (para el folio por sucursal y el movimiento de caja)
        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        renta_info = cursor.fetchone()

        if isinstance(renta_info, dict):
            sucursal_id = renta_info['id_sucursal']
        elif isinstance(renta_info, tuple) or isinstance(renta_info, list):
            sucursal_id = renta_info[0]
        else:
            sucursal_id = session.get('sucursal_id') or 1
        sucursal_id = sucursal_id or session.get('sucursal_id') or 1

        # Obtener el próximo folio (secuencia independiente por sucursal)
        folio = obtener_folio_consecutivo_prefactura(sucursal_id)

        # Insertar la prefactura (abono o inicial) CON EL FOLIO
        cursor.execute("""
            INSERT INTO prefacturas (
            renta_id, fecha_emision, tipo, pagada, metodo_pago, monto,
            monto_recibido, cambio, numero_seguimiento, generada, facturable, folio, id_sucursal
        ) VALUES (%s, NOW(), %s, 1, %s, %s, %s, %s, %s, 1, %s, %s, %s)
        """, (
            renta_id, tipo, metodo.upper(), monto, monto_recibido, cambio,
            numero_seguimiento, facturable_int, folio, sucursal_id
        ))
        prefactura_id = cursor.lastrowid

        # Registrar movimiento automático de caja si es pago en efectivo
        if metodo.upper() == 'EFECTIVO':
            concepto = f"Pago prefactura #{folio} - Renta #{renta_id} ({tipo})"
            usuario_id = session.get('user_id')

            resultado_caja = registrar_movimiento_automatico(
                tipo='ingreso',
                concepto=concepto,
                monto=float(monto),
                metodo_pago=metodo.upper(),
                usuario_id=usuario_id,
                sucursal_id=sucursal_id,
                referencia_tabla='prefacturas',
                referencia_id=prefactura_id,
                observaciones=f"Generado automáticamente desde prefactura"
            )
            
            if resultado_caja['success'] and resultado_caja.get('registered', False):
                print(f"Movimiento de caja registrado automáticamente: ID {resultado_caja['movimiento_id']}")

        # Calcular el total pagado hasta ahora (sumar todas las prefacturas pagadas de la renta)
        cursor.execute("""
            SELECT COALESCE(SUM(monto),0) as total_pagado
            FROM prefacturas
            WHERE renta_id = %s AND pagada = 1
        """, (renta_id,))
        total_pagado = cursor.fetchone()[0]

        # Obtener el total a pagar de la renta
        cursor.execute("SELECT total_con_iva FROM rentas WHERE id = %s", (renta_id,))
        total_renta = cursor.fetchone()[0]

        # Verificar si hay pagos en efectivo (que pueden tener redondeo)
        cursor.execute("""
            SELECT COUNT(*) as pagos_efectivo
            FROM prefacturas
            WHERE renta_id = %s AND pagada = 1 AND metodo_pago = 'EFECTIVO'
        """, (renta_id,))
        hay_pagos_efectivo = cursor.fetchone()[0] > 0

        # Determinar el nuevo estado de pago con lógica de redondeo de efectivo
        diferencia = float(total_renta) - float(total_pagado)
        
        # Si hay pagos en efectivo y la diferencia es mínima (menor a $1.00 por redondeo)
        # O si el total pagado es mayor o igual, considerarlo como pago realizado
        if total_pagado >= total_renta or (hay_pagos_efectivo and abs(diferencia) < 1.00):
            nuevo_estado = 'Pago realizado'
        elif total_pagado > 0:
            nuevo_estado = 'Saldo pendiente'
        else:
            nuevo_estado = 'Pago pendiente'

        # Actualizar el estado de la renta
        cursor.execute("""
            UPDATE rentas SET estado_pago=%s, metodo_pago=%s WHERE id=%s
        """, (nuevo_estado, metodo.upper(), renta_id))

        conn.commit()

        # VERIFICAR QUE SE GUARDÓ CORRECTAMENTE
        cursor.execute("SELECT metodo_pago, numero_seguimiento FROM prefacturas WHERE id = %s", (prefactura_id,))
        verificacion = cursor.fetchone()

        # Calcular el saldo pendiente actual para devolver al frontend
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total_pagado
            FROM prefacturas 
            WHERE renta_id = %s AND pagada = 1
        """, (renta_id,))
        total_pagado_actual = cursor.fetchone()[0]
        
        # Obtener el total de la renta
        cursor.execute("SELECT total_con_iva FROM rentas WHERE id = %s", (renta_id,))
        total_renta_actual = cursor.fetchone()[0]
        
        # Verificar nuevamente si hay pagos en efectivo para el cálculo del saldo
        cursor.execute("""
            SELECT COUNT(*) as pagos_efectivo
            FROM prefacturas
            WHERE renta_id = %s AND pagada = 1 AND metodo_pago = 'EFECTIVO'
        """, (renta_id,))
        hay_pagos_efectivo_actual = cursor.fetchone()[0] > 0
        
        # Calcular saldo pendiente considerando redondeo de efectivo
        diferencia_actual = float(total_renta_actual) - float(total_pagado_actual)
        
        # Si hay pagos en efectivo y la diferencia es mínima, considerar saldo = 0
        if float(total_pagado_actual) >= float(total_renta_actual) or \
           (hay_pagos_efectivo_actual and abs(diferencia_actual) < 1.00):
            saldo_pendiente_actual = 0.0
        else:
            saldo_pendiente_actual = diferencia_actual

        cursor.close()
        conn.close()

        return jsonify({
            'success': True, 
            'prefactura_id': prefactura_id,
            'saldo_pendiente': round(saldo_pendiente_actual, 2),
            'total_pagado': round(float(total_pagado_actual), 2),
            'total_renta': round(float(total_renta_actual), 2),
            'nuevo_estado': nuevo_estado,
            'tipo_pago': tipo,
            'monto_pagado': round(float(monto), 2)
        })
    except Exception as e:
        print(f"Error al registrar prefactura: {e}")
        return jsonify({'success': False, 'error': str(e)})















##################################################
##################################################
##################################################  PDF

@prefactura_bp.route('/pdf/<int:prefactura_id>')
@requiere_sesion()
@requiere_permiso('ver_prefactura')
def generar_pdf_prefactura(prefactura_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, r.fecha_entrada, r.fecha_salida, r.direccion_obra, r.metodo_pago, r.iva,
               r.traslado, r.costo_traslado, r.id_sucursal,
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
               c.rfc,
               s.plantilla_renta
        FROM prefacturas p
        JOIN rentas r ON p.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        JOIN sucursales s ON r.id_sucursal = s.id
        WHERE p.id = %s
    """, (prefactura_id,))
    prefactura = cursor.fetchone()

    cursor.execute("""
        SELECT prod.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
        FROM renta_detalle rd
        JOIN productos prod ON rd.id_producto = prod.id_producto
        WHERE rd.renta_id = %s
    """, (prefactura['renta_id'],))
    detalles = cursor.fetchall()
    
    # Obtener el total correcto de la renta original
    cursor.execute("""
        SELECT total_con_iva
        FROM rentas 
        WHERE id = %s
    """, (prefactura['renta_id'],))
    total_renta_info = cursor.fetchone()
    
    # Obtener historial completo de pagos/abonos
    cursor.execute("""
        SELECT id, tipo, metodo_pago, monto, 
               DATE_FORMAT(fecha_emision, '%d/%m/%Y %H:%i') as fecha_emision_formatted,
               fecha_emision,
               monto_recibido, cambio
        FROM prefacturas
        WHERE renta_id = %s AND pagada = 1
        ORDER BY fecha_emision ASC
    """, (prefactura['renta_id'],))
    historial_pagos = cursor.fetchall()
    
    
    # Para el PDF, usar el monto real cobrado en lugar del total original de la renta
    # Si es pago inicial completo, usar el monto de la prefactura (incluye redondeo)
    # Si hay abonos, usar el total original para cálculos de saldos
    total_renta_original = float(total_renta_info['total_con_iva']) if total_renta_info else float(prefactura['monto'])
    total_pagado = sum(float(pago['monto']) for pago in historial_pagos)
    
    # Determinar qué total mostrar en el PDF
    es_pago_inicial_solo = (len(historial_pagos) == 1 and historial_pagos[0]['tipo'] == 'inicial')
    if es_pago_inicial_solo:
        # Para pago inicial único, mostrar el monto real cobrado (con redondeo)
        total_renta = float(prefactura['monto'])
    else:
        # Para cases con abonos, mostrar el total original
        total_renta = total_renta_original
    
    saldo_pendiente = total_renta_original - total_pagado
    
    tiene_abonos = any(pago['tipo'] == 'abono' for pago in historial_pagos)
    es_pago_inicial_completo = (len(historial_pagos) == 1 and 
                               historial_pagos[0]['tipo'] == 'inicial' and 
                               saldo_pendiente <= 0.01)
    
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

    # --- FUNCIÓN DE REDONDEO PARA PDF ---
    def redondear_efectivo(monto):
        entero = int(monto)
        centavos = round((monto - entero) * 100)
        if centavos <= 49:
            return entero
        elif centavos >= 60:
            return entero + 1
        else:
            return entero + 0.5

    primer_abono_efectivo = None
    tiene_abonos_efectivo = False
    
    for pago in historial_pagos:
        if pago['tipo'] == 'abono' and pago['metodo_pago'] == 'EFECTIVO':
            if not primer_abono_efectivo:
                primer_abono_efectivo = pago
            tiene_abonos_efectivo = True
            break
    
    # Si hay abonos en efectivo, aplicar redondeo visual a los totales y saldos
    if tiene_abonos_efectivo:
        # Redondear saldo pendiente para mostrar consistencia (usar total original para cálculos)
        if saldo_pendiente > 0.01:
            saldo_pendiente_original = saldo_pendiente
            saldo_pendiente = redondear_efectivo(saldo_pendiente)
            # Ajustar el total pagado para que sume correctamente con el total original
            total_pagado = total_renta_original - saldo_pendiente
            
            print(f"PDF - Redondeo aplicado: Saldo original {saldo_pendiente_original:.2f} -> Saldo redondeado {saldo_pendiente:.2f}")
    
    print(f"PDF - Total renta mostrado: {total_renta:.2f}, Total pagado: {total_pagado:.2f}, Saldo pendiente: {saldo_pendiente:.2f}")

    # --- GENERAR OVERLAY CON DATOS ---
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    # Registrar fuentes
    try:
        font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Carlito', font_path))
    except:
        pass

    # === INFORMACIÓN DEL CLIENTE ===
    
    # === TÍTULO PRINCIPAL ===
    can.setFont("Courier-Bold", 15)
    can.drawString(490, 732, "PREFACTURA")
    
    
    # === DATOS DEL CLIENTE (ANIDADOS) ===
    y_cliente = 715
    
    can.setFont("Carlito", 10)
    
    # Código y nombre del cliente
    cliente_codigo_nombre = f"{prefactura['codigo_cliente']} - {prefactura['cliente_nombre'].upper()}"
    can.drawString(36, y_cliente, f"CLIENTE: {cliente_codigo_nombre}")
    y_cliente -= 13
    
    # Teléfono
    can.drawString(36, y_cliente, f"TELÉFONO: {prefactura['telefono'] or 'NO REGISTRADO'}")
    y_cliente -= 13
    
    # Correo
    can.drawString(36, y_cliente, f"CORREO: {prefactura['correo'] or 'NO REGISTRADO'}")
    y_cliente -= 13
    
    # Dirección completa (con ajuste multilínea si es necesario)
    direccion_completa = prefactura['calle'] or ''
    if prefactura['numero_exterior']:
        direccion_completa += f" #{prefactura['numero_exterior']}"
    if prefactura['numero_interior']:
        direccion_completa += f", INT. {prefactura['numero_interior']}"
    if prefactura['entre_calles']:
        direccion_completa += f" (ENTRE {prefactura['entre_calles']})"
    if prefactura['colonia']:
        direccion_completa += f", COL. {prefactura['colonia']}"
    if prefactura['codigo_postal']:
        direccion_completa += f" - C.P. {prefactura['codigo_postal']}"

    direccion_texto = f"DIRECCIÓN: {direccion_completa.upper()}"
    
    direccion_lines = simpleSplit(direccion_texto, "Carlito", 10, 530)
    for line in direccion_lines:
        can.drawString(36, y_cliente, line)
        y_cliente -= 13
    
    # Estado y Municipio en la misma línea
    can.drawString(36, y_cliente, f"ESTADO: {(prefactura['estado'] or 'NO REGISTRADO').upper()}")
    can.drawString(290, y_cliente, f"MUNICIPIO: {(prefactura['municipio'] or 'NO REGISTRADO').upper()}")
    y_cliente -= 13
    
    # RFC y Facturable en la misma línea
    can.drawString(36, y_cliente, f"RFC: {(prefactura['rfc'] or 'NO REGISTRADO').upper()}")
    facturable_texto = "SÍ" if prefactura['facturable'] else "NO"
    can.drawString(290, y_cliente, f"FACTURABLE: {facturable_texto}")
    y_cliente -= 20
    
    # === FECHA Y HORA DE EMISIÓN ===
    can.setFont("Carlito", 12)
    
    fecha_emision = prefactura['fecha_emision']
    can.drawRightString(575, 715, f"{fecha_emision.strftime('%d/%m/%Y - %H:%M:%S')}")
    
    # Folio (usar el folio guardado en la BD)
    can.setFont("Courier-Bold", 20)
    folio_consecutivo = prefactura['folio']  # Usar el folio guardado
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
        can.drawString(36, y_tabla + 5, item['nombre'][:35].upper())  # Limitar longitud del nombre
        can.drawRightString(350, y_tabla + 5, str(item['cantidad']))
        can.drawRightString(400, y_tabla + 5, str(item['dias_renta'] or 'N/A'))
        can.drawRightString(490, y_tabla + 5, f"${item['costo_unitario']:.2f}")
        can.drawRightString(570, y_tabla + 5, f"${item['subtotal']:.2f}")
        
        subtotal_general += float(item['subtotal'])
        y_tabla -= 13
        
        # Si hay muchos productos, crear nueva página o ajustar
        if y_tabla < 300:
            break
    
    y_tabla -= 5

    # === LÍNEA DIVISORA Y TOTALES ===
    can.line(28, y_tabla + 15, 585, y_tabla + 15)  # Línea separadora

    espacio_3mm = 10
    can.setFont("Carlito", 11)
    y_totales = y_tabla + 10 - espacio_3mm  # 3mm debajo de la línea

    # PERÍODO DE RENTA (AL LADO IZQUIERDO DEL SUBTOTAL)
    periodo_renta = f"{prefactura['fecha_salida'].strftime('%d/%m/%Y')}"
    if prefactura['fecha_entrada']:
        periodo_renta += f" - {prefactura['fecha_entrada'].strftime('%d/%m/%Y')}"
    else:
        periodo_renta += " - Indefinido"
    can.setFont("Helvetica-Bold", 10)
    can.drawString(36, y_totales, f"PERIODO DE RENTA: {periodo_renta}")

    # Subtotal de productos (AL LADO DERECHO)
    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, "SUBTOTAL:")
    can.drawRightString(570, y_totales, f"${subtotal_general:.2f}")
    y_totales -= 12

    # Traslado
    traslado_tipo = prefactura.get('traslado', 'ninguno')
    costo_traslado = prefactura.get('costo_traslado', 0)
    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, f"TRASLADO ({traslado_tipo}):")
    can.drawRightString(570, y_totales, f"${costo_traslado:.2f}")
    y_totales -= 12

    # IVA
    can.drawString(400, y_totales, "IVA (16%):")
    can.drawRightString(570, y_totales, f"${prefactura['iva']:.2f}")
    y_totales -= 12

    # Total de la renta
    can.setFont("Helvetica-Bold", 9)
    can.drawString(400, y_totales, "TOTAL RENTA:")
    can.drawRightString(570, y_totales, f"${total_renta:.2f}")
    
    # === TOTAL EN LETRAS (AL LADO IZQUIERDO DEL TOTAL RENTA) ===
    monto_entero = int(total_renta)
    monto_centavos = int(round((total_renta - monto_entero) * 100))
    monto_letras = num2words(monto_entero, lang='es').upper()
    if monto_centavos > 0:
        monto_letras = f"SON: {monto_letras} PESOS CON {monto_centavos:02d}/100 M.N."
    else:
        monto_letras = f"SON: {monto_letras} PESOS 00/100 M.N."

    # Usar simpleSplit para manejar texto multilínea si es muy largo
    can.setFont("Carlito", 9)
    monto_letras_lines = simpleSplit(monto_letras, "Carlito", 9, 350)  # Ancho máximo hasta donde empieza TOTAL RENTA
    y_letras = y_totales
    for line in monto_letras_lines:
        can.drawString(36, y_letras, line)
        y_letras -= 10
    
    # Ajustar y_totales según cuántas líneas ocupó el texto en letras
    lines_used = len(monto_letras_lines)
    y_totales -= max(12, lines_used * 10)

    # === MOSTRAR INFORMACIÓN SEGÚN TIPO DE PAGO ===
    if tiene_abonos:
        # === HISTORIAL DE PAGOS (PARA CUALQUIER ABONO, INCLUSO EL PRIMERO) ===
        # Línea separadora antes del historial
        can.line(28, y_totales + 5, 585, y_totales + 5)
        y_totales -= 10
        
        can.setFont("Helvetica-Bold", 11)
        can.drawString(36, y_totales, "HISTORIAL DE PAGOS:")
        y_totales -= 15
        
        # Encabezados de tabla de pagos
        can.setFont("Helvetica-Bold", 8)
        can.drawString(36, y_totales, "FECHA")
        can.drawString(120, y_totales, "TIPO")
        can.drawString(200, y_totales, "MÉTODO")
        can.drawRightString(350, y_totales, "MONTO")
        can.drawRightString(450, y_totales, "RECIBIDO")
        can.drawRightString(550, y_totales, "CAMBIO")
        y_totales -= 12
        
        # Datos de pagos
        can.setFont("Carlito", 8)
        for pago in historial_pagos:
            # Usar los valores exactos guardados en la base de datos
            monto_mostrar = float(pago['monto'])
            monto_recibido_mostrar = pago['monto_recibido']
            cambio_mostrar = pago['cambio']
            
            can.drawString(36, y_totales, pago['fecha_emision_formatted'])
            can.drawString(120, y_totales, pago['tipo'].upper())
            can.drawString(200, y_totales, pago['metodo_pago'])
            can.drawRightString(350, y_totales, f"${monto_mostrar:.2f}")
            
            # Mostrar monto recibido y cambio solo para pagos en efectivo
            if pago['metodo_pago'] == 'EFECTIVO':
                if monto_recibido_mostrar and float(monto_recibido_mostrar) > 0:
                    can.drawRightString(450, y_totales, f"${float(monto_recibido_mostrar):.2f}")
                else:
                    can.drawRightString(450, y_totales, "${:.2f}".format(monto_mostrar))
                
                # Mostrar cambio (usar el valor exacto de la BD)
                cambio_valor = float(cambio_mostrar) if cambio_mostrar is not None else 0.0
                can.drawRightString(550, y_totales, f"${cambio_valor:.2f}")
            else:
                # Para otros métodos de pago, mostrar monto exacto
                can.drawRightString(450, y_totales, f"${monto_mostrar:.2f}")
                can.drawRightString(550, y_totales, "$0.00")
            
            y_totales -= 10
        
        y_totales -= 10
        
        # Resumen de pagos
        can.setFont("Helvetica-Bold", 10)
        can.drawString(200, y_totales, "TOTAL PAGADO:")
        can.drawRightString(350, y_totales, f"${total_pagado:.2f}")
        y_totales -= 12
        
        can.drawString(200, y_totales, "SALDO PENDIENTE:")
        can.drawRightString(350, y_totales, f"${saldo_pendiente:.2f}")
        y_totales -= 20
        

    else:
        # === PAGO COMPLETO INICIAL ===
        pago_actual = historial_pagos[0] if historial_pagos else prefactura
        
        can.setFont("Carlito", 10)
        can.drawString(400, y_totales, "MÉTODO DE PAGO:")
        can.drawRightString(570, y_totales, f"{pago_actual['metodo_pago']}")
        y_totales -= 12
        
        # Para pagos en efectivo, siempre mostrar información de cambio
        if pago_actual['metodo_pago'] == 'EFECTIVO':
            # Obtener valores de monto recibido y cambio
            monto_recibido = pago_actual.get('monto_recibido')
            cambio_pago = pago_actual.get('cambio')
            monto_pago = float(pago_actual['monto'])
            
            # Si no hay monto_recibido registrado, asumir que se pagó exacto
            if not monto_recibido or float(monto_recibido) <= 0:
                monto_recibido = monto_pago
                cambio_pago = 0
            
            can.drawString(400, y_totales, "MONTO RECIBIDO:")
            can.drawRightString(570, y_totales, f"${float(monto_recibido):.2f}")
            y_totales -= 12
            
            can.drawString(400, y_totales, "CAMBIO:")
            cambio_valor = float(cambio_pago) if cambio_pago is not None else 0.0
            can.drawRightString(570, y_totales, f"${cambio_valor:.2f}")
            y_totales -= 12
        else:
            # Para otros métodos, mostrar monto exacto
            can.drawString(400, y_totales, "MONTO PAGADO:")
            can.drawRightString(570, y_totales, f"${float(pago_actual['monto']):.2f}")
            y_totales -= 12

    # === AVISOS IMPORTANTES PARA EL CLIENTE ===
    y_avisos = y_totales - 6  

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
    # Línea para firma
    can.line(60, y_avisos, 250, y_avisos)
    y_avisos -= 15
    
    # Etiqueta de firma con nombre del usuario
    can.drawString(60, y_avisos, f"ATENDIDO POR: {usuario_nombre}")


    # Guardar el canvas
    can.save()
    packet.seek(0)

    # --- COMBINAR CON LA PLANTILLA DE LA SUCURSAL ---
    try:
        plantilla_path = None
        if prefactura.get('plantilla_renta'):
            plantilla_path = os.path.join(current_app.root_path, prefactura['plantilla_renta'])
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
    
    return send_file(
        output_stream, 
        download_name=f"prefactura_{prefactura_id}.pdf", 
        mimetype='application/pdf'
    )

@prefactura_bp.route('/pago_combinado/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('pagar_prefactura')
def registrar_pago_combinado(renta_id):
    data = request.get_json()
    tipo = data.get('tipo', 'inicial')
    pagos = data.get('pagos', [])
    facturable = data.get('facturable', False)
    facturable_int = 1 if facturable else 0

    if len(pagos) < 2:
        return jsonify({'success': False, 'error': 'Se requieren al menos 2 métodos de pago'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id_sucursal FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        sucursal_id = (row[0] if isinstance(row, (tuple, list)) else row['id_sucursal']) if row else None
        sucursal_id = sucursal_id or session.get('sucursal_id') or 1

        folio = obtener_folio_consecutivo_prefactura(sucursal_id)

        prefactura_ids = []
        for pago in pagos:
            metodo = (pago.get('metodo_pago') or '').strip().upper()
            monto = float(pago.get('monto') or 0)
            if not metodo or monto <= 0:
                continue

            monto_recibido = pago.get('monto_recibido')
            cambio = float(pago.get('cambio') or 0)
            numero_seguimiento = pago.get('numero_seguimiento') or ''
            if metodo != 'EFECTIVO':
                cambio = 0.0

            cursor.execute("""
                INSERT INTO prefacturas (
                    renta_id, fecha_emision, tipo, pagada, metodo_pago, monto,
                    monto_recibido, cambio, numero_seguimiento, generada, facturable, folio, id_sucursal
                ) VALUES (%s, NOW(), %s, 1, %s, %s, %s, %s, %s, 1, %s, %s, %s)
            """, (renta_id, tipo, metodo, monto, monto_recibido, cambio,
                  numero_seguimiento, facturable_int, folio, sucursal_id))
            prefactura_id = cursor.lastrowid
            prefactura_ids.append(prefactura_id)

            if metodo == 'EFECTIVO':
                registrar_movimiento_automatico(
                    tipo='ingreso',
                    concepto=f"Pago combinado prefactura #{folio} - Renta #{renta_id}",
                    monto=monto,
                    metodo_pago='EFECTIVO',
                    usuario_id=session.get('user_id'),
                    sucursal_id=sucursal_id,
                    referencia_tabla='prefacturas',
                    referencia_id=prefactura_id,
                    observaciones='Generado automáticamente desde prefactura combinada'
                )

        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) FROM prefacturas WHERE renta_id = %s AND pagada = 1
        """, (renta_id,))
        total_pagado_bd = float(cursor.fetchone()[0])

        cursor.execute("SELECT total_con_iva FROM rentas WHERE id = %s", (renta_id,))
        total_renta = float(cursor.fetchone()[0])

        cursor.execute("""
            SELECT COUNT(*) FROM prefacturas
            WHERE renta_id = %s AND pagada = 1 AND metodo_pago = 'EFECTIVO'
        """, (renta_id,))
        hay_efectivo = cursor.fetchone()[0] > 0

        diferencia = total_renta - total_pagado_bd
        if total_pagado_bd >= total_renta or (hay_efectivo and abs(diferencia) < 1.00):
            nuevo_estado = 'Pago realizado'
        elif total_pagado_bd > 0:
            nuevo_estado = 'Saldo pendiente'
        else:
            nuevo_estado = 'Pago pendiente'

        cursor.execute(
            "UPDATE rentas SET estado_pago=%s, metodo_pago=%s WHERE id=%s",
            (nuevo_estado, 'COMBINADO', renta_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        saldo_pendiente = max(0.0, round(total_renta - total_pagado_bd, 2))
        if hay_efectivo and abs(saldo_pendiente) < 1.00:
            saldo_pendiente = 0.0

        return jsonify({
            'success': True,
            'folio': folio,
            'sucursal_id': sucursal_id,
            'prefactura_ids': prefactura_ids,
            'saldo_pendiente': saldo_pendiente,
            'nuevo_estado': nuevo_estado
        })

    except Exception as e:
        print(f"Error al registrar prefactura combinada: {e}")
        return jsonify({'success': False, 'error': str(e)})


@prefactura_bp.route('/pdf_combinado/<int:sucursal_id>/<int:folio>')
@requiere_sesion()
@requiere_permiso('ver_prefactura')
def generar_pdf_combinado(sucursal_id, folio):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener todas las filas del folio combinado
    cursor.execute("""
        SELECT p.*, r.fecha_entrada, r.fecha_salida, r.direccion_obra, r.iva,
               r.traslado, r.costo_traslado, r.id_sucursal,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.codigo_cliente, c.telefono, c.correo,
               c.calle, c.numero_exterior, c.numero_interior, c.entre_calles,
               c.colonia, c.codigo_postal, c.municipio, c.estado, c.rfc,
               s.plantilla_renta
        FROM prefacturas p
        JOIN rentas r ON p.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        JOIN sucursales s ON r.id_sucursal = s.id
        WHERE p.folio = %s AND p.id_sucursal = %s
        ORDER BY p.id ASC
    """, (folio, sucursal_id))
    filas = cursor.fetchall()

    if not filas:
        cursor.close()
        conn.close()
        return "No se encontró el folio combinado", 404

    pref = filas[0]  # datos del cliente / renta vienen de la primera fila
    renta_id = pref['renta_id']

    cursor.execute("""
        SELECT prod.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
        FROM renta_detalle rd
        JOIN productos prod ON rd.id_producto = prod.id_producto
        WHERE rd.renta_id = %s
    """, (renta_id,))
    detalles = cursor.fetchall()

    cursor.execute("SELECT total_con_iva FROM rentas WHERE id = %s", (renta_id,))
    total_renta_info = cursor.fetchone()
    total_renta = float(total_renta_info['total_con_iva']) if total_renta_info else 0.0

    usuario_nombre = "USUARIO NO IDENTIFICADO"
    usuario_id = session.get('user_id')
    if usuario_id:
        cursor.execute("""
            SELECT CONCAT(nombre, ' ', apellido1, ' ', apellido2) as nombre_completo
            FROM usuarios WHERE id = %s
        """, (usuario_id,))
        u = cursor.fetchone()
        if u:
            usuario_nombre = u['nombre_completo'].upper()

    cursor.close()
    conn.close()

    # Construir canvas
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    try:
        font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Carlito', font_path))
    except Exception:
        pass

    can.setFont("Courier-Bold", 15)
    can.drawString(490, 732, "PREFACTURA")

    y_cliente = 715
    can.setFont("Carlito", 10)
    can.drawString(36, y_cliente, f"CLIENTE: {pref['codigo_cliente']} - {pref['cliente_nombre'].upper()}")
    y_cliente -= 13
    can.drawString(36, y_cliente, f"TELÉFONO: {pref['telefono'] or 'NO REGISTRADO'}")
    y_cliente -= 13
    can.drawString(36, y_cliente, f"CORREO: {pref['correo'] or 'NO REGISTRADO'}")
    y_cliente -= 13

    direccion_completa = pref['calle'] or ''
    if pref['numero_exterior']:
        direccion_completa += f" #{pref['numero_exterior']}"
    if pref['numero_interior']:
        direccion_completa += f", INT. {pref['numero_interior']}"
    if pref['entre_calles']:
        direccion_completa += f" (ENTRE {pref['entre_calles']})"
    if pref['colonia']:
        direccion_completa += f", COL. {pref['colonia']}"
    if pref['codigo_postal']:
        direccion_completa += f" - C.P. {pref['codigo_postal']}"
    for line in simpleSplit(f"DIRECCIÓN: {direccion_completa.upper()}", "Carlito", 10, 530):
        can.drawString(36, y_cliente, line)
        y_cliente -= 13

    can.drawString(36, y_cliente, f"ESTADO: {(pref['estado'] or 'NO REGISTRADO').upper()}")
    can.drawString(290, y_cliente, f"MUNICIPIO: {(pref['municipio'] or 'NO REGISTRADO').upper()}")
    y_cliente -= 13
    can.drawString(36, y_cliente, f"RFC: {(pref['rfc'] or 'NO REGISTRADO').upper()}")
    facturable_texto = "SÍ" if pref['facturable'] else "NO"
    can.drawString(290, y_cliente, f"FACTURABLE: {facturable_texto}")
    y_cliente -= 20

    can.setFont("Carlito", 12)
    can.drawRightString(575, 715, f"{pref['fecha_emision'].strftime('%d/%m/%Y - %H:%M:%S')}")
    can.setFont("Courier-Bold", 20)
    can.drawRightString(575, 690, f"#{str(folio).zfill(4)}")

    # Tabla de productos
    y_tabla = y_cliente - 5
    can.line(28, y_tabla + 20, 585, y_tabla + 20)
    can.setFont("Helvetica-Bold", 9)
    can.drawString(36, y_tabla + 10, "DESCRIPCIÓN")
    can.drawRightString(350, y_tabla + 10, "CANT.")
    can.drawRightString(400, y_tabla + 10, "DÍAS")
    can.drawRightString(490, y_tabla + 10, "PRECIO UNIT.")
    can.drawRightString(570, y_tabla + 10, "SUBTOTAL")
    can.line(28, y_tabla + 5, 585, y_tabla + 5)
    y_tabla -= 15

    can.setFont("Carlito", 10)
    subtotal_general = 0
    for item in detalles:
        can.drawString(36, y_tabla + 5, item['nombre'][:35].upper())
        can.drawRightString(350, y_tabla + 5, str(item['cantidad']))
        can.drawRightString(400, y_tabla + 5, str(item['dias_renta'] or 'N/A'))
        can.drawRightString(490, y_tabla + 5, f"${item['costo_unitario']:.2f}")
        can.drawRightString(570, y_tabla + 5, f"${item['subtotal']:.2f}")
        subtotal_general += float(item['subtotal'])
        y_tabla -= 13
        if y_tabla < 300:
            break
    y_tabla -= 5

    can.line(28, y_tabla + 15, 585, y_tabla + 15)
    y_totales = y_tabla + 10 - 10

    costo_traslado = float(pref.get('costo_traslado') or 0)
    total_sin_iva = subtotal_general + costo_traslado
    iva_val = float(pref.get('iva') or 0)

    periodo_renta = f"{pref['fecha_salida'].strftime('%d/%m/%Y')}"
    if pref['fecha_entrada']:
        periodo_renta += f" - {pref['fecha_entrada'].strftime('%d/%m/%Y')}"
    else:
        periodo_renta += " - Indefinido"
    can.setFont("Helvetica-Bold", 10)
    can.drawString(36, y_totales, f"PERIODO DE RENTA: {periodo_renta}")

    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, "SUBTOTAL:")
    can.drawRightString(570, y_totales, f"${subtotal_general:.2f}")
    y_totales -= 12

    traslado_tipo = pref.get('traslado', 'ninguno')
    can.drawString(400, y_totales, f"TRASLADO ({traslado_tipo}):")
    can.drawRightString(570, y_totales, f"${costo_traslado:.2f}")
    y_totales -= 12

    can.drawString(400, y_totales, "IVA (16%):")
    can.drawRightString(570, y_totales, f"${iva_val:.2f}")
    y_totales -= 12

    can.setFont("Helvetica-Bold", 9)
    can.drawString(400, y_totales, "TOTAL RENTA:")
    can.drawRightString(570, y_totales, f"${total_renta:.2f}")

    monto_entero = int(total_renta)
    monto_centavos = int(round((total_renta - monto_entero) * 100))
    monto_letras = num2words(monto_entero, lang='es').upper()
    if monto_centavos > 0:
        monto_letras = f"SON: {monto_letras} PESOS CON {monto_centavos:02d}/100 M.N."
    else:
        monto_letras = f"SON: {monto_letras} PESOS 00/100 M.N."
    can.setFont("Carlito", 9)
    letras_lines = simpleSplit(monto_letras, "Carlito", 9, 350)
    y_letras = y_totales
    for line in letras_lines:
        can.drawString(36, y_letras, line)
        y_letras -= 10
    y_totales -= max(12, len(letras_lines) * 10)

    # === SECCIÓN PAGO COMBINADO ===
    can.line(28, y_totales + 5, 585, y_totales + 5)
    y_totales -= 10
    can.setFont("Helvetica-Bold", 11)
    can.drawString(36, y_totales, "PAGO COMBINADO:")
    y_totales -= 15

    can.setFont("Helvetica-Bold", 8)
    can.drawString(36, y_totales, "MÉTODO")
    can.drawRightString(300, y_totales, "MONTO")
    can.drawRightString(400, y_totales, "RECIBIDO")
    can.drawRightString(500, y_totales, "CAMBIO")
    can.drawString(510, y_totales, "SEGUIMIENTO")
    y_totales -= 12

    can.setFont("Carlito", 9)
    total_pagado_combinado = 0.0
    for fila in filas:
        metodo_f = fila['metodo_pago']
        monto_f = float(fila['monto'])
        total_pagado_combinado += monto_f
        can.drawString(36, y_totales, metodo_f)
        can.drawRightString(300, y_totales, f"${monto_f:.2f}")
        if metodo_f == 'EFECTIVO':
            mr = fila.get('monto_recibido')
            cb = fila.get('cambio')
            can.drawRightString(400, y_totales, f"${float(mr):.2f}" if mr else f"${monto_f:.2f}")
            can.drawRightString(500, y_totales, f"${float(cb):.2f}" if cb else "$0.00")
            can.drawString(510, y_totales, "-")
        else:
            can.drawRightString(400, y_totales, f"${monto_f:.2f}")
            can.drawRightString(500, y_totales, "$0.00")
            ns = fila.get('numero_seguimiento') or '-'
            can.drawString(510, y_totales, str(ns)[:18])
        y_totales -= 11

    y_totales -= 5
    can.setFont("Helvetica-Bold", 10)
    can.drawString(200, y_totales, "TOTAL PAGADO:")
    can.drawRightString(320, y_totales, f"${total_pagado_combinado:.2f}")
    y_totales -= 20

    # Avisos
    y_avisos = y_totales - 6
    can.line(28, y_avisos + 16, 585, y_avisos + 16)
    y_avisos -= 5
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
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "REQUISITOS DE RENTA:")
    y_avisos -= 11
    can.setFont("Carlito", 8)
    can.drawString(70, y_avisos, "• SE REQUIERE EL PAGO COMPLETO POR ADELANTADO DE LA RENTA.")
    y_avisos -= 10
    can.drawString(70, y_avisos, "• UBICACIÓN EXACTA DE LA OBRA (POR GOOGLE MAPS)")
    y_avisos -= 15
    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "¡IMPORTANTE!")
    y_avisos -= 11
    can.setFont("Carlito", 8)
    can.drawString(70, y_avisos, "• EL PERIODO DE RENTA INCLUYE DOMINGOS, DÍAS INHÁBILES Y FESTIVOS.")
    y_avisos -= 10
    can.drawString(70, y_avisos, "• NO SE ARMA, NI SE DESARMA EL EQUIPO.")
    y_avisos -= 10
    can.setFont("Carlito", 10)
    can.line(60, y_avisos, 250, y_avisos)
    y_avisos -= 15
    can.drawString(60, y_avisos, f"ATENDIDO POR: {usuario_nombre}")

    can.save()
    packet.seek(0)

    try:
        plantilla_path = None
        if pref.get('plantilla_renta'):
            plantilla_path = os.path.join(current_app.root_path, pref['plantilla_renta'])
            if not os.path.exists(plantilla_path):
                plantilla_path = None
        if not plantilla_path:
            plantilla_path = os.path.join(current_app.root_path, 'static/notas/base.pdf')

        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        if os.path.exists(plantilla_path):
            plantilla_pdf = PdfReader(plantilla_path)
            page = plantilla_pdf.pages[0]
            page.merge_page(overlay_pdf.pages[0])
            output.add_page(page)
        else:
            for page in overlay_pdf.pages:
                output.add_page(page)
    except Exception as e:
        print(f"Error con plantilla PDF combinada: {e}")
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        for page in overlay_pdf.pages:
            output.add_page(page)

    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    return send_file(output_stream, download_name=f"prefactura_combinada_{folio}.pdf", mimetype='application/pdf')


@prefactura_bp.route('/pdf_renta/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_prefactura')
def generar_pdf_prefactura_por_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, folio, id_sucursal FROM prefacturas
        WHERE renta_id = %s AND pagada = 1
        ORDER BY id DESC LIMIT 1
    """, (renta_id,))
    ultima = cursor.fetchone()
    if not ultima:
        cursor.close()
        conn.close()
        return f"No hay prefactura para la renta {renta_id}", 404

    # Verificar si el folio corresponde a un pago combinado (>1 fila con mismo folio)
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM prefacturas
        WHERE folio = %s AND id_sucursal = %s AND renta_id = %s
    """, (ultima['folio'], ultima['id_sucursal'], renta_id))
    cnt = cursor.fetchone()['cnt']
    cursor.close()
    conn.close()

    if cnt > 1:
        return redirect(url_for('prefactura.generar_pdf_combinado',
                                sucursal_id=ultima['id_sucursal'],
                                folio=ultima['folio']))
    return redirect(url_for('prefactura.generar_pdf_prefactura', prefactura_id=ultima['id']))
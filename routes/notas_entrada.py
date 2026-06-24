from flask import Blueprint, jsonify, request, current_app, send_file, redirect, url_for, session
from datetime import datetime, timedelta
from utils.db import get_db_connection
# Importar función de folio centralizada desde utils
from utils.folios import obtener_siguiente_folio_nota_sucursal
# Importar funciones de datetime utils
from utils.datetime_utils import get_local_now, format_datetime_local
from utils.decorators import requiere_sesion, requiere_permiso
from services.renta_service import RentasService

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


@notas_entrada_bp.route('/cargadores')
@requiere_sesion()
@requiere_permiso('ver_notas_entrada')
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
    
    # Bloquear nota de entrada para rentas finalizadas
    if sucursal_row['estado_renta'] in ['finalizada', 'renovación finalizada', 'cancelada']:
        cursor.close()
        conn.close()
        return jsonify({
            'error': 'Renta Finalizada',
            'message': 'No se puede crear nota de entrada porque esta renta ya fue finalizada, renovada o cancelada.'
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

    padre_real_id = sucursal_row['renta_asociada_id'] if sucursal_row['renta_asociada_id'] else renta_id

    # Obtener folio de salida y nota_salida_id del padre real
    cursor.execute("""
        SELECT folio, id AS nota_salida_id
        FROM notas_salida
        WHERE renta_id = %s
        ORDER BY id DESC LIMIT 1
    """, (padre_real_id,))
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
        WHERE r.renta_asociada_id = %s AND r.estado_renta IN ('activa renovacion', 'activo')
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

    # Piezas que salieron (suma de TODAS las notas de salida de la renta)
    piezas_salida = []
    if nota_salida_id:
        cursor.execute("""
            SELECT nsd.id_pieza, p.nombre_pieza, SUM(nsd.cantidad) AS cantidad_esperada
            FROM notas_salida ns
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE ns.renta_id = %s
            GROUP BY nsd.id_pieza, p.nombre_pieza
        """, (padre_real_id,))
        piezas_salida = cursor.fetchall()

    # Verifica si ya existe alguna nota de entrada
    cursor.execute("SELECT COUNT(*) AS total FROM notas_entrada WHERE renta_id = %s", (renta_id,))
    existe_entrada = cursor.fetchone()['total'] > 0

    # ¿Esta renta requiere que el chofer recolecte el equipo (traslado redondo o medio_regreso)?
    requiere_recoleccion = (renta['traslado'] or '').lower() in ('redondo', 'medio_regreso')

    # ¿Ya se hizo la recolección (existe una nota de entrada con todas las piezas en 0,
    # esperando que la secretaria capture lo que el chofer reportó manualmente)?
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
    ya_paso_recoleccion = cursor.fetchone() is not None

    # Piezas pendientes: compara total entregado vs total recibido a través de todas las notas
    cursor.execute("""
        SELECT
            entregado.id_pieza,
            entregado.nombre_pieza,
            entregado.cantidad_salida,
            IFNULL(recibido.cantidad_recibida_total, 0) AS cantidad_recibida_total,
            (entregado.cantidad_salida - IFNULL(recibido.cantidad_recibida_total, 0)) AS cantidad_pendiente
        FROM (
            SELECT nsd.id_pieza, p.nombre_pieza, SUM(nsd.cantidad) AS cantidad_salida
            FROM notas_salida ns
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            JOIN piezas p ON nsd.id_pieza = p.id_pieza
            WHERE ns.renta_id = %s
            GROUP BY nsd.id_pieza, p.nombre_pieza
        ) entregado
        LEFT JOIN (
            SELECT ned.id_pieza, SUM(ned.cantidad_recibida) AS cantidad_recibida_total
            FROM notas_entrada ne
            JOIN notas_entrada_detalle ned ON ne.id = ned.nota_entrada_id
            WHERE ne.renta_id = %s OR ne.renta_id = %s
                OR ne.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = %s)
            GROUP BY ned.id_pieza
        ) recibido ON entregado.id_pieza = recibido.id_pieza
        HAVING cantidad_pendiente > 0
        ORDER BY entregado.nombre_pieza
    """, (padre_real_id, renta_id, padre_real_id, padre_real_id))
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
        'piezas': piezas,
        'requiere_recoleccion': requiere_recoleccion,
        'ya_paso_recoleccion': ya_paso_recoleccion
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
    chofer_recoleccion_id = data.get('chofer_id') or None
    chofer_traslado_extra_id = data.get('chofer_traslado_extra_id') or None

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verificar si la renta ya está finalizada
        cursor.execute("SELECT estado_renta, traslado FROM rentas WHERE id = %s", (renta_id,))
        renta_check = cursor.fetchone()
        if renta_check and renta_check['estado_renta'] in ['finalizada', 'renovación finalizada', 'cancelada']:
            return jsonify({
                'success': False,
                'error': 'No se puede crear nota de entrada porque la renta ya está finalizada o cancelada.'
            }), 403

        # Validar chofer obligatorio para traslado extra
        if requiere_traslado_extra in ('medio', 'redondo') and not chofer_traslado_extra_id:
            return jsonify({
                'success': False,
                'error': 'Selecciona el chofer que realizará el traslado extra.'
            }), 403

        # --- Lógica para distinguir renovación total vs parcial ---
        cursor.execute("""
            SELECT COUNT(*) AS total_renovaciones
            FROM rentas
            WHERE renta_asociada_id = %s AND estado_renta IN ('activa renovacion', 'activo')
        """, (renta_id,))
        total_renovaciones = cursor.fetchone()['total_renovaciones']

        # Obtener padre_real_id
        cursor.execute("SELECT renta_asociada_id FROM rentas WHERE id = %s", (renta_id,))
        renta_row = cursor.fetchone()
        padre_real_id = renta_row['renta_asociada_id'] if renta_row and renta_row['renta_asociada_id'] else renta_id

        # Sumar piezas entregadas a través de TODAS las notas de salida del padre
        cursor.execute("""
            SELECT nsd.id_pieza, SUM(nsd.cantidad) AS cantidad_salida
            FROM notas_salida ns
            JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
            WHERE ns.renta_id = %s
            GROUP BY nsd.id_pieza
        """, (padre_real_id,))
        piezas_salida = cursor.fetchall()
        total_piezas_salida = sum([p['cantidad_salida'] for p in piezas_salida])
        total_piezas_recibidas = sum([int(p.get('cantidad_recibida', 0)) for p in piezas])

        # Respetar la decisión del usuario sobre cobrar retraso, independientemente de renovaciones
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

        # Gate: si la renta salió con traslado redondo o medio_regreso, la PRIMERA nota de
        # entrada debe ser obligatoriamente la de recolección (con chofer), para que la
        # secretaria no pueda finalizar la entrada con cantidades sin que el chofer haya
        # verificado físicamente el equipo.
        requiere_recoleccion = (renta_check['traslado'] or '').lower() in ('redondo', 'medio_regreso') if renta_check else False
        es_recoleccion_actual = all(
            (pieza.get('cantidad_recibida', 0) in [0, '', None]) for pieza in piezas
        ) if piezas else False

        if requiere_recoleccion and not nota_existente and not es_recoleccion_actual:
            return jsonify({
                'success': False,
                'error': 'Esta renta requiere que un chofer recolecte el equipo primero. Marca "En recolección" y selecciona el chofer antes de capturar las cantidades reales.'
            }), 403

        if requiere_recoleccion and es_recoleccion_actual and not chofer_recoleccion_id:
            return jsonify({
                'success': False,
                'error': 'Selecciona el chofer que recogerá el equipo.'
            }), 403

        if nota_existente:
            nota_entrada_id = nota_existente['id']
            # Actualizar cabecera
            if chofer_recoleccion_id:
                # Solo se sobrescribe el chofer si esta entrega trae uno nuevo,
                # para no perder el registro de quien recolectó el equipo
                cursor.execute("""
                    UPDATE notas_entrada
                    SET requiere_traslado_extra=%s, costo_traslado_extra=%s, observaciones=%s, estado_retraso=%s, accion_devolucion=%s, fecha_entrada_real=NOW(), chofer_recoleccion_id=%s, chofer_traslado_extra_id=%s
                    WHERE id=%s
                """, (requiere_traslado_extra, costo_traslado_extra, observaciones, estado_retraso, accion_devolucion, chofer_recoleccion_id, chofer_traslado_extra_id, nota_entrada_id))
            else:
                cursor.execute("""
                    UPDATE notas_entrada
                    SET requiere_traslado_extra=%s, costo_traslado_extra=%s, observaciones=%s, estado_retraso=%s, accion_devolucion=%s, fecha_entrada_real=NOW(), chofer_traslado_extra_id=%s
                    WHERE id=%s
                """, (requiere_traslado_extra, costo_traslado_extra, observaciones, estado_retraso, accion_devolucion, chofer_traslado_extra_id, nota_entrada_id))
            # Eliminar detalles anteriores
            cursor.execute("DELETE FROM notas_entrada_detalle WHERE nota_entrada_id=%s", (nota_entrada_id,))
        else:
            # Insertar nota de entrada
            cursor.execute("""
                INSERT INTO notas_entrada (
                    folio, renta_id, nota_salida_id, fecha_entrada_real,
                    requiere_traslado_extra, costo_traslado_extra, observaciones, estado, created_at, estado_retraso, accion_devolucion, chofer_recoleccion_id, chofer_traslado_extra_id, usuario_id
                ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
            """, (
                folio, renta_id, nota_salida_id, requiere_traslado_extra,
                costo_traslado_extra, observaciones, 'normal', estado_retraso, accion_devolucion, chofer_recoleccion_id, chofer_traslado_extra_id, session.get('user_id')
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

            # Perdidas: siempre que haya piezas marcadas como perdidas
            if cantidad_perdida > 0:
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
                    entregado.id_pieza,
                    entregado.cantidad_salida,
                    IFNULL(recibido.cantidad_recibida_total, 0) AS cantidad_recibida_total,
                    (entregado.cantidad_salida - IFNULL(recibido.cantidad_recibida_total, 0)) AS cantidad_pendiente
                FROM (
                    SELECT nsd.id_pieza, SUM(nsd.cantidad) AS cantidad_salida
                    FROM notas_salida ns
                    JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
                    WHERE ns.renta_id = %s
                    GROUP BY nsd.id_pieza
                ) entregado
                LEFT JOIN (
                    SELECT ned.id_pieza, SUM(ned.cantidad_recibida) AS cantidad_recibida_total
                    FROM notas_entrada ne
                    JOIN notas_entrada_detalle ned ON ne.id = ned.nota_entrada_id
                    WHERE ne.renta_id = %s OR ne.renta_id = %s
                        OR ne.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = %s)
                    GROUP BY ned.id_pieza
                ) recibido ON entregado.id_pieza = recibido.id_pieza
                HAVING cantidad_pendiente > 0
            """, (padre_real_id, renta_id, padre_real_id, padre_real_id))
            piezas_pendientes = cursor.fetchall()

            if len(piezas_pendientes) == 0:
                cursor.execute("""
                    UPDATE rentas SET estado_renta = 'finalizada'
                    WHERE id = %s
                """, (renta_id,))
                
                # Finalizar también las rentas asociadas (renovaciones)
                cursor.execute("""
                    UPDATE rentas SET estado_renta = 'finalizada'
                    WHERE renta_asociada_id = %s AND estado_renta = 'activa renovacion'
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


####################################################################
####################################################################
####################################################################
####################################################################
########## NOTA DE ENTRADA MÚLTIPLE (consolidación por cliente) ###

@notas_entrada_bp.route('/pendientes_cliente/<int:cliente_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_entrada')
def pendientes_cliente(cliente_id):
    sucursal_id = request.args.get('sucursal_id', type=int)
    if not sucursal_id:
        return jsonify({'error': 'Falta indicar la sucursal.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, CONCAT(nombre, ' ', apellido1, ' ', apellido2) AS nombre_completo, telefono
        FROM clientes WHERE id = %s
    """, (cliente_id,))
    cliente = cursor.fetchone()
    cursor.close()
    conn.close()

    if not cliente:
        return jsonify({'error': 'Cliente no encontrado.'}), 404

    rentas = RentasService.obtener_rentas_pendientes_cliente(cliente_id, sucursal_id)

    return jsonify({
        'cliente': cliente,
        'rentas': rentas
    })


@notas_entrada_bp.route('/crear_multiple', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_nota_entrada')
def crear_nota_entrada_multiple():
    data = request.get_json()
    cliente_id = data.get('cliente_id')
    sucursal_id = data.get('sucursal_id')
    rentas = data.get('rentas', [])
    observaciones = data.get('observaciones', '')
    chofer_recoleccion_id = data.get('chofer_recoleccion_id') or None
    traslado_extra = data.get('traslado_extra', 'ninguno')
    costo_traslado_extra = data.get('costo_traslado_extra', 0)
    chofer_traslado_extra_id = data.get('chofer_traslado_extra_id') or None

    if not cliente_id or not sucursal_id:
        return jsonify({'success': False, 'error': 'Falta cliente o sucursal.'}), 400

    try:
        cliente_id = int(cliente_id)
        sucursal_id = int(sucursal_id)
        for item in rentas:
            item['renta_id'] = int(item['renta_id'])
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Datos de cliente/sucursal/renta inválidos.'}), 400

    success, nota_entrada_id, folio, err_msg = RentasService.crear_nota_entrada_consolidada(
        cliente_id, sucursal_id, rentas, observaciones, session.get('user_id'),
        chofer_recoleccion_id=chofer_recoleccion_id, traslado_extra=traslado_extra,
        costo_traslado_extra=costo_traslado_extra, chofer_traslado_extra_id=chofer_traslado_extra_id
    )

    if success:
        return jsonify({'success': True, 'nota_entrada_id': nota_entrada_id, 'folio': folio})
    return jsonify({'success': False, 'error': err_msg})


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




#############################################
#############################################
#############################################
########## PDF NOTAS DE SALIDA ############

@notas_entrada_bp.route('/pdf/<int:nota_entrada_id>')
@requiere_sesion()
@requiere_permiso('ver_notas_entrada')
def generar_pdf_nota_entrada(nota_entrada_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ¿Esta nota consolida varias rentas? El folio es solo el número impreso en
    # el comprobante; cada renta consolidada tiene su propia fila en
    # notas_entrada (su propio id, igual que en el flujo normal de una sola
    # renta), así que la consolidación se detecta por filas que comparten
    # folio + sucursal.
    cursor.execute("""
        SELECT ne.folio, r.id_sucursal
        FROM notas_entrada ne
        JOIN rentas r ON ne.renta_id = r.id
        WHERE ne.id = %s
    """, (nota_entrada_id,))
    base = cursor.fetchone()
    if not base:
        cursor.close()
        conn.close()
        return "Nota de entrada no encontrada", 404

    cursor.execute("""
        SELECT ne.id AS nota_entrada_id, ne.renta_id
        FROM notas_entrada ne
        JOIN rentas r ON ne.renta_id = r.id
        WHERE ne.folio = %s AND r.id_sucursal = %s
        ORDER BY ne.id ASC
    """, (base['folio'], base['id_sucursal']))
    rentas_consolidadas = cursor.fetchall()
    cursor.close()
    conn.close()

    if len(rentas_consolidadas) > 1:
        return _generar_pdf_nota_entrada_multiple(rentas_consolidadas)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener datos completos de la nota de entrada, incluyendo la plantilla de la sucursal
    cursor.execute("""
         SELECT ne.folio, ne.fecha_entrada_real, ne.requiere_traslado_extra, ne.costo_traslado_extra, ne.observaciones,
             r.fecha_salida, r.fecha_entrada, r.direccion_obra, r.estado_renta, r.id_sucursal,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.codigo_cliente, c.telefono, c.calle, c.numero_exterior,
               c.numero_interior, c.entre_calles, c.colonia, c.codigo_postal,
               s.plantilla_renta,
               CONCAT(uc.nombre, ' ', uc.apellido1, ' ', uc.apellido2) AS chofer_nombre,
               ne.usuario_id AS creador_id,
               CONCAT(uo.nombre, ' ', uo.apellido1, ' ', uo.apellido2) AS creador_nombre
        FROM notas_entrada ne
        JOIN rentas r ON ne.renta_id = r.id
        JOIN clientes c ON r.cliente_id = c.id
        JOIN sucursales s ON r.id_sucursal = s.id
        LEFT JOIN usuarios uc ON ne.chofer_recoleccion_id = uc.id
        LEFT JOIN usuarios uo ON ne.usuario_id = uo.id
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

    # Nombre de quien recibió el equipo: el usuario que generó la nota originalmente.
    # Si la nota es de antes de registrar usuario_id, se usa el usuario en sesión como respaldo.
    usuario_nombre = "USUARIO NO IDENTIFICADO"
    if nota.get('creador_nombre'):
        usuario_nombre = nota['creador_nombre'].upper()
    else:
        usuario_id = session.get('user_id')
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
    es_recoleccion = (nota.get('estado_renta') or '').lower() == 'en recolección'

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
        recibidas_texto = mostrar_vacio_si_cero(pieza['cantidad_recibida'])
        if es_recoleccion and recibidas_texto == "":
            recibidas_texto = "(               )"
        can.drawString(355, y_position + 5, recibidas_texto)
        
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
    
    nombre_recibe = nota['chofer_nombre'].upper() if nota.get('chofer_nombre') else usuario_nombre
    can.drawString(60, y_position, f"NOMBRE: {nombre_recibe}")
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


#############################################
#############################################
########## PDF NOTA DE ENTRADA MÚLTIPLE ####
#############################################

def _generar_pdf_nota_entrada_multiple(rentas_consolidadas):
    """
    Genera un único folio (impreso) con una sección por cada renta consolidada,
    aunque internamente cada renta tiene su propia fila/id en notas_entrada
    (igual que en el flujo normal de una sola renta).
    """
    from reportlab.lib.utils import simpleSplit

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    renta_ids = [r['renta_id'] for r in rentas_consolidadas]
    nota_entrada_id_por_renta = {r['renta_id']: r['nota_entrada_id'] for r in rentas_consolidadas}

    # Cabecera: folio, fecha y observaciones se toman de la primera nota (todas
    # comparten el mismo folio impreso, generado en el mismo momento)
    primer_nota_entrada_id = rentas_consolidadas[0]['nota_entrada_id']
    cursor.execute("""
        SELECT ne.folio, ne.fecha_entrada_real, ne.observaciones, ne.usuario_id AS creador_id,
               ne.requiere_traslado_extra, ne.costo_traslado_extra,
               CONCAT(uo.nombre, ' ', uo.apellido1, ' ', uo.apellido2) AS creador_nombre,
               CONCAT(uc.nombre, ' ', uc.apellido1, ' ', uc.apellido2) AS chofer_recoleccion_nombre,
               CONCAT(uce.nombre, ' ', uce.apellido1, ' ', uce.apellido2) AS chofer_traslado_extra_nombre
        FROM notas_entrada ne
        LEFT JOIN usuarios uo ON ne.usuario_id = uo.id
        LEFT JOIN usuarios uc ON ne.chofer_recoleccion_id = uc.id
        LEFT JOIN usuarios uce ON ne.chofer_traslado_extra_id = uce.id
        WHERE ne.id = %s
    """, (primer_nota_entrada_id,))
    nota = cursor.fetchone()
    if not nota:
        cursor.close()
        conn.close()
        return "Nota de entrada no encontrada", 404

    cursor.execute(f"""
        SELECT r.id, r.folio, r.direccion_obra, r.id_sucursal,
               CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
               c.codigo_cliente, c.telefono, c.calle, c.numero_exterior, c.numero_interior,
               c.entre_calles, c.colonia, c.codigo_postal, s.plantilla_renta
        FROM rentas r
        JOIN clientes c ON r.cliente_id = c.id
        JOIN sucursales s ON r.id_sucursal = s.id
        WHERE r.id IN ({','.join(['%s'] * len(renta_ids))})
    """, tuple(renta_ids))
    rentas_info = {r['id']: r for r in cursor.fetchall()}

    nota_salida_ids = []
    for renta_id in renta_ids:
        cursor.execute("SELECT nota_salida_id FROM notas_entrada WHERE id = %s", (nota_entrada_id_por_renta[renta_id],))
        ns_row = cursor.fetchone()
        if ns_row:
            nota_salida_ids.append((renta_id, ns_row['nota_salida_id']))

    if nota_salida_ids:
        ids_unicos = list({ns_id for _, ns_id in nota_salida_ids})
        cursor.execute(f"""
            SELECT id, folio FROM notas_salida WHERE id IN ({','.join(['%s'] * len(ids_unicos))})
        """, tuple(ids_unicos))
        folio_por_nota_salida = {r['id']: r['folio'] for r in cursor.fetchall()}
        for renta_id, ns_id in nota_salida_ids:
            if renta_id in rentas_info:
                rentas_info[renta_id]['folio_salida'] = folio_por_nota_salida.get(ns_id)

    piezas_por_renta = {}
    for renta_id in renta_ids:
        cursor.execute("""
            SELECT ned.cantidad_esperada, ned.cantidad_recibida, ned.cantidad_buena,
                   ned.cantidad_danada, ned.cantidad_sucia, ned.cantidad_perdida, p.nombre_pieza
            FROM notas_entrada_detalle ned
            JOIN piezas p ON ned.id_pieza = p.id_pieza
            WHERE ned.nota_entrada_id = %s
            ORDER BY p.nombre_pieza
        """, (nota_entrada_id_por_renta[renta_id],))
        piezas_por_renta[renta_id] = cursor.fetchall()

    usuario_nombre = nota['creador_nombre'].upper() if nota.get('creador_nombre') else "USUARIO NO IDENTIFICADO"
    primera_renta = rentas_info[renta_ids[0]]
    sucursal_id = primera_renta['id_sucursal']

    cursor.close()
    conn.close()

    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    try:
        font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Carlito', font_path))
    except Exception:
        pass

    page_width, page_height = letter

    def nueva_pagina_continuacion():
        can.showPage()
        can.setFont("Carlito", 10)
        return page_height - 60

    # === ENCABEZADO ÚNICO ===
    can.setFont("Courier-Bold", 20)
    can.drawRightString(575, 690, f"#{str(nota['folio']).zfill(5)}")

    can.setFont("Carlito", 12)
    fecha_entrada = nota['fecha_entrada_real'].strftime('%d/%m/%Y - %H:%M:%S')
    can.drawRightString(575, 715, fecha_entrada)

    can.setFont("Courier-Bold", 23)
    can.drawString(390, 732, "ENTRADA MÚLTIPLE")

    can.setFont("Courier-Bold", 15)
    can.drawString(36, 715, "RENTA DE EQUIPO")

    can.setFont("Carlito", 10)
    cliente_completo = f"{primera_renta['codigo_cliente']} - {primera_renta['cliente_nombre'].upper()}"
    can.drawString(36, 695, f"CLIENTE: {cliente_completo}")
    can.drawString(36, 680, f"TELÉFONO: {primera_renta['telefono'] or 'NO REGISTRADO'}")

    direccion_completa = primera_renta['calle'] or ''
    if primera_renta['numero_exterior']:
        direccion_completa += f" #{primera_renta['numero_exterior']}"
    if primera_renta['numero_interior']:
        direccion_completa += f", INT. {primera_renta['numero_interior']}"
    if primera_renta['entre_calles']:
        direccion_completa += f" (ENTRE {primera_renta['entre_calles']})"
    if primera_renta['colonia']:
        direccion_completa += f", COL. {primera_renta['colonia']}"
    if primera_renta['codigo_postal']:
        direccion_completa += f" - C.P. {primera_renta['codigo_postal']}"

    direccion_lines = simpleSplit(f"DIRECCIÓN: {direccion_completa.upper()}", "Carlito", 10, 530)
    y_position = 665
    for line in direccion_lines:
        can.drawString(36, y_position, line)
        y_position -= 12

    if nota.get('chofer_recoleccion_nombre'):
        can.drawString(36, y_position, f"RECOLECCIÓN: {nota['chofer_recoleccion_nombre'].upper()}")
        y_position -= 12
    elif (nota.get('requiere_traslado_extra') or 'ninguno') != 'ninguno':
        costo_extra = float(nota.get('costo_traslado_extra') or 0)
        chofer_extra = nota['chofer_traslado_extra_nombre'].upper() if nota.get('chofer_traslado_extra_nombre') else 'NO ASIGNADO'
        can.drawString(36, y_position, f"TRASLADO EXTRA ({nota['requiere_traslado_extra'].upper()}): ${costo_extra:.2f} - CHOFER: {chofer_extra}")
        y_position -= 12

    y_position -= 15
    can.setFont("Carlito", 10)
    can.drawString(36, y_position, "RECIBÍ DE: ______________________________")
    y_position -= 15
    can.drawString(36, y_position, f"EL SIGUIENTE EQUIPO, CONSOLIDADO DE {len(renta_ids)} RENTAS:")
    y_position -= 20

    # === UNA SECCIÓN POR RENTA ===
    for renta_id in renta_ids:
        renta = rentas_info[renta_id]
        piezas = piezas_por_renta[renta_id]

        hay_piezas_problematicas = any(
            (p['cantidad_danada'] or 0) > 0 or (p['cantidad_sucia'] or 0) > 0 or (p['cantidad_perdida'] or 0) > 0
            for p in piezas
        )

        if y_position < 150:
            y_position = nueva_pagina_continuacion()

        folio_salida_texto = str(renta.get('folio_salida')).zfill(5) if renta.get('folio_salida') is not None else '-----'
        can.setFont("Helvetica-Bold", 11)
        can.drawString(36, y_position, f"RENTA SUC{renta['id_sucursal']}-{str(renta['folio']).zfill(4)}  (FOLIO SALIDA #{folio_salida_texto})")
        y_position -= 14

        can.setFont("Carlito", 9)
        obra_lines = simpleSplit(f"OBRA: {(renta['direccion_obra'] or '').upper()}", "Carlito", 9, 530)
        for line in obra_lines:
            can.drawString(36, y_position, line)
            y_position -= 11
        y_position -= 4

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

        def mostrar_vacio_si_cero(val):
            return "" if not val else str(val)

        for pieza in piezas:
            if y_position < 100:
                y_position = nueva_pagina_continuacion()

            can.drawString(70, y_position + 5, str(pieza['cantidad_esperada']))
            can.drawString(150, y_position + 5, pieza['nombre_pieza'].upper())
            can.drawString(355, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_recibida']))
            if hay_piezas_problematicas:
                can.drawString(435, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_buena']))
                can.drawString(485, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_danada']))
                can.drawString(535, y_position + 5, mostrar_vacio_si_cero(pieza['cantidad_perdida']))
            y_position -= 13

        y_position -= 18

    # === TÉRMINOS Y FIRMAS (una sola vez, al final) ===
    if y_position < 140:
        y_position = nueva_pagina_continuacion()

    can.setFont("Carlito", 9)
    terminos_lines = simpleSplit(
        "IMPORTANTE: CUALQUIER DAÑO, PÉRDIDA O EQUIPO SUCIO SERÁ FACTURADO SEGÚN TARIFAS VIGENTES.",
        "Carlito", 9, 520
    )
    for line in terminos_lines:
        if y_position < 100:
            y_position = nueva_pagina_continuacion()
        can.drawString(36, y_position, line)
        y_position -= 12

    y_position -= 40
    if y_position < 80:
        y_position = nueva_pagina_continuacion()

    can.setFont("Carlito", 10)
    can.line(60, y_position, 250, y_position)
    can.line(350, y_position, 540, y_position)
    y_position -= 15
    can.drawString(60, y_position, "RECIBE: ANDAMIOS COLOSIO")
    can.drawString(350, y_position, "ENTREGA: _______________________")
    y_position -= 10
    can.drawString(60, y_position, f"NOMBRE: {usuario_nombre}")
    y_position -= 15

    if nota['observaciones']:
        y_position -= 20
        can.setFont("Carlito", 13)
        obs_lines = simpleSplit(f"OBSERVACIONES: {nota['observaciones'].upper()}", "Carlito", 13, 550)
        for line in obs_lines:
            if y_position < 50:
                y_position = nueva_pagina_continuacion()
            can.drawString(36, y_position, line)
            y_position -= 18

    can.save()
    packet.seek(0)

    try:
        plantilla_path = None
        if primera_renta.get('plantilla_renta'):
            plantilla_path = os.path.join(current_app.root_path, primera_renta['plantilla_renta'])
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
            for i in range(1, len(overlay_pdf.pages)):
                output.add_page(overlay_pdf.pages[i])
        else:
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
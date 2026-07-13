
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from utils.db import get_db_connection
from utils.datetime_utils import get_local_now, format_datetime_local
from utils.decorators import requiere_sesion, requiere_permiso, requiere_uno_de_permisos
from utils.folios import obtener_siguiente_folio_nota_sucursal

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit

from io import BytesIO
from flask import send_file
from PyPDF2 import PdfReader, PdfWriter
import os

bp_inventario = Blueprint('inventario', __name__, url_prefix='/inventario')

# NOTA: La función obtener_siguiente_folio_nota_sucursal ahora está en utils/folios.py
# para evitar importaciones circulares entre módulos. Los otros blueprints la importan desde allí.


@bp_inventario.route('/general')
@requiere_sesion()
@requiere_permiso('ver_inventario_general')
def inventario_general():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM sucursales")
    sucursales = cursor.fetchall()
    cursor.execute("""
        SELECT p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion,
               SUM(i.total) AS total_empresa
        FROM piezas p
        LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza
        GROUP BY p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion
    """)
    piezas = cursor.fetchall()
    for pieza in piezas:
        pieza['sucursales'] = {}
        for suc in sucursales:
            cursor.execute("""
                SELECT total, disponibles, rentadas, daniadas, en_reparacion
                FROM inventario_sucursal
                WHERE id_pieza=%s AND id_sucursal=%s
            """, (pieza['id_pieza'], suc['id']))
            datos = cursor.fetchone() or {'total': 0, 'disponibles': 0, 'rentadas': 0, 'daniadas': 0, 'en_reparacion': 0}
            pieza['sucursales'][suc['id']] = datos
    cursor.close()
    conn.close()
    return render_template('inventario/inventario_general.html', piezas=piezas, sucursales=sucursales)



@bp_inventario.route('/agregar_pieza_general', methods=['POST'])
@requiere_sesion()
@requiere_permiso('agregar_pieza_inventario_general')
def agregar_pieza_general():
    nombre_pieza = request.form['nombre_pieza']
    codigo_pieza = request.form['codigo_pieza']
    categoria = request.form.get('categoria', '')
    descripcion = request.form.get('descripcion', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_pieza FROM piezas WHERE codigo_pieza=%s", (codigo_pieza,))
    existe = cursor.fetchone()
    if existe:
        # Trae los datos para la tabla
        cursor.execute("SELECT id, nombre FROM sucursales")
        sucursales = cursor.fetchall()
        cursor.execute("""
            SELECT p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion,
                   SUM(i.total) AS total_empresa
            FROM piezas p
            LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza
            GROUP BY p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion
        """)
        piezas = cursor.fetchall()
        for pieza in piezas:
            pieza['sucursales'] = {}
            for suc in sucursales:
                cursor.execute("""
                    SELECT total, disponibles, rentadas, daniadas, en_reparacion
                    FROM inventario_sucursal
                    WHERE id_pieza=%s AND id_sucursal=%s
                """, (pieza['id_pieza'], suc['id']))
                datos = cursor.fetchone() or {'total': 0, 'disponibles': 0, 'rentadas': 0, 'daniadas': 0, 'en_reparacion': 0}
                pieza['sucursales'][suc['id']] = datos
        cursor.close()
        conn.close()
        # Renderiza la vista con el modal abierto y los datos previos
        return render_template(
            'inventario/inventario_general.html',
            piezas=piezas,
            sucursales=sucursales,
            show_modal_nueva_pieza=True,
            error_codigo='El código ingresado ya existe. Por favor ingresa uno diferente.',
            form_data={
                'nombre_pieza': nombre_pieza,
                'codigo_pieza': codigo_pieza,
                'categoria': categoria,
                'descripcion': descripcion
            }
        )
    # Si no existe, inserta normalmente
    cursor.execute(
        "INSERT INTO piezas (codigo_pieza, nombre_pieza, categoria, descripcion) VALUES (%s, %s, %s, %s)",
        (codigo_pieza, nombre_pieza, categoria, descripcion)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_general'))



@bp_inventario.route('/editar_pieza/<int:id_pieza>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('modificar_existencias_inventario_general')
def editar_pieza(id_pieza):
    nombre_pieza = request.form['nombre_pieza']
    codigo_pieza = request.form['codigo_pieza']
    categoria = request.form.get('categoria', '')
    descripcion = request.form.get('descripcion', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Verifica si ya existe el código en otra pieza
    cursor.execute("SELECT id_pieza FROM piezas WHERE codigo_pieza=%s AND id_pieza!=%s", (codigo_pieza, id_pieza))
    existe = cursor.fetchone()
    if existe:
        # Trae los datos para la tabla
        cursor.execute("SELECT id, nombre FROM sucursales")
        sucursales = cursor.fetchall()
        cursor.execute("""
            SELECT p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion,
                   SUM(i.total) AS total_empresa
            FROM piezas p
            LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza
            GROUP BY p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion
        """)
        piezas = cursor.fetchall()
        for pieza in piezas:
            pieza['sucursales'] = {}
            for suc in sucursales:
                cursor.execute("""
                    SELECT total, disponibles, rentadas, daniadas, en_reparacion
                    FROM inventario_sucursal
                    WHERE id_pieza=%s AND id_sucursal=%s
                """, (pieza['id_pieza'], suc['id']))
                datos = cursor.fetchone() or {'total': 0, 'disponibles': 0, 'rentadas': 0, 'daniadas': 0, 'en_reparacion': 0}
                pieza['sucursales'][suc['id']] = datos
        cursor.close()
        conn.close()
        # Renderiza la vista con el modal de editar abierto y los datos previos
        return render_template(
            'inventario/inventario_general.html',
            piezas=piezas,
            sucursales=sucursales,
            show_modal_editar_pieza=id_pieza,
            error_codigo_editar='El código ingresado ya existe en otra pieza. Por favor ingresa uno diferente.',
            form_data_editar={
                'nombre_pieza': nombre_pieza,
                'codigo_pieza': codigo_pieza,
                'categoria': categoria,
                'descripcion': descripcion
            }
        )
    # Si no existe, actualiza normalmente
    cursor.execute(
        "UPDATE piezas SET codigo_pieza=%s, nombre_pieza=%s, categoria=%s, descripcion=%s WHERE id_pieza=%s",
        (codigo_pieza, nombre_pieza, categoria, descripcion, id_pieza)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario_general'))


##################################################
##################################################
##################################################

# Endpoint para obtener piezas y cantidades disponibles de una sucursal 
@bp_inventario.route('/piezas-sucursal/<int:sucursal_id>')
@requiere_sesion()
@requiere_permiso('ver_inventario_general')
def piezas_sucursal(sucursal_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.id_pieza, p.codigo_pieza, p.nombre_pieza, p.categoria, p.descripcion,
               IFNULL(i.total, 0) AS total,
               IFNULL(i.disponibles, 0) AS disponibles,
               IFNULL(i.rentadas, 0) AS rentadas,
               IFNULL(i.daniadas, 0) AS daniadas,
               IFNULL(i.en_reparacion, 0) AS en_reparacion
        FROM piezas p
        LEFT JOIN inventario_sucursal i ON p.id_pieza = i.id_pieza AND i.id_sucursal = %s
        ORDER BY p.nombre_pieza
    """, (sucursal_id,))
    piezas = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'piezas': piezas})


# Endpoint para obtener todas las piezas activas 
@bp_inventario.route('/todas-piezas-activas')
@requiere_sesion()
@requiere_permiso('ver_inventario_general')
def todas_piezas_activas():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_pieza, codigo_pieza, nombre_pieza, categoria, descripcion
        FROM piezas
        WHERE estatus = 'activo'
        ORDER BY nombre_pieza
    """)
    piezas = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'piezas': piezas})




@bp_inventario.route('/sucursal/<int:sucursal_id>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def inventario_sucursal(sucursal_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Obtener sucursal
    cursor.execute("SELECT id as id_sucursal, nombre FROM sucursales WHERE id = %s", (sucursal_id,))
    sucursal = cursor.fetchone()
    
    if not sucursal:
        flash('Sucursal no encontrada', 'error')
        return redirect(url_for('inventario.inventario_general'))
    
    # Crear sucursal_actual (ESTO ES LO QUE TE FALTA)
    sucursal_actual = {
        'id': sucursal['id_sucursal'],
        'nombre': sucursal['nombre']
    }

    # Obtener rol para saber si es admin
    sucursal_id_usuario = session.get('sucursal_id')
    es_admin = (sucursal_id_usuario is None)

    # Obtener todas las sucursales para los botones de navegación
    cursor.execute("SELECT id, nombre FROM sucursales ORDER BY id")
    sucursales = cursor.fetchall()

    # Obtener piezas
    cursor.execute("""
        SELECT p.id_pieza, p.nombre_pieza, p.categoria, 
               IFNULL(i.total, 0) AS total, 
               IFNULL(i.disponibles, 0) AS disponibles, 
               IFNULL(i.rentadas, 0) AS rentadas, 
               IFNULL(i.daniadas, 0) AS daniadas, 
               IFNULL(i.en_reparacion, 0) AS en_reparacion, 
               IFNULL(i.stock_minimo, 0) AS stock_minimo
        FROM piezas p
        LEFT JOIN inventario_sucursal i 
            ON p.id_pieza = i.id_pieza AND i.id_sucursal = %s
        ORDER BY p.nombre_pieza
    """, (sucursal_id,))
    
    piezas = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return render_template(
        'inventario/inventario_sucursal.html',
        piezas=piezas,
        sucursal=sucursal,               # 👈 lo sigues usando en modales
        sucursal_actual=sucursal_actual, # 👈 lo usa el header + tabs
        sucursales=sucursales,           # 👈 nueva: todas las sucursales para navegación
        es_admin=es_admin
    )







@bp_inventario.route('/enviar-equipos', methods=['POST'])
@requiere_sesion()
@requiere_permiso('transferir_piezas_inventario')
def enviar_equipos():
    """
    Maneja el ENVÍO de equipos - Solo genera nota de salida y resta inventario origen
    """
    try:
        data = request.get_json()
        sucursal_origen_id = data.get('sucursal_origen_id')
        sucursal_destino_id = data.get('sucursal_destino_id')
        piezas = data.get('piezas', [])
        observaciones = data.get('observaciones', '')

        if not sucursal_origen_id or not sucursal_destino_id:
            return jsonify({'success': False, 'error': 'Faltan sucursales origen o destino'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 1. Generar folio de SALIDA según sucursal origen
            folio_salida_num = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_origen_id)
            folio_salida = str(folio_salida_num).zfill(5)

            # 2. Obtener nombres de sucursales
            cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_origen_id,))
            nombre_origen = cursor.fetchone()['nombre']
            cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_destino_id,))
            nombre_destino = cursor.fetchone()['nombre']

            # 3. Procesar cada pieza (SIN crear nota de salida)
            piezas_enviadas = 0
            usuario_id = session.get('user_id', 1)

            for pieza in piezas:
                id_pieza = pieza.get('id_pieza')
                cantidad = pieza.get('cantidad', 0)

                if cantidad <= 0:
                    continue

                # Verificar disponibilidad en origen
                cursor.execute("""
                    SELECT disponibles FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, sucursal_origen_id))
                
                row = cursor.fetchone()
                if not row or row['disponibles'] < cantidad:
                    continue

                # SOLO actualizar inventario origen (RESTA)
                cursor.execute("""
                    UPDATE inventario_sucursal 
                    SET disponibles = disponibles - %s, total = total - %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (cantidad, cantidad, sucursal_origen_id, id_pieza))

                # Registrar movimiento de SALIDA
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        id_sucursal, id_pieza, tipo_movimiento, cantidad, fecha,
                        usuario, sucursal_destino, observaciones, descripcion,
                        folio_nota_salida
                    ) VALUES (%s, %s, 'transferencia_salida', %s, %s,
                             %s, %s, %s, %s, %s)
                """, (sucursal_origen_id, id_pieza, cantidad, get_local_now(), 
                      usuario_id, sucursal_destino_id, observaciones,
                      f'Envío a {nombre_destino}', folio_salida))

                piezas_enviadas += 1

            conn.commit()

            if piezas_enviadas > 0:
                return jsonify({
                    'success': True,
                    'message': f'Equipos enviados correctamente a {nombre_destino}',
                    'folio_nota_salida': folio_salida,
                    'piezas_enviadas': piezas_enviadas
                })
            else:
                return jsonify({'success': False, 'error': 'No se pudo enviar ninguna pieza'})

        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})


@bp_inventario.route('/recibir-equipos', methods=['POST'])
@requiere_sesion()
@requiere_permiso('transferir_piezas_inventario')
def recibir_equipos():
    """
    Maneja la RECEPCIÓN de equipos - Solo genera nota de entrada y suma inventario destino
    """
    try:
        data = request.get_json()
        sucursal_origen_id = data.get('sucursal_origen_id')
        sucursal_destino_id = data.get('sucursal_destino_id')
        piezas = data.get('piezas', [])
        observaciones = data.get('observaciones', '')

        if not sucursal_origen_id or not sucursal_destino_id:
            return jsonify({'success': False, 'error': 'Faltan sucursales origen o destino'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 1. Generar folio de ENTRADA según sucursal destino
            folio_entrada_num = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_destino_id)
            folio_entrada = str(folio_entrada_num).zfill(5)

            # 2. Obtener nombres de sucursales
            cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_origen_id,))
            nombre_origen = cursor.fetchone()['nombre']
            cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_destino_id,))
            nombre_destino = cursor.fetchone()['nombre']

            # 3. Procesar cada pieza (SIN crear nota de entrada)
            piezas_recibidas = 0
            usuario_id = session.get('user_id', 1)

            for pieza in piezas:
                id_pieza = pieza.get('id_pieza')
                cantidad = pieza.get('cantidad', 0)

                if cantidad <= 0:
                    continue

                # SOLO actualizar inventario destino (SUMA)
                cursor.execute("""
                    INSERT INTO inventario_sucursal (id_sucursal, id_pieza, disponibles, total)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    disponibles = disponibles + VALUES(disponibles),
                    total = total + VALUES(total)
                """, (sucursal_destino_id, id_pieza, cantidad, cantidad))

                # Registrar movimiento de ENTRADA
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        id_sucursal, id_pieza, tipo_movimiento, cantidad, fecha,
                        usuario, sucursal_destino, observaciones, descripcion,
                        folio_nota_entrada
                    ) VALUES (%s, %s, 'transferencia_entrada', %s, %s,
                             %s, %s, %s, %s, %s)
                """, (sucursal_destino_id, id_pieza, cantidad, get_local_now(), 
                      usuario_id, sucursal_origen_id, observaciones,  # CORREGIDO: guardamos origen en sucursal_destino
                      f'Recepción de {nombre_origen}', folio_entrada))

                piezas_recibidas += 1

            conn.commit()

            if piezas_recibidas > 0:
                return jsonify({
                    'success': True,
                    'message': f'Equipos recibidos correctamente de {nombre_origen}',
                    'folio_nota_entrada': folio_entrada,
                    'piezas_recibidas': piezas_recibidas
                })
            else:
                return jsonify({'success': False, 'error': 'No se pudo recibir ninguna pieza'})

        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})






@bp_inventario.route('/transferir-piezas-multiple', methods=['POST'])
@requiere_sesion()
@requiere_permiso('transferir_piezas_inventario')
def transferir_piezas_multiple():
    try:
        data = request.get_json()
        sucursal_origen_id = data.get('sucursal_origen_id')
        sucursal_destino_id = data.get('sucursal_destino_id')
        piezas = data.get('piezas', [])
        observaciones = data.get('observaciones', '')

        if not sucursal_origen_id or not sucursal_destino_id:
            return jsonify({'success': False, 'error': 'Faltan sucursales origen o destino'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 1. Generar folios consecutivos por sucursal
            # Folio de SALIDA según sucursal origen
            folio_salida_num = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_origen_id)
            folio_salida = str(folio_salida_num).zfill(5)
            
            # Folio de ENTRADA según sucursal destino
            folio_entrada_num = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_destino_id)
            folio_entrada = str(folio_entrada_num).zfill(5)

            # 2. Obtener nombres de sucursales para las observaciones
            cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_origen_id,))
            nombre_origen = cursor.fetchone()['nombre']
            cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_destino_id,))
            nombre_destino = cursor.fetchone()['nombre']

            # 3. Crear nota de SALIDA (renta_id = NULL para transferencias)
            cursor.execute("""
                INSERT INTO notas_salida (
                    folio, renta_id, fecha, numero_referencia, observaciones
                ) VALUES (%s, NULL, %s, %s, %s)
            """, (folio_salida, get_local_now(), f'TRANSFERENCIA-{folio_salida}', 
                  f'Transferencia de {nombre_origen} a {nombre_destino}. {observaciones}'))
            nota_salida_id = cursor.lastrowid

            # 4. Crear nota de ENTRADA (renta_id = NULL para transferencias)
            cursor.execute("""
                INSERT INTO notas_entrada (
                    folio, renta_id, nota_salida_id, fecha_entrada_real,
                    requiere_traslado_extra, costo_traslado_extra, observaciones,
                    estado, created_at, estado_retraso, accion_devolucion
                ) VALUES (%s, NULL, %s, %s, 'ninguno', 0, %s, 'normal', %s, 'Sin Retraso', 'no')
            """, (folio_entrada, nota_salida_id, get_local_now(),
                  f'Transferencia de {nombre_origen} a {nombre_destino}. {observaciones}',
                  get_local_now()))
            nota_entrada_id = cursor.lastrowid

            # 5. Procesar cada pieza
            transferencias_exitosas = 0
            usuario_id = session.get('user_id', 1)

            for pieza in piezas:
                id_pieza = pieza.get('id_pieza')
                cantidad = pieza.get('cantidad', 0)

                if cantidad <= 0:
                    continue

                # Verificar disponibilidad en origen
                cursor.execute("""
                    SELECT disponibles FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, sucursal_origen_id))
                
                row = cursor.fetchone()
                if not row or row['disponibles'] < cantidad:
                    continue  # Saltar si no hay suficiente stock

                # Crear detalles de las notas
                cursor.execute("""
                    INSERT INTO notas_salida_detalle (nota_salida_id, id_pieza, cantidad)
                    VALUES (%s, %s, %s)
                """, (nota_salida_id, id_pieza, cantidad))

                cursor.execute("""
                    INSERT INTO notas_entrada_detalle (
                        nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                        cantidad_buena, cantidad_danada, cantidad_sucia, cantidad_perdida
                    ) VALUES (%s, %s, %s, %s, %s, 0, 0, 0)
                """, (nota_entrada_id, id_pieza, cantidad, cantidad, cantidad))

                # Actualizar inventario origen (RESTA)
                cursor.execute("""
                    UPDATE inventario_sucursal 
                    SET disponibles = disponibles - %s, total = total - %s
                    WHERE id_sucursal = %s AND id_pieza = %s
                """, (cantidad, cantidad, sucursal_origen_id, id_pieza))

                # Actualizar/crear inventario destino (SUMA)
                cursor.execute("""
                    INSERT INTO inventario_sucursal (id_sucursal, id_pieza, disponibles, total)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    disponibles = disponibles + VALUES(disponibles),
                    total = total + VALUES(total)
                """, (sucursal_destino_id, id_pieza, cantidad, cantidad))

                # Registrar movimientos con folios
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        id_sucursal, id_pieza, tipo_movimiento, cantidad, fecha,
                        usuario, sucursal_destino, observaciones, descripcion,
                        folio_nota_salida, folio_nota_entrada
                    ) VALUES (%s, %s, 'transferencia_salida', %s, %s,
                             %s, %s, %s, %s, %s, %s)
                """, (sucursal_origen_id, id_pieza, cantidad, get_local_now(), 
                      usuario_id, sucursal_destino_id, observaciones,
                      f'Transferencia a {nombre_destino}',
                      folio_salida, folio_entrada))

                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        id_sucursal, id_pieza, tipo_movimiento, cantidad, fecha,
                        usuario, sucursal_destino, observaciones, descripcion,
                        folio_nota_salida, folio_nota_entrada
                    ) VALUES (%s, %s, 'transferencia_entrada', %s, %s,
                             %s, %s, %s, %s, %s, %s)
                """, (sucursal_destino_id, id_pieza, cantidad, get_local_now(),
                      usuario_id, sucursal_origen_id, observaciones,
                      f'Transferencia desde {nombre_origen}',
                      folio_salida, folio_entrada))

                transferencias_exitosas += 1

            conn.commit()

            if transferencias_exitosas > 0:
                return jsonify({
                    'success': True,
                    'message': f'Transferencia completada exitosamente. {transferencias_exitosas} tipos de piezas transferidas.',
                    'folio_nota_salida': folio_salida,
                    'folio_nota_entrada': folio_entrada,
                    'nota_salida_id': nota_salida_id,
                    'nota_entrada_id': nota_entrada_id,
                    'transferencias_exitosas': transferencias_exitosas
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No se pudo realizar ninguna transferencia. Verifica el stock disponible.'
                })

        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})




########################################################################
#######################################################################
########################################################################
#################################### BAJA DE EQUIPO DEL INVENTARIO GENERAL

@bp_inventario.route('/baja-equipo-nuevo', methods=['POST'])
@requiere_sesion()
@requiere_permiso('modificar_existencias_inventario_general')
def baja_equipo_nuevo():
    try:
        data = request.get_json()
        id_sucursal = data.get('id_sucursal')
        piezas = data.get('piezas', [])
        observaciones = data.get('observaciones', '')
        usuario_id = session.get('user_id')

        if not id_sucursal or not piezas:
            return jsonify({'success': False, 'error': 'Datos incompletos'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Obtener folio consecutivo para nota de salida
            folio_num = obtener_siguiente_folio_nota_sucursal(cursor, id_sucursal)
            folio = str(folio_num).zfill(5)
            
            # Procesar cada pieza
            for pieza_data in piezas:
                id_pieza = pieza_data['id_pieza']
                cantidad = pieza_data['cantidad']
                
                # Verificar inventario disponible
                cursor.execute("""
                    SELECT disponibles FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, id_sucursal))
                
                inventario = cursor.fetchone()
                if not inventario or inventario['disponibles'] < cantidad:
                    cursor.execute("SELECT nombre_pieza FROM piezas WHERE id_pieza = %s", (id_pieza,))
                    pieza_info = cursor.fetchone()
                    nombre_pieza = pieza_info['nombre_pieza'] if pieza_info else 'Desconocida'
                    return jsonify({
                        'success': False, 
                        'error': f'No hay suficiente inventario disponible de {nombre_pieza}. Disponibles: {inventario["disponibles"] if inventario else 0}'
                    })
                
                # Actualizar inventario (restar cantidad)
                cursor.execute("""
                    UPDATE inventario_sucursal 
                    SET total = total - %s, disponibles = disponibles - %s
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (cantidad, cantidad, id_pieza, id_sucursal))
                
                # Registrar movimiento de baja
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario, folio_nota_salida, fecha)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_pieza, 
                    id_sucursal, 
                    'baja_equipo_general',
                    cantidad,
                    f'Baja de equipo - {observaciones}',
                    usuario_id,
                    folio,
                    get_local_now()
                ))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Equipos dados de baja exitosamente',
                'folio_nota_salida': folio
            })
            
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})


@bp_inventario.route('/alta-equipo', methods=['POST'])
@requiere_sesion()
@requiere_uno_de_permisos('modificar_existencias_inventario_general', 'agregar_piezas_inventario_sucursal')
def alta_equipo_nuevo():

    try:
        data = request.get_json()
        id_sucursal = data.get('id_sucursal')
        piezas = data.get('piezas', [])
        observaciones = data.get('observaciones', '')
        tipo_origen = data.get('tipo_origen', 'inventario_sucursal')
        usuario_id = session.get('user_id')

        if not id_sucursal or not piezas:
            return jsonify({'success': False, 'error': 'Datos incompletos'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Obtener el siguiente folio para la sucursal
            folio_num = obtener_siguiente_folio_nota_sucursal(cursor, id_sucursal)
            folio = str(folio_num).zfill(5)
            
            # Determinar tipo de movimiento según el origen
            tipo_movimiento = 'alta_equipo_general' if tipo_origen == 'inventario_general' else 'alta_equipo'

            # Procesar cada pieza
            for pieza_data in piezas:
                id_pieza = pieza_data.get('id_pieza')
                cantidad = int(pieza_data.get('cantidad', 0))
                
                if cantidad <= 0:
                    continue
                
                # Verificar si ya existe registro de inventario para esta pieza y sucursal
                cursor.execute("""
                    SELECT total, disponibles FROM inventario_sucursal 
                    WHERE id_pieza=%s AND id_sucursal=%s
                """, (id_pieza, id_sucursal))
                row = cursor.fetchone()
                
                if row:
                    # Actualizar inventario existente
                    cursor.execute("""
                        UPDATE inventario_sucursal 
                        SET total = total + %s, disponibles = disponibles + %s
                        WHERE id_pieza = %s AND id_sucursal = %s
                    """, (cantidad, cantidad, id_pieza, id_sucursal))
                else:
                    # Crear nuevo registro de inventario
                    cursor.execute("""
                        INSERT INTO inventario_sucursal (id_pieza, id_sucursal, total, disponibles, rentadas, daniadas, en_reparacion)
                        VALUES (%s, %s, %s, %s, 0, 0, 0)
                    """, (id_pieza, id_sucursal, cantidad, cantidad))
                
                # Registrar movimiento en el historial
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        id_pieza, id_sucursal, tipo_movimiento, cantidad, 
                        descripcion, usuario, folio_nota_entrada
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_pieza, id_sucursal, tipo_movimiento, cantidad,
                    f'Alta de equipo. {observaciones}', usuario_id, str(folio)
                ))

            conn.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Alta de {len(piezas)} tipo(s) de equipo realizada exitosamente',
                'folio_nota_entrada': str(folio),
                'total_piezas': sum(pieza['cantidad'] for pieza in piezas),
                'tipo_origen': tipo_origen
            })
            
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': f'Error en la base de datos: {str(e)}'})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})


@bp_inventario.route('/marcar-daniadas', methods=['POST'])
@requiere_sesion()
@requiere_permiso('modificar_existencias_inventario_general')
def marcar_piezas_daniadas():
    """
    Marca piezas disponibles como dañadas - Movimiento interno sin generar notas
    """
    try:
        data = request.get_json()
        sucursal_id = data.get('sucursal_id')
        piezas = data.get('piezas', [])
        observaciones = data.get('observaciones', '')
        usuario_id = session.get('user_id')

        if not sucursal_id or not piezas:
            return jsonify({'success': False, 'error': 'Datos incompletos'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            total_piezas_procesadas = 0
            
            # Procesar cada pieza
            for pieza_data in piezas:
                id_pieza = pieza_data.get('id_pieza')
                cantidad = pieza_data.get('cantidad')
                
                if not id_pieza or not cantidad or cantidad <= 0:
                    continue
                
                # Verificar inventario disponible actual
                cursor.execute("""
                    SELECT disponibles, daniadas, total 
                    FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, sucursal_id))
                
                inventario = cursor.fetchone()
                if not inventario:
                    return jsonify({
                        'success': False, 
                        'error': f'No existe inventario para la pieza ID {id_pieza} en esta sucursal'
                    })
                
                if inventario['disponibles'] < cantidad:
                    cursor.execute("SELECT nombre_pieza FROM piezas WHERE id_pieza = %s", (id_pieza,))
                    pieza_info = cursor.fetchone()
                    nombre_pieza = pieza_info['nombre_pieza'] if pieza_info else f'ID {id_pieza}'
                    return jsonify({
                        'success': False,
                        'error': f'No hay suficientes piezas disponibles de {nombre_pieza}. Disponibles: {inventario["disponibles"]}, Solicitadas: {cantidad}'
                    })
                
                # Actualizar inventario: restar de disponibles, sumar a dañadas
                nuevos_disponibles = inventario['disponibles'] - cantidad
                nuevas_daniadas = inventario['daniadas'] + cantidad
                
                cursor.execute("""
                    UPDATE inventario_sucursal 
                    SET disponibles = %s, daniadas = %s 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (nuevos_disponibles, nuevas_daniadas, id_pieza, sucursal_id))
                
                # Registrar movimiento en el historial
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id_pieza, 
                    sucursal_id, 
                    'marcar_daniadas',
                    cantidad,
                    f'Marcado como dañada - {observaciones}' if observaciones else 'Marcado como dañada',
                    usuario_id
                ))
                
                total_piezas_procesadas += cantidad
            
            # Confirmar cambios
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Se marcaron como dañadas {total_piezas_procesadas} piezas correctamente'
            })
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error al marcar piezas como dañadas: {str(e)}")
            return jsonify({'success': False, 'error': f'Error al procesar: {str(e)}'})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})


@bp_inventario.route('/reparacion-lote', methods=['POST'])
@requiere_sesion()
@requiere_permiso('mandar_pieza_reparacion')
def enviar_lote_reparacion():
    """
    Maneja el ENVÍO de equipos a reparación por lotes - Genera nota de salida y resta del inventario total
    """
    try:
        data = request.get_json()
        sucursal_id = data.get('sucursal_id')
        piezas = data.get('piezas', [])
        observaciones = data.get('observaciones', '')

        if not sucursal_id or not piezas:
            return jsonify({'success': False, 'error': 'Datos incompletos'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Obtener siguiente folio
            folio_num = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)
            folio = str(folio_num).zfill(5)  # Formato de 5 dígitos
            usuario_id = session.get('user_id')

            # Procesar cada pieza del lote
            for pieza_data in piezas:
                id_pieza = pieza_data['id_pieza']
                cantidad = pieza_data['cantidad']

                # Verificar que hay suficientes piezas dañadas
                cursor.execute("""
                    SELECT daniadas, total FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, sucursal_id))
                
                inventario = cursor.fetchone()
                if not inventario or inventario['daniadas'] < cantidad:
                    raise Exception(f'No hay suficientes piezas dañadas para enviar a reparación (ID: {id_pieza})')

                # Actualizar inventario: mover de dañadas a en_reparacion (mantener total)
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET daniadas = daniadas - %s,
                        en_reparacion = en_reparacion + %s
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (cantidad, cantidad, id_pieza, sucursal_id))

                # Registrar movimiento
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario, folio_nota_salida)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (id_pieza, sucursal_id, 'reparacion_lote', cantidad, 
                     f'Equipo dañado - {observaciones}', usuario_id, folio))

            conn.commit()
            
            return jsonify({
                'success': True, 
                'folio_nota_salida': folio,
                'message': f'Lote enviado a reparación exitosamente. Folio: {folio}'
            })

        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})








@bp_inventario.route('/finalizar-reparaciones', methods=['POST'])
@requiere_sesion()
@requiere_permiso('regresar_pieza_disponible')
def finalizar_reparaciones():
    """
    Limpia el tracking de reparaciones sin afectar el inventario total
    """
    try:
        data = request.get_json()
        sucursal_id = data.get('sucursal_id')
        piezas = data.get('piezas', [])

        if not sucursal_id or not piezas:
            return jsonify({'success': False, 'error': 'Datos incompletos'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Obtener siguiente folio para nota de entrada
            folio_num = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)
            folio = str(folio_num).zfill(5)
            usuario_id = session.get('user_id')

            # Procesar cada pieza
            for pieza_data in piezas:
                id_pieza = pieza_data['id_pieza']
                cantidad = pieza_data['cantidad']

                # Verificar que hay suficientes piezas en reparación
                cursor.execute("""
                    SELECT en_reparacion FROM inventario_sucursal 
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (id_pieza, sucursal_id))
                
                inventario = cursor.fetchone()
                if not inventario or inventario['en_reparacion'] < cantidad:
                    raise Exception(f'No hay suficientes piezas en reparación (ID: {id_pieza})')

                # Mover de en_reparacion a disponibles (las piezas reparadas vuelven)
                cursor.execute("""
                    UPDATE inventario_sucursal
                    SET en_reparacion = en_reparacion - %s,
                        disponibles = disponibles + %s
                    WHERE id_pieza = %s AND id_sucursal = %s
                """, (cantidad, cantidad, id_pieza, sucursal_id))

                # Registrar movimiento con folio de nota de entrada
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (id_pieza, id_sucursal, tipo_movimiento, cantidad, descripcion, usuario, folio_nota_entrada)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (id_pieza, sucursal_id, 'finalizar_reparacion', cantidad, 
                     'Finalización de reparación - equipo disponible', usuario_id, folio))

            conn.commit()
            
            return jsonify({
                'success': True,
                'folio_nota_entrada': folio,
                'pdf_url': f'/inventario/pdf-finalizacion-reparacion/{sucursal_id}/{folio}',
                'message': f'Reparaciones finalizadas exitosamente. Folio: {folio}. Piezas regresadas a disponibles.'
            })

        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error en el procesamiento: {str(e)}'})




# ─────────────────────────────────────────────────────────────
# Historial de movimientos del inventario general (altas/bajas)
# ─────────────────────────────────────────────────────────────
@bp_inventario.route('/api/historial-general')
@requiere_sesion()
@requiere_permiso('ver_inventario_general')
def api_historial_general():
    tipo        = request.args.get('tipo', '')
    sucursal_id = request.args.get('sucursal_id', '')
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin   = request.args.get('fecha_fin', '')
    page        = max(1, int(request.args.get('page', 1)))
    limit       = 20
    offset      = (page - 1) * limit

    if tipo == 'alta':
        tipos = ['alta_equipo_general']
    elif tipo == 'baja':
        tipos = ['baja_equipo_general']
    else:
        tipos = ['alta_equipo_general', 'baja_equipo_general']

    placeholders = ','.join(['%s'] * len(tipos))
    where_parts  = [f"mi.tipo_movimiento IN ({placeholders})"]
    params       = list(tipos)

    if sucursal_id:
        where_parts.append("mi.id_sucursal = %s")
        params.append(sucursal_id)
    if fecha_inicio:
        where_parts.append("DATE(mi.fecha) >= %s")
        params.append(fecha_inicio)
    if fecha_fin:
        where_parts.append("DATE(mi.fecha) <= %s")
        params.append(fecha_fin)

    where_sql = " AND ".join(where_parts)

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Total de lotes distintos
        cursor.execute(f"""
            SELECT COUNT(*) as total FROM (
                SELECT COALESCE(folio_nota_entrada, folio_nota_salida) as folio,
                       id_sucursal, tipo_movimiento
                FROM movimientos_inventario mi
                WHERE {where_sql}
                GROUP BY folio, id_sucursal, tipo_movimiento
            ) sub
        """, params)
        total = cursor.fetchone()['total']

        # Lotes agrupados por folio
        cursor.execute(f"""
            SELECT
                COALESCE(mi.folio_nota_entrada, mi.folio_nota_salida) AS folio,
                mi.id_sucursal,
                s.nombre AS sucursal_nombre,
                mi.tipo_movimiento,
                MIN(mi.fecha) AS fecha,
                u.nombre AS usuario_nombre,
                MAX(mi.descripcion) AS descripcion,
                SUM(mi.cantidad) AS total_piezas,
                COUNT(DISTINCT mi.id_pieza) AS num_tipos
            FROM movimientos_inventario mi
            JOIN sucursales s ON mi.id_sucursal = s.id
            LEFT JOIN usuarios u ON mi.usuario = u.id
            WHERE {where_sql}
            GROUP BY folio, mi.id_sucursal, mi.tipo_movimiento, u.nombre
            ORDER BY MIN(mi.fecha) DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        lotes = cursor.fetchall()

        resultado = []
        for lote in lotes:
            folio    = lote['folio']
            id_suc   = lote['id_sucursal']
            tipo_mov = lote['tipo_movimiento']
            folio_col = 'folio_nota_entrada' if tipo_mov == 'alta_equipo_general' else 'folio_nota_salida'

            cursor.execute(f"""
                SELECT p.nombre_pieza, p.categoria, mi.cantidad
                FROM movimientos_inventario mi
                JOIN piezas p ON mi.id_pieza = p.id_pieza
                WHERE mi.{folio_col} = %s AND mi.id_sucursal = %s AND mi.tipo_movimiento = %s
                ORDER BY p.nombre_pieza
            """, (folio, id_suc, tipo_mov))
            piezas_detalle = cursor.fetchall()

            pdf_url = (f'/inventario/pdf-alta-equipo/{id_suc}/{folio}'
                       if tipo_mov == 'alta_equipo_general'
                       else f'/inventario/pdf-baja-equipo/{folio}')

            fecha_str = lote['fecha'].strftime('%d/%m/%Y %H:%M') if lote['fecha'] else ''
            resultado.append({
                'folio':           folio,
                'id_sucursal':     id_suc,
                'sucursal_nombre': lote['sucursal_nombre'],
                'tipo_movimiento': tipo_mov,
                'tipo_label':      'Alta' if tipo_mov == 'alta_equipo_general' else 'Baja',
                'fecha':           fecha_str,
                'usuario_nombre':  lote['usuario_nombre'] or 'Sistema',
                'descripcion':     lote['descripcion'] or '',
                'total_piezas':    int(lote['total_piezas']),
                'num_tipos':       int(lote['num_tipos']),
                'piezas':          piezas_detalle,
                'pdf_url':         pdf_url,
            })

        return jsonify({'success': True, 'movimientos': resultado,
                        'total': total, 'page': page, 'limit': limit})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()


# Funciones del historial de transferencias
@bp_inventario.route('/historial-transferencias/<int:sucursal_id>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def historial_transferencias_sucursal(sucursal_id):
    """
    Obtiene el historial de transferencias (enviadas y recibidas) de una sucursal específica
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener transferencias ENVIADAS (salidas) de esta sucursal
        cursor.execute("""
            SELECT 
                'enviada' as tipo_transferencia,
                mi.folio_nota_salida as folio,
                DATE(mi.fecha) as fecha,
                mi.observaciones,
                mi.descripcion,
                sd.nombre as sucursal_destino,
                NULL as sucursal_origen,
                COUNT(DISTINCT mi.id_pieza) as total_tipos_piezas,
                SUM(mi.cantidad) as total_cantidad
            FROM movimientos_inventario mi
            LEFT JOIN sucursales sd ON mi.sucursal_destino = sd.id
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento = 'transferencia_salida'
            AND mi.folio_nota_salida IS NOT NULL
            GROUP BY mi.folio_nota_salida, DATE(mi.fecha), mi.observaciones, mi.descripcion, sd.nombre
            
            UNION ALL
            
            SELECT 
                'recibida' as tipo_transferencia,
                mi.folio_nota_entrada as folio,
                DATE(mi.fecha) as fecha,
                mi.observaciones,
                mi.descripcion,
                NULL as sucursal_destino,
                so.nombre as sucursal_origen,
                COUNT(DISTINCT mi.id_pieza) as total_tipos_piezas,
                SUM(mi.cantidad) as total_cantidad
            FROM movimientos_inventario mi
            LEFT JOIN sucursales so ON mi.sucursal_destino = so.id
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento = 'transferencia_entrada'
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, DATE(mi.fecha), mi.observaciones, mi.descripcion, so.nombre
            
            UNION ALL
            
            SELECT 
                'alta_equipo' as tipo_transferencia,
                mi.folio_nota_entrada as folio,
                DATE(mi.fecha) as fecha,
                mi.observaciones,
                mi.descripcion,
                NULL as sucursal_destino,
                NULL as sucursal_origen,
                COUNT(DISTINCT mi.id_pieza) as total_tipos_piezas,
                SUM(mi.cantidad) as total_cantidad
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento IN ('alta_equipo_nuevo', 'alta_equipo_general', 'alta_admin_nuevo', 'alta_equipo')
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, DATE(mi.fecha), mi.observaciones, mi.descripcion
            
            ORDER BY 
                CASE 
                    WHEN folio REGEXP '^[0-9]+$' THEN CAST(folio AS UNSIGNED)
                    ELSE 0
                END DESC,
                folio DESC
        """, (sucursal_id, sucursal_id, sucursal_id))
        
        transferencias = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'transferencias': transferencias
        })
        
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'success': False, 'error': str(e)})


@bp_inventario.route('/historial-transferencias-page/<int:sucursal_id>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def historial_transferencias_page(sucursal_id):
    """
    Página HTML dedicada para mostrar el historial de transferencias de una sucursal
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener información de la sucursal
        cursor.execute("SELECT id as id_sucursal, nombre FROM sucursales WHERE id = %s", (sucursal_id,))
        sucursal = cursor.fetchone()
        
        if not sucursal:
            flash('Sucursal no encontrada', 'error')
            return redirect(url_for('inventario.inventario_general'))
        
        # Obtener TODOS los movimientos de inventario de la sucursal
        cursor.execute("""
            SELECT 
                'Enviado' as tipo,
                mi.folio_nota_salida as folio,
                DATE_FORMAT(MIN(mi.fecha), '%d/%m/%Y %H:%i') as fecha,
                mi.observaciones,
                mi.descripcion,
                sd.nombre as sucursal_destino,
                NULL as sucursal_origen,
                'transferencia_salida' as tipo_movimiento
            FROM movimientos_inventario mi
            LEFT JOIN sucursales sd ON mi.sucursal_destino = sd.id
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento = 'transferencia_salida'
            AND mi.folio_nota_salida IS NOT NULL
            GROUP BY mi.folio_nota_salida, DATE(mi.fecha), mi.observaciones, mi.descripcion, sd.nombre
            
            UNION ALL
            
            SELECT 
                'Recibido' as tipo,
                mi.folio_nota_entrada as folio,
                DATE_FORMAT(MIN(mi.fecha), '%d/%m/%Y %H:%i') as fecha,
                mi.observaciones,
                mi.descripcion,
                NULL as sucursal_destino,
                so.nombre as sucursal_origen,
                'transferencia_entrada' as tipo_movimiento
            FROM movimientos_inventario mi
            LEFT JOIN sucursales so ON mi.sucursal_destino = so.id
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento = 'transferencia_entrada'
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, DATE(mi.fecha), mi.observaciones, mi.descripcion, so.nombre
            
            UNION ALL
            
            SELECT 
                'Alta Equipo' as tipo,
                mi.folio_nota_entrada as folio,
                DATE_FORMAT(MIN(mi.fecha), '%d/%m/%Y %H:%i') as fecha,
                mi.observaciones,
                mi.descripcion,
                NULL as sucursal_destino,
                NULL as sucursal_origen,
                'alta_equipo' as tipo_movimiento
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento IN ('alta_equipo_nuevo', 'alta_equipo_general', 'alta_admin_nuevo', 'alta_equipo')
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, DATE(mi.fecha), mi.observaciones, mi.descripcion
            
            UNION ALL
            
            SELECT 
                'Envío a Reparación' as tipo,
                mi.folio_nota_salida as folio,
                DATE_FORMAT(MIN(mi.fecha), '%d/%m/%Y %H:%i') as fecha,
                mi.observaciones,
                mi.descripcion,
                NULL as sucursal_destino,
                NULL as sucursal_origen,
                'reparacion_lote' as tipo_movimiento
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento = 'reparacion_lote'
            AND mi.folio_nota_salida IS NOT NULL
            GROUP BY mi.folio_nota_salida, DATE(mi.fecha), mi.observaciones, mi.descripcion
            
            UNION ALL
            
            SELECT 
                'Equipos Dañados' as tipo,
                NULL as folio,
                DATE_FORMAT(MIN(mi.fecha), '%d/%m/%Y %H:%i') as fecha,
                mi.observaciones,
                mi.descripcion,
                NULL as sucursal_destino,
                NULL as sucursal_origen,
                'marcar_daniadas' as tipo_movimiento
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento = 'marcar_daniadas'
            GROUP BY DATE(mi.fecha), mi.observaciones, mi.descripcion
            
            UNION ALL
            
            SELECT 
                'Finalizar Reparaciones' as tipo,
                mi.folio_nota_entrada as folio,
                DATE_FORMAT(MIN(mi.fecha), '%d/%m/%Y %H:%i') as fecha,
                mi.observaciones,
                mi.descripcion,
                NULL as sucursal_destino,
                NULL as sucursal_origen,
                'finalizar_reparacion' as tipo_movimiento
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s 
            AND mi.tipo_movimiento = 'finalizar_reparacion'
            AND mi.folio_nota_entrada IS NOT NULL
            GROUP BY mi.folio_nota_entrada, DATE(mi.fecha), mi.observaciones, mi.descripcion
            
            ORDER BY 
                CASE 
                    WHEN folio REGEXP '^[0-9]+$' THEN CAST(folio AS UNSIGNED)
                    ELSE 0
                END DESC,
                folio DESC,
                fecha DESC
        """, (sucursal_id, sucursal_id, sucursal_id, sucursal_id, sucursal_id, sucursal_id))
        
        transferencias = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('inventario/historial_transferencias.html', 
                             sucursal=sucursal, 
                             transferencias=transferencias)
        
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        flash('Error al cargar el historial de transferencias', 'error')
        return redirect(url_for('inventario.inventario_sucursal', sucursal_id=sucursal_id))










#######################################
#######################################
#######################################
############################ ENPONIDS DE PDFS DEL INVENTARIO 

########## PDF DE TRANSFERENCIAS DE SALIDAS  ########## 

@bp_inventario.route('/pdf-transferencia-salida/<int:sucursal_id>/<folio>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def generar_pdf_transferencia_salida(sucursal_id, folio):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener datos de la transferencia de salida desde movimientos_inventario, incluyendo plantilla de sucursal origen
        # El folio es consecutivo POR SUCURSAL, así que sin filtrar por id_sucursal aquí
        # se mezclan movimientos de otras sucursales que coincidan en el mismo número de folio.
        cursor.execute("""
            SELECT mi.*, p.nombre_pieza, p.categoria,
                   so.nombre AS sucursal_origen, sd.nombre AS sucursal_destino, so.plantilla_renta
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales so ON mi.id_sucursal = so.id
            LEFT JOIN sucursales sd ON mi.sucursal_destino = sd.id
            WHERE mi.folio_nota_salida = %s
            AND mi.id_sucursal = %s
            AND mi.tipo_movimiento = 'transferencia_salida'
            ORDER BY p.nombre_pieza
        """, (folio, sucursal_id))

        movimientos = cursor.fetchall()

        if not movimientos:
            cursor.close()
            conn.close()
            return "Transferencia de salida no encontrada", 404

        # Datos generales de la transferencia
        primer_movimiento = movimientos[0]

        plantilla_renta = primer_movimiento.get('plantilla_renta')

        cursor.close()
        conn.close()
        
        # --- GENERAR PDF CON EL MISMO DISEÑO QUE NOTAS DE SALIDA ---
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
        can.drawRightString(575, 690, f"#{folio}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 12)
        fecha_emision = primer_movimiento['fecha'].strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(575, 715, f"{fecha_emision}")
        

        # === DATOS DE TRANSFERENCIA ===
        can.setFont("Courier-Bold", 23)
        can.drawString(496, 732, "SALIDA")
        
        can.setFont("Courier-Bold", 15)
        can.drawString(36, 715, "TRANSFERENCIA DE EQUIPO")

        # Sucursal origen
        can.setFont("Carlito", 10)
        can.drawString(36, 695, f"DESDE: {primer_movimiento['sucursal_origen'].upper()}")
        
        # Sucursal destino
        can.drawString(36, 680, f"HACIA: {primer_movimiento['sucursal_destino'].upper()}")
        
        # DATOS DE PIEZAS 
        y_position -= 40
        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 10)
        can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        can.drawString(150, y_position + 5, "DESCRIPCIÓN")
        y_position -= 15
        
        can.setFont("Carlito", 10)
        for movimiento in movimientos:
            # Verificar si necesitamos nueva página
            if y_position < 150:
                can.showPage()
                can.setFont("Carlito", 10)
                y_position = page_height - 60
            can.drawString(70, y_position + 5, str(movimiento['cantidad']))
            can.drawString(150, y_position + 5, movimiento['nombre_pieza'].upper())
            y_position -= 13
        y_position -= 5
        
        
        # Observaciones 
        can.setFont("Carlito", 13)
        observaciones_texto = primer_movimiento['observaciones'] if primer_movimiento['observaciones'] else "Sin observaciones."
        max_width = 550  # ancho máximo para el texto
        
        obs_lines = simpleSplit(f"OBSERVACIONES: {observaciones_texto}", "Carlito", 13, max_width)
        for line in obs_lines:
            can.drawString(36, y_position, line)
            y_position -= 18  # espacio entre líneas de observaciones

        # Mantener espacio entre observaciones y firmas
        y_position -= max(0, 90 - (len(obs_lines) * 18))
        
        # === FIRMAS ===
        can.setFont("Carlito", 10)
        # Líneas para firmas
        can.line(60, y_position, 250, y_position)  # Línea origen
        can.line(350, y_position, 540, y_position)  # Línea destino
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, f"ENTREGA: {primer_movimiento['sucursal_origen'].upper()}")
        can.drawString(350, y_position, f"RECIBE: {primer_movimiento['sucursal_destino'].upper()}")
        y_position -= 20
        
        can.drawString(60, y_position, "NOMBRE: ________________________")
        can.drawString(350, y_position, "NOMBRE: ________________________")
        y_position -= 15
        
        can.save()
        packet.seek(0)
        
        # --- COMBINAR CON LA PLANTILLA DE LA SUCURSAL ORIGEN ---
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
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        filename = f"Transf_Salida_{str(folio).zfill(5)}.pdf"
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



########################################################
########################################################
########################################################

########## PDF DE TRANSFERENCIAS DE ENTRADAS ########## 

@bp_inventario.route('/pdf-transferencia-entrada/<int:sucursal_id>/<folio>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def generar_pdf_transferencia_entrada(sucursal_id, folio):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT mi.*, p.nombre_pieza, p.categoria,
                   so.nombre AS sucursal_origen, sd.nombre AS sucursal_destino, sd.plantilla_renta
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales sd ON mi.id_sucursal = sd.id  -- sd = sucursal destino (quien recibe)
            LEFT JOIN sucursales so ON mi.sucursal_destino = so.id  -- so = sucursal origen (quien envía)
            WHERE mi.folio_nota_entrada = %s
            AND mi.id_sucursal = %s
            AND mi.tipo_movimiento = 'transferencia_entrada'
            ORDER BY p.nombre_pieza
        """, (folio, sucursal_id))

        movimientos = cursor.fetchall()

        if not movimientos:
            cursor.close()
            conn.close()
            return "Transferencia de entrada no encontrada", 404

        # Datos generales de la transferencia
        primer_movimiento = movimientos[0]

        plantilla_renta = primer_movimiento.get('plantilla_renta')

        cursor.close()
        conn.close()
        
        # --- GENERAR PDF CON EL MISMO DISEÑO QUE NOTAS DE SALIDA ---
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
        can.drawRightString(575, 690, f"#{folio}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 12)
        fecha_emision = primer_movimiento['fecha'].strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(575, 715, f"{fecha_emision}")
        

        # === DATOS DE TRANSFERENCIA ===
        can.setFont("Courier-Bold", 23)
        can.drawString(482, 732, "ENTRADA")
        
        can.setFont("Courier-Bold", 15)
        can.drawString(36, 715, "TRANSFERENCIA DE EQUIPO")

        # Sucursal origen
        can.setFont("Carlito", 10)
        can.drawString(36, 695, f"DESDE: {primer_movimiento['sucursal_origen'].upper()}")
        
        # Sucursal destino
        can.drawString(36, 680, f"HACIA: {primer_movimiento['sucursal_destino'].upper()}")
        
        # DATOS DE PIEZAS 
        y_position -= 40
        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 10)
        can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        can.drawString(150, y_position + 5, "DESCRIPCIÓN")
        y_position -= 15
        
        can.setFont("Carlito", 10)
        for movimiento in movimientos:
            # Verificar si necesitamos nueva página
            if y_position < 150:
                can.showPage()
                can.setFont("Carlito", 10)
                y_position = page_height - 60
            can.drawString(70, y_position + 5, str(movimiento['cantidad']))
            can.drawString(150, y_position + 5, movimiento['nombre_pieza'].upper())
            y_position -= 13
        y_position -= 5
        
        
        # Observaciones (ajustar a varias líneas si es necesario)
        can.setFont("Carlito", 13)
        observaciones_texto = primer_movimiento['observaciones'] if primer_movimiento['observaciones'] else "Sin observaciones."
        max_width = 550  # ancho máximo para el texto
       
        obs_lines = simpleSplit(f"OBSERVACIONES: {observaciones_texto}", "Carlito", 13, max_width)
        for line in obs_lines:
            can.drawString(36, y_position, line)
            y_position -= 18  # espacio entre líneas de observaciones

        # Mantener espacio entre observaciones y firmas
        y_position -= max(0, 90 - (len(obs_lines) * 18))
        
        # === FIRMAS ===
        can.setFont("Carlito", 10)
        # Líneas para firmas
        can.line(60, y_position, 250, y_position)  # Línea origen
        can.line(350, y_position, 540, y_position)  # Línea destino
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, f"ENTREGA: {primer_movimiento['sucursal_origen'].upper()}")
        can.drawString(350, y_position, f"RECIBE: {primer_movimiento['sucursal_destino'].upper()}")
        y_position -= 20
        
        can.drawString(60, y_position, "NOMBRE: ________________________")
        can.drawString(350, y_position, "NOMBRE: ________________________")
        y_position -= 15
        
        can.save()
        packet.seek(0)
        
        # --- COMBINAR CON LA PLANTILLA DE LA SUCURSAL DESTINO ---
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
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        filename = f"Transf_Entrada_{str(folio).zfill(5)}.pdf"
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





########################################################
########################################################
########################################################

########## PDF DE ALTA DE EQUIPO NUEVO O RENTAS DEL ANTIGUO SISTEMA


@bp_inventario.route('/pdf-alta-equipo/<int:sucursal_id>/<folio>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def generar_pdf_alta_equipo(sucursal_id, folio):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener datos del movimiento de alta de equipo (incluye inventario general y plantilla de sucursal)
        # El folio es consecutivo POR SUCURSAL, así que sin filtrar por id_sucursal aquí
        # se mezclan movimientos de otras sucursales que coincidan en el mismo número de folio.
        cursor.execute("""
            SELECT mi.*, p.nombre_pieza, p.categoria, s.nombre as sucursal_nombre,
                   u.nombre as usuario_nombre, s.plantilla_renta
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales s ON mi.id_sucursal = s.id
            LEFT JOIN usuarios u ON mi.usuario = u.id
            WHERE mi.folio_nota_entrada = %s
            AND mi.id_sucursal = %s
            AND mi.tipo_movimiento IN ('alta_equipo', 'alta_equipo_general')
            ORDER BY mi.fecha ASC, p.nombre_pieza ASC
        """, (folio, sucursal_id))
        movimientos = cursor.fetchall()
        
        if not movimientos:
            cursor.close()
            conn.close()
            return "Folio de alta no encontrado", 404
            
        # Datos básicos
        primer_movimiento = movimientos[0]
        sucursal_nombre = primer_movimiento['sucursal_nombre']
        usuario_nombre = primer_movimiento['usuario_nombre'] or 'No disponible'
        fecha_movimiento = primer_movimiento['fecha']
        observaciones = primer_movimiento['descripcion'] or ''
        tipo_movimiento = primer_movimiento['tipo_movimiento']
        plantilla_renta = primer_movimiento.get('plantilla_renta')
        
        cursor.close()
        conn.close()

        # --- GENERAR PDF CON EL MISMO DISEÑO QUE TRANSFERENCIAS ---
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
        can.drawRightString(575, 690, f"#{folio}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 12)
        fecha_emision = fecha_movimiento.strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(575, 715, f"{fecha_emision}")
        

        # === DATOS DE ALTA DE EQUIPO ===
        can.setFont("Courier-Bold", 23)
        can.drawString(482, 732, "ENTRADA")
        
        can.setFont("Courier-Bold", 15)
        # Título dinámico según el tipo de movimiento
        titulo = "ALTA DE EQUIPO" if tipo_movimiento == 'alta_equipo' else "ALTA DE EQUIPO"
        can.drawString(36, 715, titulo)

        # Sucursal
        can.setFont("Carlito", 10)
        can.drawString(36, 695, f"SUCURSAL: {sucursal_nombre.upper()}")
        
        # Usuario
        can.drawString(36, 680, f"REGISTRADO POR: {usuario_nombre.upper()}")
        
        # DATOS DE PIEZAS 
        y_position -= 40
        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 10)
        can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        can.drawString(150, y_position + 5, "DESCRIPCIÓN")
        y_position -= 15
        
        can.setFont("Carlito", 10)
        for movimiento in movimientos:
            # Verificar si necesitamos nueva página
            if y_position < 150:
                can.showPage()
                y_position = page_height - 100
            can.drawString(70, y_position + 5, str(movimiento['cantidad']))
            can.drawString(150, y_position + 5, movimiento['nombre_pieza'].upper())
            y_position -= 13
        y_position -= 5
        
        
        # Observaciones (ajustar a varias líneas si es necesario)
        can.setFont("Carlito", 13)
        observaciones_texto = observaciones if observaciones else "Sin observaciones."
        max_width = 550  # ancho máximo para el texto
      
        obs_lines = simpleSplit(f"OBSERVACIONES: {observaciones_texto}", "Carlito", 13, max_width)
        for line in obs_lines:
            can.drawString(36, y_position, line)
            y_position -= 18  # espacio entre líneas de observaciones

        # Mantener espacio entre observaciones y firmas
        y_position -= max(0, 90 - (len(obs_lines) * 18))
        
        # === FIRMAS ===
        can.setFont("Carlito", 10)
        # Líneas para firmas
        can.line(60, y_position, 250, y_position)  # Línea sucursal
        can.line(350, y_position, 540, y_position)  # Línea almacén
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, f"REGISTRA: {sucursal_nombre.upper()}")
        can.drawString(350, y_position, f"RECIBE: {sucursal_nombre.upper()}")
        y_position -= 20
        
        can.drawString(60, y_position, "NOMBRE: ________________________")
        can.drawString(350, y_position, "NOMBRE: ________________________")
        y_position -= 15
        
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
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        filename = f"Alta_Entrada_{str(folio).zfill(5)}.pdf"
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




########################################################
########################################################
########################################################

########## PDF DE BAJA DE INVENTARIO GENERAL ########## 

@bp_inventario.route('/pdf-baja-equipo/<folio>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def generar_pdf_baja_equipo(folio):
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener datos del movimiento de baja de equipo (inventario general y plantilla de sucursal)
        cursor.execute("""
            SELECT mi.*, p.nombre_pieza, p.categoria, s.nombre as sucursal_nombre,
                   u.nombre as usuario_nombre, s.plantilla_renta
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales s ON mi.id_sucursal = s.id
            LEFT JOIN usuarios u ON mi.usuario = u.id
            WHERE mi.folio_nota_salida = %s 
            AND mi.tipo_movimiento IN ('baja_equipo_general')
            ORDER BY mi.fecha ASC, p.nombre_pieza ASC
        """, (folio,))
        movimientos = cursor.fetchall()
        
        if not movimientos:
            cursor.close()
            conn.close()
            return "Folio de baja no encontrado", 404
            
        # Datos básicos
        primer_movimiento = movimientos[0]
        sucursal_nombre = primer_movimiento['sucursal_nombre']
        usuario_nombre = primer_movimiento['usuario_nombre'] or 'No disponible'
        fecha_movimiento = primer_movimiento['fecha']
        observaciones = primer_movimiento['descripcion'] or ''
        tipo_movimiento = primer_movimiento['tipo_movimiento']
        plantilla_renta = primer_movimiento.get('plantilla_renta')
        
        cursor.close()
        conn.close()

        # --- GENERAR PDF CON EL MISMO DISEÑO QUE TRANSFERENCIAS ---
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
        can.drawRightString(575, 690, f"#{folio}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 12)
        fecha_emision = fecha_movimiento.strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(575, 715, f"{fecha_emision}")
        

        # === DATOS DE BAJA DE EQUIPO ===
        can.setFont("Courier-Bold", 23)
        can.drawString(496, 732, "SALIDA")
        
        can.setFont("Courier-Bold", 15)
        # Título para baja de inventario
        titulo = "BAJA DE INVENTARIO"
        can.drawString(36, 715, titulo)

        # Sucursal
        can.setFont("Carlito", 10)
        can.drawString(36, 695, f"SUCURSAL: {sucursal_nombre.upper()}")
        
        # Usuario
        can.drawString(36, 680, f"REGISTRADO POR: {usuario_nombre.upper()}")
        
        # DATOS DE PIEZAS 
        y_position -= 40
        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 10)
        can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        can.drawString(150, y_position + 5, "DESCRIPCIÓN")
        y_position -= 15
        
        can.setFont("Carlito", 10)
        for movimiento in movimientos:
            # Verificar si necesitamos nueva página
            if y_position < 150:
                can.showPage()
                y_position = page_height - 100
            can.drawString(70, y_position + 5, str(movimiento['cantidad']))
            can.drawString(150, y_position + 5, movimiento['nombre_pieza'].upper())
            y_position -= 13
        y_position -= 5
        
        
        # Observaciones (ajustar a varias líneas si es necesario)
        can.setFont("Carlito", 13)
        observaciones_texto = observaciones if observaciones else "Sin observaciones."
        max_width = 550  # ancho máximo para el texto
       
        obs_lines = simpleSplit(f"OBSERVACIONES: {observaciones_texto}", "Carlito", 13, max_width)
        for line in obs_lines:
            can.drawString(36, y_position, line)
            y_position -= 18  # espacio entre líneas de observaciones

        # Mantener espacio entre observaciones y firmas
        y_position -= max(0, 90 - (len(obs_lines) * 18))
        
        # === FIRMAS ===
        can.setFont("Carlito", 10)
        # Líneas para firmas
        can.line(60, y_position, 250, y_position)  # Línea sucursal
        can.line(350, y_position, 540, y_position)  # Línea almacén
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, f"REGISTRA: {sucursal_nombre.upper()}")
        y_position -= 20
        
        can.drawString(60, y_position, "NOMBRE: ________________________")
        y_position -= 15
        
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
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        filename = f"Baja_Salida_{str(folio).zfill(5)}.pdf"
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








########################################################
########################################################
########################################################

#################### PDF DE REPARACIÓN 

@bp_inventario.route('/pdf-reparacion-lote/<int:sucursal_id>/<folio>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def generar_pdf_reparacion_lote(sucursal_id, folio):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener datos del envío a reparación (incluye plantilla de sucursal)
        # El folio es consecutivo POR SUCURSAL, así que sin filtrar por id_sucursal aquí
        # se mezclan movimientos de otras sucursales que coincidan en el mismo número de folio.
        cursor.execute("""
            SELECT mi.*, p.nombre_pieza, p.categoria, s.nombre as sucursal_nombre,
                   u.nombre as usuario_nombre, s.plantilla_renta
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales s ON mi.id_sucursal = s.id
            LEFT JOIN usuarios u ON mi.usuario = u.id
            WHERE mi.folio_nota_salida = %s
            AND mi.id_sucursal = %s
            AND mi.tipo_movimiento = 'reparacion_lote'
            ORDER BY mi.fecha ASC, p.nombre_pieza ASC
        """, (folio, sucursal_id))
        movimientos = cursor.fetchall()
        
        if not movimientos:
            cursor.close()
            conn.close()
            return "Folio de reparación no encontrado", 404
            
        # Datos básicos
        primer_movimiento = movimientos[0]
        sucursal_nombre = primer_movimiento['sucursal_nombre']
        usuario_nombre = primer_movimiento['usuario_nombre'] or 'No disponible'
        fecha_movimiento = primer_movimiento['fecha']
        observaciones = primer_movimiento['observaciones'] or primer_movimiento['descripcion'] or ''
        plantilla_renta = primer_movimiento.get('plantilla_renta')
        
        cursor.close()
        conn.close()

        # --- GENERAR PDF CON EL MISMO DISEÑO QUE ALTA DE EQUIPO ---
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
        can.drawRightString(575, 690, f"#{folio}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 12)
        fecha_emision = fecha_movimiento.strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(575, 715, f"{fecha_emision}")
        

        # === DATOS DE REPARACIÓN ===
        can.setFont("Courier-Bold", 23)
        can.drawString(496, 732, "SALIDA")
        
        can.setFont("Courier-Bold", 15)
        can.drawString(36, 715, "EQUIPO DAÑADO")

        # Sucursal
        can.setFont("Carlito", 10)
        can.drawString(36, 695, f"SUCURSAL: {sucursal_nombre.upper()}")
        
        # Usuario
        can.drawString(36, 680, f"ENVIADO POR: {usuario_nombre.upper()}")
        
        # DATOS DE PIEZAS 
        y_position -= 40
        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 10)
        can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        can.drawString(150, y_position + 5, "DESCRIPCIÓN")
        y_position -= 15
        
        can.setFont("Carlito", 10)
        for movimiento in movimientos:
            # Verificar si necesitamos nueva página
            if y_position < 150:
                can.showPage()
                y_position = page_height - 100
            can.drawString(70, y_position + 5, str(movimiento['cantidad']))
            can.drawString(150, y_position + 5, movimiento['nombre_pieza'].upper())
            y_position -= 13
        y_position -= 5
        
        
        # Observaciones (ajustar a varias líneas si es necesario)
        can.setFont("Carlito", 13)
        observaciones_texto = observaciones if observaciones else "Sin observaciones."
        max_width = 550  # ancho máximo para el texto
       
        obs_lines = simpleSplit(f"OBSERVACIONES: {observaciones_texto}", "Carlito", 13, max_width)
        for line in obs_lines:
            can.drawString(36, y_position, line)
            y_position -= 18  # espacio entre líneas de observaciones

        # Mantener espacio entre observaciones y firmas
        y_position -= max(0, 90 - (len(obs_lines) * 18))
        
        # === FIRMAS ===
        can.setFont("Carlito", 10)
        # Líneas para firmas
        can.line(60, y_position, 250, y_position)  # Línea sucursal
        can.line(350, y_position, 540, y_position)  # Línea taller
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, f"ENTREGA: {sucursal_nombre.upper()}")
        can.drawString(350, y_position, "RECIBE: TALLER DE REPARACIÓN")
        y_position -= 20
        
        can.drawString(60, y_position, "NOMBRE: ________________________")
        can.drawString(350, y_position, "NOMBRE: ________________________")
        y_position -= 15
        
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
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        filename = f"Rep_Salida_{str(folio).zfill(5)}.pdf"
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




########################################################
########################################################
########################################################

########## PDF DE FINALIZACIÓN DE REPARACIONES (ENTRADA) ##########

@bp_inventario.route('/pdf-finalizacion-reparacion/<int:sucursal_id>/<folio>')
@requiere_sesion()
@requiere_permiso('ver_inventario_sucursal')
def generar_pdf_finalizacion_reparacion(sucursal_id, folio):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener datos de la finalización de reparación (incluye plantilla de sucursal)
        # El folio es consecutivo POR SUCURSAL, así que sin filtrar por id_sucursal aquí
        # se mezclan movimientos de otras sucursales que coincidan en el mismo número de folio.
        cursor.execute("""
            SELECT mi.*, p.nombre_pieza, p.categoria, s.nombre as sucursal_nombre,
                   u.nombre as usuario_nombre, s.plantilla_renta
            FROM movimientos_inventario mi
            JOIN piezas p ON mi.id_pieza = p.id_pieza
            JOIN sucursales s ON mi.id_sucursal = s.id
            LEFT JOIN usuarios u ON mi.usuario = u.id
            WHERE mi.folio_nota_entrada = %s
            AND mi.id_sucursal = %s
            AND mi.tipo_movimiento = 'finalizar_reparacion'
            ORDER BY mi.fecha ASC, p.nombre_pieza ASC
        """, (folio, sucursal_id))
        movimientos = cursor.fetchall()
        
        if not movimientos:
            cursor.close()
            conn.close()
            return "Folio de finalización de reparación no encontrado", 404
            
        # Datos básicos
        primer_movimiento = movimientos[0]
        sucursal_nombre = primer_movimiento['sucursal_nombre']
        usuario_nombre = primer_movimiento['usuario_nombre'] or 'No disponible'
        fecha_movimiento = primer_movimiento['fecha']
        observaciones = primer_movimiento['descripcion'] or ''
        plantilla_renta = primer_movimiento.get('plantilla_renta')
        
        cursor.close()
        conn.close()

        # --- GENERAR PDF CON EL MISMO DISEÑO QUE NOTAS DE ENTRADA ---
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
        can.drawRightString(575, 690, f"#{folio}")
        
        # Fecha y hora de emisión
        can.setFont("Carlito", 12)
        fecha_emision = fecha_movimiento.strftime('%d/%m/%Y - %H:%M:%S')
        can.drawRightString(575, 715, f"{fecha_emision}")
        

        # === DATOS DE FINALIZACIÓN DE REPARACIÓN ===
        can.setFont("Courier-Bold", 23)
        can.drawString(482, 732, "ENTRADA")
        
        can.setFont("Courier-Bold", 15)
        can.drawString(36, 715, "FINALIZACIÓN DE REPARACIÓN")

        # Sucursal
        can.setFont("Carlito", 10)
        can.drawString(36, 695, f"SUCURSAL: {sucursal_nombre.upper()}")
        
        # Usuario
        can.drawString(36, 680, f"RECIBIDO POR: {usuario_nombre.upper()}")
        
        # DATOS DE PIEZAS 
        y_position -= 40
        # Encabezado de tabla
        can.setFont("Helvetica-Bold", 10)
        can.drawString(36, y_position + 5, "CANT. (PIEZAS)")
        can.drawString(150, y_position + 5, "DESCRIPCIÓN")
        y_position -= 15
        
        can.setFont("Carlito", 10)
        for movimiento in movimientos:
            # Verificar si necesitamos nueva página
            if y_position < 150:
                can.showPage()
                y_position = page_height - 100
            can.drawString(70, y_position + 5, str(movimiento['cantidad']))
            can.drawString(150, y_position + 5, movimiento['nombre_pieza'].upper())
            y_position -= 13
        y_position -= 5
        
        
        # Observaciones (ajustar a varias líneas si es necesario)
        can.setFont("Carlito", 13)
        observaciones_texto = observaciones if observaciones else "Equipos reparados y listos para uso."
        max_width = 550  # ancho máximo para el texto
        
        obs_lines = simpleSplit(f"OBSERVACIONES: {observaciones_texto}", "Carlito", 13, max_width)
        for line in obs_lines:
            can.drawString(36, y_position, line)
            y_position -= 18  # espacio entre líneas de observaciones

        # Mantener espacio entre observaciones y firmas
        y_position -= max(0, 90 - (len(obs_lines) * 18))
        
        # === FIRMAS ===
        can.setFont("Carlito", 10)
        # Líneas para firmas
        can.line(60, y_position, 250, y_position)  # Línea taller
        can.line(350, y_position, 540, y_position)  # Línea sucursal
        y_position -= 15
        
        # Etiquetas de firmas
        can.drawString(60, y_position, "ENTREGA: TALLER DE REPARACIÓN")
        can.drawString(350, y_position, f"RECIBE: {sucursal_nombre.upper()}")
        y_position -= 20
        
        can.drawString(60, y_position, "NOMBRE: ________________________")
        can.drawString(350, y_position, "NOMBRE: ________________________")
        y_position -= 15
        
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
            print(f"Error con plantilla: {e}")
            overlay_pdf = PdfReader(packet)
            output = PdfWriter()
            for page in overlay_pdf.pages:
                output.add_page(page)

        filename = f"Rep_Entrada_{str(folio).zfill(5)}.pdf"
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








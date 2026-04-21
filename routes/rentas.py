

# ======================= IMPORTS =======================
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from utils.db import get_db_connection
from utils.decorators import requiere_sesion, requiere_permiso
from itertools import zip_longest
from utils.datetime_utils import get_local_now, get_local_now_naive
# PDF/Reportlab imports (usados en otras rutas, mantener agrupados)
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

# ======================= BLUEPRINT =======================
rentas_bp = Blueprint('rentas', __name__, url_prefix='/rentas')



###########################################################
# ======================= ELIMINACIÓN DE RENTAS =======================
@rentas_bp.route('/info_eliminar/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def info_eliminar_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Verificar notas de salida y entrada
    cursor.execute("SELECT id FROM notas_salida WHERE renta_id = %s", (renta_id,))
    nota_salida = cursor.fetchone()
    cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s", (renta_id,))
    nota_entrada = cursor.fetchone()
    mensaje = "¿Seguro que deseas eliminar esta renta?"  # Mensaje base
    if nota_salida and not nota_entrada:
        mensaje = "Esta renta tiene nota de salida pero no de entrada. Si eliminas, el equipo se descontará del inventario total. ¿Deseas continuar?"
    elif nota_salida and nota_entrada:
        mensaje = "Esta renta tiene nota de salida y de entrada. El equipo ya regresó, puedes eliminar sin afectar inventario. ¿Deseas continuar?"
    elif not nota_salida:
        mensaje += "Esta renta no tiene nota de salida. Se eliminará sin afectar inventario. ¿Deseas continuar?"
    cursor.close()
    conn.close()
    return jsonify({"status": "ok", "mensaje": mensaje})



@rentas_bp.route('/eliminar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('eliminar_renta')
def eliminar_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Verificar notas de salida y entrada
    cursor.execute("SELECT id FROM notas_salida WHERE renta_id = %s", (renta_id,))
    nota_salida = cursor.fetchone()
    cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s", (renta_id,))
    nota_entrada = cursor.fetchone()

    # Si hay nota de salida pero no de entrada, descontar equipo del inventario
    if nota_salida and not nota_entrada:
        # Obtener productos y cantidades de la renta
        cursor.execute("SELECT id_producto, cantidad FROM renta_detalle WHERE renta_id = %s", (renta_id,))
        productos = cursor.fetchall()
        for id_producto, cantidad in productos:
            # Descontar del inventario principal
            cursor.execute("UPDATE productos SET cantidad = cantidad - %s WHERE id_producto = %s", (cantidad, id_producto))
    # Soft delete: marcar la renta como eliminada
    cursor.execute("UPDATE rentas SET estado_renta = 'eliminada' WHERE id = %s", (renta_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "ok", "mensaje": "Renta eliminada correctamente."})






###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
# ======================= CANCELACIÓN DE RENTAS =======================
@rentas_bp.route('/cancelar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('cancelar_renta')
def cancelar_renta(renta_id):
    motivo = request.form.get('motivo_cancelacion', '')
    monto_reembolso = request.form.get('monto_reembolso', None)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Marcar la renta como cancelada y guardar motivo
        cursor.execute("UPDATE rentas SET estado_renta = 'cancelada', estado_pago = 'Reembolsado' WHERE id = %s", (renta_id,))

        # Registrar en historial de rentas
        descripcion = f"Cancelación de renta. Motivo: {motivo}"
        if monto_reembolso:
            descripcion += f" | Reembolso: ${monto_reembolso}"
        cursor.execute("""
            INSERT INTO historial_rentas (renta_id, accion, descripcion, fecha)
            VALUES (%s, %s, %s, NOW())
        """, (renta_id, 'cancelacion', descripcion))

        conn.commit()
        return jsonify({"status": "ok", "mensaje": "Renta cancelada correctamente."})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "mensaje": str(e)})
    finally:
        cursor.close()
        conn.close()




###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
# ======================= LISTADO Y CREACIÓN DE RENTAS =======================
@rentas_bp.route('/')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def modulo_rentas():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener sucursal del usuario desde la sesión
    sucursal_id_usuario = session.get('sucursal_id')
    rol_id = session.get('rol_id')
    
    # Obtener todas las sucursales para el filtro (solo admin)
    sucursales = []
    if rol_id == 2:  # Solo admin
        cursor.execute("SELECT id, nombre FROM sucursales ORDER BY id")
        sucursales = cursor.fetchall()
    
    # Determinar qué sucursal filtrar
    sucursal_filtro = request.args.get('sucursal_id')
    sucursal_actual = None
    
    if rol_id == 2:  # Admin
        if sucursal_filtro:
            # Admin filtrando por sucursal específica
            try:
                sucursal_filtro = int(sucursal_filtro)
                where_sucursal = "WHERE r.id_sucursal = %s"
                params_sucursal = (sucursal_filtro,)
                # Obtener nombre de la sucursal filtrada
                cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_filtro,))
                row = cursor.fetchone()
                sucursal_actual = {'id': sucursal_filtro, 'nombre': row[0] if row else 'Desconocida'}
            except (ValueError, TypeError):
                sucursal_filtro = None
        
        if not sucursal_filtro:
            # Admin viendo todas las sucursales
            where_sucursal = ""
            params_sucursal = ()
            sucursal_actual = {'id': 'todas', 'nombre': 'Todas las Sucursales'}
    else:
        # Usuario normal solo ve su sucursal
        where_sucursal = "WHERE r.id_sucursal = %s"
        params_sucursal = (sucursal_id_usuario,)
        sucursal_filtro = sucursal_id_usuario
        # Obtener nombre de la sucursal del usuario
        cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_id_usuario,))
        row = cursor.fetchone()
        sucursal_actual = {'id': sucursal_id_usuario, 'nombre': row[0] if row else 'Mi Sucursal'}

    # Consulta principal con filtro de sucursal y folio
    cursor.execute(f"""
    SELECT 
        r.id, r.fecha_registro, r.fecha_salida, r.fecha_entrada,
        r.estado_renta, r.estado_pago, r.metodo_pago,
        r.total_con_iva, r.total, r.iva, r.observaciones,
        r.direccion_obra,
        c.nombre, c.apellido1, c.apellido2,
        (SELECT COUNT(*) FROM notas_entrada ne WHERE ne.renta_id = r.id) as tiene_nota_entrada,
        CASE 
            WHEN r.fecha_entrada IS NOT NULL THEN 
                DATE_ADD(r.fecha_entrada, INTERVAL 1 DAY)
            ELSE NULL 
        END as fecha_limite_entrega,
        r.estado_cobro_extra,
        nce.estado_pago AS estado_pago_extra,
        nce.id AS cobro_extra_id,
        ne.estado_retraso,
        (
            CASE
                WHEN (
                    SELECT COUNT(*) FROM notas_entrada ne
                    WHERE ne.renta_id = r.id OR ne.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = r.id)
                ) > 0
                THEN (
                    SELECT COUNT(*) FROM (
                        SELECT nsd.id_pieza,
                               nsd.cantidad AS cantidad_salida,
                               (
                                   SELECT COALESCE(SUM(ned2.cantidad_recibida), 0)
                                   FROM notas_entrada ne2
                                   JOIN notas_entrada_detalle ned2 ON ned2.nota_entrada_id = ne2.id
                                   WHERE (
                                       ne2.renta_id = r.id
                                       OR ne2.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = r.id)
                                   )
                                   AND ned2.id_pieza = nsd.id_pieza
                               ) AS cantidad_recibida_total
                        FROM notas_salida ns
                        JOIN notas_salida_detalle nsd ON nsd.nota_salida_id = ns.id
                        WHERE ns.renta_id = r.id
                        GROUP BY nsd.id_pieza, nsd.cantidad
                        HAVING nsd.cantidad > (
                            SELECT COALESCE(SUM(ned2.cantidad_recibida), 0)
                            FROM notas_entrada ne2
                            JOIN notas_entrada_detalle ned2 ON ned2.nota_entrada_id = ne2.id
                            WHERE (
                                ne2.renta_id = r.id
                                OR ne2.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = r.id)
                            )
                            AND ned2.id_pieza = nsd.id_pieza
                        )
                    ) AS pendientes
                )
                ELSE 0
            END
        ) AS piezas_pendientes,
        -- Verificar si hay rentas asociadas (renovaciones activas)
        (
            SELECT COUNT(*)
            FROM rentas r_hija
            WHERE r_hija.renta_asociada_id = r.id AND r_hija.estado_renta = 'activa renovación'
        ) AS tiene_renovaciones,
        r.renta_asociada_id,
        r.id_sucursal,
        -- Calcular folio por sucursal
        (SELECT COUNT(*) FROM rentas r2 WHERE r2.id_sucursal = r.id_sucursal AND r2.id <= r.id ORDER BY r2.id) AS folio_sucursal,
        s.nombre AS sucursal_nombre,
        ncr.id AS cobro_retraso_id
    FROM rentas r
    JOIN clientes c ON r.cliente_id = c.id
    JOIN sucursales s ON r.id_sucursal = s.id
    LEFT JOIN notas_entrada ne ON ne.renta_id = r.id
        AND ne.id = (SELECT MAX(id) FROM notas_entrada WHERE renta_id = r.id)
    LEFT JOIN notas_cobro_extra nce ON nce.nota_entrada_id = ne.id
    LEFT JOIN notas_cobro_retraso ncr ON ncr.nota_entrada_id = ne.id
    {where_sucursal}
    ORDER BY 
        CASE 
            WHEN LOWER(r.estado_renta) = 'activo' || LOWER(r.estado_renta) = 'activa renovación' THEN 0
            ELSE 1
        END,
        r.id DESC
    """, params_sucursal)
    
    rentas = cursor.fetchall()

    # Modificar consulta de detalles para filtrar por rentas de la sucursal
    detalles = []
    productos_por_renta = {}
    if rentas:
        renta_ids = [str(renta[0]) for renta in rentas]
        cursor.execute(f"""
            SELECT d.renta_id, p.nombre, d.cantidad, d.id_producto, p.tipo
            FROM renta_detalle d
            JOIN productos p ON d.id_producto = p.id_producto
            WHERE d.renta_id IN ({','.join(['%s'] * len(renta_ids))})
        """, renta_ids)
        detalles = cursor.fetchall()
        for renta_id, nombre, cantidad, id_producto, tipo in detalles:
            productos_por_renta.setdefault(renta_id, []).append(f"{nombre} x{cantidad}")        
                # Si no se especifica sucursal_id, redirigir a Matriz Colosio (id=1)
            if not sucursal_filtro:
                return redirect(url_for('rentas.modulo_rentas', sucursal_id=1))

    # Clientes activos
    cursor.execute("SELECT id, nombre, apellido1 FROM clientes WHERE activo = 1")
    clientes = cursor.fetchall()

    # Productos y precios (JOIN con producto_precios)
    cursor.execute("""
        SELECT p.id_producto, p.nombre, 
               pp.precio_dia, pp.precio_14_dias, pp.precio_29_dias, pp.precio_30_dias, p.precio_unico
        FROM productos p
        JOIN producto_precios pp ON p.id_producto = pp.id_producto
        WHERE p.estatus = 'activo'
        ORDER BY p.nombre
    """)
    productos = cursor.fetchall()

    # Prepara los precios para JS
    precios_productos = {}
    for prod in productos:
        precios_productos[prod[0]] = {
            "precio_dia": float(prod[2]),
            "precio_14_dias": float(prod[3]),
            "precio_29_dias": float(prod[4]),
            "precio_30_dias": float(prod[5]),
            "precio_unico": int(prod[6])
        }

            # Sucursal actual
    sucursal_id = session.get('sucursal_id')
    sucursal_nombre = None
    if sucursal_id:
        cursor.execute("SELECT nombre FROM sucursales WHERE id = %s", (sucursal_id,))
        row = cursor.fetchone()
        if row:
            sucursal_nombre = row[0]

    def calcular_estado_entrega(renta):

        # Si no tiene fecha de entrada definida, no mostrar indicador
        if not renta[3]:  
            return None
        
        # Si ya tiene nota de entrada, no mostrar indicador (ya está finalizada)
        if renta[15]:  
            return None
        
        # Si el estado de la renta no es 'Activo', no mostrar indicador
        if renta[4] != 'Activo':  
            return None

        
        fecha_entrada = renta[3]  
        fecha_limite = renta[16]  
        ahora_naive = get_local_now_naive()
        
        # Solo mostrar indicadores para rentas ACTIVAS con fechas específicas
        if fecha_limite:
            # Crear fecha_limite_con_hora y convertir a zona horaria local
            fecha_limite_con_hora = datetime.combine(fecha_limite, datetime.strptime('10:00', '%H:%M').time())

            # Si ya pasó la fecha y hora límite = VENCIDA
            if ahora_naive > fecha_limite_con_hora:
                return {
                    'estado': 'vencida',
                    'clase': 'badge-vencida',
                    'texto': 'Vencida'
                }
            
            # Si llegó a la fecha de entrada pero no ha pasado la hora límite = POR REGRESAR
            elif ahora_naive.date() >= fecha_entrada:
                return {
                    'estado': 'por_regresar',
                    'clase': 'badge-por-regresar',
                    'texto': 'Por regresar'
                }
            
        return None

    # Aplicar la función a todas las rentas
    rentas_con_estado = []
    for renta in rentas:
        estado_entrega = calcular_estado_entrega(renta)
        renta_lista = list(renta) + [estado_entrega]
        rentas_con_estado.append(renta_lista)

    cursor.close()
    conn.close()

    return render_template(
        'rentas/index.html',
        rentas=rentas_con_estado,
        clientes=clientes,
        productos=productos,
        productos_por_renta=productos_por_renta,
        sucursal_nombre=sucursal_actual['nombre'],
        precios_productos=precios_productos,
        sucursal_id=sucursal_id_usuario,
        # Nuevos datos para filtros admin
        sucursales=sucursales,
        sucursal_actual=sucursal_actual,
        es_admin=(rol_id == 2) 
    )



# ======================= UTILIDADES =======================
def obtener_siguiente_folio_sucursal(cursor, sucursal_id):
    """
    Obtiene el siguiente folio consecutivo para una sucursal específica
    """
    cursor.execute("""
        SELECT COALESCE(MAX(
            (SELECT COUNT(*) FROM rentas r2 WHERE r2.id_sucursal = %s AND r2.id <= r.id)
        ), 0) + 1 
        FROM rentas r 
        WHERE r.id_sucursal = %s
    """, (sucursal_id, sucursal_id))
    resultado = cursor.fetchone()
    return resultado[0] if resultado else 1

def generar_folio_display(sucursal_id, folio_numero):
    """
    Genera el folio formateado para mostrar
    Formato: SUC1-0001, SUC2-0001, etc.
    """
    return f"SUC{sucursal_id}-{folio_numero:04d}"









###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
# ======================= CREAR RENTA =======================
@rentas_bp.route('/crear', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_renta')
def crear_renta():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Determinar la sucursal correcta según el rol
        rol_id = session.get('rol_id')
        sucursal_id_usuario = session.get('sucursal_id')
        
        if rol_id == 2:  # Admin
            # Admin puede crear rentas en la sucursal que está viendo
            sucursal_para_renta = request.form.get('id_sucursal')
            if not sucursal_para_renta:
                sucursal_para_renta = sucursal_id_usuario
            try:
                sucursal_para_renta = int(sucursal_para_renta)
            except (ValueError, TypeError):
                sucursal_para_renta = sucursal_id_usuario
        else:
            # Usuario normal solo puede crear en su sucursal
            sucursal_para_renta = sucursal_id_usuario

        if not sucursal_para_renta:
            flash("Error: No se pudo determinar la sucursal.", "danger")
            return redirect(url_for('rentas.modulo_rentas', sucursal_id=sucursal_para_renta))

        # Resto del código usando sucursal_para_renta
        if request.form.get('renta_programada'):
            estado_renta = 'programada'
        else:
            estado_renta = 'en curso'
        
        estado_pago = 'Pago pendiente'
        metodo_pago = 'Pendiente'
        cliente_id = request.form['cliente_id']
        direccion_obra = request.form['direccion_obra']
        fecha_salida = request.form['fecha_salida']
        fecha_entrada = request.form.get('fecha_entrada') or None
        observaciones = request.form.get('observaciones')
        fecha_registro = get_local_now()
        fecha_programada = request.form.get('fecha_programada') or None
        costo_traslado = float(request.form.get('costo_traslado') or 0)
        traslado = request.form.get('traslado') or 'ninguno'

        cursor.execute("""
            INSERT INTO rentas (
                cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                direccion_obra, estado_renta, estado_pago, metodo_pago,
                total, iva, total_con_iva, observaciones, fecha_programada, id_sucursal,
                costo_traslado, traslado
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cliente_id, fecha_registro, fecha_salida, fecha_entrada,
            direccion_obra, estado_renta, estado_pago, metodo_pago,
            0, 0, 0, observaciones, fecha_programada, sucursal_para_renta,  # ← Usar la sucursal correcta
            costo_traslado, traslado
        ))

        renta_id = cursor.lastrowid
        
        # Obtener folio para mostrar mensaje usando la sucursal correcta
        folio_numero = obtener_siguiente_folio_sucursal(cursor, sucursal_para_renta)
        folio_display = generar_folio_display(sucursal_para_renta, folio_numero)

        # Procesar productos
        productos = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        dias = request.form.getlist('dias_renta[]')
        costos = request.form.getlist('costo_unitario[]')

        total = 0
        
        for i in range(len(productos)):
            prod_id = int(productos[i])
            cant = int(cantidades[i])
            dias_renta_raw = dias[i]
            if dias_renta_raw in (None, '', 'null'):
                dias_renta = 1
            else:
                dias_renta = int(dias_renta_raw)
                if dias_renta < 1:
                    dias_renta = 1

            # Obtener precios y si es precio_unico
            cursor.execute("SELECT precio_dia, precio_14_dias, precio_29_dias, precio_30_dias FROM producto_precios WHERE id_producto = %s", (prod_id,))
            precios = cursor.fetchone()
            cursor.execute("SELECT precio_unico FROM productos WHERE id_producto = %s", (prod_id,))
            precio_unico = cursor.fetchone()[0]

            # Selección de precio según días
            if precio_unico == 1:
                costo_unitario = float(precios[0])
            else:
                if dias_renta <= 2:
                    costo_unitario = float(precios[0])  # precio_dia (1-2 días)
                elif dias_renta <= 14:
                    costo_unitario = float(precios[1])  # precio_14_dias (3-14 días)
                elif dias_renta <= 29:
                    costo_unitario = float(precios[2])  # precio_29_dias (15-29 días)
                else:
                    costo_unitario = float(precios[3])  # precio_30_dias (30+ días)

            subtotal = cant * dias_renta * costo_unitario
            total += subtotal

            cursor.execute("""
                INSERT INTO renta_detalle (
                    renta_id, id_producto, cantidad, dias_renta,
                    costo_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                renta_id, prod_id, cant, dias_renta,
                costo_unitario, subtotal
            ))

        # Calcular IVA y total con IVA
        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        cursor.execute("""
            UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
        """, (total, iva, total_con_iva, renta_id))

        conn.commit()
        flash(f"Renta {folio_display} registrada con éxito.", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"Error al guardar la renta: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas', sucursal_id=sucursal_para_renta))



############################################################
############################################################
#############################################################
##############################################################|
#############################################################
###########################################################
# ======================= ACTUALIZAR FECHA DE ENTRADA =======================
@rentas_bp.route('/actualizar_fecha_entrada/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('editar_renta')
def actualizar_fecha_entrada(renta_id):
    try:
        nueva_fecha_str = request.json.get('fecha_entrada')
        if not nueva_fecha_str:
            return jsonify({'success': False, 'error': 'Fecha de entrada no proporcionada'}), 400

        # Parsear fecha_entrada enviada (asumiendo formato ISO YYYY-MM-DD)
        nueva_fecha = datetime.strptime(nueva_fecha_str, '%Y-%m-%d').date()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Obtener fecha_salida actual para calcular días
        cursor.execute("SELECT fecha_salida, costo_traslado FROM rentas WHERE id = %s", (renta_id,))
        fila = cursor.fetchone()
        if not fila:
            return jsonify({'success': False, 'error': 'Renta no encontrada'}), 404

        fecha_salida = fila[0]
        costo_traslado = float(fila[1] or 0)

        if not fecha_salida:
            return jsonify({'success': False, 'error': 'Fecha de salida no definida'}), 400

        # Calcular días de renta
        dias_renta = (nueva_fecha - fecha_salida).days + 1
        if dias_renta < 1:
            dias_renta = 1

        # Actualizar fecha_entrada en rentas
        cursor.execute("UPDATE rentas SET fecha_entrada = %s WHERE id = %s", (nueva_fecha, renta_id))

        # Obtener detalles para actualizar días y subtotal
        cursor.execute("SELECT id, cantidad, costo_unitario FROM renta_detalle WHERE renta_id = %s", (renta_id,))
        detalles = cursor.fetchall()

        total = 0
        for detalle in detalles:
            detalle_id, cantidad, costo_unitario = detalle
            subtotal = cantidad * dias_renta * float(costo_unitario)
            cursor.execute("""
                UPDATE renta_detalle SET dias_renta = %s, subtotal = %s WHERE id = %s
            """, (dias_renta, subtotal, detalle_id))
            total += subtotal

        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        # Actualizar totales en rentas
        cursor.execute("""
            UPDATE rentas SET total = %s, iva = %s, total_con_iva = %s WHERE id = %s
        """, (total, iva, total_con_iva, renta_id))

        conn.commit()

        return jsonify({'success': True, 'message': 'Fecha de entrada y totales actualizados correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()



###########################################################
###########################################################
###########################################################
###########################################################
###########################################################

# Ejemplo de endpoint para cerrar renta y actualizar días/subtotales
###########################################################
# ======================= CERRAR RENTA =======================
@rentas_bp.route('/cerrar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('cerrar_renta')
def cerrar_renta(renta_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        fecha_entrada = request.form.get('fecha_entrada')
        if not fecha_entrada:
            flash("Debes ingresar la fecha de entrada para cerrar la renta.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))

        # Obtener fecha_salida de la renta
        cursor.execute("SELECT fecha_salida FROM rentas WHERE id = %s", (renta_id,))
        row = cursor.fetchone()
        if not row:
            flash("Renta no encontrada.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))
        fecha_salida = row[0]

        # Calcular días de renta
        dias_renta = (datetime.strptime(fecha_entrada, "%Y-%m-%d") - datetime.strptime(str(fecha_salida), "%Y-%m-%d")).days + 1
        if dias_renta < 1:
            dias_renta = 1

        # Actualizar cada detalle de la renta
        cursor.execute("""
            SELECT id, cantidad, costo_unitario FROM renta_detalle WHERE renta_id = %s
        """, (renta_id,))
        detalles = cursor.fetchall()
        for detalle in detalles:
            detalle_id, cantidad, costo_unitario = detalle
            subtotal = cantidad * dias_renta * costo_unitario
            cursor.execute("""
                UPDATE renta_detalle
                SET dias_renta = %s, subtotal = %s
                WHERE id = %s
            """, (dias_renta, subtotal, detalle_id))

        # Recalcular totales
        cursor.execute("""
            SELECT SUM(subtotal) FROM renta_detalle WHERE renta_id = %s
        """, (renta_id,))
        total = cursor.fetchone()[0] or 0

        # Obtener costo_traslado
        cursor.execute("SELECT costo_traslado FROM rentas WHERE id = %s", (renta_id,))
        costo_traslado = cursor.fetchone()[0] or 0

        total += costo_traslado
        iva = total * 0.16
        total_con_iva = total + iva

        # Verificar estado actual de la renta
        cursor.execute("SELECT estado_renta FROM rentas WHERE id = %s", (renta_id,))
        estado_actual = cursor.fetchone()[0]
        if estado_actual == 'cancelada':
            # Si está cancelada, solo actualiza totales y fecha_entrada, no el estado
            cursor.execute("""
                UPDATE rentas SET fecha_entrada=%s, total=%s, iva=%s, total_con_iva=%s
                WHERE id=%s
            """, (fecha_entrada, total, iva, total_con_iva, renta_id))
        else:
            # Si no está cancelada, actualiza también el estado a 'cerrada'
            cursor.execute("""
                UPDATE rentas SET fecha_entrada=%s, total=%s, iva=%s, total_con_iva=%s, estado_renta='cerrada'
                WHERE id=%s
            """, (fecha_entrada, total, iva, total_con_iva, renta_id))

        conn.commit()
        flash("Renta cerrada y actualizada con éxito.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al cerrar la renta: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('rentas.modulo_rentas'))





###########################################################
###########################################################
###########################################################
###########################################################
# ======================= DETALLE DE RENTA =======================
@rentas_bp.route('/detalle/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def obtener_detalle_renta(renta_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Datos principales de la renta
        cursor.execute("""
            SELECT r.*, 
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) AS cliente_nombre,
                   c.codigo_cliente, c.telefono, c.correo, c.rfc,
                   c.calle, c.numero_exterior, c.numero_interior, c.entre_calles,
                   c.colonia, c.codigo_postal, c.municipio, c.estado
            FROM rentas r
            JOIN clientes c ON r.cliente_id = c.id
            WHERE r.id = %s
        """, (renta_id,))
        renta = cursor.fetchone()
        
        if not renta:
            return jsonify({'error': 'Renta no encontrada'}), 404
        
        # Productos de la renta
        cursor.execute("""
            SELECT p.id_producto, p.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
            FROM renta_detalle rd
            JOIN productos p ON rd.id_producto = p.id_producto
            WHERE rd.renta_id = %s
        """, (renta_id,))
        productos = cursor.fetchall()
        
        # Calcular fecha límite de entrega
        fecha_limite = "INDEFINIDA"
        if renta['fecha_entrada']:
            from datetime import timedelta
            fecha_limite_obj = renta['fecha_entrada'] + timedelta(days=1)
            fecha_limite = f"{fecha_limite_obj.strftime('%d/%m/%Y')} antes de las 9:00 a.m."
        
        # Formatear dirección completa del cliente
        direccion_cliente = renta['calle'] or ''
        if renta['numero_exterior']:
            direccion_cliente += f" #{renta['numero_exterior']}"
        if renta['numero_interior']:
            direccion_cliente += f", Int. {renta['numero_interior']}"
        if renta['entre_calles']:
            direccion_cliente += f" (entre {renta['entre_calles']})"
        if renta['colonia']:
            direccion_cliente += f", COL. {renta['colonia']}"
        if renta['codigo_postal']:
            direccion_cliente += f" - C.P. {renta['codigo_postal']}"
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'renta': {
                'id': renta['id'],
                'fecha_registro': renta['fecha_registro'].strftime('%d/%m/%Y %H:%M:%S'),
                'fecha_salida': renta['fecha_salida'].strftime('%Y-%m-%d') if renta['fecha_salida'] else 'No definida',
                'fecha_entrada': renta['fecha_entrada'].strftime('%Y-%m-%d') if renta['fecha_entrada'] else 'Indefinida',
                'estado_renta': renta['estado_renta'],
                'estado_pago': renta['estado_pago'],
                'metodo_pago': renta['metodo_pago'] or 'No definido',
                'direccion_obra': renta['direccion_obra'],
                'traslado': renta['traslado'] or 'Ninguno',
                'costo_traslado': float(renta['costo_traslado'] or 0),
                'iva': float(renta['iva'] or 0),
                'total': float(renta['total_con_iva'] or 0),
                'observaciones': renta['observaciones'],
                'fecha_limite': fecha_limite
            },
            'cliente': {
                'codigo': renta['codigo_cliente'],
                'nombre': renta['cliente_nombre'],
                'telefono': renta['telefono'] or 'No registrado',
                'email': renta['correo'] or 'No registrado',
                'rfc': renta['rfc'] or 'No registrado',
                'direccion': direccion_cliente
            },
            'productos': productos
        })
        
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 500



###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
###########################################################
# ======================= RENOVAR RENTA =======================
@rentas_bp.route('/renovar/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('renovar_renta')
def renovar_renta(renta_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Datos del formulario
        nueva_fecha_salida = request.form.get('nueva_fecha_salida')
        fecha_entrada = request.form.get('fecha_entrada') or None
        observaciones = request.form.get('observaciones') or ''
        productos = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        dias_form = request.form.getlist('dias_renta[]')
        costos = request.form.getlist('costo_unitario[]')

        if not nueva_fecha_salida:
            flash("Debes ingresar la nueva fecha de salida para renovar la renta.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))

        # Obtener datos de la renta original
        cursor.execute(
            "SELECT cliente_id, direccion_obra, id_sucursal, costo_traslado, traslado "
            "FROM rentas WHERE id = %s", (renta_id,)
        )
        renta_original = cursor.fetchone()
        if not renta_original:
            flash("La renta original no existe.", "danger")
            return redirect(url_for('rentas.modulo_rentas'))
        
        fecha_registro = get_local_now()
        costo_traslado = renta_original[3] or 0
        traslado = renta_original[4] or 'ninguno'

        # Insertar nueva renta hija con estado 'activa renovación'
        cursor.execute("""
            INSERT INTO rentas (
                cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                direccion_obra, estado_renta, estado_pago, metodo_pago,
                total, iva, total_con_iva, observaciones, fecha_programada, id_sucursal,
                costo_traslado, traslado, renta_asociada_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            renta_original[0], fecha_registro, nueva_fecha_salida, fecha_entrada,
            renta_original[1], 'activa renovación', 'Pago pendiente', 'Pendiente',
            0, 0, 0, observaciones, None, renta_original[2],
            costo_traslado, traslado, renta_id
        ))
        nueva_renta_id = cursor.lastrowid

        # Insertar productos renovados en renta_detalle
        total = 0
        for prod_id_raw, cant_raw, dias_raw, costo_raw in zip_longest(productos, cantidades, dias_form, costos):
            # Saltar si algún dato es inválido
            if not prod_id_raw or not cant_raw:
                continue
            try:
                prod_id = int(prod_id_raw)
                cant = int(cant_raw)
            except ValueError:
                continue

            # Buscar el precio unitario original de la renta padre
            cursor.execute("SELECT costo_unitario FROM renta_detalle WHERE renta_id = %s AND id_producto = %s LIMIT 1", (renta_id, prod_id))
            result = cursor.fetchone()
            if result:
                costo_unitario = float(result[0])
            else:
                costo_unitario = 0.0

            # Calcular días según fechas o datos existentes
            if fecha_entrada:
                try:
                    fecha_salida_dt = datetime.strptime(nueva_fecha_salida, "%Y-%m-%d")
                    fecha_entrada_dt = datetime.strptime(fecha_entrada, "%Y-%m-%d")
                    dias_renta = (fecha_entrada_dt - fecha_salida_dt).days + 1
                    if dias_renta < 1:
                        dias_renta = 1
                except:
                    dias_renta = int(dias_raw) if dias_raw else 1
            else:
                dias_renta = int(dias_raw) if dias_raw else 1
                if dias_renta < 1:
                    dias_renta = 1

            subtotal = cant * dias_renta * costo_unitario
            total += subtotal

            cursor.execute("""
                INSERT INTO renta_detalle (
                    renta_id, id_producto, cantidad, dias_renta,
                    costo_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (nueva_renta_id, prod_id, cant, dias_renta, costo_unitario, subtotal))

        # Actualizar totales de la renta hija
        total_iva = total * 0.16
        total_con_iva = total + total_iva
        cursor.execute("""
            UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
        """, (total, total_iva, total_con_iva, nueva_renta_id))

        conn.commit()
        flash(f"Renta renovada con éxito (nueva renta ID {nueva_renta_id}).", "success")

    except Exception as e:
        if conn:
            conn.rollback()
        flash(f"Error al renovar la renta: {e}", "danger")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return redirect(url_for('rentas.modulo_rentas'))


###########################################################
# ======================= API: RENTAS PENDIENTES =======================
@rentas_bp.route('/api/rentas_pendientes/<int:renta_id>')
@requiere_sesion()
@requiere_permiso('ver_rentas')
def api_rentas_pendientes(renta_id):
    """Endpoint para obtener productos pendientes de una renta"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Obtener datos básicos de la renta
        cursor.execute("""
            SELECT r.direccion_obra, c.nombre as cliente_nombre
            FROM rentas r
            JOIN clientes c ON r.cliente_id = c.id
            WHERE r.id = %s
        """, (renta_id,))
        
        renta_data = cursor.fetchone()
        if not renta_data:
            return jsonify({'success': False, 'error': 'Renta no encontrada'})
        
        # Obtener productos pendientes
        cursor.execute("""
            SELECT 
                dr.producto_id,
                p.nombre as nombre_producto,
                pi.nombre as nombre_pieza,
                dr.cantidad_pendiente
            FROM detalle_renta dr
            JOIN productos p ON dr.producto_id = p.id
            LEFT JOIN piezas pi ON dr.pieza_id = pi.id
            WHERE dr.renta_id = %s AND dr.cantidad_pendiente > 0
        """, (renta_id,))
        
        productos_pendientes = []
        for row in cursor.fetchall():
            productos_pendientes.append({
                'producto_id': row[0],
                'nombre_producto': row[1],
                'nombre_pieza': row[2] or '',
                'cantidad_pendiente': row[3]
            })
        
        return jsonify({
            'success': True,
            'direccion_obra': renta_data[0] or '',
            'cliente_nombre': renta_data[1] or '',
            'pendientes': productos_pendientes
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


###########################################################
# ======================= CREAR RENOVACIÓN DE PENDIENTES =======================
@rentas_bp.route('/renovacion_pendientes/<int:renta_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_renovacion_pendiente')
def crear_renovacion_pendientes(renta_id):
    """Endpoint para crear renovación de productos pendientes"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('fecha_salida') or not data.get('fecha_entrada'):
            return jsonify({'success': False, 'error': 'Fechas son requeridas'})
        
        # Obtener datos de la renta original
        cursor.execute("""
            SELECT cliente_id, sucursal_id, id_sucursal 
            FROM rentas WHERE id = %s
        """, (renta_id,))
        
        renta_original = cursor.fetchone()
        if not renta_original:
            return jsonify({'success': False, 'error': 'Renta original no encontrada'})
        
        # Crear nueva renta para la renovación
        cursor.execute("""
            INSERT INTO rentas (
                cliente_id, sucursal_id, id_sucursal, fecha_salida, fecha_entrada,
                direccion_obra, traslado_extra, costo_traslado_extra, 
                factura_legal, estado, renta_asociada_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'activa', %s)
        """, (
            renta_original[0], renta_original[1], renta_original[2],
            data['fecha_salida'], data['fecha_entrada'],
            data.get('direccion_obra', ''),
            data.get('traslado_extra', 'ninguno'),
            data.get('costo_traslado_extra', 0),
            data.get('factura_legal', 0),
            renta_id
        ))
        
        nueva_renta_id = cursor.lastrowid
        
        # Copiar productos pendientes a la nueva renta
        total = 0
        for pendiente in data.get('pendientes', []):
            # Obtener el precio original de la renta padre
            cursor.execute("""
                SELECT costo_unitario, dias_renta
                FROM renta_detalle
                WHERE renta_id = %s AND id_producto = %s
                LIMIT 1
            """, (renta_id, pendiente['producto_id']))
            result = cursor.fetchone()
            if result:
                costo_unitario = float(result[0])
            else:
                costo_unitario = 0.0
            # Calcular días de renta
            fecha_salida = datetime.strptime(data['fecha_salida'], '%Y-%m-%dT%H:%M')
            fecha_entrada = datetime.strptime(data['fecha_entrada'], '%Y-%m-%dT%H:%M')
            dias = (fecha_entrada - fecha_salida).days + 1
            if dias < 1:
                dias = 1
            # Insertar en detalle_renta (o renta_detalle si corresponde)
            cursor.execute("""
                INSERT INTO renta_detalle (
                    renta_id, id_producto, cantidad, dias_renta,
                    costo_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                nueva_renta_id, pendiente['producto_id'],
                pendiente['cantidad_pendiente'], dias,
                costo_unitario, pendiente['cantidad_pendiente'] * dias * costo_unitario
            ))
            total += pendiente['cantidad_pendiente'] * costo_unitario * dias
        
        # Agregar costo de traslado
        total += data.get('costo_traslado_extra', 0)
        
        # Calcular IVA y total final
        iva = total * 0.16
        total_con_iva = total + iva
        
        # Actualizar totales de la nueva renta
        cursor.execute("""
            UPDATE rentas SET total = %s, iva = %s, total_con_iva = %s
            WHERE id = %s
        """, (total, iva, total_con_iva, nueva_renta_id))
        
        # Actualizar estado de la renta original a 'renovación finalizada'
        cursor.execute("""
            UPDATE rentas SET estado = 'renovación finalizada'
            WHERE id = %s
        """, (renta_id,))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'nueva_renta_id': nueva_renta_id,
            'message': 'Renovación creada exitosamente'
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
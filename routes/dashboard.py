# routes/dashboard.py - Versión completa

from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from utils.db import get_db_connection
from utils.datetime_utils import get_local_now, format_datetime_local
from datetime import datetime, timedelta
from utils.decorators import requiere_sesion, requiere_permiso

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@requiere_sesion()
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Obtener sucursal del usuario
    sucursal_id = session.get('sucursal_id')
    es_admin = session.get('rol_id') == 2
    
    # Determinar filtro de sucursal
    where_sucursal = ""
    params = []
    if not es_admin and sucursal_id:
        where_sucursal = "WHERE r.id_sucursal = %s"
        params = [sucursal_id]
    elif es_admin and sucursal_id and sucursal_id != 'todas':
        where_sucursal = "WHERE r.id_sucursal = %s"
        params = [sucursal_id]
    
    try:
        # 1. RENTAS A VENCER (el equipo debe regresar HOY)
        # Incluye: rentas originales sin renovaciones activas + renovaciones activas que vencen hoy
        cursor.execute(f"""
            (
                SELECT r.id, r.fecha_entrada, r.direccion_obra,
                       CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                       c.telefono, s.nombre as sucursal_nombre,
                       r.fecha_salida, r.estado_renta, 'original' as tipo_renta
                FROM rentas r
                JOIN clientes c ON r.cliente_id = c.id
                JOIN sucursales s ON r.id_sucursal = s.id
                {where_sucursal}
                {"AND" if where_sucursal else "WHERE"} r.estado_renta IN ('Activo', 'en curso')
                AND DATE(r.fecha_entrada) = CURDATE()
                AND r.renta_asociada_id IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM rentas rn 
                    WHERE rn.renta_asociada_id = r.id 
                    AND rn.estado_renta IN ('activa renovación', 'activo')
                )
            )
            UNION ALL
            (
                SELECT r.id, r.fecha_entrada, r.direccion_obra,
                       CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                       c.telefono, s.nombre as sucursal_nombre,
                       r.fecha_salida, r.estado_renta, 'renovacion' as tipo_renta
                FROM rentas r
                JOIN clientes c ON r.cliente_id = c.id
                JOIN sucursales s ON r.id_sucursal = s.id
                {where_sucursal}
                {"AND" if where_sucursal else "WHERE"} r.estado_renta IN ('activa renovación', 'activo')
                AND DATE(r.fecha_entrada) = CURDATE()
                AND r.renta_asociada_id IS NOT NULL
            )
            ORDER BY fecha_entrada ASC
            LIMIT 10
        """, params + params)
        rentas_a_vencer = cursor.fetchall()
        
        # 2. RENTAS VENCIDAS (el equipo ya debía haber regresado)
        # Incluye: rentas originales sin renovaciones activas + renovaciones activas vencidas
        cursor.execute(f"""
            (
                SELECT r.id, r.fecha_entrada, r.direccion_obra,
                       CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                       c.telefono, s.nombre as sucursal_nombre,
                       DATEDIFF(CURDATE(), DATE(r.fecha_entrada)) as dias_vencida,
                       r.fecha_salida, r.estado_renta, 'original' as tipo_renta
                FROM rentas r
                JOIN clientes c ON r.cliente_id = c.id
                JOIN sucursales s ON r.id_sucursal = s.id
                {where_sucursal}
                {"AND" if where_sucursal else "WHERE"} r.estado_renta IN ('Activo', 'en curso')
                AND DATE(r.fecha_entrada) < CURDATE()
                AND r.renta_asociada_id IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM rentas rn 
                    WHERE rn.renta_asociada_id = r.id 
                    AND rn.estado_renta IN ('activa renovación', 'activo')
                )
            )
            UNION ALL
            (
                SELECT r.id, r.fecha_entrada, r.direccion_obra,
                       CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                       c.telefono, s.nombre as sucursal_nombre,
                       DATEDIFF(CURDATE(), DATE(r.fecha_entrada)) as dias_vencida,
                       r.fecha_salida, r.estado_renta, 'renovacion' as tipo_renta
                FROM rentas r
                JOIN clientes c ON r.cliente_id = c.id
                JOIN sucursales s ON r.id_sucursal = s.id
                {where_sucursal}
                {"AND" if where_sucursal else "WHERE"} r.estado_renta IN ('activa renovación', 'activo')
                AND DATE(r.fecha_entrada) < CURDATE()
                AND r.renta_asociada_id IS NOT NULL
            )
            ORDER BY dias_vencida DESC, fecha_entrada ASC
            LIMIT 10
        """, params + params)
        rentas_vencidas = cursor.fetchall()
        
        # 3. RENTAS PROGRAMADAS (rentas con fecha futura programada)
        cursor.execute(f"""
            SELECT r.id, r.fecha_programada as fecha_entrada, r.direccion_obra,
                   CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                   c.telefono, s.nombre as sucursal_nombre,
                   r.fecha_salida, r.estado_renta,
                   DATEDIFF(DATE(r.fecha_programada), CURDATE()) as dias_para_inicio
            FROM rentas r
            JOIN clientes c ON r.cliente_id = c.id
            JOIN sucursales s ON r.id_sucursal = s.id
            {where_sucursal}
            {"AND" if where_sucursal else "WHERE"} r.estado_renta = 'programada'
            AND r.fecha_programada IS NOT NULL
            AND DATE(r.fecha_programada) >= CURDATE()
            ORDER BY r.fecha_programada ASC
            LIMIT 10
        """, params)
        rentas_programadas = cursor.fetchall()
        
        # 4. PAGOS PENDIENTES UNIFICADOS (retrasos, extras, saldos, pagos)
        cursor.execute(f"""
            (
                SELECT 'retraso' as tipo_pago, ncr.id as pago_id, ncr.fecha as fecha_pago, 
                       ncr.total, ncr.estado_pago,
                       r.id as renta_id, r.direccion_obra,
                       CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                       c.telefono, s.nombre as sucursal_nombre,
                       ncr.observaciones, ncr.total as monto_pendiente
                FROM notas_cobro_retraso ncr
                JOIN notas_entrada ne ON ncr.nota_entrada_id = ne.id
                JOIN rentas r ON ne.renta_id = r.id
                JOIN clientes c ON r.cliente_id = c.id
                JOIN sucursales s ON r.id_sucursal = s.id
                {where_sucursal}
                {"AND" if where_sucursal else "WHERE"} ncr.estado_pago = 'Retraso Pendiente'
            )
            UNION ALL
            (
                SELECT 'extra' as tipo_pago, r.id as pago_id, r.fecha_entrada as fecha_pago,
                       0 as total, r.estado_cobro_extra as estado_pago,
                       r.id as renta_id, r.direccion_obra,
                       CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                       c.telefono, s.nombre as sucursal_nombre,
                       'Cobro extra pendiente' as observaciones, 0 as monto_pendiente
                FROM rentas r
                JOIN clientes c ON r.cliente_id = c.id
                JOIN sucursales s ON r.id_sucursal = s.id
                {where_sucursal}
                {"AND" if where_sucursal else "WHERE"} r.estado_cobro_extra = 'Extra Pendiente'
            )
            UNION ALL
            (
                SELECT 'saldo' as tipo_pago, r.id as pago_id, r.fecha_salida as fecha_pago,
                       r.total_con_iva, r.estado_pago,
                       r.id as renta_id, r.direccion_obra,
                       CONCAT(c.nombre, ' ', c.apellido1, ' ', c.apellido2) as cliente_nombre,
                       c.telefono, s.nombre as sucursal_nombre,
                       'Saldo pendiente de renta' as observaciones,
                       (r.total_con_iva - COALESCE(SUM(p.monto), 0)) as monto_pendiente
                FROM rentas r
                JOIN clientes c ON r.cliente_id = c.id
                JOIN sucursales s ON r.id_sucursal = s.id
                LEFT JOIN prefacturas p ON p.renta_id = r.id AND p.pagada = 1
                {where_sucursal}
                {"AND" if where_sucursal else "WHERE"} r.estado_pago IN ('Pago Pendiente', 'Saldo Pendiente')
                GROUP BY r.id, r.total_con_iva, c.nombre, c.apellido1, c.apellido2, c.telefono, s.nombre, r.direccion_obra, r.fecha_salida, r.estado_pago
                HAVING monto_pendiente > 0
            )
            ORDER BY fecha_pago ASC
            LIMIT 15
        """, params * 3)
        pagos_pendientes = cursor.fetchall()
        
        # 6. OBTENER NOTAS DEL BLOC (crear tabla si no existe)
        try:
            cursor.execute("SELECT * FROM dashboard_notas ORDER BY created_at DESC LIMIT 10")
            notas_bloc = cursor.fetchall()
        except:
            # Crear tabla de notas si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_notas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nota TEXT NOT NULL,
                    usuario_id INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            notas_bloc = []
        
        cursor.close()
        conn.close()
        
        return render_template('dashboard/dashboard.html',
                             rentas_a_vencer=rentas_a_vencer,
                             rentas_vencidas=rentas_vencidas,
                             rentas_programadas=rentas_programadas,
                             pagos_pendientes=pagos_pendientes,
                             notas_bloc=notas_bloc)
    except Exception as e:
        cursor.close()
        conn.close()
        return render_template('dashboard/dashboard.html', error=str(e))

# APIs para el bloc de notas
@dashboard_bp.route('/notas', methods=['POST'])
@requiere_sesion()
def agregar_nota():
    data = request.get_json()
    nota = data.get('nota', '').strip()
    
    if not nota:
        return jsonify({'success': False, 'error': 'Nota vacía'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO dashboard_notas (nota, usuario_id) 
            VALUES (%s, %s)
        """, (nota, session.get('user_id')))
        conn.commit()
        
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@dashboard_bp.route('/notas/<int:nota_id>', methods=['DELETE'])
@requiere_sesion()
def eliminar_nota(nota_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM dashboard_notas WHERE id = %s", (nota_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})
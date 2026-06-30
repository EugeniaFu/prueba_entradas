# routes/dashboard.py - Versión completa

from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from utils.db import get_db_connection
from utils.datetime_utils import get_local_now, format_datetime_local
from datetime import datetime, timedelta
from utils.decorators import requiere_sesion, requiere_permiso

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


def _asegurar_tabla_dashboard_notas(cursor):
    """Crea dashboard_notas si no existe, y agrega la columna sucursal_id si
    la tabla ya existía de antes sin ella (migración perezosa)."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_notas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nota TEXT NOT NULL,
            usuario_id INT,
            sucursal_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("SELECT sucursal_id FROM dashboard_notas LIMIT 1")
        cursor.fetchall()
    except Exception:
        cursor.execute("ALTER TABLE dashboard_notas ADD COLUMN sucursal_id INT")


def _obtener_sucursal_matriz_id(cursor):
    """ID de la sucursal que se usa como default del dashboard para el admin.
    Se busca por nombre (Matriz) y si no existe se cae a la sucursal activa
    con el id más chico, para no romper si todavía no hay una 'Matriz'."""
    cursor.execute("""
        SELECT id FROM sucursales
        WHERE activo = 1 AND nombre LIKE %s
        ORDER BY id LIMIT 1
    """, ('%matriz%',))
    row = cursor.fetchone()
    if row:
        return row['id']
    cursor.execute("SELECT id FROM sucursales WHERE activo = 1 ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    return row['id'] if row else None


@dashboard_bp.route('/')
@requiere_sesion()
@requiere_permiso('ver_dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener sucursal del usuario
    sucursal_id_usuario = session.get('sucursal_id')
    es_admin = (sucursal_id_usuario is None)

    sucursales_selector = []
    sucursal_id = None  # None = "todas" (solo posible para admin)

    if es_admin:
        cursor.execute("SELECT id, nombre FROM sucursales WHERE activo = 1 ORDER BY nombre")
        sucursales_selector = cursor.fetchall()

        param = request.args.get('sucursal_id', '').strip()
        if param == 'todas':
            sucursal_id = None
        elif param:
            try:
                sucursal_id = int(param)
            except ValueError:
                sucursal_id = _obtener_sucursal_matriz_id(cursor)
        else:
            # Sin selección explícita: default a Matriz Colosio
            sucursal_id = _obtener_sucursal_matriz_id(cursor)
    else:
        sucursal_id = sucursal_id_usuario

    # Determinar filtro de sucursal
    where_sucursal = ""
    params = []
    if sucursal_id:
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
                    AND rn.estado_renta IN ('activa renovacion', 'activo')
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
                {"AND" if where_sucursal else "WHERE"} r.estado_renta IN ('activa renovacion', 'activo')
                AND DATE(r.fecha_entrada) = CURDATE()
                AND r.renta_asociada_id IS NOT NULL
            )
            ORDER BY fecha_entrada ASC
        """, params + params)
        rentas_a_vencer = cursor.fetchall()
        
        # 2. RENTAS VENCIDAS (el equipo ya debía haber regresado)
        # Incluye: rentas originales sin renovaciones vigentes + renovaciones vencidas
        # NO incluye rentas cuya renovación más reciente está aún vigente
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
                    AND rn.estado_renta IN ('activa renovacion', 'activo')
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
                {"AND" if where_sucursal else "WHERE"} r.estado_renta IN ('activa renovacion', 'activo')
                AND DATE(r.fecha_entrada) < CURDATE()
                AND r.renta_asociada_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM rentas rn_posterior
                    WHERE rn_posterior.renta_asociada_id = r.renta_asociada_id
                    AND rn_posterior.id > r.id
                )
            )
            ORDER BY dias_vencida DESC, fecha_entrada ASC
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
        """, params * 3)
        pagos_pendientes = cursor.fetchall()
        
        # 6. OBTENER NOTAS DEL BLOC (crear tabla/columna si no existen)
        _asegurar_tabla_dashboard_notas(cursor)
        conn.commit()

        if sucursal_id:
            cursor.execute("""
                SELECT id, nota, created_at
                FROM dashboard_notas
                WHERE sucursal_id = %s
                ORDER BY created_at DESC
            """, (sucursal_id,))
            notas_bloc = cursor.fetchall()
        else:
            # "Todas las sucursales" seleccionado: una nota es de UNA sucursal
            # específica, así que aquí no se muestra ni se puede crear ninguna.
            notas_bloc = []

        cursor.close()
        conn.close()

        return render_template('dashboard/dashboard.html',
                             rentas_a_vencer=rentas_a_vencer,
                             rentas_vencidas=rentas_vencidas,
                             rentas_programadas=rentas_programadas,
                             pagos_pendientes=pagos_pendientes,
                             notas_bloc=notas_bloc,
                             es_admin=es_admin,
                             sucursales_selector=sucursales_selector,
                             sucursal_seleccionada=sucursal_id)
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
    usuario_id = session.get('user_id')

    sucursal_id_usuario = session.get('sucursal_id')
    es_admin = (sucursal_id_usuario is None)

    if es_admin:
        # El admin puede estar viendo el dashboard de cualquier sucursal; la
        # nota se guarda en la que tenga seleccionada en ese momento.
        try:
            sucursal_id = int(data.get('sucursal_id'))
        except (TypeError, ValueError):
            sucursal_id = None
    else:
        # Para la secretaria, siempre se fuerza su propia sucursal de sesión
        # (no se confía en lo que mande el navegador).
        sucursal_id = sucursal_id_usuario

    if not nota:
        return jsonify({'success': False, 'error': 'Nota vacía'})

    if not sucursal_id:
        return jsonify({'success': False, 'error': 'Selecciona una sucursal específica para poder agregar notas.'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        _asegurar_tabla_dashboard_notas(cursor)

        cursor.execute("SELECT id FROM sucursales WHERE id = %s", (sucursal_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': 'Sucursal inválida'})

        cursor.execute("""
            INSERT INTO dashboard_notas (nota, usuario_id, sucursal_id)
            VALUES (%s, %s, %s)
        """, (nota, usuario_id, sucursal_id))

        conn.commit()
        return jsonify({'success': True})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

    finally:
        cursor.close()
        conn.close()

@dashboard_bp.route('/notas/<int:nota_id>', methods=['DELETE'])
@requiere_sesion()
def eliminar_nota(nota_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        sucursal_id_usuario = session.get('sucursal_id')
        es_admin = (sucursal_id_usuario is None)

        if not es_admin:
            # La secretaria solo puede borrar notas de su propia sucursal.
            cursor.execute("SELECT sucursal_id FROM dashboard_notas WHERE id = %s", (nota_id,))
            nota = cursor.fetchone()
            if not nota or nota['sucursal_id'] != sucursal_id_usuario:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'No tienes permiso para eliminar esta nota'}), 403

        cursor.execute("DELETE FROM dashboard_notas WHERE id = %s", (nota_id,))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})
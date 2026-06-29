from flask import session
from datetime import datetime, timedelta
from utils.db import get_db_connection
from utils.folios import obtener_siguiente_folio_renta_sucursal, obtener_siguiente_folio_nota_sucursal
from utils.datetime_utils import get_local_now_naive

class RentasService:
    @staticmethod
    def obtener_rentas_por_sucursal_y_estado(sucursal_actual_id, es_admin, estado_filtro):
        """
        Retorna las rentas basándose en la sucursal actual (para admin o empleado) 
        y el estado (activas o finalizadas/pagadas).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Determinamos si se filtra por una sucursal específica o no (admin puede ver todas)
            if es_admin and sucursal_actual_id == 'todas':
                where_sucursal = "WHERE 1=1"
                params_sucursal = ()
            else:
                where_sucursal = "WHERE r.id_sucursal = %s"
                params_sucursal = (sucursal_actual_id,)
            
            # Filtros de estado por defecto en la plataforma
            if estado_filtro == 'activas':
                filtro_estado = """
                HAVING (
                    LOWER(TRIM(estado_renta)) IN ('en curso', 'activo', 'activa renovacion', 'en recolección', 'programada', 'entrega parcial')

                    OR (
                        LOWER(TRIM(estado_renta)) = 'finalizada'
                        AND LOWER(TRIM(estado_pago)) IN ('pago pendiente', 'saldo pendiente')
                    )
                    OR piezas_pendientes > 0
                    OR estado_retraso = 'Retraso Pendiente'
                    OR estado_cobro_extra = 'Extra Pendiente'
                )
                """
            elif estado_filtro == 'pagadas':
                filtro_estado = """
                HAVING (
                    (LOWER(TRIM(estado_renta)) = 'finalizada' AND LOWER(TRIM(estado_pago)) = 'pago realizado' AND piezas_pendientes = 0)
                    OR LOWER(TRIM(estado_renta)) = 'cancelada'
                )
                AND (estado_retraso IS NULL OR estado_retraso != 'Retraso Pendiente')
                AND (estado_cobro_extra IS NULL OR estado_cobro_extra != 'Extra Pendiente')
                """
            else:
                filtro_estado = ""
                
            query = f"""
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
                (
                    SELECT COUNT(*)
                    FROM rentas r_hija
                    WHERE r_hija.renta_asociada_id = r.id AND r_hija.estado_renta = 'activa renovacion'
                ) AS tiene_renovaciones,
                r.renta_asociada_id,
                r.id_sucursal,
                r.folio AS folio_sucursal,
                s.nombre AS sucursal_nombre,
                ncr.id AS cobro_retraso_id,
                (SELECT r3.folio FROM rentas r3 WHERE r3.id = r.renta_asociada_id) AS folio_asociado,
                (
                    SELECT CASE
                        WHEN COUNT(*) = 0 THEN 0
                        WHEN (SELECT es_entrega_parcial FROM notas_salida WHERE renta_id = r.id ORDER BY id DESC LIMIT 1) = 1 THEN 0
                        ELSE 1
                    END
                    FROM notas_salida ns WHERE ns.renta_id = r.id
                ) AS tiene_nota_salida

            FROM rentas r
            JOIN clientes c ON r.cliente_id = c.id
            JOIN sucursales s ON r.id_sucursal = s.id
            LEFT JOIN notas_entrada ne ON ne.renta_id = r.id
                AND ne.id = (SELECT MAX(id) FROM notas_entrada WHERE renta_id = r.id)
            LEFT JOIN notas_cobro_extra nce ON nce.nota_entrada_id = ne.id
            LEFT JOIN notas_cobro_retraso ncr ON ncr.nota_entrada_id = ne.id

            {where_sucursal}
            {filtro_estado}

            ORDER BY r.id DESC
            """
            
            cursor.execute(query, params_sucursal)
            return cursor.fetchall()
            
        except Exception as e:
            print(f"Error en RentasService.obtener_rentas_por_sucursal_y_estado: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def crear_nueva_renta(datos_renta, sucursal_id, es_admin, productos, cantidades, dias, costos, precios_base, tipos_ajuste, valores_ajuste):
        """
        Calcula precios, inserta la nueva renta, inserta sus detalles 
        y actualiza los folios y totales, dentro de una transacción segura.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            conn.start_transaction()
            
            # Determinamos sucursal
            sucursal_para_renta = sucursal_id
            if not sucursal_para_renta and not es_admin: # Fail-safe si viene nulo
                raise Exception("No se pudo determinar la sucursal del empleado.")
            
            # Datos principales
            estado_renta = 'programada' if datos_renta.get('renta_programada') else 'en curso'
            estado_pago = 'Pago pendiente'
            metodo_pago = 'Pendiente'
            
            # Obtener el folio consecutivo de la sucursal (inicia en 1 por sucursal)
            folio = obtener_siguiente_folio_renta_sucursal(cursor, sucursal_para_renta)

            # Insertar cabecera de Renta (inicialmente en 0)
            cursor.execute("""
                INSERT INTO rentas (
                    cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                    direccion_obra, estado_renta, estado_pago, metodo_pago,
                    total, iva, total_con_iva, observaciones, fecha_programada, id_sucursal,
                    costo_traslado, traslado, folio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datos_renta['cliente_id'], datos_renta['fecha_registro'], datos_renta['fecha_salida'],
                datos_renta['fecha_entrada'], datos_renta['direccion_obra'], estado_renta,
                estado_pago, metodo_pago, 0, 0, 0, datos_renta['observaciones'],
                datos_renta['fecha_programada'], sucursal_para_renta,
                datos_renta['costo_traslado'], datos_renta['traslado'], folio
            ))

            renta_id = cursor.lastrowid
            
            # Procesar detalles
            total = 0
            for i in range(len(productos)):
                prod_id = int(productos[i])
                cant = int(cantidades[i])
                dias_renta_raw = dias[i]
                dias_renta = 1 if dias_renta_raw in (None, '', 'null') else max(1, int(dias_renta_raw))

                # Usar el costo_unitario que viene del frontend (ya incluye ajustes de precio)
                costo_unitario = float(costos[i])
                subtotal = cant * dias_renta * costo_unitario
                total += subtotal

                # Obtener datos de ajuste (auditoría)
                precio_base = float(precios_base[i]) if i < len(precios_base) else costo_unitario
                tipo_ajuste = tipos_ajuste[i] if i < len(tipos_ajuste) else 'ninguno'
                valor_ajuste = float(valores_ajuste[i]) if i < len(valores_ajuste) else 0

                cursor.execute("""
                    INSERT INTO renta_detalle (
                        renta_id, id_producto, cantidad, dias_renta,
                        costo_unitario, subtotal, precio_base, ajuste_tipo, ajuste_valor
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (renta_id, prod_id, cant, dias_renta, costo_unitario, subtotal, precio_base, tipo_ajuste, valor_ajuste))

            # Actualizar totales
            total += datos_renta['costo_traslado']
            iva = total * 0.16
            total_con_iva = total + iva

            cursor.execute("""
                UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
            """, (total, iva, total_con_iva, renta_id))

            conn.commit()
            return True, renta_id, sucursal_para_renta, folio, None

        except Exception as e:
            conn.rollback()
            return False, None, None, None, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_historial_cliente(cliente_id):
        """
        Devuelve el historial de rentas de un cliente, agrupando las renovaciones
        en cadena bajo su folio raíz y calculando estados/pagos/totales consolidados.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT
                    r.id, r.folio, r.id_sucursal, s.nombre AS sucursal_nombre,
                    r.fecha_registro, r.fecha_salida, r.fecha_entrada,
                    r.estado_renta, r.estado_pago, r.total_con_iva,
                    r.renta_asociada_id, r.direccion_obra,
                    ne.estado_retraso,
                    (SELECT COUNT(*) FROM notas_salida WHERE renta_id = r.id) > 0 AS tiene_salida,
                    (SELECT folio FROM notas_salida WHERE renta_id = r.id ORDER BY id DESC LIMIT 1) AS folio_salida,
                    (ne.id IS NOT NULL) AS tiene_entrada,
                    (SELECT COUNT(*) FROM prefacturas WHERE renta_id = r.id) > 0 AS tiene_prefactura,
                    nce.id AS cobro_extra_id,
                    ncr.id AS cobro_retraso_id
                FROM rentas r
                JOIN sucursales s ON r.id_sucursal = s.id
                LEFT JOIN notas_entrada ne ON ne.id = (
                    SELECT MAX(id) FROM notas_entrada WHERE renta_id = r.id
                )
                LEFT JOIN notas_cobro_extra nce ON nce.nota_entrada_id = ne.id
                LEFT JOIN notas_cobro_retraso ncr ON ncr.nota_entrada_id = ne.id
                WHERE r.cliente_id = %s AND r.estado_renta != 'eliminada'
                ORDER BY r.id ASC
            """, (cliente_id,))
            rentas = cursor.fetchall()

            # Agrupar por folio raíz (renta original de cada cadena de renovaciones)
            cadenas = {}
            orden_raiz = []
            for r in rentas:
                raiz_id = r['renta_asociada_id'] or r['id']
                if raiz_id not in cadenas:
                    cadenas[raiz_id] = []
                    orden_raiz.append(raiz_id)
                cadenas[raiz_id].append(r)

            historial = []
            for raiz_id in orden_raiz:
                eslabones = cadenas[raiz_id]
                raiz = eslabones[0]
                actual = eslabones[-1]

                estados_pago = [e['estado_pago'] or '' for e in eslabones]
                num_pagos_pendientes = sum(1 for ep in estados_pago if 'pendiente' in ep.lower())

                estado_renta_actual = (actual['estado_renta'] or '').lower().strip()
                if estado_renta_actual == 'cancelada':
                    estado_consolidado = 'Cancelada'
                elif estado_renta_actual == 'finalizada':
                    estado_consolidado = 'Finalizada'
                else:
                    estado_consolidado = 'Activa'

                tiene_retraso = any((e['estado_retraso'] or '') == 'Retraso Pendiente' for e in eslabones)
                total_acumulado = sum(float(e['total_con_iva'] or 0) for e in eslabones)

                historial.append({
                    'raiz_id': raiz_id,
                    'renta_id_actual': actual['id'],
                    'folio': raiz['folio'],
                    'id_sucursal': raiz['id_sucursal'],
                    'folio_salida': raiz['folio_salida'],
                    'sucursal_nombre': raiz['sucursal_nombre'],
                    'fecha_inicio': raiz['fecha_salida'],
                    'fecha_fin': actual['fecha_entrada'] if estado_renta_actual == 'finalizada' else None,
                    'direccion_obra': actual['direccion_obra'],
                    'estado_consolidado': estado_consolidado,
                    'num_pagos_pendientes': num_pagos_pendientes,
                    'num_renovaciones': len(eslabones),
                    'tiene_retraso': tiene_retraso,
                    'total_acumulado': total_acumulado,
                    'eslabones': eslabones
                })

            historial.sort(key=lambda h: h['raiz_id'], reverse=True)
            return historial
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_sucursales():
        """Obtiene todas las sucursales del sistema."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, nombre FROM sucursales ORDER BY id")
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def actualizar_fecha_entrada(renta_id, nueva_fecha_obj):
        """
        Actualiza la fecha de entrada de la renta, re-calcula los días y subtotales,
        y actualiza los totales finales.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            conn.start_transaction()

            # Obtener fecha_salida actual para calcular días
            cursor.execute("SELECT fecha_salida, costo_traslado FROM rentas WHERE id = %s", (renta_id,))
            fila = cursor.fetchone()
            if not fila:
                raise ValueError("Renta no encontrada")

            fecha_salida = fila[0]
            costo_traslado = float(fila[1] or 0)

            if not fecha_salida:
                raise ValueError("Fecha de salida no definida para esta renta")

            # Calcular días de renta
            dias_renta = (nueva_fecha_obj - fecha_salida).days + 1
            if dias_renta < 1:
                dias_renta = 1

            # Actualizar fecha_entrada en rentas
            cursor.execute("UPDATE rentas SET fecha_entrada = %s WHERE id = %s", (nueva_fecha_obj, renta_id))

            # Obtener detalles con id_producto para recalcular precios
            cursor.execute("SELECT id, id_producto, cantidad FROM renta_detalle WHERE renta_id = %s", (renta_id,))
            detalles = cursor.fetchall()

            total = 0
            for detalle in detalles:
                detalle_id, prod_id, cantidad = detalle
                
                # Obtener precios del producto
                cursor.execute("SELECT precio_dia, precio_14_dias, precio_29_dias, precio_30_dias FROM producto_precios WHERE id_producto = %s", (prod_id,))
                precios = cursor.fetchone()
                cursor.execute("SELECT precio_unico FROM productos WHERE id_producto = %s", (prod_id,))
                precio_unico_row = cursor.fetchone()
                precio_unico = precio_unico_row[0] if precio_unico_row else 0

                # Recalcular precio según días (misma lógica que crear_nueva_renta)
                if precio_unico == 1:
                    costo_unitario = float(precios[0])
                else:
                    if dias_renta <= 2:
                        costo_unitario = float(precios[0])
                    elif dias_renta <= 14:
                        costo_unitario = float(precios[1])
                    elif dias_renta <= 29:
                        costo_unitario = float(precios[2])
                    else:
                        costo_unitario = float(precios[3])

                subtotal = cantidad * dias_renta * costo_unitario
                cursor.execute("""
                    UPDATE renta_detalle SET dias_renta = %s, costo_unitario = %s, subtotal = %s WHERE id = %s
                """, (dias_renta, costo_unitario, subtotal, detalle_id))
                total += subtotal

            total += costo_traslado
            iva = total * 0.16
            total_con_iva = total + iva

            # Actualizar totales en rentas
            cursor.execute("""
                UPDATE rentas SET total = %s, iva = %s, total_con_iva = %s WHERE id = %s
            """, (total, iva, total_con_iva, renta_id))

            conn.commit()
            return True, "Fecha de entrada y totales actualizados correctamente"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _calcular_piezas_pendientes_renta(cursor, padre_real_id):
        """
        Suma todas las notas de salida de la renta (raíz) menos todas las notas de
        entrada ya registradas (incluyendo renovaciones), por pieza.
        """
        cursor.execute("""
            SELECT
                entregado.id_pieza,
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
                WHERE ne.renta_id = %s OR ne.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = %s)
                GROUP BY ned.id_pieza
            ) recibido ON entregado.id_pieza = recibido.id_pieza
            HAVING cantidad_pendiente > 0
        """, (padre_real_id, padre_real_id, padre_real_id))
        return cursor.fetchall()

    @staticmethod
    def obtener_rentas_pendientes_cliente(cliente_id, sucursal_id):
        """
        Lista las rentas activas de un cliente en una sucursal dada que aún tienen
        piezas pendientes de regresar. Es la base de la nota de entrada múltiple:
        permite elegir cuáles de esas rentas se devuelven juntas en un solo folio.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT r.id, r.folio, r.direccion_obra, r.fecha_salida, r.fecha_entrada,
                       r.estado_renta, r.renta_asociada_id, r.traslado
                FROM rentas r
                WHERE r.cliente_id = %s AND r.id_sucursal = %s
                  AND LOWER(TRIM(r.estado_renta)) IN ('en curso', 'activo', 'activa renovacion', 'programada', 'en recolección')
                ORDER BY r.id ASC
            """, (cliente_id, sucursal_id))
            rentas = cursor.fetchall()

            resultado = []
            for renta in rentas:
                padre_real_id = renta['renta_asociada_id'] or renta['id']

                cursor.execute("""
                    SELECT id AS nota_salida_id, folio AS folio_salida
                    FROM notas_salida WHERE renta_id = %s ORDER BY id DESC LIMIT 1
                """, (padre_real_id,))
                ns_row = cursor.fetchone()
                if not ns_row:
                    continue
                folio_salida = ns_row['folio_salida']

                cursor.execute("""
                    SELECT
                        entregado.id_pieza, p.nombre_pieza,
                        (entregado.cantidad_salida - IFNULL(recibido.cantidad_recibida_total, 0)) AS cantidad_pendiente
                    FROM (
                        SELECT nsd.id_pieza, SUM(nsd.cantidad) AS cantidad_salida
                        FROM notas_salida ns
                        JOIN notas_salida_detalle nsd ON ns.id = nsd.nota_salida_id
                        WHERE ns.renta_id = %s
                        GROUP BY nsd.id_pieza
                    ) entregado
                    JOIN piezas p ON p.id_pieza = entregado.id_pieza
                    LEFT JOIN (
                        SELECT ned.id_pieza, SUM(ned.cantidad_recibida) AS cantidad_recibida_total
                        FROM notas_entrada ne
                        JOIN notas_entrada_detalle ned ON ne.id = ned.nota_entrada_id
                        WHERE ne.renta_id = %s OR ne.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = %s)
                        GROUP BY ned.id_pieza
                    ) recibido ON entregado.id_pieza = recibido.id_pieza
                    HAVING cantidad_pendiente > 0
                    ORDER BY p.nombre_pieza
                """, (padre_real_id, padre_real_id, padre_real_id))
                piezas_pendientes = cursor.fetchall()

                if not piezas_pendientes:
                    continue

                resultado.append({
                    'renta_id': renta['id'],
                    'folio': renta['folio'],
                    'folio_salida': folio_salida,
                    'nota_salida_id': ns_row['nota_salida_id'],
                    'direccion_obra': renta['direccion_obra'],
                    'traslado': renta['traslado'] or 'ninguno',
                    'fecha_salida': renta['fecha_salida'].strftime('%Y-%m-%d') if renta['fecha_salida'] else None,
                    'fecha_entrada': renta['fecha_entrada'].strftime('%Y-%m-%d') if renta['fecha_entrada'] else None,
                    'piezas': piezas_pendientes
                })

            return resultado
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def crear_nota_entrada_consolidada(cliente_id, sucursal_id, rentas_payload, observaciones, usuario_id):
        """
        Crea UNA sola nota de entrada que consolida la devolución completa de varias
        rentas del mismo cliente y sucursal, cuando el cliente trae el equipo él
        mismo (no hay viaje de recolección que esperar, por lo que se conocen las
        cantidades finales desde el principio). Solo se permite cuando cada renta
        incluida cierra al 100% (sin piezas pendientes); si alguna queda parcial,
        se rechaza y debe devolverse aparte con el flujo normal de una sola renta.

        Si el cliente solicita un traslado (o alguna renta ya lo tenía pagado), eso
        ya no pasa por aquí: se maneja como despacho de recolección
        (crear_recoleccion_multiple), porque en ese caso no se conocen las
        cantidades finales hasta que el chofer regresa.
        """
        if not rentas_payload or len(rentas_payload) < 2:
            return False, None, None, "Selecciona al menos 2 rentas para consolidar."

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            info_rentas = []
            for item in rentas_payload:
                renta_id = item['renta_id']
                cursor.execute("""
                    SELECT id, cliente_id, id_sucursal, renta_asociada_id, estado_renta, folio, fecha_entrada
                    FROM rentas WHERE id = %s
                """, (renta_id,))
                renta_row = cursor.fetchone()
                if not renta_row:
                    raise ValueError(f"Renta {renta_id} no encontrada.")
                if renta_row['cliente_id'] != cliente_id or renta_row['id_sucursal'] != sucursal_id:
                    raise ValueError(f"La renta {renta_id} no pertenece a este cliente o sucursal.")
                if (renta_row['estado_renta'] or '').lower().strip() not in ('en curso', 'activo', 'activa renovacion', 'programada', 'en recolección'):
                    raise ValueError(f"La renta SUC{sucursal_id}-{renta_row['folio']} ya no admite nota de entrada.")

                padre_real_id = renta_row['renta_asociada_id'] or renta_id

                cursor.execute("""
                    SELECT id AS nota_salida_id FROM notas_salida
                    WHERE renta_id = %s ORDER BY id DESC LIMIT 1
                """, (padre_real_id,))
                ns_row = cursor.fetchone()
                if not ns_row:
                    raise ValueError(f"La renta SUC{sucursal_id}-{renta_row['folio']} no tiene nota de salida asociada.")

                # Validar que la devolución sea completa contra lo que realmente está
                # pendiente en BD (no lo que mande el cliente a ciegas desde el navegador)
                pendientes = RentasService._calcular_piezas_pendientes_renta(cursor, padre_real_id)
                pendientes_dict = {p['id_pieza']: p['cantidad_pendiente'] for p in pendientes}
                piezas_enviadas = {int(p['id_pieza']): int(p.get('cantidad_recibida', 0)) for p in item['piezas']}

                for id_pieza, pendiente in pendientes_dict.items():
                    if piezas_enviadas.get(id_pieza, 0) != pendiente:
                        raise ValueError(
                            f"La renta SUC{sucursal_id}-{renta_row['folio']} no se está devolviendo completa. "
                            "Solo se pueden consolidar rentas que cierran al 100%."
                        )

                # Calcular si esta renta en particular llega con retraso (cada
                # renta consolidada puede estar o no vencida; no se cobra aquí,
                # solo se marca para que el flujo normal de "Cobrar Retraso" la
                # detecte después)
                estado_retraso_renta = 'Sin Retraso'
                if renta_row['fecha_entrada']:
                    fecha_base = renta_row['fecha_entrada']
                    if isinstance(fecha_base, datetime):
                        fecha_base = fecha_base.date()
                    fecha_limite_dt = datetime.combine(fecha_base + timedelta(days=1), datetime.strptime('10:00', '%H:%M').time())
                    if get_local_now_naive() > fecha_limite_dt:
                        estado_retraso_renta = 'Retraso Pendiente'

                info_rentas.append({
                    'renta_id': renta_id,
                    'folio': renta_row['folio'],
                    'nota_salida_id': ns_row['nota_salida_id'],
                    'estado_retraso': estado_retraso_renta,
                    'piezas': item['piezas']
                })

            # Un solo folio de entrada compartido por todas las rentas consolidadas
            # (es solo el número impreso en el comprobante). Internamente cada renta
            # sigue generando su propia fila en notas_entrada con su propio id único,
            # exactamente igual que en el flujo normal de una sola renta.
            folio = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)

            primer_nota_entrada_id = None
            for info in info_rentas:
                cursor.execute("""
                    INSERT INTO notas_entrada (
                        folio, renta_id, nota_salida_id, fecha_entrada_real,
                        requiere_traslado_extra, costo_traslado_extra, observaciones,
                        estado, created_at, estado_retraso, accion_devolucion, usuario_id
                    ) VALUES (%s, %s, %s, NOW(), 'ninguno', 0, %s, 'normal', NOW(), %s, 'no', %s)
                """, (folio, info['renta_id'], info['nota_salida_id'], observaciones, info['estado_retraso'], usuario_id))
                nota_entrada_id = cursor.lastrowid
                if primer_nota_entrada_id is None:
                    primer_nota_entrada_id = nota_entrada_id

                hay_cobro_extra = False
                for pieza in info['piezas']:
                    id_pieza = int(pieza['id_pieza'])
                    cantidad_esperada = int(pieza.get('cantidad_esperada', 0))
                    cantidad_recibida = int(pieza.get('cantidad_recibida', 0))
                    cantidad_buena = int(pieza.get('cantidad_buena', 0))
                    cantidad_danada = int(pieza.get('cantidad_danada', 0))
                    cantidad_sucia = int(pieza.get('cantidad_sucia', 0))
                    cantidad_perdida = int(pieza.get('cantidad_perdida', 0))

                    if cantidad_danada > 0 or cantidad_sucia > 0 or cantidad_perdida > 0:
                        hay_cobro_extra = True

                    cursor.execute("""
                        INSERT INTO notas_entrada_detalle (
                            nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                            cantidad_buena, cantidad_danada, cantidad_sucia, cantidad_perdida
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                        cantidad_buena, cantidad_danada, cantidad_sucia, cantidad_perdida
                    ))

                    cursor.execute("""
                        SELECT id_inventario FROM inventario_sucursal
                        WHERE id_sucursal = %s AND id_pieza = %s
                    """, (sucursal_id, id_pieza))
                    if not cursor.fetchone():
                        continue

                    # Buenas y sucias: +disponibles, -rentadas 
                    cantidad_buena_o_sucia = cantidad_buena + cantidad_sucia
                    cursor.execute("""
                        UPDATE inventario_sucursal
                        SET disponibles = disponibles + %s, rentadas = rentadas - %s
                        WHERE id_sucursal = %s AND id_pieza = %s
                    """, (cantidad_buena_o_sucia, cantidad_buena_o_sucia, sucursal_id, id_pieza))

                    if cantidad_danada > 0:
                        cursor.execute("""
                            UPDATE inventario_sucursal
                            SET daniadas = daniadas + %s, rentadas = rentadas - %s
                            WHERE id_sucursal = %s AND id_pieza = %s
                        """, (cantidad_danada, cantidad_danada, sucursal_id, id_pieza))

                    if cantidad_perdida > 0:
                        cursor.execute("""
                            UPDATE inventario_sucursal
                            SET perdidas = perdidas + %s, rentadas = rentadas - %s, total = total - %s
                            WHERE id_sucursal = %s AND id_pieza = %s
                        """, (cantidad_perdida, cantidad_perdida, cantidad_perdida, sucursal_id, id_pieza))

                # Por construcción esta renta cierra al 100% (ya validado arriba)
                cursor.execute("UPDATE rentas SET estado_renta = 'finalizada' WHERE id = %s", (info['renta_id'],))
                cursor.execute("""
                    UPDATE rentas SET estado_renta = 'finalizada'
                    WHERE renta_asociada_id = %s AND estado_renta = 'activa renovacion'
                """, (info['renta_id'],))
                cursor.execute("""
                    UPDATE rentas SET estado_cobro_extra = %s WHERE id = %s
                """, ('Extra Pendiente' if hay_cobro_extra else None, info['renta_id']))

            conn.commit()
            return True, primer_nota_entrada_id, folio, None
        except Exception as e:
            conn.rollback()
            return False, None, None, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def crear_recoleccion_multiple(cliente_id, sucursal_id, renta_ids, chofer_recoleccion_id, observaciones, usuario_id,
                                    traslado_extra='ninguno', costo_traslado_extra=0):
        """
        Despacha al chofer a recoger varias rentas del mismo cliente/sucursal en un
        solo viaje, porque alguna de ellas ya tiene traslado redondo/medio_regreso
        pagado, o porque el cliente solicita ahora que vayan a recoger. Todavía NO
        se capturan cantidades reales (no se sabe qué va a traer el chofer hasta
        que regrese) -- esto solo crea, para cada renta, la misma nota "vacía"
        (todo en cero) que ya genera hoy el primer paso del flujo de una sola
        renta. La captura real (completa o parcial) se hace después, renta por
        renta, con el botón normal "Generar Nota de Entrada": el sistema ya
        detecta esa nota vacía pendiente y permite completarla con renovación,
        cobro extra o pendiente, igual que siempre.

        Se puede cobrar un traslado extra aunque alguna renta ya tenga traslado
        pagado: si hay mucho equipo y no entra todo en una sola vuelta de la
        camioneta, se necesita un viaje adicional que sí se cobra.
        """
        if not renta_ids or len(renta_ids) < 2:
            return False, None, None, "Selecciona al menos 2 rentas para el despacho."
        if not chofer_recoleccion_id:
            return False, None, None, "Selecciona el chofer que recolectará el equipo."

        traslado_extra = traslado_extra or 'ninguno'
        costo_traslado_extra = float(costo_traslado_extra or 0)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            info_rentas = []
            for renta_id in renta_ids:
                cursor.execute("""
                    SELECT id, cliente_id, id_sucursal, renta_asociada_id, estado_renta, folio
                    FROM rentas WHERE id = %s
                """, (renta_id,))
                renta_row = cursor.fetchone()
                if not renta_row:
                    raise ValueError(f"Renta {renta_id} no encontrada.")
                if renta_row['cliente_id'] != cliente_id or renta_row['id_sucursal'] != sucursal_id:
                    raise ValueError(f"La renta {renta_id} no pertenece a este cliente o sucursal.")
                if (renta_row['estado_renta'] or '').lower().strip() not in ('en curso', 'activo', 'activa renovacion', 'programada'):
                    raise ValueError(f"La renta SUC{sucursal_id}-{renta_row['folio']} ya no admite recolección.")

                padre_real_id = renta_row['renta_asociada_id'] or renta_id

                cursor.execute("""
                    SELECT id AS nota_salida_id FROM notas_salida
                    WHERE renta_id = %s ORDER BY id DESC LIMIT 1
                """, (padre_real_id,))
                ns_row = cursor.fetchone()
                if not ns_row:
                    raise ValueError(f"La renta SUC{sucursal_id}-{renta_row['folio']} no tiene nota de salida asociada.")

                pendientes = RentasService._calcular_piezas_pendientes_renta(cursor, padre_real_id)
                if not pendientes:
                    raise ValueError(f"La renta SUC{sucursal_id}-{renta_row['folio']} no tiene piezas pendientes por recoger.")

                info_rentas.append({
                    'renta_id': renta_id,
                    'nota_salida_id': ns_row['nota_salida_id'],
                    'piezas_pendientes': pendientes
                })

            # Mismo folio compartido para todo el viaje; cada renta sigue generando
            # su propia fila/id en notas_entrada, como siempre.
            folio = obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id)
            primer_nota_entrada_id = None

            for idx, info in enumerate(info_rentas):
                # El costo del traslado extra es por VIAJE, no por renta: si se
                # guardara en cada fila, "Cobrar Extra" lo sugeriría una vez por
                # cada renta y se cobraría varias veces el mismo viaje. Se carga
                # una sola vez, en la primera renta del grupo.
                traslado_extra_fila = traslado_extra if idx == 0 else 'ninguno'
                costo_traslado_extra_fila = costo_traslado_extra if idx == 0 else 0

                cursor.execute("""
                    INSERT INTO notas_entrada (
                        folio, renta_id, nota_salida_id, fecha_entrada_real,
                        requiere_traslado_extra, costo_traslado_extra, observaciones,
                        estado, created_at, estado_retraso, accion_devolucion,
                        chofer_recoleccion_id, usuario_id
                    ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, 'normal', NOW(), 'Sin Retraso', 'no', %s, %s)
                """, (
                    folio, info['renta_id'], info['nota_salida_id'],
                    traslado_extra_fila, costo_traslado_extra_fila, observaciones,
                    chofer_recoleccion_id, usuario_id
                ))
                nota_entrada_id = cursor.lastrowid
                if primer_nota_entrada_id is None:
                    primer_nota_entrada_id = nota_entrada_id

                for pieza in info['piezas_pendientes']:
                    cursor.execute("""
                        INSERT INTO notas_entrada_detalle (
                            nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                            cantidad_buena, cantidad_danada, cantidad_sucia, cantidad_perdida
                        ) VALUES (%s, %s, %s, 0, 0, 0, 0, 0)
                    """, (nota_entrada_id, pieza['id_pieza'], pieza['cantidad_pendiente']))

                cursor.execute("UPDATE rentas SET estado_renta = 'en recolección' WHERE id = %s", (info['renta_id'],))

            conn.commit()
            return True, primer_nota_entrada_id, folio, None
        except Exception as e:
            conn.rollback()
            return False, None, None, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _puede_cancelar_renta(estado_renta, estado_pago):
        estado_renta_lower = (estado_renta or '').lower().strip()
        estado_pago_lower = (estado_pago or '').lower().strip()
        return (
            estado_renta_lower in ('en curso', 'activo', 'activa renovacion', 'programada')
            and estado_pago_lower in ('pago pendiente', 'pago realizado')
        )

    @staticmethod
    def info_cancelar_renta(renta_id):
        """
        Analiza el estado de la renta y devuelve información para decidir cómo cancelar.
        Distingue entre renta original y renovación.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT estado_renta, estado_pago, id_sucursal, renta_asociada_id
                FROM rentas WHERE id = %s
            """, (renta_id,))
            renta = cursor.fetchone()

            if not renta:
                return {'error': 'Renta no encontrada'}

            if not RentasService._puede_cancelar_renta(renta['estado_renta'], renta['estado_pago']):
                return {'error': 'Esta renta ya no se puede cancelar en su estado actual.'}

            es_renovacion = renta['renta_asociada_id'] is not None
            padre_real_id = renta['renta_asociada_id'] if es_renovacion else renta_id

            info = {
                'estado_renta': renta['estado_renta'],
                'estado_pago': renta['estado_pago'],
                'es_renovacion': es_renovacion,
                'tiene_piezas_pendientes': False,
                'requiere_reembolso': False,
                'mensaje': ''
            }

            if es_renovacion:
                info['mensaje'] = ('Esta es una renovación. Al cancelarla se reactivará la renta '
                                    'anterior para que puedas generarle nota de entrada, cancelarla o renovarla de nuevo.')
            else:
                if (renta['estado_renta'] or '').lower() == 'finalizada':
                    info['mensaje'] = 'Esta renta ya está finalizada (el equipo ya regresó). Solo se procesará el reembolso si aplica.'
                else:
                    pendientes = RentasService._calcular_piezas_pendientes_renta(cursor, padre_real_id)
                    if pendientes:
                        info['tiene_piezas_pendientes'] = True
                        info['mensaje'] = ('Esta renta tiene equipo pendiente de regresar. Se generará una nota '
                                            'de entrada automática y se actualizará el inventario.')
                    else:
                        info['mensaje'] = 'Esta renta no tiene equipo pendiente de regresar. Se cancelará sin afectar inventario.'

            estado_pago_lower = (renta['estado_pago'] or '').lower().strip()
            if 'realizado' in estado_pago_lower or 'pagado' in estado_pago_lower or 'anticipo' in estado_pago_lower:
                info['requiere_reembolso'] = True

            return info

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def cancelar_renta(renta_id, motivo, monto_reembolso, metodo_reembolso=None):
        """
        Cancela una renta original o una renovación.

        - Renta original: si no está finalizada y tiene piezas pendientes (de cualquiera
          de sus notas de salida), genera automáticamente una nota de entrada con
          observación "Renta cancelada" y regresa el inventario.
        - Renovación: reactiva la renta inmediatamente anterior en la cadena (puede ser
          la original o otra renovación) para que el usuario pueda seguir operándola.
        - En ambos casos, si el pago estaba realizado, se procesa el reembolso manual. El
          reembolso puede darse en efectivo o por transferencia independientemente de cómo
          se haya pagado originalmente la renta (ej. se pagó con tarjeta pero se reembolsa
          en efectivo, o se pagó en efectivo pero no hay fondos en caja y se reembolsa por
          transferencia). Solo el reembolso en efectivo afecta el corte de caja física.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute("""
                SELECT estado_renta, estado_pago, id_sucursal, renta_asociada_id, folio
                FROM rentas WHERE id = %s
            """, (renta_id,))
            renta = cursor.fetchone()

            if not renta:
                return False, "Renta no encontrada"

            if not RentasService._puede_cancelar_renta(renta['estado_renta'], renta['estado_pago']):
                return False, "Esta renta ya no se puede cancelar en su estado actual."

            es_renovacion = renta['renta_asociada_id'] is not None
            padre_real_id = renta['renta_asociada_id'] if es_renovacion else renta_id
            descripcion_extra = ""

            if es_renovacion:
                # Buscar la renta inmediatamente anterior dentro de la cadena (por id)
                cursor.execute("""
                    SELECT id FROM rentas
                    WHERE (id = %s OR renta_asociada_id = %s) AND id < %s
                    ORDER BY id DESC LIMIT 1
                """, (padre_real_id, padre_real_id, renta_id))
                anterior = cursor.fetchone()
                if anterior:
                    cursor.execute("""
                        UPDATE rentas SET estado_renta = 'Activo' WHERE id = %s
                    """, (anterior['id'],))
                    descripcion_extra = f" | Renta anterior reactivada (ID {anterior['id']})"
            else:
                if (renta['estado_renta'] or '').lower() != 'finalizada':
                    pendientes = RentasService._calcular_piezas_pendientes_renta(cursor, padre_real_id)
                    if pendientes:
                        id_sucursal = renta['id_sucursal']
                        folio_siguiente = obtener_siguiente_folio_nota_sucursal(cursor, id_sucursal)
                        folio = str(folio_siguiente).zfill(5)

                        cursor.execute("""
                            SELECT id FROM notas_salida WHERE renta_id = %s ORDER BY id DESC LIMIT 1
                        """, (padre_real_id,))
                        ultima_nota_salida = cursor.fetchone()
                        nota_salida_id = ultima_nota_salida['id'] if ultima_nota_salida else None

                        cursor.execute("""
                            INSERT INTO notas_entrada (
                                folio, renta_id, nota_salida_id, fecha_entrada_real,
                                requiere_traslado_extra, costo_traslado_extra,
                                observaciones, estado, created_at, estado_retraso, accion_devolucion, usuario_id
                            ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, NOW(), %s, %s, %s)
                        """, (
                            folio, renta_id, nota_salida_id, 'ninguno', 0,
                            'Renta cancelada', 'normal',
                            'Sin Retraso', 'no', session.get('user_id')
                        ))
                        nota_entrada_id = cursor.lastrowid

                        for pieza in pendientes:
                            cantidad = pieza['cantidad_pendiente']
                            cursor.execute("""
                                INSERT INTO notas_entrada_detalle (
                                    nota_entrada_id, id_pieza, cantidad_esperada, cantidad_recibida,
                                    cantidad_buena, cantidad_danada, cantidad_sucia, cantidad_perdida, observaciones_pieza
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                nota_entrada_id, pieza['id_pieza'], cantidad, cantidad,
                                cantidad, 0, 0, 0, 'Entrada automática por cancelación'
                            ))
                            cursor.execute("""
                                UPDATE inventario_sucursal
                                SET disponibles = disponibles + %s, rentadas = rentadas - %s
                                WHERE id_sucursal = %s AND id_pieza = %s
                            """, (cantidad, cantidad, id_sucursal, pieza['id_pieza']))

                        descripcion_extra = " | Nota de entrada generada automáticamente (Renta cancelada)"

            # Determinar estado de pago según si hay reembolso manual
            estado_pago_lower = (renta['estado_pago'] or '').lower().strip()
            if monto_reembolso and float(monto_reembolso) > 0:
                nuevo_estado_pago = 'Reembolsado'
            elif 'pendiente' in estado_pago_lower:
                nuevo_estado_pago = 'Cancelado sin pago'
            else:
                nuevo_estado_pago = renta['estado_pago']

            cursor.execute("""
                UPDATE rentas
                SET estado_renta = 'cancelada', estado_pago = %s
                WHERE id = %s
            """, (nuevo_estado_pago, renta_id))

            descripcion = f"Cancelación de renta. Motivo: {motivo}"
            if monto_reembolso and float(monto_reembolso) > 0:
                descripcion += f" | Reembolso: ${monto_reembolso}"
            descripcion += descripcion_extra

            cursor.execute("""
                INSERT INTO historial_rentas (renta_id, accion, descripcion, fecha)
                VALUES (%s, %s, %s, NOW())
            """, (renta_id, 'cancelacion', descripcion))

            conn.commit()

            # Registrar el reembolso como egreso en movimientos de caja (fuera de la
            # transacción principal: si esto falla no debe revertir la cancelación ya confirmada)
            if monto_reembolso and float(monto_reembolso) > 0:
                try:
                    from routes.caja import registrar_movimiento_automatico
                    folio_display = f"SUC{renta['id_sucursal']}-{int(renta['folio']):04d}" if renta['folio'] else f"#{renta_id}"
                    registrar_movimiento_automatico(
                        tipo='egreso',
                        concepto=f"Reembolso renta {folio_display} - Cancelación",
                        monto=float(monto_reembolso),
                        metodo_pago=(metodo_reembolso or 'EFECTIVO').upper(),
                        usuario_id=session.get('user_id'),
                        sucursal_id=renta['id_sucursal'],
                        referencia_tabla='rentas',
                        referencia_id=renta_id,
                        observaciones=f"Motivo de cancelación: {motivo}"
                    )
                except Exception as e:
                    print(f"Error al registrar movimiento de caja por reembolso: {e}")

            return True, "Renta cancelada correctamente."

        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _puede_editar_renta(estado_renta, estado_pago, es_renovacion):
        estado_renta_lower = (estado_renta or '').lower().strip()
        estado_pago_lower = (estado_pago or '').lower().strip()
        if es_renovacion:
            return estado_renta_lower == 'activa renovacion' and estado_pago_lower == 'pago pendiente'
        return estado_renta_lower in ('en curso', 'programada') and estado_pago_lower == 'pago pendiente'

    @staticmethod
    def info_editar_renta(renta_id):
        """
        Devuelve los datos actuales de la renta para precargar el modal de edición.
        Distingue entre renta original (editable por completo, menos cliente/sucursal)
        y renovación (solo fechas y dirección de obra).
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT estado_renta, estado_pago, renta_asociada_id, fecha_salida, fecha_entrada,
                       fecha_programada, direccion_obra, traslado, costo_traslado, observaciones, id_sucursal
                FROM rentas WHERE id = %s
            """, (renta_id,))
            renta = cursor.fetchone()
            if not renta:
                return {'error': 'Renta no encontrada'}

            es_renovacion = renta['renta_asociada_id'] is not None
            if not RentasService._puede_editar_renta(renta['estado_renta'], renta['estado_pago'], es_renovacion):
                return {'error': 'Esta renta ya no se puede editar. Si necesitas hacer cambios, cancélala y crea una nueva.'}

            info = {
                'tipo': 'renovacion' if es_renovacion else 'original',
                'fecha_salida': renta['fecha_salida'].strftime('%Y-%m-%d') if renta['fecha_salida'] else None,
                'fecha_entrada': renta['fecha_entrada'].strftime('%Y-%m-%d') if renta['fecha_entrada'] else None,
                'direccion_obra': renta['direccion_obra']
            }

            if es_renovacion:
                return info

            info['fecha_programada'] = renta['fecha_programada'].strftime('%Y-%m-%d') if renta['fecha_programada'] else None
            info['traslado'] = renta['traslado'] or 'ninguno'
            info['costo_traslado'] = float(renta['costo_traslado'] or 0)
            info['observaciones'] = renta['observaciones'] or ''
            info['id_sucursal'] = renta['id_sucursal']

            cursor.execute("""
                SELECT id_producto, cantidad, dias_renta, costo_unitario, precio_base, ajuste_tipo, ajuste_valor
                FROM renta_detalle WHERE renta_id = %s
            """, (renta_id,))
            info['productos'] = cursor.fetchall()

            return info
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def editar_renta(renta_id, data):
        """
        Aplica la edición de una renta original o de una renovación, revalidando en
        backend que la renta todavía cumpla las condiciones para ser editada.
        """
        from datetime import datetime
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute("""
                SELECT estado_renta, estado_pago, renta_asociada_id, id_sucursal
                FROM rentas WHERE id = %s
            """, (renta_id,))
            renta = cursor.fetchone()
            if not renta:
                return False, "Renta no encontrada"

            es_renovacion = renta['renta_asociada_id'] is not None
            if not RentasService._puede_editar_renta(renta['estado_renta'], renta['estado_pago'], es_renovacion):
                return False, "Esta renta ya no se puede editar (ya tiene salida, cobro o pago registrado). Cancélala si necesitas hacer cambios."

            fecha_salida = data.get('fecha_salida')
            fecha_entrada = data.get('fecha_entrada') or None
            direccion_obra = data.get('direccion_obra', '')

            if not fecha_salida:
                return False, "La fecha de inicio es requerida"

            if es_renovacion:
                # Solo fechas y dirección de obra; recalcular días y totales con las
                # mismas piezas/precios que ya tenía la renovación
                cursor.execute("""
                    UPDATE rentas SET fecha_salida=%s, fecha_entrada=%s, direccion_obra=%s
                    WHERE id=%s
                """, (fecha_salida, fecha_entrada, direccion_obra, renta_id))

                if fecha_entrada:
                    dias_renta = max(1, (datetime.strptime(fecha_entrada, '%Y-%m-%d') - datetime.strptime(fecha_salida, '%Y-%m-%d')).days + 1)
                else:
                    dias_renta = 1

                cursor.execute("SELECT id, id_producto, cantidad FROM renta_detalle WHERE renta_id = %s", (renta_id,))
                detalles = cursor.fetchall()
                total = 0
                for detalle in detalles:
                    cursor.execute("SELECT precio_dia, precio_14_dias, precio_29_dias, precio_30_dias FROM producto_precios WHERE id_producto = %s", (detalle['id_producto'],))
                    precios = cursor.fetchone()
                    cursor.execute("SELECT precio_unico FROM productos WHERE id_producto = %s", (detalle['id_producto'],))
                    precio_unico_row = cursor.fetchone()
                    precio_unico = precio_unico_row['precio_unico'] if precio_unico_row else 0

                    if precio_unico == 1:
                        costo_unitario = float(precios['precio_dia'])
                    elif dias_renta <= 2:
                        costo_unitario = float(precios['precio_dia'])
                    elif dias_renta <= 14:
                        costo_unitario = float(precios['precio_14_dias'])
                    elif dias_renta <= 29:
                        costo_unitario = float(precios['precio_29_dias'])
                    else:
                        costo_unitario = float(precios['precio_30_dias'])

                    subtotal = detalle['cantidad'] * dias_renta * costo_unitario
                    cursor.execute("""
                        UPDATE renta_detalle SET dias_renta=%s, costo_unitario=%s, subtotal=%s WHERE id=%s
                    """, (dias_renta, costo_unitario, subtotal, detalle['id']))
                    total += subtotal

                iva = total * 0.16
                total_con_iva = total + iva
                cursor.execute("""
                    UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
                """, (total, iva, total_con_iva, renta_id))

            else:
                # Renta original: se puede editar todo menos cliente y sucursal
                traslado = data.get('traslado') or 'ninguno'
                costo_traslado = float(data.get('costo_traslado') or 0)
                observaciones = data.get('observaciones', '')
                fecha_programada = data.get('fecha_programada') or None
                productos = data.get('productos', [])

                cursor.execute("""
                    UPDATE rentas
                    SET fecha_salida=%s, fecha_entrada=%s, fecha_programada=%s, direccion_obra=%s,
                        traslado=%s, costo_traslado=%s, observaciones=%s
                    WHERE id=%s
                """, (fecha_salida, fecha_entrada, fecha_programada, direccion_obra,
                      traslado, costo_traslado, observaciones, renta_id))

                # Reemplazar por completo el detalle de productos
                cursor.execute("DELETE FROM renta_detalle WHERE renta_id = %s", (renta_id,))

                total = 0
                for prod in productos:
                    id_producto = int(prod['id_producto'])
                    cantidad = int(prod['cantidad'])
                    dias_renta = max(1, int(prod.get('dias_renta') or 1))
                    costo_unitario = float(prod.get('costo_unitario') or 0)
                    precio_base = float(prod.get('precio_base') or costo_unitario)
                    ajuste_tipo = prod.get('ajuste_tipo', 'ninguno')
                    ajuste_valor = float(prod.get('ajuste_valor') or 0)
                    subtotal = cantidad * dias_renta * costo_unitario
                    total += subtotal

                    cursor.execute("""
                        INSERT INTO renta_detalle (
                            renta_id, id_producto, cantidad, dias_renta,
                            costo_unitario, subtotal, precio_base, ajuste_tipo, ajuste_valor
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (renta_id, id_producto, cantidad, dias_renta, costo_unitario, subtotal, precio_base, ajuste_tipo, ajuste_valor))

                total += costo_traslado
                iva = total * 0.16
                total_con_iva = total + iva
                cursor.execute("""
                    UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
                """, (total, iva, total_con_iva, renta_id))

            cursor.execute("""
                INSERT INTO historial_rentas (renta_id, accion, descripcion, fecha)
                VALUES (%s, %s, %s, NOW())
            """, (renta_id, 'edicion', 'Renta editada por el usuario.'))

            conn.commit()
            return True, "Renta actualizada correctamente."

        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def info_eliminar_renta(renta_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM notas_salida WHERE renta_id = %s", (renta_id,))
            nota_salida = cursor.fetchone()
            cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s", (renta_id,))
            nota_entrada = cursor.fetchone()
            
            mensaje = "¿Seguro que deseas eliminar esta renta?"
            if nota_salida and not nota_entrada:
                mensaje = "Esta renta tiene nota de salida pero no de entrada. Si eliminas, el equipo se descontará del inventario total. ¿Deseas continuar?"
            elif nota_salida and nota_entrada:
                mensaje = "Esta renta tiene nota de salida y de entrada. El equipo ya regresó, puedes eliminar sin afectar inventario. ¿Deseas continuar?"
            elif not nota_salida:
                mensaje += " Esta renta no tiene nota de salida. Se eliminará sin afectar inventario. ¿Deseas continuar?"
            return mensaje
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def eliminar_renta(renta_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()
            
            # Verificar notas de salida y entrada
            cursor.execute("SELECT id FROM notas_salida WHERE renta_id = %s", (renta_id,))
            nota_salida = cursor.fetchone()
            cursor.execute("SELECT id FROM notas_entrada WHERE renta_id = %s", (renta_id,))
            nota_entrada = cursor.fetchone()

            # Si hay nota de salida pero no de entrada, descontar equipo del inventario
            if nota_salida and not nota_entrada:
                cursor.execute("SELECT id_producto, cantidad FROM renta_detalle WHERE renta_id = %s", (renta_id,))
                productos = cursor.fetchall()
                for id_producto, cantidad in productos:
                    cursor.execute("UPDATE productos SET cantidad = cantidad - %s WHERE id_producto = %s", (cantidad, id_producto))
                    
            # Soft delete
            cursor.execute("UPDATE rentas SET estado_renta = 'eliminada' WHERE id = %s", (renta_id,))
            conn.commit()
            return True, "Renta eliminada correctamente."
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def cerrar_renta(renta_id, fecha_entrada_obj):
        """
        Cierra la renta (si aplica) calculando los días en base a la fecha de entrada ingresada,
        y ajusta los totales.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            conn.start_transaction()

            # Obtener fecha_salida de la renta
            cursor.execute("SELECT fecha_salida FROM rentas WHERE id = %s", (renta_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Renta no encontrada")
            
            fecha_salida = row[0]

            # Calcular días de renta
            dias_renta = (fecha_entrada_obj - fecha_salida).days + 1
            if dias_renta < 1:
                dias_renta = 1

            # Actualizar cada detalle de la renta con recálculo de precios
            cursor.execute("SELECT id, id_producto, cantidad FROM renta_detalle WHERE renta_id = %s", (renta_id,))
            detalles = cursor.fetchall()
            for detalle in detalles:
                detalle_id, prod_id, cantidad = detalle
                
                # Obtener precios del producto
                cursor.execute("SELECT precio_dia, precio_14_dias, precio_29_dias, precio_30_dias FROM producto_precios WHERE id_producto = %s", (prod_id,))
                precios = cursor.fetchone()
                cursor.execute("SELECT precio_unico FROM productos WHERE id_producto = %s", (prod_id,))
                precio_unico_row = cursor.fetchone()
                precio_unico = precio_unico_row[0] if precio_unico_row else 0

                # Recalcular precio según días (misma lógica que crear_nueva_renta)
                if precio_unico == 1:
                    costo_unitario = float(precios[0])
                else:
                    if dias_renta <= 2:
                        costo_unitario = float(precios[0])
                    elif dias_renta <= 14:
                        costo_unitario = float(precios[1])
                    elif dias_renta <= 29:
                        costo_unitario = float(precios[2])
                    else:
                        costo_unitario = float(precios[3])

                subtotal = cantidad * dias_renta * costo_unitario
                cursor.execute("""
                    UPDATE renta_detalle SET dias_renta = %s, costo_unitario = %s, subtotal = %s WHERE id = %s
                """, (dias_renta, costo_unitario, subtotal, detalle_id))

            # Recalcular totales
            cursor.execute("SELECT SUM(subtotal) FROM renta_detalle WHERE renta_id = %s", (renta_id,))
            total = cursor.fetchone()[0] or 0

            # Obtener costo_traslado
            cursor.execute("SELECT costo_traslado FROM rentas WHERE id = %s", (renta_id,))
            costo_traslado = cursor.fetchone()[0] or 0

            total += float(costo_traslado)
            iva = total * 0.16
            total_con_iva = total + iva

            # Verificar estado actual de la renta
            cursor.execute("SELECT estado_renta FROM rentas WHERE id = %s", (renta_id,))
            estado_actual = cursor.fetchone()[0]
            
            if estado_actual == 'cancelada':
                # Si está cancelada, solo actualiza totales y fecha_entrada, no el estado
                cursor.execute("""
                    UPDATE rentas SET fecha_entrada=%s, total=%s, iva=%s, total_con_iva=%s WHERE id=%s
                """, (fecha_entrada_obj, total, iva, total_con_iva, renta_id))
            else:
                # Si no está cancelada, actualiza también el estado a 'cerrada'
                cursor.execute("""
                    UPDATE rentas SET fecha_entrada=%s, total=%s, iva=%s, total_con_iva=%s, estado_renta='cerrada'
                    WHERE id=%s
                """, (fecha_entrada_obj, total, iva, total_con_iva, renta_id))

            conn.commit()
            return True, "Renta cerrada y actualizada con éxito"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _calcular_estado_entrega_modal(renta, get_local_now_naive_func):
        from datetime import datetime, time, timedelta

        if not renta.get('fecha_entrada'): return None
        if not renta.get('estado_renta'): return None
        if renta['estado_renta'].lower() != 'activo': return None

        fecha_entrada = renta['fecha_entrada']
        fecha_limite = fecha_entrada + timedelta(days=1)
        ahora = get_local_now_naive_func()
        fecha_limite_con_hora = datetime.combine(fecha_limite, time(10, 0))

        if ahora > fecha_limite_con_hora:
            return {'estado': 'vencida', 'texto': 'Vencida'}
        elif ahora.date() >= fecha_entrada:
            return {'estado': 'por_regresar', 'texto': 'Por regresar'}
        return None

    @staticmethod
    def obtener_detalle_renta(renta_id, get_local_now_naive_func):
        """Obtiene la información estructurada de la renta para el Modal de detalle."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
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
                return False, "Renta no encontrada", None, None, None

            cursor.execute("""
                SELECT p.id_producto, p.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
                FROM renta_detalle rd
                JOIN productos p ON rd.id_producto = p.id_producto
                WHERE rd.renta_id = %s
            """, (renta_id,))
            productos = cursor.fetchall()

            # Renovaciones parciales
            padre_real_id = renta['renta_asociada_id'] or renta_id
            piezas_pendientes = {
                p['id_pieza']: p['cantidad_pendiente']
                for p in RentasService._calcular_piezas_pendientes_renta(cursor, padre_real_id)
            }
            for prod in productos:
                cursor.execute("""
                    SELECT id_pieza, cantidad FROM producto_piezas WHERE id_producto = %s
                """, (prod['id_producto'],))
                piezas_producto = cursor.fetchall()
                if piezas_producto:
                    cantidad_pendiente = max(
                        -(-piezas_pendientes.get(pp['id_pieza'], 0) // pp['cantidad'])
                        for pp in piezas_producto
                    )
                    prod['cantidad_pendiente'] = min(max(0, cantidad_pendiente), prod['cantidad'])
                else:
                    prod['cantidad_pendiente'] = 0

            fecha_limite = "INDEFINIDA"
            if renta['fecha_entrada']:
                from datetime import timedelta
                fecha_limite_obj = renta['fecha_entrada'] + timedelta(days=1)
                fecha_limite = f"{fecha_limite_obj.strftime('%d/%m/%Y')} antes de las 10:00 a.m."
            
            direccion_cliente = renta['calle'] or ''
            if renta['numero_exterior']: direccion_cliente += f" #{renta['numero_exterior']}"
            if renta['numero_interior']: direccion_cliente += f", Int. {renta['numero_interior']}"
            if renta['entre_calles']: direccion_cliente += f" (entre {renta['entre_calles']})"
            if renta['colonia']: direccion_cliente += f", COL. {renta['colonia']}"
            if renta['codigo_postal']: direccion_cliente += f" - C.P. {renta['codigo_postal']}"
            
            estado_entrega = RentasService._calcular_estado_entrega_modal(renta, get_local_now_naive_func)

            renta_dict = {
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
                'fecha_limite': fecha_limite,
                'estado_entrega': estado_entrega
            }

            cliente_dict = {
                'codigo': renta['codigo_cliente'],
                'nombre': renta['cliente_nombre'],
                'telefono': renta['telefono'] or 'No registrado',
                'email': renta['correo'] or 'No registrado',
                'rfc': renta['rfc'] or 'No registrado',
                'direccion': direccion_cliente
            }

            return True, None, renta_dict, cliente_dict, productos
        except Exception as e:
            return False, str(e), None, None, None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def renovar_renta(renta_id, nueva_fecha_salida, fecha_entrada, observaciones, productos_d, cantidades_d, dias_d, costos_d, current_time):
        """Copia la renta inicial y crea una nueva con estado 'activa renovacion'."""
        from itertools import zip_longest
        from datetime import datetime

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()

            cursor.execute(
                "SELECT cliente_id, direccion_obra, id_sucursal, costo_traslado, traslado, renta_asociada_id "
                "FROM rentas WHERE id = %s", (renta_id,)
            )
            renta_original = cursor.fetchone()
            if not renta_original:
                raise ValueError("La renta original no existe.")

            cliente_id, direccion_obra, sucursal_id, costo_traslado, traslado, renta_asociada_id_db = renta_original
            costo_traslado = costo_traslado or 0
            traslado = traslado or 'ninguno'
            
            # Heredar el padre raíz (Logica 1)
            padre_real_id = renta_asociada_id_db if renta_asociada_id_db else renta_id

            # Obtener el folio consecutivo de la sucursal (inicia en 1 por sucursal)
            folio = obtener_siguiente_folio_renta_sucursal(cursor, sucursal_id)

            cursor.execute("""
                INSERT INTO rentas (
                    cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                    direccion_obra, estado_renta, estado_pago, metodo_pago,
                    total, iva, total_con_iva, observaciones, fecha_programada, id_sucursal,
                    costo_traslado, traslado, renta_asociada_id, folio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cliente_id, current_time, nueva_fecha_salida, fecha_entrada,
                direccion_obra, 'activa renovacion', 'Pago pendiente', 'Pendiente',
                0, 0, 0, observaciones, None, sucursal_id,
                costo_traslado, traslado, padre_real_id, folio
            ))
            nueva_renta_id = cursor.lastrowid

            total = 0
            for prod_id_raw, cant_raw, dias_raw, costo_raw in zip_longest(productos_d, cantidades_d, dias_d, costos_d):
                if not prod_id_raw or not cant_raw:
                    continue
                try:
                    prod_id = int(prod_id_raw)
                    cant = int(cant_raw)
                except ValueError:
                    continue

                cursor.execute("SELECT costo_unitario FROM renta_detalle WHERE renta_id = %s AND id_producto = %s LIMIT 1", (renta_id, prod_id))
                result = cursor.fetchone()
                costo_unitario = float(result[0]) if result else 0.0

                if fecha_entrada:
                    try:
                        f_salida_dt = datetime.strptime(nueva_fecha_salida, "%Y-%m-%d")
                        f_entrada_dt = datetime.strptime(fecha_entrada, "%Y-%m-%d")
                        dias_renta = max(1, (f_entrada_dt - f_salida_dt).days + 1)
                    except Exception:
                        dias_renta = max(1, int(dias_raw) if dias_raw else 1)
                else:
                    dias_renta = max(1, int(dias_raw) if dias_raw else 1)

                subtotal = cant * dias_renta * costo_unitario
                total += subtotal

                cursor.execute("""
                    INSERT INTO renta_detalle (
                        renta_id, id_producto, cantidad, dias_renta,
                        costo_unitario, subtotal
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (nueva_renta_id, prod_id, cant, dias_renta, costo_unitario, subtotal))

            total_iva = total * 0.16
            total_con_iva = total + total_iva
            cursor.execute("""
                UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
            """, (total, total_iva, total_con_iva, nueva_renta_id))

            # Finalizar la renta antigua para que no le puedan meter más acciones
            cursor.execute("""
                UPDATE rentas SET estado_renta = 'finalizada' WHERE id = %s
            """, (renta_id,))

            conn.commit()
            return True, nueva_renta_id, sucursal_id, "Renta renovada con éxito"

        except Exception as e:
            conn.rollback()
            return False, None, None, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_productos_pendientes(renta_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT r.direccion_obra, c.nombre as cliente_nombre
                FROM rentas r
                JOIN clientes c ON r.cliente_id = c.id
                WHERE r.id = %s
            """, (renta_id,))
            renta_data = cursor.fetchone()
            if not renta_data:
                return False, "Renta no encontrada", None, None, None

            cursor.execute("""
                SELECT 
                    dr.producto_id, p.nombre as nombre_producto,
                    pi.nombre as nombre_pieza, dr.cantidad_pendiente
                FROM detalle_renta dr
                JOIN productos p ON dr.producto_id = p.id
                LEFT JOIN piezas pi ON dr.pieza_id = pi.id
                WHERE dr.renta_id = %s AND dr.cantidad_pendiente > 0
            """, (renta_id,))
            
            pendientes = []
            for row in cursor.fetchall():
                pendientes.append({
                    'producto_id': row[0],
                    'nombre_producto': row[1],
                    'nombre_pieza': row[2] or '',
                    'cantidad_pendiente': row[3]
                })

            return True, None, renta_data[0] or '', renta_data[1] or '', pendientes
        except Exception as e:
            return False, str(e), None, None, None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def crear_renovacion_pendientes(renta_id, data):
        from datetime import datetime
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()

            cursor.execute("""
                SELECT cliente_id, sucursal_id, id_sucursal, renta_asociada_id 
                FROM rentas WHERE id = %s
            """, (renta_id,))
            renta_original = cursor.fetchone()
            if not renta_original:
                raise ValueError("Renta original no encontrada")
            
            # Heredar el padre raíz (Logica 1 - misma línea que en renovacion total)
            padre_real_id = renta_original[3] if len(renta_original)>3 and renta_original[3] else renta_id

            cursor.execute("""
                INSERT INTO rentas (
                    cliente_id, sucursal_id, id_sucursal, fecha_salida, fecha_entrada,
                    direccion_obra, traslado_extra, costo_traslado_extra, 
                    factura_legal, estado_renta, estado_pago, metodo_pago, renta_asociada_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'activa renovacion', 'Pago pendiente', 'Pendiente', %s)
            """, (
                renta_original[0], renta_original[1], renta_original[2],
                data['fecha_salida'], data['fecha_entrada'],
                data.get('direccion_obra', ''),
                data.get('traslado_extra', 'ninguno'),
                data.get('costo_traslado_extra', 0),
                data.get('factura_legal', 0),
                padre_real_id
            ))
            nueva_renta_id = cursor.lastrowid

            total = 0
            for pendiente in data.get('pendientes', []):
                cursor.execute("""
                    SELECT costo_unitario, dias_renta
                    FROM renta_detalle WHERE renta_id = %s AND id_producto = %s LIMIT 1
                """, (renta_id, pendiente['producto_id']))
                result = cursor.fetchone()
                costo_unitario = float(result[0]) if result else 0.0

                f_salida = datetime.strptime(data['fecha_salida'], '%Y-%m-%dT%H:%M')
                f_entrada = datetime.strptime(data['fecha_entrada'], '%Y-%m-%dT%H:%M')
                dias = max(1, (f_entrada - f_salida).days + 1)

                sub = pendiente['cantidad_pendiente'] * dias * costo_unitario
                cursor.execute("""
                    INSERT INTO renta_detalle (
                        renta_id, id_producto, cantidad, dias_renta,
                        costo_unitario, subtotal
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (nueva_renta_id, pendiente['producto_id'], pendiente['cantidad_pendiente'], dias, costo_unitario, sub))
                total += pendiente['cantidad_pendiente'] * costo_unitario * dias

            total += float(data.get('costo_traslado_extra', 0))
            iva = total * 0.16
            total_con_iva = total + iva

            cursor.execute("UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s", (total, iva, total_con_iva, nueva_renta_id))
            
            # FINALIZAR la renta anterior!
            cursor.execute("UPDATE rentas SET estado_renta = 'finalizada' WHERE id = %s", (renta_id,))

            conn.commit()
            return True, nueva_renta_id, "Renovación creada exitosamente"
        except Exception as e:
            conn.rollback()
            return False, None, str(e)
        finally:
            cursor.close()
            conn.close()
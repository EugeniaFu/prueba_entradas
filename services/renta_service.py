from utils.db import get_db_connection

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
                    LOWER(TRIM(estado_renta)) IN ('en curso', 'activo', 'activa renovacion', 'en recolección', 'programada')
                    
                    OR (
                        LOWER(TRIM(estado_renta)) = 'finalizada'
                        AND LOWER(TRIM(estado_pago)) IN ('pago pendiente', 'saldo pendiente')
                    )
                    OR piezas_pendientes > 0
                )
                """
            elif estado_filtro == 'pagadas':
                filtro_estado = """
                HAVING (
                    (LOWER(TRIM(estado_renta)) = 'finalizada' AND LOWER(TRIM(estado_pago)) = 'pago realizado' AND piezas_pendientes = 0)
                    OR LOWER(TRIM(estado_renta)) = 'cancelada'
                )
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
                (SELECT COUNT(*) FROM rentas r2 WHERE r2.id_sucursal = r.id_sucursal AND r2.id <= r.id) AS folio_sucursal,
                s.nombre AS sucursal_nombre,
                ncr.id AS cobro_retraso_id,
                (SELECT COUNT(*) FROM rentas r3 WHERE r3.id_sucursal = r.id_sucursal AND r3.id <= r.renta_asociada_id) AS folio_asociado

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
    def crear_nueva_renta(datos_renta, sucursal_id, es_admin, productos, cantidades, dias, costos):
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
            
            # Insertar cabecera de Renta (inicialmente en 0)
            cursor.execute("""
                INSERT INTO rentas (
                    cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                    direccion_obra, estado_renta, estado_pago, metodo_pago,
                    total, iva, total_con_iva, observaciones, fecha_programada, id_sucursal,
                    costo_traslado, traslado
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datos_renta['cliente_id'], datos_renta['fecha_registro'], datos_renta['fecha_salida'], 
                datos_renta['fecha_entrada'], datos_renta['direccion_obra'], estado_renta, 
                estado_pago, metodo_pago, 0, 0, 0, datos_renta['observaciones'], 
                datos_renta['fecha_programada'], sucursal_para_renta, 
                datos_renta['costo_traslado'], datos_renta['traslado']
            ))

            renta_id = cursor.lastrowid
            
            # Procesar detalles
            total = 0
            for i in range(len(productos)):
                prod_id = int(productos[i])
                cant = int(cantidades[i])
                dias_renta_raw = dias[i]
                dias_renta = 1 if dias_renta_raw in (None, '', 'null') else max(1, int(dias_renta_raw))

                # Obtener la lógica de precios
                cursor.execute("SELECT precio_dia, precio_14_dias, precio_29_dias, precio_30_dias FROM producto_precios WHERE id_producto = %s", (prod_id,))
                precios = cursor.fetchone()
                cursor.execute("SELECT precio_unico FROM productos WHERE id_producto = %s", (prod_id,))
                precio_unico_row = cursor.fetchone()
                precio_unico = precio_unico_row[0] if precio_unico_row else 0

                # Selección dinámica según días
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

                subtotal = cant * dias_renta * costo_unitario
                total += subtotal

                cursor.execute("""
                    INSERT INTO renta_detalle (
                        renta_id, id_producto, cantidad, dias_renta,
                        costo_unitario, subtotal
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (renta_id, prod_id, cant, dias_renta, costo_unitario, subtotal))

            # Actualizar totales
            total += datos_renta['costo_traslado']
            iva = total * 0.16
            total_con_iva = total + iva

            cursor.execute("""
                UPDATE rentas SET total=%s, iva=%s, total_con_iva=%s WHERE id=%s
            """, (total, iva, total_con_iva, renta_id))

            conn.commit()
            return True, renta_id, sucursal_para_renta, None
            
        except Exception as e:
            conn.rollback()
            return False, None, None, str(e)
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
            return True, "Fecha de entrada y totales actualizados correctamente"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def cancelar_renta(renta_id, motivo, monto_reembolso):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()
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
            return True, "Renta cancelada correctamente."
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

            # Actualizar cada detalle de la renta
            cursor.execute("SELECT id, cantidad, costo_unitario FROM renta_detalle WHERE renta_id = %s", (renta_id,))
            detalles = cursor.fetchall()
            for detalle in detalles:
                detalle_id, cantidad, costo_unitario = detalle
                subtotal = cantidad * dias_renta * float(costo_unitario)
                cursor.execute("""
                    UPDATE renta_detalle SET dias_renta = %s, subtotal = %s WHERE id = %s
                """, (dias_renta, subtotal, detalle_id))

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

            cursor.execute("""
                INSERT INTO rentas (
                    cliente_id, fecha_registro, fecha_salida, fecha_entrada,
                    direccion_obra, estado_renta, estado_pago, metodo_pago,
                    total, iva, total_con_iva, observaciones, fecha_programada, id_sucursal,
                    costo_traslado, traslado, renta_asociada_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cliente_id, current_time, nueva_fecha_salida, fecha_entrada,
                direccion_obra, 'activa renovacion', 'Pago pendiente', 'Pendiente',
                0, 0, 0, observaciones, None, sucursal_id,
                costo_traslado, traslado, padre_real_id
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
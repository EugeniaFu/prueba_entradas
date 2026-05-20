import re

with open('services/renta_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_method = '''def crear_renovacion_pendientes(renta_id, data):
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
            conn.close()'''

content_new = re.sub(r'def crear_renovacion_pendientes\(renta_id, data\):.*$', new_method, content, flags=re.DOTALL)

with open('services/renta_service.py', 'w', encoding='utf-8') as f:
    f.write(content_new)

print('Renovacion parcial updated')
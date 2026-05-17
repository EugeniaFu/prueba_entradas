from utils.db import get_db_connection

class ClienteService:
    @staticmethod
    def obtener_lista_clientes(busqueda='', filtro='', ver_bajas='0'):
        """
        Obtiene la lista de clientes aplicando filtros, lógica de negocio 
        y construyendo la consulta segura con parámetros.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Lógica central: Activos vs Inactivos
            if ver_bajas == '1':
                query = "SELECT * FROM clientes WHERE activo = 0"
            else:
                query = "SELECT * FROM clientes WHERE activo = 1"
            
            params = []

            # Lógica: Filtro por búsqueda de texto
            if busqueda:
                query += " AND (nombre LIKE %s OR apellido1 LIKE %s OR apellido2 LIKE %s OR telefono LIKE %s)"
                like = f"%{busqueda}%"
                params.extend([like, like, like, like])

            # Lógica: Filtro por tipo de cliente
            if filtro in ['betado', 'frecuente', 'ocasional']:
                query += " AND tipo_cliente = %s"
                params.append(filtro)

            query += " ORDER BY id DESC"
            
            cursor.execute(query, params)
            clientes = cursor.fetchall()
            
            return clientes
            
        except Exception as e:
            # Aquí se puede añadir logs si hay un error
            print(f"Error en ClienteService.obtener_lista_clientes: {e}")
            return []
            
        finally:
            # Siempre aseguramos que la base de datos se cierre sin importar qué pase
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def obtener_cliente_por_id(id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM clientes WHERE id=%s", (id,))
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def obtener_documentos_cliente(id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM documentos_cliente WHERE cliente_id=%s", (id,))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def cambiar_estado_cliente(id, activo: bool):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            val = 1 if activo else 0
            cursor.execute("UPDATE clientes SET activo = %s WHERE id = %s", (val, id))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def eliminar_cliente_definitivo(id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM clientes WHERE id = %s", (id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def obtener_detalle_cliente(id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT c.*, s.nombre AS sucursal_nombre, r.nombre AS rol_nombre
                FROM clientes c
                LEFT JOIN sucursales s ON c.sucursal_id = s.id
                LEFT JOIN roles r ON c.rol_id = r.id
                WHERE c.id=%s
            """, (id,))
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def buscar_clientes_dinamico(term):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            query = """
            SELECT id, codigo_cliente, nombre, apellido1, apellido2, telefono, correo
            FROM clientes
            WHERE activo = 1 AND (
                codigo_cliente LIKE %s OR
                nombre LIKE %s OR
                apellido1 LIKE %s OR
                apellido2 LIKE %s OR
                CONCAT(nombre, ' ', apellido1, ' ', apellido2) LIKE %s OR
                telefono LIKE %s OR
                correo LIKE %s
            )
            LIMIT 10
            """
            like = f"%{term}%"
            cursor.execute(query, (like, like, like, like, like, like, like))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def verificar_duplicados(telefono, correo):
        """Verifica si ya existe un cliente con ese teléfono o correo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        errores = []
        try:
            cursor.execute("SELECT * FROM clientes WHERE telefono = %s AND activo = 1", (telefono,))
            if cursor.fetchone():
                errores.append("Ya existe un cliente registrado con ese número de teléfono.")
            if correo:
                cursor.execute("SELECT * FROM clientes WHERE correo = %s AND activo = 1", (correo,))
                if cursor.fetchone():
                    errores.append("Ya existe un cliente registrado con ese correo.")
            return errores
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def crear_cliente_completo(datos_cliente, sucursal_id, prefijo_sucursal, documentos_nuevos):
        """
        Crea el cliente y todos sus documentos dentro de una sola transacción.
        Si hay un error, deshace todos los cambios automáticamente en la BD.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()
            
            # OBTENER ID del rol cliente automáticamente
            cursor.execute("SELECT id FROM roles WHERE nombre = 'cliente'")
            rol_cliente = cursor.fetchone()
            rol_id = rol_cliente[0] if rol_cliente else None
            
            # Insertar cliente
            cursor.execute("""
                INSERT INTO clientes (nombre, apellido1, apellido2, telefono, correo, rfc, tipo_cliente, 
                                     calle, entre_calles, numero_exterior, numero_interior, colonia, 
                                     codigo_postal, municipio, estado, rol_id, sucursal_id, fecha_alta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datos_cliente['nombre'], datos_cliente['apellido1'], datos_cliente['apellido2'], 
                datos_cliente['telefono'], datos_cliente['correo'], datos_cliente['rfc'], datos_cliente['tipo_cliente'],
                datos_cliente['calle'], datos_cliente['entre_calles'], datos_cliente['numero_exterior'], 
                datos_cliente['numero_interior'], datos_cliente['colonia'], datos_cliente['codigo_postal'], 
                datos_cliente['municipio'], datos_cliente['estado'], rol_id, sucursal_id, datos_cliente['fecha_alta']
            ))
            
            cliente_id = cursor.lastrowid

            # Generar Código de Cliente
            cursor.execute("SELECT MAX(CAST(SUBSTRING(codigo_cliente, 3, 5) AS UNSIGNED)) FROM clientes WHERE sucursal_id = %s", (sucursal_id,))
            max_consecutivo = cursor.fetchone()[0] or 0
            consecutivo = max_consecutivo + 1
            consecutivo_str = str(consecutivo).zfill(5)
            codigo_cliente = f"{prefijo_sucursal}{consecutivo_str}"
            cursor.execute("UPDATE clientes SET codigo_cliente = %s WHERE id = %s", (codigo_cliente, cliente_id))

            # Insertar documentos
            for doc in documentos_nuevos:
                cursor.execute("""
                    INSERT INTO documentos_cliente (cliente_id, tipo_documento, archivo)
                    VALUES (%s, %s, %s)
                """, (cliente_id, doc['tipo_documento'], doc['filename']))

            conn.commit()
            return True, None
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def actualizar_cliente_y_documentos(id, datos_cliente, ids_eliminar, documentos_existentes, documentos_nuevos):
        """Actualiza un cliente y maneja la lógica de documentos en una sola transacción."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()
            # Update campos cliente
            cursor.execute("""
                UPDATE clientes SET nombre=%s, apellido1=%s, apellido2=%s, telefono=%s, correo=%s, rfc=%s, tipo_cliente=%s,
                                calle=%s, entre_calles=%s, numero_exterior=%s, numero_interior=%s, colonia=%s,
                                codigo_postal=%s, municipio=%s, estado=%s
                WHERE id=%s
            """, (
                datos_cliente['nombre'], datos_cliente['apellido1'], datos_cliente['apellido2'], 
                datos_cliente['telefono'], datos_cliente['correo'], datos_cliente['rfc'], datos_cliente['tipo_cliente'],
                datos_cliente['calle'], datos_cliente['entre_calles'], datos_cliente['numero_exterior'], 
                datos_cliente['numero_interior'], datos_cliente['colonia'], datos_cliente['codigo_postal'], 
                datos_cliente['municipio'], datos_cliente['estado'], id
            ))

            # Eliminar documentos seleccionados
            if ids_eliminar:
                for doc_id in ids_eliminar:
                    cursor.execute("DELETE FROM documentos_cliente WHERE id=%s AND cliente_id=%s", (doc_id, id))
            
            # Actualizar documentos existentes (cambio de tipo_documento)
            for doc_id, nuevo_tipo in documentos_existentes.items():
                cursor.execute("""
                    UPDATE documentos_cliente SET tipo_documento=%s WHERE id=%s AND cliente_id=%s
                """, (nuevo_tipo, doc_id, id))

            # Subir nuevos documentos
            for doc in documentos_nuevos:
                cursor.execute("""
                    INSERT INTO documentos_cliente (cliente_id, tipo_documento, archivo)
                    VALUES (%s, %s, %s)
                """, (id, doc['tipo_documento'], doc['filename']))

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

from difflib import SequenceMatcher
from utils.db import get_db_connection
from utils.nombres import simplificar_nombre

class ClienteService:
    @staticmethod
    def _condicion_busqueda(texto):
        """
        Arma el WHERE de búsqueda: cada palabra escrita debe aparecer en el código,
        nombre, apellidos, teléfono (comparado sin espacios) o correo.
        Así "Juan Pérez" o "Pérez López" encuentran al cliente aunque estén en campos distintos.
        """
        condiciones, params = [], []
        for palabra in texto.split():
            like = f"%{palabra}%"
            condiciones.append(
                "(codigo_cliente LIKE %s OR nombre LIKE %s OR apellido1 LIKE %s OR apellido2 LIKE %s"
                " OR REPLACE(telefono, ' ', '') LIKE %s OR correo LIKE %s)"
            )
            params.extend([like] * 6)
        return ' AND '.join(condiciones) or '1 = 1', params

#########################################################
#########################################################
#########################################################
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
                condicion, params_busqueda = ClienteService._condicion_busqueda(busqueda)
                query += f" AND {condicion}"
                params.extend(params_busqueda)

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
            condicion, params = ClienteService._condicion_busqueda(term)
            if not params:
                return []
            cursor.execute(f"""
                SELECT id, codigo_cliente, nombre, apellido1, apellido2, telefono, correo
                FROM clientes
                WHERE activo = 1 AND {condicion}
                LIMIT 10
            """, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def buscar_nombres_similares(nombre, apellido1, apellido2, excluir_id=None, limite=5):
        """
        Busca clientes (activos, dados de baja y betados) con el nombre completo
        igual o muy parecido. No bloquea: sirve para avisar antes de dar de alta.
        """
        buscado = simplificar_nombre(f"{nombre} {apellido1} {apellido2}")
        if not buscado:
            return []

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT id, codigo_cliente, nombre, apellido1, apellido2, telefono, tipo_cliente, activo
                FROM clientes
            """)
            similares = []
            for c in cursor.fetchall():
                if excluir_id and c['id'] == excluir_id:
                    continue
                existente = simplificar_nombre(f"{c['nombre']} {c['apellido1']} {c['apellido2'] or ''}")
                comparador = SequenceMatcher(None, buscado, existente)
                if existente == buscado or (comparador.quick_ratio() >= 0.9 and comparador.ratio() >= 0.9):
                    c['parecido'] = 1.0 if existente == buscado else comparador.ratio()
                    similares.append(c)
            similares.sort(key=lambda c: c['parecido'], reverse=True)
            return similares[:limite]
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def obtener_clientes_para_renta():
        """Clientes a los que se les puede rentar: activos y no betados."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT id, codigo_cliente, nombre, apellido1, apellido2
                FROM clientes
                WHERE activo = 1 AND tipo_cliente != 'betado'
                ORDER BY nombre, apellido1
            """)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def puede_rentar(cliente_id):
        """
        Revisa si al cliente se le puede rentar.
        Regresa None si puede, o el mensaje de por qué no.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT codigo_cliente, activo, tipo_cliente FROM clientes WHERE id = %s", (cliente_id,))
            cliente = cursor.fetchone()
            if not cliente:
                return "El cliente seleccionado no existe."
            if not cliente['activo']:
                return f"El cliente {cliente['codigo_cliente']} está dado de baja. No se le puede rentar."
            if cliente['tipo_cliente'] == 'betado':
                return f"El cliente {cliente['codigo_cliente']} está betado. No se le puede rentar."
            return None
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def buscar_cliente_por_telefono(telefono, excluir_id=None):
        """
        Busca el teléfono (ya normalizado) en TODOS los clientes: activos, dados de baja y betados.
        excluir_id: id del cliente que se está editando, para no compararlo consigo mismo.
        Regresa el cliente que tiene ese teléfono o None si está libre.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            query = """
                SELECT id, codigo_cliente, nombre, apellido1, apellido2, telefono, tipo_cliente, activo
                FROM clientes WHERE telefono = %s
            """
            params = [telefono]
            if excluir_id:
                query += " AND id <> %s"
                params.append(excluir_id)
            cursor.execute(query + " LIMIT 1", params)
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

#########################################################
#########################################################
#########################################################
    @staticmethod
    def verificar_telefono_duplicado(telefono, excluir_id=None):
        """Regresa el mensaje de error si el teléfono ya lo tiene otro cliente, o None si está libre."""
        existente = ClienteService.buscar_cliente_por_telefono(telefono, excluir_id)
        if not existente:
            return None

        nombre = ' '.join(filter(None, [existente['nombre'], existente['apellido1'], existente['apellido2']]))
        cliente = f"{existente['codigo_cliente']} - {nombre}"
        if not existente['activo']:
            return f"Este teléfono pertenece a un cliente DADO DE BAJA: {cliente}. No se puede registrar."
        if existente['tipo_cliente'] == 'betado':
            return f"Este teléfono pertenece a un cliente BETADO: {cliente}. No se puede registrar."
        return f"Ya existe un cliente registrado con ese teléfono: {cliente}."

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
            error_telefono = ClienteService.verificar_telefono_duplicado(telefono)
            if error_telefono:
                errores.append(error_telefono)
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
                                     codigo_postal, municipio, estado, es_foraneo, direccion_alojamiento,
                                     rol_id, sucursal_id, fecha_alta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datos_cliente['nombre'], datos_cliente['apellido1'], datos_cliente['apellido2'],
                datos_cliente['telefono'], datos_cliente['correo'], datos_cliente['rfc'], datos_cliente['tipo_cliente'],
                datos_cliente['calle'], datos_cliente['entre_calles'], datos_cliente['numero_exterior'],
                datos_cliente['numero_interior'], datos_cliente['colonia'], datos_cliente['codigo_postal'],
                datos_cliente['municipio'], datos_cliente['estado'],
                datos_cliente['es_foraneo'], datos_cliente['direccion_alojamiento'],
                rol_id, sucursal_id, datos_cliente['fecha_alta']
            ))
            
            cliente_id = cursor.lastrowid

            # Generar Código de Cliente: prefijo de sucursal + id (consecutivo global, único por la BD)
            codigo_cliente = f"{prefijo_sucursal}{str(cliente_id).zfill(4)}"
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
                                codigo_postal=%s, municipio=%s, estado=%s,
                                es_foraneo=%s, direccion_alojamiento=%s
                WHERE id=%s
            """, (
                datos_cliente['nombre'], datos_cliente['apellido1'], datos_cliente['apellido2'],
                datos_cliente['telefono'], datos_cliente['correo'], datos_cliente['rfc'], datos_cliente['tipo_cliente'],
                datos_cliente['calle'], datos_cliente['entre_calles'], datos_cliente['numero_exterior'],
                datos_cliente['numero_interior'], datos_cliente['colonia'], datos_cliente['codigo_postal'],
                datos_cliente['municipio'], datos_cliente['estado'],
                datos_cliente['es_foraneo'], datos_cliente['direccion_alojamiento'], id
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

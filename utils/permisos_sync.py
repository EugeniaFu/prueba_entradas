from utils.db import get_db_connection

# Aquí defines TODOS los permisos de tu sistema.
# Cuando agregues una nueva función al sistema (ej. facturación avanzada),
# solo tienes que agregar una línea a esta lista.
PERMISOS_SISTEMA = [
    # Módulo de Clientes
    ('ver_clientes', 'Ver la lista de clientes'),
    ('crear_cliente', 'Registrar un nuevo cliente'),
    ('editar_cliente', 'Editar datos de un cliente'),
    ('baja_cliente', 'Dar de baja a un cliente'),
    ('reactivar_cliente', 'Reactivar un cliente dado de baja'),
    ('eliminar_cliente', 'Eliminar un cliente definitivamente'),
    ('ver_detalle_cliente', 'Ver el detalle de un cliente'),
    ('buscar_clientes', 'Buscar clientes por nombre, apellido, teléfono, etc.'),
    
    # Módulo de Inventario General
    ('ver_inventario_general', 'Ver el inventario general de la empresa'),
    ('agregar_pieza_inventario_general', 'Agregar piezas al inventario general'),
    ('modificar_existencias_inventario_general', 'Dar de alta o baja piezas en inventario general'),
    ('transferir_piezas_inventario', 'Transferir piezas entre sucursales'),
    
    # Módulo de Inventario de Sucursal
    ('ver_inventario_sucursal', 'Ver el inventario de la sucursal asignada'),
    ('agregar_piezas_inventario_sucursal', 'Dar de alta equipos nuevos en el inventario de la sucursal'),
    ('mandar_pieza_reparacion', 'Mandar piezas a reparación desde la sucursal'),
    ('regresar_pieza_disponible', 'Regresar piezas a disponibles desde la sucursal'),
    
    # Módulo de Productos
    ('ver_productos', 'Ver la lista de productos y sus precios'),
    ('crear_producto', 'Crear un nuevo producto'),
    ('editar_producto', 'Editar un producto existente'),
    ('baja_producto', 'Dar de baja (descontinuar) un producto'),
    ('alta_producto', 'Dar de alta (activar) un producto'),
    
    # Módulo de Empleados
    ('ver_empleados', 'Ver la lista de empleados'),
    ('crear_empleado', 'Registrar un nuevo empleado'),
    ('editar_empleado', 'Editar datos de un empleado'),
    ('baja_empleado', 'Dar de baja a un empleado'),
    ('alta_empleado', 'Dar de alta (reactivar) un empleado'),
    ('gestionar_permisos_empleado', 'Gestionar permisos individuales de empleados'),
    
    # Módulo de Rentas
    ('ver_rentas', 'Ver la lista general de rentas de una sucursal'),
    ('crear_renta', 'Iniciar una nueva renta y generar prefactura'),
    ('editar_renta', 'Editar información de una renta existente'),
    ('cancelar_renta', 'Cancelar una renta'),
    ('eliminar_renta', 'Eliminar una renta definitivamente'),
    ('cerrar_renta', 'Cerrar/finalizar una renta'),
    ('renovar_renta', 'Realizar la renovación de herramientas rentadas'),
    ('crear_renovacion_pendiente', 'Crear una renovación pendiente para una renta'),
    ('cobrar_retraso', 'Registrar nota de cobro por retraso'),
    ('ver_cobro_retraso', 'Ver notas de cobro por retraso'),
    ('cobrar_extra', 'Registrar nota de cobro extra por daños'),
    ('ver_cobro_extra', 'Ver notas de cobro extra'),
    
    # Módulo Caja y Reportes
    ('ver_movimientos_caja', 'Acceder al control de caja (efectivo y digital)'),
    ('crear_movimiento_caja', 'Registrar entradas o salidas de dinero en caja'),
    ('ver_reportes', 'Ver el reporte diario de operación'),
    
    # Módulo de Sucursales (Nuevo)
    ('ver_sucursales', 'Ver la lista de sucursales'),
    ('crear_sucursal', 'Registrar una nueva sucursal'),
    ('editar_sucursal', 'Editar datos de una sucursal'),
    
    # Roles y Permisos (Nuevo)
    ('gestionar_roles_permisos', 'Tener acceso a la matriz de roles global y poder modificar qué rol hace qué cosa'),
    
    # Perfil / Generales
    ('ver_perfil', 'Ver perfil de usuario'),
    ('cambiar_foto_perfil', 'Cambiar foto de perfil del usuario'),
    
    # --- PERMISOS FALTANTES / MÓDULOS ENCONTRADOS ---

    # Notas de Salida y Entrada
    ('ver_notas_salida', 'Consultar el historial y PDF de notas de salida'),
    ('crear_nota_salida', 'Generar una nota de salida (entregar piezas de renta)'),
    ('ver_notas_entrada', 'Consultar el historial y PDF de notas de entrada'),
    ('crear_nota_entrada', 'Generar una nota de entrada (recibir piezas de renta)'),
    
    # Prefacturas
    ('ver_prefactura', 'Consultar prefacturas generadas'),
    ('pagar_prefactura', 'Registrar pagos de prefacturas'),
    ('crear_prefactura', 'Generar prefactura de rentas'),

    # Cotizaciones
    ('ver_cotizaciones', 'Ver la lista de cotizaciones'),
    ('crear_cotizacion', 'Registrar una nueva cotización'),
    ('editar_cotizacion', 'Modificar una cotización existente'),
    ('eliminar_cotizacion', 'Eliminar una cotización definitivamente'),
    ('cancelar_cotizacion', 'Cancelar (dar de baja) una cotización'),
    ('convertir_cotizacion', 'Generar una renta a partir de una cotización'),

    # Salidas Internas
    ('ver_salidas_internas', 'Ver la bitácora de salidas internas de la sucursal'),
    ('finalizar_salida_interna', 'Finalizar/cerrar una salida interna y registrar entrada'),
    ('crear_salida_interna', 'Registrar una salida interna para uso de la tienda'),

    # Dashboard
    ('ver_dashboard', 'Acceder a las gráficas y métricas principales del dashboard')
]

def inicializar_permisos():
    """
    Función que lee la lista PERMISOS_SISTEMA y se asegura de que
    todos existan en la tabla 'permisos' de la base de datos.
    Si encuentra uno nuevo, lo inserta y se lo asigna automáticamente
    al Administrador (rol_id = 2).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        for p_nombre, p_desc in PERMISOS_SISTEMA:
            cursor.execute("SELECT id FROM permisos WHERE nombre = %s", (p_nombre,))
            permiso_db = cursor.fetchone()
            
            if not permiso_db:
                # El permiso no existe en la BD, lo insertamos
                cursor.execute(
                    "INSERT INTO permisos (nombre, descripcion) VALUES (%s, %s)",
                    (p_nombre, p_desc)
                )
                nuevo_permiso_id = cursor.lastrowid
                
                # Le asignamos este nuevo permiso automáticamente al SuperAdmin (rol_id = 2)
                # para que los dueños nunca se queden sin acceso a lo nuevo
                cursor.execute(
                    "INSERT INTO roles_permisos (rol_id, permiso_id, permitido) VALUES (2, %s, 1)",
                    (nuevo_permiso_id,)
                )
                print(f"[*] Nuevo permiso registrado: {p_nombre}")
                
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[!] Error al sincronizar permisos: {e}")

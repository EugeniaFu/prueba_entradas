-- Este script sirve para configurar correctamente los permisos de la Secretaria
-- y dejar limpio el rol de Administrador.

-- 1. Primero, regresamos a todas las secretarias a rol_id = 3
UPDATE usuarios 
SET rol_id = 3 
WHERE rol_id = 2 AND sucursal_id IS NOT NULL;
-- (Es decir, si era un 'admin' que estaba anclado a una sucursal física, en realidad era secretaria/admin local)

-- 2. Limpiamos a los verdaderos los administradores (Los dueños)
UPDATE usuarios
SET sucursal_id = NULL
WHERE rol_id = 2;
-- (El Administrador Global no tiene sucursal fija)

-- 3. Vamos a inyectar todos los permisos que necesita la Secretaria (rol_id = 3)
-- Primero listamos rápidamente los permisos típicos.
-- (Modifica estos ID o nombres de permiso según tu tabla 'permisos')

-- Supongamos que quieres que la secretaria tenga los siguientes permisos:
-- (Asegúrate de que la palabra coincida con la columna "nombre" de tu tabla permisos)

INSERT IGNORE INTO roles_permisos (rol_id, permiso_id, permitido)
SELECT 3, id, 1 FROM permisos 
WHERE nombre IN (
    'ver_rentas', 
    'crear_renta', 
    'editar_renta',
    'ver_clientes', 
    'crear_cliente', 
    'editar_cliente',
    'ver_cotizaciones',
    'crear_cotizacion',
    'ver_inventario',
    'crear_movimiento_caja'
);

-- NOTA IMPORTANTE: Si ya usas el rol "Secretaria" debes asegurarte
-- que permisos como 'ver_empleados' o 'ver_inventario_general' NO
-- estén en este grupo.
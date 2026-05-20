from utils.db import get_db_connection

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

print("=" * 60)
print("LIMPIEZA DE PERMISOS INDIVIDUALES INCORRECTOS")
print("=" * 60)

# Encontrar permisos individuales activados que NO deberían estar
cursor.execute("""
    SELECT up.usuario_id, up.permiso_id, u.nombre, u.apellido1, p.nombre as permiso_nombre, up.permitido
    FROM usuarios_permisos up
    JOIN usuarios u ON up.usuario_id = u.id
    JOIN permisos p ON up.permiso_id = p.id
    WHERE u.rol_id = 3 
    AND p.nombre IN ('ver_empleados', 'ver_inventario_general')
    AND up.permitido = 1
""")
permisos_incorrectos = cursor.fetchall()

if permisos_incorrectos:
    print(f"\nEncontrados {len(permisos_incorrectos)} permisos individuales activados incorrectamente:")
    for pi in permisos_incorrectos:
        print(f"  - {pi['nombre']} {pi['apellido1']}: {pi['permiso_nombre']}")
    
    # Eliminar estos permisos
    print("\nEliminando permisos individuales activados...")
    for pi in permisos_incorrectos:
        cursor.execute("DELETE FROM usuarios_permisos WHERE usuario_id = %s AND permiso_id = %s", 
                      (pi['usuario_id'], pi['permiso_id']))
        print(f"  ✓ Eliminado: {pi['permiso_nombre']} para {pi['nombre']} {pi['apellido1']}")
    
    conn.commit()
    print("\n✅ Permisos eliminados correctamente")
else:
    print("\n✓ No se encontraron permisos individuales activados incorrectamente")

# Verificar si hay permisos desactivados (que sí deberían estar)
cursor.execute("""
    SELECT up.usuario_id, up.permiso_id, u.nombre, u.apellido1, p.nombre as permiso_nombre
    FROM usuarios_permisos up
    JOIN usuarios u ON up.usuario_id = u.id
    JOIN permisos p ON up.permiso_id = p.id
    WHERE u.rol_id = 3 
    AND p.nombre IN ('ver_empleados', 'ver_inventario_general')
    AND up.permitido = 0
""")
permisos_desactivados = cursor.fetchall()

if permisos_desactivados:
    print(f"\n✓ Encontrados {len(permisos_desactivados)} permisos correctamente desactivados:")
    for pd in permisos_desactivados:
        print(f"  - {pd['nombre']} {pd['apellido1']}: {pd['permiso_nombre']} (DESACTIVADO)")

cursor.close()
conn.close()

print("\n" + "=" * 60)
print("LIMPIEZA COMPLETADA")
print("=" * 60)
print("\n⚠️  IMPORTANTE: Los usuarios deben cerrar sesión y volver a")
print("    iniciar sesión para que los cambios tengan efecto.")
print("=" * 60)

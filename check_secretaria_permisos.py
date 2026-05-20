from utils.db import get_db_connection

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

print("=" * 60)
print("VERIFICACIÓN DE PERMISOS - ROL SECRETARIA (rol_id=3)")
print("=" * 60)

# 1. Verificar permisos del rol
cursor.execute("""
    SELECT p.nombre, rp.permitido 
    FROM roles_permisos rp 
    JOIN permisos p ON rp.permiso_id = p.id 
    WHERE rp.rol_id = 3 
    AND p.nombre IN ('ver_empleados', 'ver_inventario_general')
    ORDER BY p.nombre
""")
permisos_rol = cursor.fetchall()

print("\n1. Permisos asignados al ROL Secretaria:")
if permisos_rol:
    for p in permisos_rol:
        estado = "✓ ACTIVO" if p['permitido'] else "✗ DESACTIVADO"
        print(f"   - {p['nombre']}: {estado}")
else:
    print("   [No tiene estos permisos asignados al rol]")

# 2. Verificar si hay usuarios secretaria
cursor.execute("SELECT id, nombre, apellido1, correo FROM usuarios WHERE rol_id = 3")
usuarios_secretaria = cursor.fetchall()

print(f"\n2. Usuarios con rol Secretaria: {len(usuarios_secretaria)}")
for u in usuarios_secretaria:
    print(f"   - {u['nombre']} {u['apellido1']} ({u['correo']}) - ID: {u['id']}")
    
    # Verificar permisos individuales desactivados
    cursor.execute("""
        SELECT p.nombre, up.permitido 
        FROM usuarios_permisos up 
        JOIN permisos p ON up.permiso_id = p.id 
        WHERE up.usuario_id = %s 
        AND p.nombre IN ('ver_empleados', 'ver_inventario_general')
    """, (u['id'],))
    permisos_usuario = cursor.fetchall()
    
    if permisos_usuario:
        print(f"     Permisos individuales:")
        for pu in permisos_usuario:
            estado = "ACTIVADO" if pu['permitido'] else "DESACTIVADO"
            print(f"       • {pu['nombre']}: {estado}")

# 3. Simular cálculo de permisos finales para un usuario secretaria (si existe)
if usuarios_secretaria:
    usuario_id = usuarios_secretaria[0]['id']
    print(f"\n3. Simulación de permisos finales para usuario ID {usuario_id}:")
    
    # Permisos del rol
    cursor.execute("""
        SELECT p.nombre 
        FROM permisos p 
        JOIN roles_permisos rp ON p.id = rp.permiso_id 
        WHERE rp.rol_id = 3 AND rp.permitido = 1
    """)
    permisos_rol_calc = {row['nombre'] for row in cursor.fetchall()}
    
    # Permisos desactivados
    cursor.execute("""
        SELECT p.nombre 
        FROM permisos p 
        JOIN usuarios_permisos up ON p.id = up.permiso_id 
        WHERE up.usuario_id = %s AND up.permitido = 0
    """, (usuario_id,))
    permisos_desactivados = {row['nombre'] for row in cursor.fetchall()}
    
    # Permisos activados
    cursor.execute("""
        SELECT p.nombre 
        FROM permisos p 
        JOIN usuarios_permisos up ON p.id = up.permiso_id 
        WHERE up.usuario_id = %s AND up.permitido = 1
    """, (usuario_id,))
    permisos_activados = {row['nombre'] for row in cursor.fetchall()}
    
    # Cálculo final
    permisos_finales = list((permisos_rol_calc | permisos_activados) - permisos_desactivados)
    
    print(f"   Permisos del rol: {len(permisos_rol_calc)}")
    print(f"   Permisos activados individuales: {len(permisos_activados)}")
    print(f"   Permisos desactivados individuales: {len(permisos_desactivados)}")
    print(f"   PERMISOS FINALES: {len(permisos_finales)}")
    
    # Verificar específicamente los dos permisos problemáticos
    print(f"\n   ¿Tiene 'ver_empleados'? {'SÍ ✓' if 'ver_empleados' in permisos_finales else 'NO ✗'}")
    print(f"   ¿Tiene 'ver_inventario_general'? {'SÍ ✓' if 'ver_inventario_general' in permisos_finales else 'NO ✗'}")

cursor.close()
conn.close()

print("\n" + "=" * 60)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 60)

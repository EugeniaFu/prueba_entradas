from utils.db import get_db_connection

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

print("=" * 70)
print("LIMPIEZA: PERMISOS INDIVIDUALES QUE NO CORRESPONDEN AL ROL")
print("=" * 70)

# Obtener usuarios secretaria
cursor.execute("SELECT id, nombre, apellido1 FROM usuarios WHERE rol_id = 3")
secretarias = cursor.fetchall()

total_eliminados = 0

for sec in secretarias:
    print(f"\n{'='*70}")
    print(f"Usuario: {sec['nombre']} {sec['apellido1']} (ID: {sec['id']})")
    print(f"{'='*70}")
    
    # Permisos del rol
    cursor.execute("""
        SELECT p.id
        FROM permisos p 
        JOIN roles_permisos rp ON p.id = rp.permiso_id 
        WHERE rp.rol_id = 3 AND rp.permitido = 1
    """)
    permisos_rol_ids = {row['id'] for row in cursor.fetchall()}
    
    # Permisos activados individualmente que NO están en el rol
    cursor.execute("""
        SELECT up.usuario_id, up.permiso_id, p.nombre, p.descripcion
        FROM usuarios_permisos up
        JOIN permisos p ON up.permiso_id = p.id 
        WHERE up.usuario_id = %s AND up.permitido = 1
    """, (sec['id'],))
    permisos_activados = cursor.fetchall()
    
    permisos_a_eliminar = []
    for pa in permisos_activados:
        if pa['permiso_id'] not in permisos_rol_ids:
            permisos_a_eliminar.append(pa)
    
    if permisos_a_eliminar:
        print(f"\n🗑️  Eliminando {len(permisos_a_eliminar)} permisos activados incorrectamente:")
        for pe in permisos_a_eliminar:
            print(f"   ✓ {pe['nombre']}: {pe['descripcion']}")
            cursor.execute("""
                DELETE FROM usuarios_permisos 
                WHERE usuario_id = %s AND permiso_id = %s
            """, (pe['usuario_id'], pe['permiso_id']))
            total_eliminados += 1
        conn.commit()
    else:
        print("\n✅ No hay permisos activados incorrectos")
    
    # También eliminar permisos desactivados que NO están en el rol (innecesarios)
    cursor.execute("""
        SELECT up.usuario_id, up.permiso_id, p.nombre
        FROM usuarios_permisos up
        JOIN permisos p ON up.permiso_id = p.id 
        WHERE up.usuario_id = %s AND up.permitido = 0
    """, (sec['id'],))
    permisos_desactivados = cursor.fetchall()
    
    desactivados_innecesarios = []
    for pd in permisos_desactivados:
        if pd['permiso_id'] not in permisos_rol_ids:
            desactivados_innecesarios.append(pd)
    
    if desactivados_innecesarios:
        print(f"\n🧹 Eliminando {len(desactivados_innecesarios)} permisos desactivados innecesarios:")
        for pd in desactivados_innecesarios:
            print(f"   ✓ {pd['nombre']}")
            cursor.execute("""
                DELETE FROM usuarios_permisos 
                WHERE usuario_id = %s AND permiso_id = %s
            """, (pd['usuario_id'], pd['permiso_id']))
            total_eliminados += 1
        conn.commit()

cursor.close()
conn.close()

print("\n" + "=" * 70)
print(f"✅ LIMPIEZA COMPLETADA: {total_eliminados} registros eliminados")
print("=" * 70)
print("\n⚠️  IMPORTANTE: Los usuarios deben cerrar sesión y volver a")
print("    iniciar sesión para que los cambios tengan efecto.")
print("=" * 70)

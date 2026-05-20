from utils.db import get_db_connection

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

print("=" * 70)
print("ANÁLISIS: PERMISOS DEL ROL vs PERMISOS INDIVIDUALES ACTIVADOS")
print("=" * 70)

# Obtener usuarios secretaria
cursor.execute("SELECT id, nombre, apellido1 FROM usuarios WHERE rol_id = 3")
secretarias = cursor.fetchall()

for sec in secretarias:
    print(f"\n{'='*70}")
    print(f"Usuario: {sec['nombre']} {sec['apellido1']} (ID: {sec['id']})")
    print(f"{'='*70}")
    
    # Permisos del rol
    cursor.execute("""
        SELECT p.nombre 
        FROM permisos p 
        JOIN roles_permisos rp ON p.id = rp.permiso_id 
        WHERE rp.rol_id = 3 AND rp.permitido = 1
        ORDER BY p.nombre
    """)
    permisos_rol = {row['nombre'] for row in cursor.fetchall()}
    
    # Permisos activados individualmente
    cursor.execute("""
        SELECT p.nombre, p.descripcion
        FROM permisos p 
        JOIN usuarios_permisos up ON p.id = up.permiso_id 
        WHERE up.usuario_id = %s AND up.permitido = 1
        ORDER BY p.nombre
    """, (sec['id'],))
    permisos_activados = cursor.fetchall()
    
    # Permisos desactivados individualmente
    cursor.execute("""
        SELECT p.nombre, p.descripcion
        FROM permisos p 
        JOIN usuarios_permisos up ON p.id = up.permiso_id 
        WHERE up.usuario_id = %s AND up.permitido = 0
        ORDER BY p.nombre
    """, (sec['id'],))
    permisos_desactivados = cursor.fetchall()
    
    print(f"\n📊 Resumen:")
    print(f"   - Permisos del rol Secretaria: {len(permisos_rol)}")
    print(f"   - Permisos activados individuales: {len(permisos_activados)}")
    print(f"   - Permisos desactivados individuales: {len(permisos_desactivados)}")
    
    # Permisos activados que NO están en el rol (INCORRECTOS)
    permisos_incorrectos = []
    for pa in permisos_activados:
        if pa['nombre'] not in permisos_rol:
            permisos_incorrectos.append(pa)
    
    if permisos_incorrectos:
        print(f"\n⚠️  PROBLEMA: {len(permisos_incorrectos)} permisos activados que NO pertenecen al rol:")
        for pi in permisos_incorrectos:
            print(f"      • {pi['nombre']}: {pi['descripcion']}")
    else:
        print(f"\n✅ Todos los permisos activados pertenecen al rol")
    
    # Permisos desactivados que NO están en el rol (INNECESARIOS)
    desactivados_innecesarios = []
    for pd in permisos_desactivados:
        if pd['nombre'] not in permisos_rol:
            desactivados_innecesarios.append(pd)
    
    if desactivados_innecesarios:
        print(f"\n⚠️  LIMPIEZA: {len(desactivados_innecesarios)} permisos desactivados que no pertenecen al rol (innecesarios):")
        for pd in desactivados_innecesarios:
            print(f"      • {pd['nombre']}")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("ANÁLISIS COMPLETADO")
print("=" * 70)
print("\n💡 Los permisos individuales ACTIVADOS solo deberían usarse para")
print("   agregar permisos que NO tiene el rol.")
print("   Los permisos individuales DESACTIVADOS solo deberían usarse para")
print("   quitar permisos que SÍ tiene el rol.")
print("=" * 70)

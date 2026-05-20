from utils.db import get_db_connection

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

print("=" * 70)
print("SIMULACIÓN: PERMISOS AL CREAR UN NUEVO EMPLEADO CON ROL SECRETARIA")
print("=" * 70)

# Obtener información del rol Secretaria
cursor.execute("SELECT * FROM roles WHERE id = 3")
rol_secretaria = cursor.fetchone()

print(f"\n📋 Rol: {rol_secretaria['nombre']}")
print(f"    ID: {rol_secretaria['id']}")

# Obtener permisos asignados al rol Secretaria
cursor.execute("""
    SELECT p.id, p.nombre, p.descripcion
    FROM permisos p
    JOIN roles_permisos rp ON p.id = rp.permiso_id
    WHERE rp.rol_id = 3 AND rp.permitido = 1
    ORDER BY p.nombre
""")
permisos_rol = cursor.fetchall()

print(f"\n✅ Permisos que aparecerán en el modal de permisos del empleado: {len(permisos_rol)}")
print("\n" + "=" * 70)
print("LISTA DE PERMISOS QUE VERÁ EL ADMINISTRADOR:")
print("=" * 70)

# Agrupar por módulo para mejor visualización
modulos = {}
for p in permisos_rol:
    nombre = p['nombre']
    # Extraer módulo del nombre del permiso
    if 'cliente' in nombre:
        modulo = 'CLIENTES'
    elif 'inventario_sucursal' in nombre or 'reparacion' in nombre:
        modulo = 'INVENTARIO SUCURSAL'
    elif 'producto' in nombre:
        modulo = 'PRODUCTOS'
    elif 'renta' in nombre or 'renovacion' in nombre:
        modulo = 'RENTAS'
    elif 'cotizacion' in nombre:
        modulo = 'COTIZACIONES'
    elif 'nota_entrada' in nombre or 'nota_salida' in nombre:
        modulo = 'NOTAS DE ENTRADA/SALIDA'
    elif 'prefactura' in nombre:
        modulo = 'PREFACTURAS'
    elif 'salida_interna' in nombre:
        modulo = 'SALIDAS INTERNAS'
    elif 'dashboard' in nombre:
        modulo = 'DASHBOARD'
    elif 'perfil' in nombre:
        modulo = 'PERFIL'
    else:
        modulo = 'OTROS'
    
    if modulo not in modulos:
        modulos[modulo] = []
    modulos[modulo].append(p)

for modulo, permisos in sorted(modulos.items()):
    print(f"\n📂 {modulo} ({len(permisos)} permisos):")
    for p in permisos:
        print(f"   ☑️  {p['descripcion']}")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("RESUMEN DEL FUNCIONAMIENTO:")
print("=" * 70)
print("""
1. 📝 Al crear un nuevo empleado con rol 'Secretaria'
2. 🔧 En el botón de permisos aparecerán estos 39 permisos
3. ✅ Todos estarán ACTIVADOS por defecto (heredados del rol)
4. 🔀 Puedes DESACTIVAR individualmente los que NO quieres que tenga
5. 🚫 NO aparecerán los otros 43 permisos que el rol no tiene

💡 Ejemplo:
   - Si quieres que una secretaria NO pueda ver cotizaciones:
     → Desactivas 'ver_cotizaciones' solo para ese empleado
   - Si quieres que TODAS las secretarias dejen de ver cotizaciones:
     → Vas a /roles y desactivas 'ver_cotizaciones' para el rol Secretaria
""")
print("=" * 70)

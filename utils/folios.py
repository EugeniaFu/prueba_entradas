"""
Utilidades para generación de folios consecutivos por sucursal
"""

def obtener_siguiente_folio_nota_sucursal(cursor, sucursal_id):
    """
    Obtiene el siguiente folio consecutivo para notas de una sucursal específica.
    Considera todos los tipos de notas: entrada, salida, transferencias, salidas internas, etc.
    
    Args:
        cursor: Cursor de base de datos MySQL
        sucursal_id: ID de la sucursal
        
    Returns:
        int: Siguiente número de folio disponible
    """
    cursor.execute("""
        SELECT IFNULL(MAX(folio), 0) + 1 AS siguiente_folio
        FROM (
            SELECT ne.folio 
            FROM notas_entrada ne
            JOIN rentas r ON ne.renta_id = r.id
            WHERE r.id_sucursal = %s
            UNION ALL
            SELECT ns.folio 
            FROM notas_salida ns
            JOIN rentas r ON ns.renta_id = r.id
            WHERE r.id_sucursal = %s
            UNION ALL
            SELECT CAST(mi.folio_nota_salida AS UNSIGNED) as folio
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s 
            AND mi.folio_nota_salida IS NOT NULL
            AND mi.folio_nota_salida != ''
            AND mi.tipo_movimiento IN ('transferencia_salida', 'reparacion_lote', 'salida_interna', 'baja_equipo_general')
            UNION ALL
            SELECT CAST(mi.folio_nota_entrada AS UNSIGNED) as folio
            FROM movimientos_inventario mi
            WHERE mi.id_sucursal = %s 
            AND mi.folio_nota_entrada IS NOT NULL
            AND mi.folio_nota_entrada != ''
            AND mi.tipo_movimiento IN ('alta_equipo', 'alta_equipo_general', 'transferencia_entrada', 'retorno_salida_interna', 'finalizar_reparacion')
            UNION ALL
            SELECT si.folio_sucursal as folio
            FROM salidas_internas si
            WHERE si.id_sucursal = %s
            UNION ALL
            SELECT sie.folio as folio
            FROM salidas_internas_entradas sie
            JOIN salidas_internas si2 ON sie.salida_interna_id = si2.id
            WHERE si2.id_sucursal = %s
        ) AS todos_folios_sucursal
    """, (sucursal_id, sucursal_id, sucursal_id, sucursal_id, sucursal_id, sucursal_id))

    resultado = cursor.fetchone()
    return resultado['siguiente_folio'] if resultado and resultado.get('siguiente_folio') else 1


def obtener_siguiente_folio_renta_sucursal(cursor, sucursal_id):
    """
    Obtiene el siguiente folio consecutivo para una renta de una sucursal específica.
    Cada sucursal tiene su propia secuencia, inicia en 1.

    Args:
        cursor: Cursor de base de datos MySQL (tipo tupla)
        sucursal_id: ID de la sucursal

    Returns:
        int: Siguiente número de folio disponible
    """
    cursor.execute("""
        SELECT IFNULL(MAX(folio), 0) + 1
        FROM rentas
        WHERE id_sucursal = %s
    """, (sucursal_id,))
    resultado = cursor.fetchone()
    return resultado[0] if resultado and resultado[0] else 1

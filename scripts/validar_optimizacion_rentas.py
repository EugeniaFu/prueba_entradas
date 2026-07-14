"""
Script de validación: compara los resultados de la consulta VIEJA (antes de la
optimización) contra la NUEVA (ya integrada en services/renta_service.py) para
el listado de rentas por sucursal/estado.

Uso:
    python scripts/validar_optimizacion_rentas.py

Requiere las mismas variables de entorno que usa la app (DB_HOST, DB_USER,
DB_PASSWORD, DB_NAME, DB_PORT) -- si corres esto en el VPS dentro del venv con
el .env ya cargado, funciona igual que la app.

No modifica datos: ambas consultas son de solo lectura.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import mysql.connector


def get_conn():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
        charset='utf8mb4',
    )


QUERY_VIEJA_TEMPLATE = """
SELECT
    r.id,
    (
        CASE
            WHEN (
                SELECT COUNT(*) FROM notas_entrada ne
                WHERE ne.renta_id = r.id OR ne.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = r.id)
            ) > 0
            THEN (
                SELECT COUNT(*) FROM (
                    SELECT nsd.id_pieza,
                        nsd.cantidad AS cantidad_salida,
                        (
                            SELECT COALESCE(SUM(ned2.cantidad_recibida), 0)
                            FROM notas_entrada ne2
                            JOIN notas_entrada_detalle ned2 ON ned2.nota_entrada_id = ne2.id
                            WHERE (
                                ne2.renta_id = r.id
                                OR ne2.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = r.id)
                            )
                            AND ned2.id_pieza = nsd.id_pieza
                        ) AS cantidad_recibida_total
                    FROM notas_salida ns
                    JOIN notas_salida_detalle nsd ON nsd.nota_salida_id = ns.id
                    WHERE ns.renta_id = r.id
                    GROUP BY nsd.id_pieza, nsd.cantidad
                    HAVING nsd.cantidad > (
                        SELECT COALESCE(SUM(ned2.cantidad_recibida), 0)
                        FROM notas_entrada ne2
                        JOIN notas_entrada_detalle ned2 ON ned2.nota_entrada_id = ne2.id
                        WHERE (
                            ne2.renta_id = r.id
                            OR ne2.renta_id IN (SELECT id FROM rentas WHERE renta_asociada_id = r.id)
                        )
                        AND ned2.id_pieza = nsd.id_pieza
                    )
                ) AS pendientes
            )
            ELSE 0
        END
    ) AS piezas_pendientes,
    r.estado_cobro_extra,
    ne.estado_retraso
FROM rentas r
LEFT JOIN notas_entrada ne ON ne.renta_id = r.id
    AND ne.id = (SELECT MAX(id) FROM notas_entrada WHERE renta_id = r.id)
{where_sucursal}
"""


def piezas_pendientes_viejo(cursor, sucursal_id):
    """Recalcula igual que la consulta vieja pero solo trayendo lo necesario
    para clasificar activas/pagadas (evita duplicar toda la consulta de UI)."""
    where = "WHERE r.id_sucursal = %s" if sucursal_id != 'todas' else "WHERE 1=1"
    params = (sucursal_id,) if sucursal_id != 'todas' else ()
    cursor.execute(QUERY_VIEJA_TEMPLATE.format(where_sucursal=where), params)
    # row = (id, piezas_pendientes, estado_cobro_extra, estado_retraso)
    return {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall()}


def clasificar(estado_renta, estado_pago, piezas_pendientes, estado_retraso, estado_cobro_extra):
    er = (estado_renta or '').strip().lower()
    ep = (estado_pago or '').strip().lower()
    es_activa = (
        er in ('en curso', 'activo', 'activa renovacion', 'en recolección', 'programada', 'entrega parcial')
        or (er == 'finalizada' and ep in ('pago pendiente', 'saldo pendiente'))
        or piezas_pendientes > 0
        or estado_retraso == 'Retraso Pendiente'
        or estado_cobro_extra == 'Extra Pendiente'
    )
    es_pagada = (
        (er == 'finalizada' and ep == 'pago realizado' and piezas_pendientes == 0)
        or er == 'cancelada'
    ) and (estado_retraso != 'Retraso Pendiente') and (estado_cobro_extra != 'Extra Pendiente')
    return es_activa, es_pagada


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from services.renta_service import RentasService

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre FROM sucursales ORDER BY id")
    sucursales = cursor.fetchall()

    total_diffs = 0

    for sucursal_id, nombre in sucursales:
        print(f"\n=== Sucursal {sucursal_id} - {nombre} ===")

        # --- VIEJA: clasificar manualmente activa/pagada por renta ---
        t0 = time.time()
        cursor.execute("SELECT id, estado_renta, estado_pago FROM rentas WHERE id_sucursal = %s", (sucursal_id,))
        rentas_base = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        pendientes_map = piezas_pendientes_viejo(cursor, sucursal_id)

        activas_viejo = set()
        pagadas_viejo = set()
        for renta_id, (estado_renta, estado_pago) in rentas_base.items():
            pend, extra, retraso = pendientes_map.get(renta_id, (0, None, None))
            es_activa, es_pagada = clasificar(estado_renta, estado_pago, pend, retraso, extra)
            if es_activa:
                activas_viejo.add(renta_id)
            if es_pagada:
                pagadas_viejo.add(renta_id)
        t_viejo = time.time() - t0

        # --- NUEVA: usar el service ya optimizado ---
        t0 = time.time()
        activas_nuevo = {row[0] for row in RentasService.obtener_rentas_por_sucursal_y_estado(sucursal_id, False, 'activas')}
        pagadas_nuevo = {row[0] for row in RentasService.obtener_rentas_por_sucursal_y_estado(sucursal_id, False, 'pagadas')}
        t_nuevo = time.time() - t0

        diff_activas = activas_viejo.symmetric_difference(activas_nuevo)
        diff_pagadas = pagadas_viejo.symmetric_difference(pagadas_nuevo)

        print(f"  Tiempo viejo: {t_viejo:.2f}s | Tiempo nuevo: {t_nuevo:.2f}s")
        print(f"  Activas -> viejo: {len(activas_viejo)}, nuevo: {len(activas_nuevo)}, diferencias: {len(diff_activas)}")
        print(f"  Pagadas -> viejo: {len(pagadas_viejo)}, nuevo: {len(pagadas_nuevo)}, diferencias: {len(diff_pagadas)}")

        if diff_activas:
            print(f"  IDs distintos en ACTIVAS: {sorted(diff_activas)[:20]}{'...' if len(diff_activas) > 20 else ''}")
        if diff_pagadas:
            print(f"  IDs distintos en PAGADAS: {sorted(diff_pagadas)[:20]}{'...' if len(diff_pagadas) > 20 else ''}")

        total_diffs += len(diff_activas) + len(diff_pagadas)

    cursor.close()
    conn.close()

    print("\n" + "=" * 50)
    if total_diffs == 0:
        print("OK: la consulta nueva coincide exactamente con la vieja en todas las sucursales.")
    else:
        print(f"ATENCION: se encontraron {total_diffs} rentas con clasificacion distinta. Revisar antes de desplegar.")


if __name__ == '__main__':
    main()

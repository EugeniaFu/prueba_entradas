# Solución para Cobro de Retraso en Renovaciones

## Problema Identificado
Las renovaciones no pueden generar cobros de retraso porque:
1. Se bloquea la creación de notas de entrada para renovaciones
2. El cobro de retraso requiere una nota de entrada para calcular días de retraso
3. Esto crea un conflicto que impide cobrar retrasos en renovaciones

## Opción 1: Modelo "Renovación Virtual" (RECOMENDADO)

### Cambios necesarios:

1. **Crear nota de entrada virtual automática para renovaciones**
2. **Modificar el cálculo de retraso para considerar fechas de renovación**
3. **Permitir cobro de retraso sin devolución física**

### Archivos a modificar:

#### A. routes/notas_entrada.py - Permitir notas virtuales para renovaciones
```python
# En lugar de bloquear completamente, crear nota virtual
if sucursal_row['renta_asociada_id'] is not None:
    # Es una renovación - crear nota de entrada virtual automática
    return crear_nota_entrada_virtual_renovacion(renta_id)
```

#### B. routes/cobro_retraso.py - Mejorar la lógica de detección
```python
# Buscar nota de entrada (real o virtual)
cursor.execute("""
    SELECT ne.id AS nota_entrada_id, ne.estado_retraso, ne.fecha_entrada_real, 
           r.fecha_entrada, r.traslado, r.renta_asociada_id, r.estado_renta
    FROM notas_entrada ne
    RIGHT JOIN rentas r ON ne.renta_id = r.id
    WHERE r.id = %s
    ORDER BY ne.id DESC LIMIT 1
""", (renta_id,))
```

#### C. Base de datos - Agregar campo para distinguir notas virtuales
```sql
ALTER TABLE notas_entrada ADD COLUMN es_virtual BOOLEAN DEFAULT FALSE;
```

## Opción 2: Modelo "Sin Retraso en Renovaciones"

Si las renovaciones NO pueden tener retrasos, entonces:
1. Remover botones de cobro de retraso para renovaciones
2. Mostrar mensaje explicativo
3. Solo permitir cobro de retraso en rentas originales

## Opción 3: Modelo "Devolución Obligatoria"

Si las renovaciones SÍ requieren devolución física:
1. Remover el bloqueo de notas de entrada para renovaciones
2. Tratar renovaciones igual que rentas normales
3. Requerir devolución física para cualquier renovación

## Recomendación

**Opción 1** es la más práctica porque:
- Mantiene la lógica de negocio (no hay devolución física)
- Permite cobrar retrasos cuando corresponda
- Es transparente para el usuario final
- Requiere cambios mínimos en el frontend
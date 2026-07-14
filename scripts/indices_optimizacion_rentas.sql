-- Índices para acelerar el módulo de rentas (listado de activas/pagadas).
-- Seguro de correr en cualquier momento: solo agrega índices, no cambia datos ni lógica.
-- Si algún índice ya existe, MySQL devolverá un error "Duplicate key name" para esa
-- línea en particular -- puedes ignorarlo y seguir con las demás.

CREATE INDEX idx_notas_salida_renta_id ON notas_salida (renta_id);
CREATE INDEX idx_notas_salida_detalle_nota_salida_id ON notas_salida_detalle (nota_salida_id);

CREATE INDEX idx_notas_entrada_renta_id ON notas_entrada (renta_id);
CREATE INDEX idx_notas_entrada_detalle_nota_entrada_id ON notas_entrada_detalle (nota_entrada_id);

CREATE INDEX idx_rentas_renta_asociada_id ON rentas (renta_asociada_id);
CREATE INDEX idx_rentas_id_sucursal ON rentas (id_sucursal);

CREATE INDEX idx_notas_cobro_extra_nota_entrada_id ON notas_cobro_extra (nota_entrada_id);
CREATE INDEX idx_notas_cobro_retraso_nota_entrada_id ON notas_cobro_retraso (nota_entrada_id);

-- Compuestos: ayudan a los GROUP BY de la nueva consulta de piezas pendientes
CREATE INDEX idx_notas_salida_detalle_pieza ON notas_salida_detalle (id_pieza);
CREATE INDEX idx_notas_entrada_detalle_pieza ON notas_entrada_detalle (id_pieza);

document.addEventListener('DOMContentLoaded', function () {
    const modalEl = document.getElementById('modalNuevaRentaRenovacion');
    const botones = document.querySelectorAll('.btn-abrir-modal-renovacion');
    const formRenovar = document.getElementById('form-renovar-renta');
    
    // Función global para abrir modal de renovación
    window.abrirModalRenovacion = function(rentaId, tipo = 'completa') {
        formRenovar.action = `/rentas/renovar/${rentaId}`;
        document.getElementById('renta_id_hidden').value = rentaId;
        
        // Actualizar título según tipo
        const titulo = document.querySelector('#modalNuevaRentaRenovacionLabel');
        if (titulo) {
            titulo.innerHTML = tipo === 'parcial' 
                ? '<i class="bi bi-arrow-repeat"></i> Renovar Equipos Pendientes'
                : '<i class="bi bi-arrow-repeat"></i> Renovar Renta Completa';
        }
        
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
        cargarDatosRenta(rentaId, tipo);
    };
    const fechaInicioInput = document.getElementById('fecha_salida_modal');
    const fechaFinInput = document.getElementById('fecha_entrada_modal');
    const tbody = document.querySelector('#tabla-productos-renovacion tbody');
    const trasladoEl = document.getElementById('costo_traslado');

    // Función para calcular días según fechas
    function calcularDiasRenta() {
        const inicio = fechaInicioInput.value;
        const fin = fechaFinInput.value;
        if (!inicio || !fin) return 1;
        let dias = Math.floor((new Date(fin) - new Date(inicio)) / (1000 * 60 * 60 * 24)) + 1;
        return dias < 1 ? 1 : dias;
    }

    // Obtener precio según días y producto
    function obtenerPrecioProducto(productoId, dias) {
        const precios = window.preciosProductos ? window.preciosProductos[String(productoId)] : null;
        if (!precios) return 0;
        if (precios.precio_unico === 1) return precios.precio_dia;
        if (dias <= 2) return precios.precio_dia;
        if (dias >= 3 && dias <= 14) return precios.precio_7dias;
        if (dias >= 15 && dias <= 29) return precios.precio_15dias;
        if (dias >= 30) return precios.precio_30dias;
        return precios.precio_dia;
    }

    // Recalcular totales dinámicos
    function recalcularTotalesDinamicos() {
        let subtotal = 0;
        tbody.querySelectorAll('tr').forEach(fila => {
            const cantidad = parseFloat(fila.querySelector('.cantidad').value) || 0;
            const dias = parseFloat(fila.querySelector('.dias').value) || 1;
            const costo = parseFloat(fila.querySelector('.costo').value) || 0;
            const filaSubtotal = cantidad * dias * costo;
            fila.querySelector('.subtotal').value = filaSubtotal.toFixed(2);
            subtotal += filaSubtotal;
        });

        const traslado = trasladoEl ? parseFloat(trasladoEl.value) || 0 : 0;
        const subtotalConTraslado = subtotal + traslado;
        const iva = subtotalConTraslado * 0.16;
        const total = subtotalConTraslado + iva;

        const container = document.getElementById('totales_container');
        container.innerHTML = `
            <table class="table table-sm">
                <tr>
                    <td>Subtotal</td>
                    <td id="subtotal_general">$${subtotal.toFixed(2)}</td>
                </tr>
                <tr>
                    <td>+IVA (16%)</td>
                    <td id="iva_general">$${iva.toFixed(2)}</td>
                </tr>
                <tr>
                    <td><strong>Total</strong></td>
                    <td id="total_general"><strong>$${total.toFixed(2)}</strong></td>
                </tr>
            </table>
        `;
    }

    // Actualizar días y precios según fechas
    function actualizarDiasYPrecios() {
        const dias = calcularDiasRenta();
        tbody.querySelectorAll('tr').forEach(fila => {
            const diasInput = fila.querySelector('.dias');
            const costoInput = fila.querySelector('.costo');
            const productoIdInput = fila.querySelector('input[name="producto_id[]"]');

            if (diasInput && costoInput && productoIdInput) {
                diasInput.value = dias;
                // Si el campo tiene data-fijo, no actualizar el precio
                if (!costoInput.hasAttribute('data-fijo') || costoInput.getAttribute('data-fijo') !== '1') {
                    const precio = obtenerPrecioProducto(productoIdInput.value, dias);
                    costoInput.value = precio.toFixed(2);
                }
            }
        });

        recalcularTotalesDinamicos();
    }

    // Función para cargar datos de renta unificada
    function cargarDatosRenta(rentaId, tipo = 'completa') {
        // Limpiar tabla y campos
        tbody.innerHTML = '';
        document.getElementById('cliente_nombre_modal').value = 'Cargando...';
        document.getElementById('direccion_obra_modal').value = '';
        fechaInicioInput.value = '';
        fechaFinInput.value = '';
        document.getElementById('observaciones_modal').value = '';

        fetch(`/rentas/detalle/${rentaId}`)
            .then(res => res.json())
            .then(data => {
                document.getElementById('cliente_nombre_modal').value = data.cliente.nombre || '';
                document.getElementById('direccion_obra_modal').value = data.renta.direccion_obra || '';
                fechaInicioInput.value = data.renta.fecha_salida?.substring(0, 10) || '';
                fechaFinInput.value = data.renta.fecha_entrada?.substring(0, 10) || '';
                document.getElementById('observaciones_modal').value = data.renta.observaciones || '';

                if (Array.isArray(data.productos)) {
                    let productosParaMostrar = data.productos;
                    
                    // Si es tipo 'parcial', filtrar solo productos pendientes
                    if (tipo === 'parcial') {
                        productosParaMostrar = data.productos.filter(p => (p.cantidad_pendiente || 0) > 0);
                    }
                    
                    productosParaMostrar.forEach(p => {
                        const cantidad = tipo === 'parcial' 
                            ? (Number(p.cantidad_pendiente) || 1)
                            : (Number(p.cantidad) || 1);
                        const dias = calcularDiasRenta();
                        // Usar precio original en renovaciones completas
                        const precio = (tipo === 'completa' && p.costo_unitario !== undefined)
                            ? parseFloat(p.costo_unitario)
                            : obtenerPrecioProducto(p.id_producto, dias);

                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><input type="hidden" name="producto_id[]" value="${p.id_producto}">${p.nombre}</td>
                            <td><input type="number" name="cantidad[]" class="form-control cantidad" min="1" value="${cantidad}"></td>
                            <td><input type="number" name="dias_renta[]" class="form-control dias" min="1" value="${dias}" readonly style="width:50px;"></td>
                            <td><input type="number" name="costo_unitario[]" class="form-control costo" step="0.01" min="0" value="${precio.toFixed(2)}" readonly data-fijo="${tipo === 'completa' ? '1' : ''}"></td>
                            <td><input type="number" class="form-control subtotal" step="0.01" min="0" value="${(cantidad*dias*precio).toFixed(2)}" readonly></td>
                            <td><button type="button" class="btn btn-danger btn-sm btn-quitar"><i class="bi bi-trash"></i></button></td>
                        `;
                        tbody.appendChild(tr);
                    });
                    actualizarDiasYPrecios();
                }
            })
            .catch(console.error);
    }

    // Abrir modal y cargar datos
    botones.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const rentaId = this.dataset.rentaId;
            abrirModalRenovacion(rentaId, 'completa');
        });
    });

    // Eliminar producto de la tabla
    tbody.addEventListener('click', function (e) {
        if (e.target.closest('.btn-quitar')) {
            e.target.closest('tr').remove();
            recalcularTotalesDinamicos();
        }
    });

    // Recalcular totales cuando cambian cantidad o costo
    tbody.addEventListener('input', function (e) {
        if (e.target.classList.contains('cantidad') || e.target.classList.contains('costo')) {
            recalcularTotalesDinamicos();
        }
    });

    // Recalcular totales cuando cambian fechas
    fechaInicioInput.addEventListener('change', actualizarDiasYPrecios);
    fechaFinInput.addEventListener('change', actualizarDiasYPrecios);

    // Recalcular totales cuando cambia traslado
    if (trasladoEl) trasladoEl.addEventListener('input', recalcularTotalesDinamicos);
});
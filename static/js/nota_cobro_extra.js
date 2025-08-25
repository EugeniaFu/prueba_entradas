document.addEventListener('DOMContentLoaded', function () {

    // --- Calcular total ---
    function actualizarTotalCobroExtra() {
        let subtotal = 0;
        document.querySelectorAll('.subtotal').forEach(input => {
            subtotal += parseFloat(input.value) || 0;
        });
        const iva = subtotal * 0.16;
        const totalConIva = subtotal + iva;

        const subtotalSpan = document.getElementById('subtotal-cobro-extra');
        const ivaSpan = document.getElementById('iva-cobro-extra');
        const totalConIvaSpan = document.getElementById('total-cobro-extra-con-iva');

        if (subtotalSpan) subtotalSpan.textContent = subtotal.toFixed(2);
        if (ivaSpan) ivaSpan.textContent = iva.toFixed(2);
        if (totalConIvaSpan) totalConIvaSpan.textContent = totalConIva.toFixed(2);
    }


    function redondearEfectivo(total) {
        const decimal = total - Math.floor(total);
        if (decimal <= 0.49) {
            return Math.floor(total);
        } else if (decimal >= 0.60) {
            return Math.ceil(total);
        } else if (decimal >= 0.50 && decimal <= 0.59) {
            return Math.floor(total) + 0.50;
        }
        return total;
    }

    // --- Calcular cambio ---
    function actualizarCambioCobroExtra() {
        const montoRecibidoInput = document.getElementById('monto-recibido-extra');
        const cambioInput = document.getElementById('cambio-extra');
        const total = parseFloat(document.getElementById('total-cobro-extra-con-iva').textContent) || 0;
        const montoRecibido = parseFloat(montoRecibidoInput.value) || 0;
        cambioInput.value = (montoRecibido - total).toFixed(2);
    }

    // --- Cargar piezas afectadas para sugerir detalles de cobro extra ---
    window.llenarModalCobroExtra = function (rentaId) {
        window.rentaIdCobroExtraActual = rentaId;
        const detalleDiv = document.getElementById('detalle-cobro-extra');
        detalleDiv.innerHTML = '<div class="text-center my-3"><span class="spinner-border"></span> Cargando...</div>';

        fetch(`/cobros_extra/sugerencias/${rentaId}`)
            .then(response => response.json())
            .then(data => {
                if (!data.detalles || data.detalles.length === 0) {
                    detalleDiv.innerHTML = '<div class="alert alert-warning">No hay piezas afectadas para cobrar extra.</div>';
                    return;
                }
                let html = `
                    <h6>Detalles sugeridos para cobro extra</h6>
                    <table class="table table-sm" id="tabla-detalles-cobro-extra">
                        <thead>
                            <tr>
                                <th>Pieza</th>
                                <th>Tipo afectación</th>
                                <th>Cantidad</th>
                                <th>Costo unitario ($)</th>
                                <th>Subtotal ($)</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                data.detalles.forEach((det, idx) => {
                    const esTraslado = det.es_traslado_extra;
                    html += `
                        <tr>
                            <td>
                                ${det.id_pieza ? `
                                    <input type="hidden" class="id-pieza" value="${det.id_pieza}">
                                    <input type="hidden" class="tipo-afectacion" value="${det.tipo_afectacion}">
                                ` : ''}
                                ${det.nombre_pieza}
                            </td>
                            <td>${det.tipo_afectacion === 'traslado_extra' ? 'Traslado Extra' : det.tipo_afectacion}</td>
                            <td>
                                <input type="number" class="form-control cantidad" min="1" value="${det.cantidad}" ${esTraslado ? 'readonly' : ''}>
                            </td>
                            <td>
                                <input type="number" class="form-control costo-unitario" min="0" step="0.01" data-idx="${idx}" value="${det.costo_unitario}" ${esTraslado ? 'readonly' : ''}>
                            </td>
                            <td>
                                <input type="number" class="form-control subtotal" min="0" step="0.01" data-idx="${idx}" value="${det.subtotal}" readonly>
                            </td>
                        </tr>
                    `;
                });


                detalleDiv.innerHTML = html;

                // Actualiza subtotales y total
                document.querySelectorAll('.costo-unitario').forEach(input => {
                    input.addEventListener('input', function () {
                        const idx = this.dataset.idx;
                        const cantidad = document.querySelectorAll('.cantidad')[idx].value;
                        const costo = parseFloat(this.value) || 0;
                        const subtotal = cantidad * costo;
                        document.querySelectorAll('.subtotal')[idx].value = subtotal.toFixed(2);
                        actualizarTotalCobroExtra();
                        document.getElementById('metodo-pago-extra').dispatchEvent(new Event('change'));

                    });
                });

                // Inicializa el total y cambio al abrir el modal
                actualizarTotalCobroExtra();


                // Actualiza cambio al ingresar monto recibido
                document.getElementById('monto-recibido-extra').addEventListener('input', function () {
                    actualizarCambioCobroExtra();
                });



                // Lógica para método de pago
                document.getElementById('metodo-pago-extra').addEventListener('change', function () {
                    const metodo = this.value;
                    const total = parseFloat(document.getElementById('total-cobro-extra-con-iva').textContent) || 0;
                    const montoRecibidoInput = document.getElementById('monto-recibido-extra');
                    const cambioInput = document.getElementById('cambio-extra');
                    const grupoSeguimiento = document.getElementById('grupo-numero-seguimiento');
                    const inputSeguimiento = document.getElementById('numero-seguimiento-extra');

                    if (metodo === 'efectivo') {
                        document.getElementById('total-cobro-extra-con-iva').textContent = redondearEfectivo(total).toFixed(2);
                        montoRecibidoInput.value = '';
                        montoRecibidoInput.removeAttribute('readonly');
                        cambioInput.value = '';
                        // Oculta y limpia el campo de seguimiento
                        grupoSeguimiento.style.display = 'none';
                        inputSeguimiento.value = '';
                    } else {
                        document.getElementById('total-cobro-extra-con-iva').textContent = total.toFixed(2);
                        montoRecibidoInput.value = total.toFixed(2);
                        montoRecibidoInput.setAttribute('readonly', 'readonly');
                        cambioInput.value = '0.00';
                        // Muestra el campo de seguimiento
                        grupoSeguimiento.style.display = '';
                    }
                });

            })
            .catch(() => {
                detalleDiv.innerHTML = '<div class="alert alert-danger">Error al cargar los detalles del cobro extra.</div>';
            });
    };

    // --- Enviar formulario ---
    const form = document.getElementById('form-cobro-extra');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const rentaId = window.rentaIdCobroExtraActual;

            // Obtener detalles
            // Obtener detalles
            const detalles = [];
            document.querySelectorAll('#tabla-detalles-cobro-extra tbody tr').forEach(tr => {
                const id_pieza = tr.querySelector('.id-pieza') ? tr.querySelector('.id-pieza').value : null;
                let tipo_afectacion = tr.querySelector('.tipo-afectacion') ? tr.querySelector('.tipo-afectacion').value : '';
                const cantidad = parseInt(tr.querySelector('.cantidad').value) || 0;
                const costo_unitario = parseFloat(tr.querySelector('.costo-unitario').value) || 0;
                const subtotal = parseFloat(tr.querySelector('.subtotal').value) || 0;

                // Si es traslado extra, ajusta el tipo_afectacion
                if (tipo_afectacion === 'traslado_extra') {
                    tipo_afectacion = 'traslado';
                    detalles.push({
                        id_pieza,
                        tipo_afectacion,
                        cantidad,
                        costo_unitario,
                        subtotal
                    });
                } else if (cantidad > 0 && costo_unitario > 0) {
                    detalles.push({
                        id_pieza,
                        tipo_afectacion,
                        cantidad,
                        costo_unitario,
                        subtotal
                    });
                }
            });

            // Total
            let subtotal_general = 0;
            detalles.forEach(d => subtotal_general += d.subtotal);

            // Otros campos
            const metodoPago = document.getElementById('metodo-pago-extra').value;
            const facturable = document.getElementById('facturable-extra').value;
            const observaciones = document.getElementById('observaciones-cobro-extra').value;
            let montoRecibido = parseFloat(document.getElementById('monto-recibido-extra').value) || 0;
            const cambio = parseFloat(document.getElementById('cambio-extra').value) || 0;
            const numeroSeguimiento = document.getElementById('numero-seguimiento-extra').value || '';

            if (metodoPago === 'tarjeta_debito' || metodoPago === 'tarjeta_credito' || metodoPago === 'transferencia') {
                montoRecibido = parseFloat(document.getElementById('total-cobro-extra-con-iva').textContent) || 0;
            }
            // Calcular IVA y total
            const iva = subtotal_general * 0.16;
            const total = subtotal_general + iva;

            // Validación
            if (detalles.length === 0) {
                Swal.fire('Error', 'Agrega al menos un concepto con cantidad y costo mayor a 0.', 'warning');
                return;
            }

            fetch(`/cobros_extra/crear/${rentaId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    subtotal: subtotal_general,
                    iva: iva,
                    total: total,
                    metodo_pago: metodoPago,
                    facturable: facturable,
                    observaciones: observaciones,
                    monto_recibido: montoRecibido,
                    cambio: cambio,
                    numero_seguimiento: numeroSeguimiento,
                    detalles: detalles
                })
            })
                .then(resp => resp.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            title: 'Cobro extra guardado correctamente.',
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Ver PDF',
                            cancelButtonText: 'Cerrar'
                        }).then((result) => {
                            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCobroExtra'));
                            modal.hide();
                            if (result.isConfirmed && data.cobro_id) {
                                window.open(`/cobros_extra/pdf/${data.cobro_id}`, '_blank');
                                window.location.reload();
                            } else {
                                window.location.reload();
                            }
                        });
                    } else {
                        Swal.fire('Error', data.error || 'No se pudo guardar el cobro extra.', 'error');
                    }
                })
                .catch(() => {
                    Swal.fire('Error', 'Error inesperado al guardar el cobro extra.', 'error');
                });
        });
    }
});
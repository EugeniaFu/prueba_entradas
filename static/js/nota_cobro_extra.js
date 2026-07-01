document.addEventListener('DOMContentLoaded', function () {

    // --- Calcular total con precisión mejorada ---
    function actualizarTotalCobroExtra() {
        let subtotal = 0;
        document.querySelectorAll('.subtotal').forEach(input => {
            subtotal += parseFloat(input.value) || 0;
        });
        
        // Aplicar precisión decimal para evitar errores de punto flotante
        subtotal = Math.round(subtotal * 100) / 100;
        const iva = Math.round((subtotal * 0.16) * 100) / 100;
        const totalConIva = Math.round((subtotal + iva) * 100) / 100;

        const subtotalSpan = document.getElementById('subtotal-cobro-extra');
        const ivaSpan = document.getElementById('iva-cobro-extra');
        const totalConIvaSpan = document.getElementById('total-cobro-extra-con-iva');

        if (subtotalSpan) subtotalSpan.textContent = subtotal.toFixed(2);
        if (ivaSpan) ivaSpan.textContent = iva.toFixed(2);
        if (totalConIvaSpan) totalConIvaSpan.textContent = totalConIva.toFixed(2);
    }


    // --- Función de redondeo para efectivo (mejorada) ---
    function redondearEfectivo(total) {
        if (!total || isNaN(total)) return 0;
        const entero = Math.floor(total);
        const centavos = Math.round((total - entero) * 100);
        
        if (centavos <= 49) return entero;
        if (centavos >= 60) return entero + 1;
        return entero + 0.5;
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
                    <div class="p-3">
                        <h6 class="mb-3 text-center">Detalles Sugeridos para Cobro Extra</h6>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-striped table-sm" id="tabla-detalles-cobro-extra">
                            <thead class="table-dark">
                                <tr>
                                    <th>Pieza</th>
                                    <th>Tipo Afectación</th>
                                    <th>Cantidad</th>
                                    <th>Costo Unitario</th>
                                    <th>Subtotal</th>
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

                html += `
                            </tbody>
                        </table>
                    </div>
                `;

                detalleDiv.innerHTML = html;

                // Actualiza subtotales y total con precisión mejorada
                document.querySelectorAll('.costo-unitario').forEach(input => {
                    input.addEventListener('input', function () {
                        const idx = this.dataset.idx;
                        const cantidad = parseInt(document.querySelectorAll('.cantidad')[idx].value) || 0;
                        const costo = parseFloat(this.value) || 0;
                        const subtotal = Math.round((cantidad * costo) * 100) / 100;
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

                    if (metodo === 'EFECTIVO') {
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

            // Total con precisión mejorada
            let subtotal_general = 0;
            detalles.forEach(d => subtotal_general += d.subtotal);
            subtotal_general = Math.round(subtotal_general * 100) / 100;

            // Otros campos
            const metodoPago = document.getElementById('metodo-pago-extra').value;
            const facturable = document.getElementById('facturable-extra').value;
            const observaciones = document.getElementById('observaciones-cobro-extra').value;
            let montoRecibido = parseFloat(document.getElementById('monto-recibido-extra').value) || 0;
            const cambio = parseFloat(document.getElementById('cambio-extra').value) || 0;
            const numeroSeguimiento = document.getElementById('numero-seguimiento-extra').value || '';

            if (metodoPago === 'T.DÉBITO' || metodoPago === 'T.CRÉDITO' || metodoPago === 'TRANSFERENCIA') {
                montoRecibido = parseFloat(document.getElementById('total-cobro-extra-con-iva').textContent) || 0;
            }
            
            // Calcular IVA y total con precisión
            const iva = Math.round((subtotal_general * 0.16) * 100) / 100;
            let total = Math.round((subtotal_general + iva) * 100) / 100;

            // Para efectivo, usar el monto redondeado como total real
            if (metodoPago === 'EFECTIVO') {
                total = redondearEfectivo(total); 
            }

            // Validación
            if (detalles.length === 0) {
                Swal.fire('Atención', 'Agrega al menos un concepto con cantidad y costo mayor a 0.', 'warning');
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
                            title: '¡Cobro Extra Exitoso!',
                            html: `El cobro extra se guardó correctamente.<br>Folio: <strong>#${data.cobro_id}</strong>`,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
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

// Función global para abrir modal de cobro extra desde otros lugares
window.abrirModalCobroExtra = function(rentaId) {
    if (window.llenarModalCobroExtra) {
        window.llenarModalCobroExtra(rentaId);
    }
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCobroExtra'));
    modal.show();
};
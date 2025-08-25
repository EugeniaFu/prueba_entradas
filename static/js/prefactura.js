document.addEventListener('DOMContentLoaded', function () {

    // Función para redondear según las reglas de efectivo
    function redondearEfectivo(monto) {
        const entero = Math.floor(monto);
        const centavos = Math.round((monto - entero) * 100);
        if (centavos <= 49) return entero;
        if (centavos >= 60) return entero + 1;
        return entero + 0.5;
    }

    // Permite abrir el modal desde el flujo principal y seleccionar el tipo automáticamente
    window.abrirModalPrefacturaPago = function (rentaId, tipoNota) {
        document.querySelectorAll('.modal.show').forEach(m => {
            bootstrap.Modal.getInstance(m)?.hide();
        });

        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalPrefacturaPago'));
        modal.show();

        const form = document.getElementById('form-pago-prefactura-pago');
        form.reset();
        form.dataset.rentaId = rentaId;

        // Selecciona el tipo de prefactura y deshabilita el select
        const tipoSelect = document.getElementById('tipo_prefactura_pago');
        if (tipoSelect) {
            tipoSelect.value = tipoNota;
            tipoSelect.disabled = true;
        }

        document.getElementById('prefactura-detalle-pago').innerHTML = '<div class="text-center text-muted">Cargando...</div>';
        document.getElementById('prefactura-total-pago').textContent = '0.00';
        document.getElementById('pago-total-pago').textContent = '0.00';

        // Reiniciar campos de pago
        const metodoPago = document.getElementById('metodo-pago-pago');
        const efectivo = document.getElementById('pago-efectivo-pago');
        const seguimiento = document.getElementById('pago-seguimiento-pago');
        const montoRecibido = document.getElementById('monto-recibido-pago');
        const cambio = document.getElementById('cambio-pago');
        const numSeguimiento = document.getElementById('numero-seguimiento-pago');
        const btnGenerar = document.getElementById('btn-generar-pago-pago');
        const facturable = document.getElementById('facturable');
        const montoExacto = document.getElementById('monto-exacto-pago');

        metodoPago.value = '';
        efectivo.style.display = 'none';
        seguimiento.style.display = 'none';
        montoRecibido.value = '';
        cambio.textContent = '0.00';
        numSeguimiento.value = '';
        btnGenerar.style.display = 'none';
        facturable.value = '';
        if (montoExacto) montoExacto.value = '';

        // Cargar datos de prefactura
        fetch(`/prefactura/${rentaId}`)
            .then(resp => resp.json())
            .then(data => {
                let html = `
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>Producto</th>
                                <th>Cantidad</th>
                                <th>Días</th>
                                <th>Costo unitario</th>
                                <th>Subtotal</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                data.detalle.forEach(item => {
                    html += `
                        <tr>
                            <td>${item.nombre}</td>
                            <td>${item.cantidad}</td>
                            <td>${item.dias_renta}</td>
                            <td>$${parseFloat(item.costo_unitario).toFixed(2)}</td>
                            <td>$${parseFloat(item.subtotal).toFixed(2)}</td>
                        </tr>
                    `;
                });
                html += `</tbody></table>`;

                let subtotal = 0;
                data.detalle.forEach(item => {
                    subtotal += parseFloat(item.subtotal) || 0;
                });

                let trasladoHtml = '';
                if (data.costo_traslado && data.costo_traslado > 0) {
                    trasladoHtml = `<tr>
                        <td>Traslado <span class="text-muted">(${data.traslado})</span></td>
                        <td colspan="4" class="text-end">$${parseFloat(data.costo_traslado).toFixed(2)}</td>
                    </tr>`;
                }

                const total = parseFloat(data.total_con_iva) || 0;
                const iva = total - subtotal - (parseFloat(data.costo_traslado) || 0);

                html += `
                    <table class="table table-sm">
                        <tr>
                            <td>Subtotal</td>
                            <td colspan="4" class="text-end">$${subtotal.toFixed(2)}</td>
                        </tr>
                        ${trasladoHtml}
                        <tr>
                            <td>+IVA (16%)</td>
                            <td colspan="4" class="text-end">$${iva.toFixed(2)}</td>
                        </tr>
                        <tr>
                            <td><strong>Total</strong></td>
                            <td colspan="4" class="text-end"><strong>$${total.toFixed(2)}</strong></td>
                        </tr>
                    </table>
                `;

                document.getElementById('prefactura-detalle-pago').innerHTML = html;
                document.getElementById('prefactura-total-pago').textContent = total.toFixed(2);
                document.getElementById('pago-total-pago').textContent = total.toFixed(2);

                // Listeners para pago
                metodoPago.onchange = () => {
                    const metodo = metodoPago.value;
                    btnGenerar.style.display = 'none';
                    montoRecibido.value = '';
                    cambio.textContent = '0.00';
                    numSeguimiento.value = '';

                    if (metodo === 'EFECTIVO') {
                        efectivo.style.display = '';
                        seguimiento.style.display = 'none';
                        const montoRedondeado = redondearEfectivo(total);
                        document.getElementById('pago-total-pago').textContent = montoRedondeado.toFixed(2);
                    } else if (metodo) {
                        efectivo.style.display = 'none';
                        seguimiento.style.display = '';
                        document.getElementById('pago-total-pago').textContent = total.toFixed(2);
                        document.getElementById('monto-exacto-display').textContent = total.toFixed(2);
                    } else {
                        efectivo.style.display = 'none';
                        seguimiento.style.display = 'none';
                        document.getElementById('pago-total-pago').textContent = total.toFixed(2);
                    }
                };

                montoRecibido.oninput = () => {
                    const recibido = parseFloat(montoRecibido.value) || 0;
                    const totalPagar = parseFloat(document.getElementById('pago-total-pago').textContent) || 0;
                    const calcCambio = recibido - totalPagar;
                    cambio.textContent = calcCambio > 0 ? calcCambio.toFixed(2) : '0.00';
                    btnGenerar.style.display = (recibido >= totalPagar && validarFormulario()) ? '' : 'none';
                };

                // Validación para tarjetas/transferencia
                const validarPagoNoEfectivo = () => {
                    const numSeg = numSeguimiento.value.trim();
                    if (metodoPago.value !== 'EFECTIVO' && metodoPago.value !== '') {
                        const totalPagar = parseFloat(document.getElementById('pago-total-pago').textContent) || 0;
                        document.getElementById('monto-exacto-display').textContent = totalPagar.toFixed(2);
                        btnGenerar.style.display = (numSeg.length > 0 && validarFormulario()) ? '' : 'none';
                    }
                };

                numSeguimiento.oninput = validarPagoNoEfectivo;
                if (montoExacto) {
                    montoExacto.addEventListener('input', validarPagoNoEfectivo);
                }

                facturable.onchange = () => {
                    if (metodoPago.value === 'EFECTIVO') {
                        const recibido = parseFloat(montoRecibido.value) || 0;
                        const totalPagar = parseFloat(document.getElementById('pago-total-pago').textContent) || 0;
                        btnGenerar.style.display = (recibido >= totalPagar && validarFormulario()) ? '' : 'none';
                    } else if (metodoPago.value !== '' && metodoPago.value !== 'EFECTIVO') {
                        validarPagoNoEfectivo();
                    }
                };

                function validarFormulario() {
                    const facturableVal = facturable.value;
                    const metodoVal = metodoPago.value;
                    if (!facturableVal || !metodoVal) return false;
                    return true;
                }
            })
            .catch(err => {
                document.getElementById('prefactura-detalle-pago').innerHTML = '<div class="text-danger">Error al cargar la prefactura.</div>';
                console.error('Error al obtener prefactura:', err);
            });
    };

    // Mantén el listener para el botón manual (por si lo usas en otras partes)
    document.body.addEventListener('click', function (e) {
        const target = e.target.closest('.btn-prefactura');
        if (target) {
            e.preventDefault();
            const fechaEntrada = target.dataset.fechaEntrada;
            if (!fechaEntrada || fechaEntrada.toLowerCase() === 'indefinido' || fechaEntrada.toLowerCase() === 'none') {
                Swal.fire({
                    icon: 'warning',
                    title: 'No puedes generar la prefactura',
                    text: 'Debes registrar primero la fecha de entrada para esta renta con valor indefinido.'
                });
                return;
            }
            const rentaId = target.dataset.rentaId;
            // Por defecto, tipo "inicial" si no se especifica
            window.abrirModalPrefacturaPago(rentaId, "inicial");
        }
    });

    // Enviar prefactura/pago
    const form = document.getElementById('form-pago-prefactura-pago');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            const facturable = document.getElementById('facturable').value;
            const metodo = document.getElementById('metodo-pago-pago').value;

            if (!facturable) {
                Swal.fire('Error', 'Debes seleccionar si requiere facturación', 'error');
                return;
            }
            if (!metodo) {
                Swal.fire('Error', 'Debes seleccionar un método de pago', 'error');
                return;
            }

            if (metodo === 'EFECTIVO') {
                const montoRecibido = parseFloat(document.getElementById('monto-recibido-pago').value) || 0;
                const totalPagar = parseFloat(document.getElementById('pago-total-pago').textContent) || 0;
                if (montoRecibido < totalPagar) {
                    Swal.fire('Error', 'El monto recibido debe ser mayor o igual al total a pagar', 'error');
                    return;
                }
            } else {
                const numSeguimiento = document.getElementById('numero-seguimiento-pago').value.trim();
                if (!numSeguimiento) {
                    Swal.fire('Error', 'Debes ingresar el número de seguimiento', 'error');
                    return;
                }
            }

            const btn = document.getElementById('btn-generar-pago-pago');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';
            }

            const rentaId = form.dataset.rentaId;
            const tipo = document.getElementById('tipo_prefactura_pago').value;
            const monto = parseFloat(document.getElementById('pago-total-pago').textContent);

            let montoRecibido, cambio, seguimiento;
            if (metodo === 'EFECTIVO') {
                montoRecibido = parseFloat(document.getElementById('monto-recibido-pago').value);
                cambio = parseFloat(document.getElementById('cambio-pago').textContent);
                seguimiento = null;
            } else {
                montoRecibido = monto;
                cambio = null;
                seguimiento = document.getElementById('numero-seguimiento-pago').value;
            }

            const datos = {
                tipo: tipo,
                metodo_pago: metodo,
                monto: monto,
                monto_recibido: montoRecibido,
                cambio: cambio || 0,
                numero_seguimiento: seguimiento || '',
                facturable: facturable === '1'
            };

            try {
                const res = await fetch(`/prefactura/pago/${rentaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(datos)
                });

                const json = await res.json();
                if (json.success) {
                    bootstrap.Modal.getInstance(document.getElementById('modalPrefacturaPago')).hide();
                    Swal.fire({
                        title: 'Prefactura generada',
                        text: '¿Deseas imprimir la prefactura ahora?',
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, imprimir',
                        cancelButtonText: 'No'
                    }).then(result => {
                        if (result.isConfirmed) {
                            window.open(`/prefactura/pdf/${json.prefactura_id}`, '_blank');
                        }
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Error', json.error || 'No se pudo registrar la prefactura', 'error');
                }
            } catch (err) {
                console.error('Error en el guardado:', err);
                Swal.fire('Error', 'Error al enviar los datos al servidor', 'error');
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = 'Generar pago';
                }
            }
        });
    }
});
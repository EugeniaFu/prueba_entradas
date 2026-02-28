document.addEventListener('DOMContentLoaded', function () {

    // Función para redondear según las reglas de efectivo
    function redondearEfectivo(monto) {
        if (!monto || isNaN(monto)) return 0;
        const entero = Math.floor(monto);
        const centavos = Math.round((monto - entero) * 100);
        if (centavos <= 49) return entero;
        if (centavos >= 60) return entero + 1;
        return entero + 0.5;
    }

    // Permite abrir el modal desde el flujo principal y seleccionar el tipo automáticamente
    window.abrirModalPrefacturaPago = function (rentaId, tipoNota) {
        document.querySelectorAll('.modal.show').forEach(m => {
            const existingModal = bootstrap.Modal.getInstance(m);
            if (existingModal) {
                existingModal.hide();
            }
        });

        const modalElement = document.getElementById('modalPrefacturaPago');
        if (!modalElement) {
            console.error('Modal element not found');
            return;
        }

        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        
        // Esperar a que el modal se muestre completamente antes de cargar datos
        modalElement.addEventListener('shown.bs.modal', function inicializarModal() {
            // Remover el listener después de usarlo
            modalElement.removeEventListener('shown.bs.modal', inicializarModal);
            
            const form = document.getElementById('form-pago-prefactura-pago');
            if (!form) {
                console.error('Form not found');
                return;
            }
            
            form.reset();
            form.dataset.rentaId = rentaId;

            form.reset();
            form.dataset.rentaId = rentaId;

            // Selecciona el tipo de prefactura y permite elegir
            const tipoSelect = document.getElementById('tipo_prefactura_pago');
            if (tipoSelect) {
                tipoSelect.value = tipoNota;
                tipoSelect.disabled = false;
            }

            const detalleElement = document.getElementById('prefactura-detalle-pago');
            if (detalleElement) {
                detalleElement.innerHTML = '<div class="text-center text-muted">Cargando...</div>';
            }
            
            // Resetear los campos de totales con validación
            const totalEl = document.getElementById('pago-total-pago');
            const subtotalEl = document.getElementById('prefactura-subtotal');
            const ivaEl = document.getElementById('prefactura-iva');
            
            if (totalEl) totalEl.textContent = '0.00';
            if (subtotalEl) subtotalEl.textContent = '0.00';
            if (ivaEl) ivaEl.textContent = '0.00';

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

            if (metodoPago) metodoPago.value = '';
            if (efectivo) efectivo.style.display = 'none';
            if (seguimiento) seguimiento.style.display = 'none';
            if (montoRecibido) montoRecibido.value = '';
            if (cambio) cambio.textContent = '0.00';
            if (numSeguimiento) numSeguimiento.value = '';
            if (btnGenerar) btnGenerar.style.display = '';
            if (facturable) facturable.value = '';
            if (montoExacto) montoExacto.value = '';
            
            // Ocultar info de saldo
            const infoSaldo = document.getElementById('info-saldo');
            if (infoSaldo) infoSaldo.style.display = 'none';

            // Cargar datos de prefactura y abonos
            cargarDatosPrefactura(rentaId, tipoSelect, metodoPago, efectivo, seguimiento, montoRecibido, cambio, numSeguimiento);
        });
        
        modal.show();
    };

    // Función separada para cargar datos de prefactura
    function cargarDatosPrefactura(rentaId, tipoSelect, metodoPago, efectivo, seguimiento, montoRecibido, cambio, numSeguimiento) {
        Promise.all([
            fetch(`/prefactura/${rentaId}`).then(resp => resp.json()),
            fetch(`/prefactura/api/pagos/${rentaId}`).then(resp => resp.json()),
            fetch(`/prefactura/api/info-redondeo/${rentaId}`).then(resp => resp.json())
        ]).then(([data, pagos, infoRedondeo]) => {
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

            // Calcular totales siguiendo la lógica exacta del backend
            let subtotalProductos = 0;
            data.detalle.forEach(item => {
                subtotalProductos += Math.round((parseFloat(item.subtotal) || 0) * 100) / 100;
            });

            // El costo de traslado se agrega al total antes de calcular IVA (lógica del backend)
            const costoTraslado = Math.round((parseFloat(data.costo_traslado) || 0) * 100) / 100;
            const totalSinIva = Math.round((subtotalProductos + costoTraslado) * 100) / 100;

            let trasladoHtml = '';
            if (costoTraslado > 0) {
                trasladoHtml = `<tr>
                    <td>Traslado <span class="text-muted">(${data.traslado})</span></td>
                    <td colspan="4" class="text-end">$${costoTraslado.toFixed(2)}</td>
                </tr>`;
            }

            // Usar el total con IVA del backend y calcular el IVA como diferencia
            const totalConIva = Math.round((parseFloat(data.total_con_iva) || 0) * 100) / 100;
            const iva = Math.round((totalConIva - totalSinIva) * 100) / 100;

            html += `
                <table class="table table-sm">
                    <tr>
                        <td>Subtotal</td>
                        <td colspan="4" class="text-end">$${subtotalProductos.toFixed(2)}</td>
                    </tr>
                    ${trasladoHtml}
                    <tr>
                        <td>+IVA (16%)</td>
                        <td colspan="4" class="text-end">$${iva.toFixed(2)}</td>
                    </tr>
                    <tr>
                        <td><strong>Total</strong></td>
                        <td colspan="4" class="text-end"><strong>$${totalConIva.toFixed(2)}</strong></td>
                    </tr>
                </table>
            `;

            // Mostrar historial de pagos/abonos
            let totalAbonado = 0;
            let pagosHtml = '';
            if (pagos && pagos.length > 0) {
                pagosHtml += `<div class="mt-2"><strong>Historial de pagos:</strong></div>`;
                pagosHtml += `<table class="table table-sm table-bordered"><thead><tr><th>Folio</th><th>Tipo</th><th>Método</th><th>Monto</th><th>Fecha</th><th>PDF</th></tr></thead><tbody>`;
                pagos.forEach(p => {
                    totalAbonado += parseFloat(p.monto) || 0;
                    pagosHtml += `<tr>
                        <td>${p.id}</td>
                        <td>${p.tipo}</td>
                        <td>${p.metodo_pago}</td>
                        <td>$${parseFloat(p.monto).toFixed(2)}</td>
                        <td>${p.fecha_emision}</td>
                        <td><a href="/prefactura/pdf/${p.id}" target="_blank">PDF</a></td>
                    </tr>`;
                });
                pagosHtml += `</tbody></table>`;
            }
            const saldoPendiente = parseFloat(infoRedondeo.saldo_pendiente) || 0;
            const totalPagado = parseFloat(infoRedondeo.total_pagado) || 0;
            html += `<div class="mt-2"><strong>Total abonado:</strong> $${totalPagado.toFixed(2)}<br><strong>Saldo pendiente:</strong> $${saldoPendiente.toFixed(2)}</div>`;
            html += pagosHtml;

            document.getElementById('prefactura-detalle-pago').innerHTML = html;

            // Actualizar los elementos de totales en el modal
            const subtotalEl = document.getElementById('prefactura-subtotal');
            const ivaEl = document.getElementById('prefactura-iva');
            const totalEl = document.getElementById('pago-total-pago');
            
            // El subtotal del modal muestra solo productos (sin traslado)
            // El IVA se calcula sobre productos + traslado
            // El total es el total con IVA completo
            if (subtotalEl) subtotalEl.textContent = subtotalProductos.toFixed(2);
            if (ivaEl) ivaEl.textContent = iva.toFixed(2);
            if (totalEl) totalEl.textContent = totalConIva.toFixed(2);

            // Lógica para mostrar el monto correcto según tipo de prefactura
            function actualizarMontoPagar() {
                const tipo = tipoSelect ? tipoSelect.value : 'inicial';
                const infoSaldo = document.getElementById('info-saldo');
                const montoExactoInput = document.getElementById('monto-exacto-input');
                const montoExactoDisplay = document.getElementById('monto-exacto-display');
                const montoExactoHelp = document.getElementById('monto-exacto-help');
                const saldoPendienteDisplay = document.getElementById('saldo-pendiente-display');
                const pagoTotalElement = document.getElementById('pago-total-pago');
                
                if (tipo === 'abono') {
                    // Para abonos, mostrar siempre el saldo pendiente real
                    if (infoSaldo) infoSaldo.style.display = '';
                    
                    // Redondear saldo pendiente a 2 decimales para evitar errores de precisión
                    let saldoRedondeado = Math.round(saldoPendiente * 100) / 100;
                    if (saldoRedondeado < 0.01) saldoRedondeado = 0;
                    
                    if (saldoPendienteDisplay) {
                        saldoPendienteDisplay.textContent = saldoRedondeado.toFixed(2);
                    }
                    
                    // Si el método es tarjeta/transferencia, permitir liquidar con centavos exactos
                    if (metodoPago && metodoPago.value && metodoPago.value !== 'EFECTIVO') {
                        if (montoExactoInput) {
                            montoExactoInput.style.display = '';
                            montoExactoInput.value = saldoRedondeado.toFixed(2);
                            montoExactoInput.max = saldoRedondeado.toFixed(2);
                        }
                        if (montoExactoDisplay) montoExactoDisplay.style.display = 'none';
                        if (montoExactoHelp) montoExactoHelp.style.display = '';
                        if (pagoTotalElement && montoExactoInput) {
                            pagoTotalElement.textContent = montoExactoInput.value;
                        }
                    } else {
                        if (pagoTotalElement) pagoTotalElement.textContent = saldoRedondeado.toFixed(2);
                    }
                } else {
                    // Pago inicial: mostrar total completo de la renta
                    if (infoSaldo) infoSaldo.style.display = 'none';
                    if (pagoTotalElement) pagoTotalElement.textContent = totalConIva.toFixed(2);
                    
                    // Asegurar que el campo editable esté oculto
                    if (montoExactoInput) montoExactoInput.style.display = 'none';
                    if (montoExactoDisplay) montoExactoDisplay.style.display = '';
                    if (montoExactoHelp) montoExactoHelp.style.display = 'none';
                }
                
                // Aplicar redondeo según el tipo y método (coincidiendo con lógica Python)
                if (metodoPago && metodoPago.value === 'EFECTIVO' && pagoTotalElement) {
                    if (tipo === 'inicial') {
                        // Pago inicial en efectivo: siempre redondear
                        const montoRedondeado = redondearEfectivo(parseFloat(pagoTotalElement.textContent));
                        pagoTotalElement.textContent = montoRedondeado.toFixed(2);
                    } else if (tipo === 'abono' && infoRedondeo && infoRedondeo.aplicar_redondeo_efectivo) {
                        // Abono en efectivo: redondear si es primer abono O si el primero fue efectivo
                        const montoRedondeado = redondearEfectivo(saldoPendiente);
                        pagoTotalElement.textContent = montoRedondeado.toFixed(2);
                    }
                }
                
                if (montoExactoDisplay && pagoTotalElement) {
                    montoExactoDisplay.textContent = pagoTotalElement.textContent;
                }

                // Mantener los valores de subtotal e IVA actualizados
                const subtotalEl = document.getElementById('prefactura-subtotal');
                const ivaEl = document.getElementById('prefactura-iva');
                
                // El subtotal del modal muestra solo productos (sin traslado)
                if (subtotalEl) subtotalEl.textContent = subtotalProductos.toFixed(2);
                if (ivaEl) ivaEl.textContent = iva.toFixed(2);
            }

            if (tipoSelect) {
                tipoSelect.onchange = actualizarMontoPagar;
            }
            actualizarMontoPagar();
            
            // Listeners para pago
            if (metodoPago) {
                metodoPago.onchange = () => {
                    const metodo = metodoPago.value;
                    if (montoRecibido) montoRecibido.value = '';
                    if (cambio) cambio.textContent = '0.00';
                    if (numSeguimiento) numSeguimiento.value = '';

                    const montoExactoInput = document.getElementById('monto-exacto-input');
                    const montoExactoDisplay = document.getElementById('monto-exacto-display');
                    const montoExactoHelp = document.getElementById('monto-exacto-help');
                    
                    if (metodo === 'EFECTIVO') {
                        if (efectivo) efectivo.style.display = '';
                        if (seguimiento) seguimiento.style.display = 'none';
                        if (montoExactoInput) montoExactoInput.style.display = 'none';
                        if (montoExactoDisplay) montoExactoDisplay.style.display = '';
                        if (montoExactoHelp) montoExactoHelp.style.display = 'none';
                    } else if (metodo) {
                        if (efectivo) efectivo.style.display = 'none';
                        if (seguimiento) seguimiento.style.display = '';
                        // Para abonos con otros métodos, mostrar campo editable
                        if (tipoSelect && tipoSelect.value === 'abono') {
                            if (montoExactoInput) {
                                montoExactoInput.style.display = '';
                                montoExactoInput.value = saldoPendiente.toFixed(2);
                                montoExactoInput.max = saldoPendiente;
                            }
                            if (montoExactoDisplay) montoExactoDisplay.style.display = 'none';
                            if (montoExactoHelp) montoExactoHelp.style.display = '';
                        } else {
                            if (montoExactoInput) montoExactoInput.style.display = 'none';
                            if (montoExactoDisplay) montoExactoDisplay.style.display = '';
                            if (montoExactoHelp) montoExactoHelp.style.display = 'none';
                        }
                    } else {
                        if (efectivo) efectivo.style.display = 'none';
                        if (seguimiento) seguimiento.style.display = 'none';
                        if (montoExactoInput) montoExactoInput.style.display = 'none';
                        if (montoExactoDisplay) montoExactoDisplay.style.display = '';
                        if (montoExactoHelp) montoExactoHelp.style.display = 'none';
                    }
                    
                    // Recalcular el monto después del cambio de método
                    actualizarMontoPagar();
                };
            }

            if (montoRecibido) {
                montoRecibido.oninput = () => {
                    if (!tipoSelect || !metodoPago) return;
                    
                    const recibido = parseFloat(montoRecibido.value) || 0;
                    const tipo = tipoSelect.value;
                    const pagoTotalElement = document.getElementById('pago-total-pago');
                    const totalPagar = pagoTotalElement ? parseFloat(pagoTotalElement.textContent) || 0 : 0;
                    
                    if (tipo === 'abono') {
                        // Para abonos, permitir hasta el doble del saldo para cambio
                        if (recibido > saldoPendiente * 2) {
                            montoRecibido.value = (saldoPendiente * 2).toFixed(2);
                            return;
                        }
                        
                        // Determinar el monto real a cobrar y el cambio (coincidiendo con lógica Python)
                        let montoCobrar, cambioCalculado;
                        if (recibido >= saldoPendiente) {
                            // Liquidación: cobrar según redondeo si aplica (primer abono efectivo O si primero fue efectivo)
                            if (metodoPago.value === 'EFECTIVO' && infoRedondeo && infoRedondeo.aplicar_redondeo_efectivo) {
                                montoCobrar = redondearEfectivo(saldoPendiente);
                            } else {
                                montoCobrar = saldoPendiente;
                            }
                            cambioCalculado = recibido - montoCobrar;
                            
                            const ayudaTexto = document.querySelector('#info-saldo .text-info, #info-saldo .text-success');
                            if (ayudaTexto) {
                                ayudaTexto.textContent = '✓ Liquidando saldo completo - se calculará cambio si aplica';
                                ayudaTexto.className = 'text-success d-block';
                            }
                        } else {
                            // Abono parcial: en efectivo redondear si aplica, en otros métodos cobrar exacto
                            if (metodoPago.value === 'EFECTIVO' && infoRedondeo && infoRedondeo.aplicar_redondeo_efectivo) {
                                montoCobrar = redondearEfectivo(recibido);
                            } else {
                                montoCobrar = recibido;
                            }
                            cambioCalculado = 0;
                            
                            const ayudaTexto = document.querySelector('#info-saldo .text-success, #info-saldo .text-info');
                            if (ayudaTexto) {
                                ayudaTexto.textContent = 'Abono parcial - no se genera cambio';
                                ayudaTexto.className = 'text-info d-block';
                            }
                        }
                        
                        if (pagoTotalElement) pagoTotalElement.textContent = montoCobrar.toFixed(2);
                        if (cambio) cambio.textContent = cambioCalculado > 0 ? cambioCalculado.toFixed(2) : '0.00';
                    } else {
                        // Pago inicial: comportamiento normal
                        const calcCambio = recibido - totalPagar;
                        if (cambio) cambio.textContent = calcCambio > 0 ? calcCambio.toFixed(2) : '0.00';
                    }
                };
            }

            // Listener para el campo editable de monto exacto (abonos con tarjeta/transferencia)
            const montoExactoInput = document.getElementById('monto-exacto-input');
            if (montoExactoInput) {
                montoExactoInput.addEventListener('input', function() {
                    const tipo = tipoSelect ? tipoSelect.value : '';
                    if (tipo === 'abono' && metodoPago && metodoPago.value !== 'EFECTIVO') {
                        const montoAbono = parseFloat(this.value) || 0;
                        const maxAbono = parseFloat(this.max) || saldoPendiente;
                        if (montoAbono > maxAbono) {
                            this.value = maxAbono.toFixed(2);
                        }
                        const montoFinal = parseFloat(this.value) || 0;
                        const pagoTotalElement = document.getElementById('pago-total-pago');
                        if (pagoTotalElement) {
                            pagoTotalElement.textContent = montoFinal.toFixed(2);
                        }
                    }
                });
            }

            // Validación para tarjetas/transferencia
            const validarPagoNoEfectivo = () => {
                const numSeg = numSeguimiento ? numSeguimiento.value.trim() : '';
                const tipo = tipoSelect ? tipoSelect.value : '';
                const pagoTotalElement = document.getElementById('pago-total-pago');
                const totalPagar = pagoTotalElement ? parseFloat(pagoTotalElement.textContent) || 0 : 0;
                if (metodoPago && metodoPago.value !== 'EFECTIVO' && metodoPago.value !== '') {
                    const montoExactoDisplay = document.getElementById('monto-exacto-display');
                    if (montoExactoDisplay) {
                        montoExactoDisplay.textContent = totalPagar.toFixed(2);
                    }
                }
            };

            if (numSeguimiento) {
                numSeguimiento.oninput = validarPagoNoEfectivo;
            }
            
            const montoExacto = document.getElementById('monto-exacto-pago');
            if (montoExacto) {
                montoExacto.addEventListener('input', validarPagoNoEfectivo);
            }

            const facturable = document.getElementById('facturable');
            if (facturable) {
                facturable.onchange = () => {
                    // Ya no se condiciona el botón
                };
            }
        }).catch(err => {
            const detalleElement = document.getElementById('prefactura-detalle-pago');
            if (detalleElement) {
                detalleElement.innerHTML = '<div class="text-danger">Error al cargar la prefactura o abonos.</div>';
            }
            console.error('Error al obtener prefactura o abonos:', err);
        });
    }

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
            if (window.abrirModalPrefacturaPago) {
                window.abrirModalPrefacturaPago(rentaId, "inicial");
            }
        }
    });

    // Enviar prefactura/pago
    const form = document.getElementById('form-pago-prefactura-pago');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            const facturable = document.getElementById('facturable');
            const metodo = document.getElementById('metodo-pago-pago');

            if (!facturable || !facturable.value) {
                Swal.fire('Error', 'Debes seleccionar si requiere facturación', 'error');
                return;
            }
            if (!metodo || !metodo.value) {
                Swal.fire('Error', 'Debes seleccionar un método de pago', 'error');
                return;
            }

            if (metodo.value === 'EFECTIVO') {
                const montoRecibido = document.getElementById('monto-recibido-pago');
                const pagoTotal = document.getElementById('pago-total-pago');
                const montoRecibidoVal = montoRecibido ? parseFloat(montoRecibido.value) || 0 : 0;
                const totalPagar = pagoTotal ? parseFloat(pagoTotal.textContent) || 0 : 0;
                if (montoRecibidoVal < totalPagar) {
                    Swal.fire('Error', 'El monto recibido debe ser mayor o igual al total a pagar', 'error');
                    return;
                }
            } else {
                const numSeguimiento = document.getElementById('numero-seguimiento-pago');
                const numSeguimientoVal = numSeguimiento ? numSeguimiento.value.trim() : '';
                if (!numSeguimientoVal) {
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
            const tipoSelect = document.getElementById('tipo_prefactura_pago');
            const tipo = tipoSelect ? tipoSelect.value : 'inicial';
            const pagoTotalElement = document.getElementById('pago-total-pago');
            const monto = pagoTotalElement ? parseFloat(pagoTotalElement.textContent) || 0 : 0;

            let montoRecibido, cambio, seguimiento;
            if (metodo.value === 'EFECTIVO') {
                const montoRecibidoElement = document.getElementById('monto-recibido-pago');
                const cambioElement = document.getElementById('cambio-pago');
                montoRecibido = montoRecibidoElement ? parseFloat(montoRecibidoElement.value) : 0;
                cambio = cambioElement ? parseFloat(cambioElement.textContent) : 0;
                seguimiento = null;
            } else {
                montoRecibido = monto;
                cambio = null;
                const seguimientoElement = document.getElementById('numero-seguimiento-pago');
                seguimiento = seguimientoElement ? seguimientoElement.value : '';
            }

            const datos = {
                tipo: tipo,
                metodo_pago: metodo.value,
                monto: monto,
                monto_recibido: montoRecibido,
                cambio: cambio || 0,
                numero_seguimiento: seguimiento || '',
                facturable: facturable.value === '1'
            };

            try {
                const res = await fetch(`/prefactura/pago/${rentaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(datos)
                });

                const json = await res.json();
                if (json.success) {
                    const modalElement = document.getElementById('modalPrefacturaPago');
                    if (modalElement) {
                        const modalInstance = bootstrap.Modal.getInstance(modalElement);
                        if (modalInstance) {
                            modalInstance.hide();
                        }
                    }
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
document.addEventListener('DOMContentLoaded', function () {

    // Función para actualizar totales del recuadro con retry mejorado y creación forzada
    function actualizarTotalesPrefactura(subtotalProductos, iva, totalConIva, intentos = 0) {
        console.log(`Intento ${intentos + 1} de actualizar totales`);
        
        const modal = document.getElementById('modalPrefacturaPago');
        if (!modal) {
            console.error('❌ Modal no encontrado');
            return;
        }
        
        // Buscar el contenedor donde debe ir el recuadro
        const cardBody = modal.querySelector('.col-md-6:nth-child(2) .card-body');
        if (!cardBody) {
            console.error('❌ card-body no encontrado');
            return;
        }
        
        // Verificar si ya existe el recuadro de totales  
        let recuadroInfo = modal.querySelector('.alert.alert-info');
        
        // Si no existe el recuadro, crearlo
        if (!recuadroInfo) {
            console.log(`🔧 Creando recuadro de totales (intento ${intentos + 1})`);
            
            const recuadroHTML = `
                <div class="mb-3">
                    <div class="alert alert-info">
                        <div class="row text-center">
                            <div class="col-4">
                                <small>Subtotal</small><br>
                                <strong>$<span id="prefactura-subtotal">0.00</span></strong>
                            </div>
                            <div class="col-4">
                                <small>IVA (16%)</small><br>
                                <strong>$<span id="prefactura-iva">0.00</span></strong>
                            </div>
                            <div class="col-4">
                                <small class="text-primary">TOTAL</small><br>
                                <strong class="text-primary">$<span id="pago-total-pago">0.00</span></strong>
                            </div>
                        </div>
                    </div>
                    <div id="info-saldo" class="mb-3" style="display:none;">
                        <small class="text-muted">Saldo pendiente: $<span id="saldo-pendiente-display">0.00</span></small>
                        <small class="text-info d-block">Para abonos, ingrese cualquier monto hasta el saldo pendiente</small>
                    </div>
                </div>
            `;
            
            // Insertar el recuadro al principio del card-body
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = recuadroHTML;
            cardBody.insertBefore(tempDiv.firstElementChild, cardBody.firstElementChild);
            
            // Actualizar referencia
            recuadroInfo = modal.querySelector('.alert.alert-info');
            console.log('✅ Recuadro de totales creado');
        }
        
        // Ahora buscar los elementos individuales
        const subtotalEl = document.getElementById('prefactura-subtotal');
        const ivaEl = document.getElementById('prefactura-iva');
        const totalEl = document.getElementById('pago-total-pago');
        
        console.log(`Intento ${intentos + 1} - Estados:`, {
            modal: !!modal,
            cardBody: !!cardBody,
            recuadroInfo: !!recuadroInfo,
            subtotalEl: !!subtotalEl,
            ivaEl: !!ivaEl,
            totalEl: !!totalEl
        });
        
        // Si aún no tenemos los elementos después de crear el recuadro, reintentar
        if ((!subtotalEl || !ivaEl || !totalEl) && intentos < 3) {
            console.log(`⏳ Elementos aún no listos, reintentando en 200ms (intento ${intentos + 1}/3)`);
            setTimeout(() => {
                actualizarTotalesPrefactura(subtotalProductos, iva, totalConIva, intentos + 1);
            }, 200);
            return;
        }
        
        // Actualizar los valores
        if (subtotalEl) {
            subtotalEl.textContent = subtotalProductos.toFixed(2);
            console.log('✅ Subtotal actualizado:', subtotalEl.textContent);
        }
        if (ivaEl) {
            ivaEl.textContent = iva.toFixed(2);
            console.log('✅ IVA actualizado:', ivaEl.textContent);
        }
        if (totalEl) {
            totalEl.textContent = totalConIva.toFixed(2);
            console.log('✅ Total actualizado:', totalEl.textContent);
        }
        
        // Asegurar visibilidad del recuadro
        if (recuadroInfo) {
            recuadroInfo.style.display = 'block';
            recuadroInfo.style.visibility = 'visible';
            recuadroInfo.style.opacity = '1';
            console.log('✅ Recuadro de totales visible');
        }
        
        console.log(`📊 Totales aplicados: Subtotal=${subtotalProductos.toFixed(2)}, IVA=${iva.toFixed(2)}, Total=${totalConIva.toFixed(2)}`);
    }

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
        // Cerrar otros modales primero
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
        modal.show();
        
        // Cargar datos inmediatamente después de mostrar el modal con un pequeño delay
        setTimeout(() => {
            inicializarModalPrefactura(rentaId, tipoNota);
        }, 300);
    };
    
    // Función separada para inicializar el modal una vez que está visible
    function inicializarModalPrefactura(rentaId, tipoNota) {
        const form = document.getElementById('form-pago-prefactura-pago');
        if (!form) {
            console.error('Form not found');
            return;
        }
        
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
        if (montoRecibido) {
            montoRecibido.value = '';
            montoRecibido.removeAttribute('readonly');
        }
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
    }

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

            // Delay más largo para asegurar renderizado completo y usar estrategia mejorada
            setTimeout(() => {
                // Actualizar los elementos de totales en el modal usando la función centralizada
                actualizarTotalesPrefactura(subtotalProductos, iva, totalConIva);
                
                // Asegurar que el botón esté visible
                const btnGenerar = document.getElementById('btn-generar-pago-pago');
                if (btnGenerar) {
                    btnGenerar.style.display = '';
                    console.log('✅ Botón generar pago hecho visible');
                }
            }, 500);

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
                
                // Resetear campos de efectivo al cambiar tipo o método
                if (montoRecibido) montoRecibido.value = '';
                if (cambio) cambio.textContent = '0.00';
            }

            if (tipoSelect) {
                tipoSelect.onchange = actualizarMontoPagar;
            }
            actualizarMontoPagar();
            
            // CONFIGURAR LISTENERS DESPUÉS DE QUE SE ACTUALICEN LOS TOTALES
            configurarListenersPago();
            
            function configurarListenersPago() {
                console.log('Configurando listeners de pago...');
                console.log('Elementos disponibles:', {
                    metodoPago: !!metodoPago,
                    efectivo: !!efectivo,
                    seguimiento: !!seguimiento,
                    montoRecibido: !!montoRecibido,
                    cambio: !!cambio,
                    numSeguimiento: !!numSeguimiento
                });
                
                // Lógica para método de pago (replicada desde nota_cobro_extra.js)
                if (metodoPago) {
                    metodoPago.addEventListener('change', function () {
                        const metodo = this.value;
                        const pagoTotalElement = document.getElementById('pago-total-pago');
                        const total = pagoTotalElement ? parseFloat(pagoTotalElement.textContent) || 0 : 0;
                        const tipoSelect = document.getElementById('tipo_prefactura_pago');
                        const tipo = tipoSelect ? tipoSelect.value : 'inicial';
                        
                        // Obtener elementos de abono
                        const montoExactoInput = document.getElementById('monto-exacto-input');
                        const montoExactoDisplay = document.getElementById('monto-exacto-display');
                        const montoExactoHelp = document.getElementById('monto-exacto-help');

                        if (metodo === 'EFECTIVO') {
                            // Para efectivo: aplicar redondeo, mostrar campos de efectivo, ocultar seguimiento
                            if (pagoTotalElement) {
                                pagoTotalElement.textContent = redondearEfectivo(total).toFixed(2);
                            }
                            if (montoRecibido) {
                                montoRecibido.value = '';
                                montoRecibido.removeAttribute('readonly');
                            }
                            if (cambio) cambio.textContent = '';
                            if (efectivo) efectivo.style.display = '';
                            if (seguimiento) seguimiento.style.display = 'none';
                            if (numSeguimiento) numSeguimiento.value = '';
                            
                            // Para efectivo, ocultar el campo de monto exacto para abonos
                            if (tipo === 'abono') {
                                if (montoExactoInput) montoExactoInput.style.display = 'none';
                                if (montoExactoDisplay) montoExactoDisplay.style.display = '';
                                if (montoExactoHelp) montoExactoHelp.style.display = 'none';
                            }
                        } else {
                            // Para otros métodos: usar total exacto, poner readonly en recibido, mostrar seguimiento
                            if (pagoTotalElement) {
                                pagoTotalElement.textContent = total.toFixed(2);
                            }
                            if (montoRecibido) {
                                montoRecibido.value = total.toFixed(2);
                                montoRecibido.setAttribute('readonly', 'readonly');
                            }
                            if (cambio) cambio.textContent = '0.00';
                            if (efectivo) efectivo.style.display = 'none';
                            if (seguimiento) seguimiento.style.display = '';
                            
                            // Para métodos no-efectivo con abonos, mostrar el campo de monto exacto
                            if (tipo === 'abono') {
                                if (montoExactoInput) {
                                    montoExactoInput.style.display = '';
                                    const saldoPendiente = document.getElementById('saldo-pendiente-display');
                                    const saldoVal = saldoPendiente ? parseFloat(saldoPendiente.textContent) || 0 : total;
                                    montoExactoInput.value = saldoVal.toFixed(2);
                                    montoExactoInput.max = saldoVal.toFixed(2);
                                }
                                if (montoExactoDisplay) montoExactoDisplay.style.display = 'none';
                                if (montoExactoHelp) montoExactoHelp.style.display = '';
                            } else {
                                // Para pagos iniciales, ocultar el campo editable
                                if (montoExactoInput) montoExactoInput.style.display = 'none';
                                if (montoExactoDisplay) montoExactoDisplay.style.display = '';
                                if (montoExactoHelp) montoExactoHelp.style.display = 'none';
                            }
                        }
                    });
                }

                // Actualizar cambio al ingresar monto recibido
                if (montoRecibido) {
                    montoRecibido.addEventListener('input', function () {
                        if (metodoPago && metodoPago.value === 'EFECTIVO') {
                            const pagoTotalElement = document.getElementById('pago-total-pago');
                            const total = pagoTotalElement ? parseFloat(pagoTotalElement.textContent) || 0 : 0;
                            const recibido = parseFloat(this.value) || 0;
                            const cambioCalculado = recibido - total;
                            if (cambio) {
                                cambio.textContent = cambioCalculado.toFixed(2);
                            }
                        }
                    });
                }
                
                // Event listener para cambio de tipo de prefactura
                const tipoSelect = document.getElementById('tipo_prefactura_pago');
                if (tipoSelect) {
                    tipoSelect.addEventListener('change', function () {
                        // Reinicializar al cambiar el tipo
                        actualizarMontoPagar();
                        
                        // Reconfigurar campos según método de pago actual
                        if (metodoPago && metodoPago.value) {
                            metodoPago.dispatchEvent(new Event('change'));
                        }
                    });
                }
                
                // Event listener para campo monto exacto (abonos con métodos no-efectivo)
                const montoExactoInput = document.getElementById('monto-exacto-input');
                if (montoExactoInput) {
                    montoExactoInput.addEventListener('input', function () {
                        const pagoTotalElement = document.getElementById('pago-total-pago');
                        const montoAbono = parseFloat(this.value) || 0;
                        if (pagoTotalElement) {
                            pagoTotalElement.textContent = montoAbono.toFixed(2);
                        }
                    });
                }
            } // Fin de configurarListenersPago
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
                const tipoSelect = document.getElementById('tipo_prefactura_pago');
                const tipo = tipoSelect ? tipoSelect.value : 'inicial';
                
                const montoRecibidoVal = montoRecibido ? parseFloat(montoRecibido.value) || 0 : 0;
                const totalPagar = pagoTotal ? parseFloat(pagoTotal.textContent) || 0 : 0;
                
                // Para pagos iniciales, validar que el monto sea suficiente
                // Para abonos, solo validar que sea mayor que 0
                if (tipo === 'inicial' && montoRecibidoVal < totalPagar) {
                    Swal.fire('Error', 'El monto recibido debe ser mayor o igual al total a pagar', 'error');
                    return;
                } else if (tipo === 'abono' && montoRecibidoVal <= 0) {
                    Swal.fire('Error', 'El monto del abono debe ser mayor que cero', 'error');
                    return;
                } else if (tipo === 'abono') {
                    // Para abonos, verificar que no exceda el saldo pendiente
                    const saldoPendiente = document.getElementById('saldo-pendiente-display');
                    const saldoPendienteVal = saldoPendiente ? parseFloat(saldoPendiente.textContent) || 0 : totalPagar;
                    if (montoRecibidoVal > saldoPendienteVal) {
                        Swal.fire('Error', `El abono no puede ser mayor que el saldo pendiente ($${saldoPendienteVal.toFixed(2)})`, 'error');
                        return;
                    }
                }
            } else {
                const numSeguimiento = document.getElementById('numero-seguimiento-pago');
                const numSeguimientoVal = numSeguimiento ? numSeguimiento.value.trim() : '';
                if (!numSeguimientoVal) {
                    Swal.fire('Error', 'Debes ingresar el número de seguimiento', 'error');
                    return;
                }
                
                // Para abonos con métodos no-efectivo, validar el monto exacto
                const tipoSelect = document.getElementById('tipo_prefactura_pago');
                const tipo = tipoSelect ? tipoSelect.value : 'inicial';
                if (tipo === 'abono') {
                    const montoExactoInput = document.getElementById('monto-exacto-input');
                    const montoAbono = montoExactoInput ? parseFloat(montoExactoInput.value) || 0 : 0;
                    
                    if (montoAbono <= 0) {
                        Swal.fire('Error', 'El monto del abono debe ser mayor que cero', 'error');
                        return;
                    }
                    
                    // Verificar que no exceda el saldo pendiente
                    const saldoPendiente = document.getElementById('saldo-pendiente-display');
                    const saldoPendienteVal = saldoPendiente ? parseFloat(saldoPendiente.textContent) || 0 : 0;
                    if (montoAbono > saldoPendienteVal) {
                        Swal.fire('Error', `El abono no puede ser mayor que el saldo pendiente ($${saldoPendienteVal.toFixed(2)})`, 'error');
                        return;
                    }
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
            
            // Determinar el monto correcto según el tipo de pago
            let monto;
            if (tipo === 'abono') {
                // Para abonos, usar el monto específico del abono
                if (metodo.value === 'EFECTIVO') {
                    // Abono en efectivo: usar monto recibido
                    const montoRecibidoElement = document.getElementById('monto-recibido-pago');
                    monto = montoRecibidoElement ? parseFloat(montoRecibidoElement.value) || 0 : 0;
                } else {
                    // Abono no-efectivo: usar monto exacto
                    const montoExactoInput = document.getElementById('monto-exacto-input');
                    monto = montoExactoInput ? parseFloat(montoExactoInput.value) || 0 : 0;
                }
            } else {
                // Para pagos iniciales, usar el total completo
                monto = pagoTotalElement ? parseFloat(pagoTotalElement.textContent) || 0 : 0;
            }

            let montoRecibido, cambio, seguimiento;
            if (metodo.value === 'EFECTIVO') {
                const montoRecibidoElement = document.getElementById('monto-recibido-pago');
                montoRecibido = montoRecibidoElement ? parseFloat(montoRecibidoElement.value) || 0 : 0;
                
                // Recalcular cambio correctamente basado en el monto del abono
                cambio = montoRecibido > monto ? (montoRecibido - monto) : 0;
                seguimiento = null;
            } else {
                // Para métodos no-efectivo, el monto recibido es igual al monto
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
                    Swal.fire({
                        title: '¡Prefactura Exitosa!',
                        html: `La prefactura se guardó correctamente.<br>Prefactura: <strong>#${json.prefactura_id}</strong>`,
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Descargar PDF',
                        cancelButtonText: 'Cerrar',
                        reverseButtons: true,
                        allowOutsideClick: false
                    }).then(result => {
                        const modalElement = document.getElementById('modalPrefacturaPago');
                        if (modalElement) {
                            const modalInstance = bootstrap.Modal.getInstance(modalElement);
                            if (modalInstance) {
                                modalInstance.hide();
                            }
                        }
                        
                        if (result.isConfirmed) {
                            window.open(`/prefactura/pdf/${json.prefactura_id}`, '_blank');
                        }
                        
                        // Recargar la página como los otros modales
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

    // Función para actualizar el estado de la renta dinámicamente
    function actualizarEstadoRenta(rentaId, responseData) {
        setTimeout(() => {
            // Buscar elementos de la renta por diferentes posibles selectores
            const rentaElements = [
                document.querySelector(`[data-renta-id="${rentaId}"]`),
                document.querySelector(`tr[data-renta="${rentaId}"]`),
                document.querySelector(`#renta-${rentaId}`),
                document.querySelector(`.renta-item[data-id="${rentaId}"]`)
            ].filter(el => el !== null);

            rentaElements.forEach(rentaElement => {
                // Actualizar badges de estado de pago
                const estadoBadges = rentaElement.querySelectorAll('.badge-estado, .estado-pago, .badge-pago, .estado-prefactura');
                estadoBadges.forEach(badge => {
                    if (responseData.saldo_pendiente && responseData.saldo_pendiente > 0.01) {
                        badge.textContent = 'Con Abono';
                        badge.className = 'badge bg-warning text-dark';
                    } else {
                        badge.textContent = 'Pagado';
                        badge.className = 'badge bg-success';
                    }
                });

                // Actualizar celdas de estado en tablas
                const celdaEstado = rentaElement.querySelector('.td-estado, .celda-estado, td.estado');
                if (celdaEstado) {
                    if (responseData.saldo_pendiente && responseData.saldo_pendiente > 0.01) {
                        celdaEstado.innerHTML = '<span class="badge bg-warning text-dark">Con Abono</span>';
                    } else {
                        celdaEstado.innerHTML = '<span class="badge bg-success">Pagado</span>';
                    }
                }

                // Actualizar botones de prefactura
                const botonesAccion = rentaElement.querySelectorAll('.btn-prefactura, .btn-pago');
                botonesAccion.forEach(boton => {
                    if (responseData.saldo_pendiente && responseData.saldo_pendiente > 0.01) {
                        boton.textContent = 'Abono';
                        boton.className = boton.className.replace('btn-primary', 'btn-warning');
                    } else {
                        boton.textContent = 'Pagado';
                        boton.disabled = true;
                        boton.className = boton.className.replace('btn-primary', 'btn-success').replace('btn-warning', 'btn-success');
                    }
                });
            });

            // Mostrar notificación de actualización
            mostrarNotificacionEstado(responseData);
        }, 300);
    }

    // Función para mostrar notificación del cambio de estado
    function mostrarNotificacionEstado(responseData) {
        const mensaje = responseData.saldo_pendiente && responseData.saldo_pendiente > 0.01 
            ? `Abono registrado. Saldo pendiente: $${responseData.saldo_pendiente.toFixed(2)}`
            : 'Renta pagada completamente';

        const toastHtml = `
            <div class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;">
                <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="true" data-bs-delay="4000">
                    <div class="toast-header">
                        <i class="bi bi-check-circle-fill text-success me-2"></i>
                        <strong class="me-auto">Estado Actualizado</strong>
                        <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                    <div class="toast-body">
                        ${mensaje}
                    </div>
                </div>
            </div>
        `;

        const toastElement = document.createElement('div');
        toastElement.innerHTML = toastHtml;
        document.body.appendChild(toastElement);

        // Auto-remover el toast después de 5 segundos
        setTimeout(() => {
            if (toastElement.parentNode) {
                toastElement.parentNode.removeChild(toastElement);
            }
        }, 5000);
    }
});
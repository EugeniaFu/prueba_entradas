/**
 * Consolidación de pagos y saldo a favor por cliente.
 * Depends on: Bootstrap 5, SweetAlert2
 */
(function () {
    'use strict';

    let clienteId = null;
    let estadoCuenta = null; // { rentas, rentas_indefinidas, saldo_favor, total_adeudo }

    // ── Helpers ──────────────────────────────────────────────────────────────

    function fmt(n) {
        return parseFloat(n || 0).toFixed(2);
    }

    function redondearEfectivo(monto) {
        const entero = Math.floor(monto);
        const centavos = Math.round((monto - entero) * 100);
        if (centavos <= 49) return entero;
        if (centavos >= 60) return entero + 1;
        return entero + 0.5;
    }

    function getDisponible() {
        const monto = parseFloat(document.getElementById('consolidar-monto').value) || 0;
        const usarSaldo = document.getElementById('consolidar-usar-saldo-favor').checked;
        const saldoFavor = estadoCuenta ? estadoCuenta.saldo_favor : 0;
        return monto + (usarSaldo ? saldoFavor : 0);
    }

    // IDs de las rentas marcadas con su checkbox (las que sí se incluyen en
    // el PDF y en el pago). Por default vienen todas marcadas.
    function getRentaIdsSeleccionados() {
        return Array.from(document.querySelectorAll('.consolidar-check-renta:checked'))
            .map(function (cb) { return parseInt(cb.getAttribute('data-renta-id'), 10); });
    }

    // Actualiza el checkbox "Seleccionar todas" según el estado
    // (marcado/parcial/vacío) de las rentas.
    function sincronizarCheckboxesPadre() {
        const todas = document.querySelectorAll('.consolidar-check-renta');
        const todasMarcadas = document.querySelectorAll('.consolidar-check-renta:checked');
        const checkTodas = document.getElementById('consolidar-check-todas');
        if (checkTodas) {
            checkTodas.checked = todas.length > 0 && todasMarcadas.length === todas.length;
            checkTodas.indeterminate = todasMarcadas.length > 0 && todasMarcadas.length < todas.length;
        }
    }

    // Actualiza el href del botón "Ver PDF" para que el estado de cuenta
    // también respete la selección actual.
    function actualizarPdfHref() {
        const pdfBtn = document.getElementById('consolidar-btn-pdf');
        if (!pdfBtn || !clienteId) return;
        const ids = getRentaIdsSeleccionados();
        const todas = document.querySelectorAll('.consolidar-check-renta').length;
        const usarSaldoFavor = document.getElementById('consolidar-usar-saldo-favor').checked;

        const params = [];
        if (ids.length > 0 && ids.length < todas) params.push('renta_ids=' + ids.join(','));
        if (usarSaldoFavor) params.push('usar_saldo_favor=1');

        pdfBtn.href = '/clientes/pdf-estado-cuenta/' + clienteId + (params.length ? '?' + params.join('&') : '');
    }

    // Si el usuario edita "Cambio a entregar" a mano, ya no lo pisamos con el
    // default automático hasta que cambien monto/método (se resetea ahí).
    let cambioEditadoManualmente = false;

    // ── Preview: distribute greedy and fill the "A pagar" column ─────────────

    function actualizarPreview() {
        if (!estadoCuenta) return;
        sincronizarCheckboxesPadre();
        actualizarPdfHref();

        const idsSeleccionados = getRentaIdsSeleccionados();
        const rentasSeleccionadas = estadoCuenta.rentas.filter(function (r) {
            return idsSeleccionados.indexOf(r.id) !== -1;
        });

        const disponible = getDisponible();
        const metodo = document.getElementById('consolidar-metodo').value;
        // Total adeudo SOLO de las rentas seleccionadas, no de todo el cliente.
        const totalAdeudo = round2(rentasSeleccionadas.reduce(function (s, r) { return s + r.saldo_pendiente; }, 0));
        const cubreTodo = disponible >= totalAdeudo;
        const esEfectivo = metodo === 'EFECTIVO';

        const totalRedondeadoInfo = esEfectivo ? redondearEfectivo(totalAdeudo) : totalAdeudo;

        const totalACobrar = (esEfectivo && cubreTodo) ? totalRedondeadoInfo : totalAdeudo;

        // Bolsa para pagar deudas (limitada al total ya redondeado)
        let poolDeudas = cubreTodo ? Math.min(disponible, totalACobrar) : disponible;
        let totalAplicar = 0;

        estadoCuenta.rentas.forEach(function (r) {
            const cell = document.getElementById('consolidar-aplicar-' + r.id);
            if (!cell) return;
            if (idsSeleccionados.indexOf(r.id) === -1) {
                cell.textContent = '-';
                return;
            }
            const pendiente = r.saldo_pendiente;
            const pago = Math.min(poolDeudas, pendiente);
            poolDeudas = Math.max(0, poolDeudas - pago);
            totalAplicar += pago;
            cell.textContent = fmt(pago);
        });

        // La columna "Se abona" solo se muestra cuando el monto no alcanza para
        // liquidar todo lo seleccionado (pago parcial): ahí sí importa ver a qué
        // rentas se aplica el dinero (de la más antigua a la más reciente).
        const esPagoParcial = disponible > 0 && !cubreTodo;
        document.querySelectorAll('#modalConsolidarPago .consolidar-col-abono').forEach(function (el) {
            el.style.display = esPagoParcial ? '' : 'none';
        });

        const excedente = Math.max(0, round2(disponible - totalACobrar));

        // Campo de "Cambio a entregar" — solo aplica en efectivo con excedente
        const cambioDiv = document.getElementById('consolidar-cambio-div');
        const cambioInput = document.getElementById('consolidar-cambio-entregado');
        let cambioEntregado = 0;
        if (esEfectivo && excedente > 0.01) {
            cambioDiv.style.display = '';
            if (!cambioEditadoManualmente) {
                cambioInput.value = excedente.toFixed(2);
            }
            cambioInput.max = excedente.toFixed(2);
            cambioEntregado = Math.min(Math.max(parseFloat(cambioInput.value) || 0, 0), excedente);
        } else {
            cambioDiv.style.display = 'none';
            cambioInput.value = '0';
        }

        const saldoFavorGenerado = round2(excedente - cambioEntregado);

        document.getElementById('consolidar-total-aplicar').textContent = fmt(totalAplicar);
        document.getElementById('consolidar-total-adeudo').textContent = fmt(totalAdeudo);

        // "Total a pagar": el saldo de las rentas seleccionadas, ya redondeado
        // si el método es Efectivo (informativo, así se va a cobrar).
        document.getElementById('consolidar-preview-adeudo').textContent = fmt(totalRedondeadoInfo);

        // "Saldo a Favor": el saldo disponible del cliente (mismo dato que la
        // caja verde de arriba), y "Total Final": lo que realmente le falta
        // pagar — solo se descuenta el saldo si el check está marcado.
        const usarSaldoFavor = document.getElementById('consolidar-usar-saldo-favor').checked;
        const saldoFavorDisponible = estadoCuenta.saldo_favor || 0;
        const totalFinal = Math.max(0, round2(totalRedondeadoInfo - (usarSaldoFavor ? saldoFavorDisponible : 0)));
        document.getElementById('consolidar-preview-saldo-favor').textContent = fmt(saldoFavorDisponible);
        document.getElementById('consolidar-preview-total-final').textContent = fmt(totalFinal);

        const cambioRow = document.getElementById('consolidar-preview-cambio-row');
        // Se usa d-none (no style.display) porque la fila es d-flex, que en
        // Bootstrap lleva !important y le gana a un display:none inline.
        cambioRow.classList.toggle('d-none', !(esEfectivo && excedente > 0.01));
        document.getElementById('consolidar-preview-cambio').textContent = fmt(cambioEntregado);

        document.getElementById('consolidar-preview-remanente').textContent = fmt(saldoFavorGenerado);
    }

    function round2(n) {
        return Math.round(n * 100) / 100;
    }

    // ── Load estado de cuenta ────────────────────────────────────────────────

    function cargarEstadoCuenta() {
        if (!clienteId) return;
        document.getElementById('consolidar-loading').style.display = '';
        document.getElementById('consolidar-content').style.display = 'none';
        document.getElementById('consolidar-sin-rentas').style.display = 'none';
        document.getElementById('consolidar-btn-aplicar').style.display = 'none';
        document.getElementById('consolidar-indefinidas').style.display = 'none';

        fetch('/clientes/api/estado-cuenta/' + clienteId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                document.getElementById('consolidar-loading').style.display = 'none';
                if (!data.success) {
                    Swal.fire('Error', data.message || 'No se pudo cargar el estado de cuenta.', 'error');
                    return;
                }
                estadoCuenta = data;

                // Aviso de rentas indefinidas (no cobrables hasta registrar su fecha de entrada)
                if (data.rentas_indefinidas && data.rentas_indefinidas.length > 0) {
                    document.getElementById('consolidar-indefinidas-lista').textContent =
                        data.rentas_indefinidas.map(function (r) {
                            return 'SUC' + r.id_sucursal + '-' + String(r.folio || r.id).padStart(4, '0');
                        }).join(', ');
                    document.getElementById('consolidar-indefinidas').style.display = '';
                }

                if (!data.rentas || data.rentas.length === 0) {
                    document.getElementById('consolidar-sin-rentas').style.display = '';
                    return;
                }

                // Build table
                const tbody = document.getElementById('consolidar-rentas-tbody');
                tbody.innerHTML = '';

                // Fecha de entrada + si el equipo ya regresó o sigue en la obra
                function celdaEntrada(r) {
                    var finalizada = (r.estado_renta || '').toLowerCase().trim() === 'finalizada';
                    var badge = finalizada
                        ? '<span class="badge bg-success ms-1" style="font-size:.7em;">Finalizada</span>'
                        : '<span class="badge bg-warning text-dark ms-1" style="font-size:.7em;">En renta</span>';
                    return (r.fecha_entrada || '') + badge;
                }

                // Todas las rentas como filas independientes, de la más vieja a la
                // más nueva (por id = orden de creación del folio). Las renovaciones
                // solo llevan una etiqueta; el agrupado por cadena queda en el PDF.
                // Ojo: se ordena una copia; estadoCuenta.rentas conserva el orden del
                // backend, que es el mismo con el que se reparte el pago.
                var rentasOrdenadas = data.rentas.slice().sort(function (a, b) { return a.id - b.id; });

                rentasOrdenadas.forEach(function (r) {
                    var folioStr = '#' + String(r.folio || r.id).padStart(4, '0');
                    var renoBadge = r.renta_asociada_id
                        ? '<span class="badge bg-info text-dark ms-1" style="font-size:.7em;" title="Renovación de #' +
                            String(r.folio_raiz || '').padStart(4, '0') + '">Renovación</span>'
                        : '';
                    var tr = document.createElement('tr');
                    tr.innerHTML =
                        '<td><input type="checkbox" class="form-check-input consolidar-check-renta" data-renta-id="' + r.id + '" checked></td>' +
                        '<td><span class="badge bg-secondary">' + folioStr + '</span>' + renoBadge + '</td>' +
                        '<td>' + (r.fecha_salida || '') + '</td>' +
                        '<td>' + celdaEntrada(r) + '</td>' +
                        '<td class="text-end text-danger fw-bold">$' + fmt(r.saldo_pendiente) + '</td>' +
                        '<td class="text-end text-primary fw-bold consolidar-col-abono" style="display:none;">$<span id="consolidar-aplicar-' + r.id + '">0.00</span></td>';
                    tbody.appendChild(tr);
                });

                document.getElementById('consolidar-badge-rentas').textContent = rentasOrdenadas.length;
                document.getElementById('consolidar-total-adeudo').textContent = fmt(data.total_adeudo);
                document.getElementById('consolidar-saldo-favor').textContent = fmt(data.saldo_favor);
                document.getElementById('consolidar-preview-adeudo').textContent = fmt(data.total_adeudo);

                // Reset form
                document.getElementById('consolidar-monto').value = '';
                document.getElementById('consolidar-usar-saldo-favor').checked = data.saldo_favor > 0;
                document.getElementById('consolidar-metodo').value = '';
                document.getElementById('consolidar-seguimiento-div').style.display = 'none';
                document.getElementById('consolidar-seguimiento').value = '';
                document.getElementById('consolidar-facturable').value = '0';
                document.getElementById('consolidar-cambio-div').style.display = 'none';
                document.getElementById('consolidar-cambio-entregado').value = '0';
                cambioEditadoManualmente = false;

                actualizarPreview();

                document.getElementById('consolidar-content').style.display = '';
                document.getElementById('consolidar-btn-aplicar').style.display = '';
                const pdfBtn = document.getElementById('consolidar-btn-pdf');
                if (pdfBtn) pdfBtn.style.display = '';
            })
            .catch(function () {
                document.getElementById('consolidar-loading').style.display = 'none';
                Swal.fire('Error', 'Error de conexión al cargar el estado de cuenta.', 'error');
            });
    }

    // ── Open modal ───────────────────────────────────────────────────────────

    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-consolidar-pago');
        if (btn) {
            clienteId = btn.getAttribute('data-cliente-id');
            estadoCuenta = null;
            // Wire PDF button
            const pdfBtn = document.getElementById('consolidar-btn-pdf');
            if (pdfBtn) {
                pdfBtn.href = '/clientes/pdf-estado-cuenta/' + clienteId;
                pdfBtn.style.display = 'none'; // show after data loads
            }
            const modal = new bootstrap.Modal(document.getElementById('modalConsolidarPago'));
            modal.show();
            cargarEstadoCuenta();
        }
    });

    // ── Live listeners inside modal ──────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {
        const modalEl = document.getElementById('modalConsolidarPago');
        if (!modalEl) return;

        modalEl.addEventListener('input', function (e) {
            if (e.target.id === 'consolidar-monto') {
                cambioEditadoManualmente = false; // el monto cambió, vuelve a proponer el cambio completo
                actualizarPreview();
            }
            if (e.target.id === 'consolidar-cambio-entregado') {
                cambioEditadoManualmente = true;
                actualizarPreview();
            }
        });
        modalEl.addEventListener('change', function (e) {
            if (e.target.id === 'consolidar-usar-saldo-favor') actualizarPreview();
            // Al salir del campo, si se escribió más cambio del que sobra (o un
            // negativo), se corrige el valor mostrado al rango permitido.
            if (e.target.id === 'consolidar-cambio-entregado') {
                const max = parseFloat(e.target.max) || 0;
                const val = parseFloat(e.target.value) || 0;
                e.target.value = Math.min(Math.max(val, 0), max).toFixed(2);
                actualizarPreview();
            }
            if (e.target.id === 'consolidar-metodo') {
                cambioEditadoManualmente = false;
                const metodo = e.target.value;
                const sigDiv = document.getElementById('consolidar-seguimiento-div');
                sigDiv.style.display = (metodo && metodo !== 'EFECTIVO') ? '' : 'none';
                actualizarPreview();
            }

            // "Seleccionar todas" (marca/desmarca cada renta)
            if (e.target.id === 'consolidar-check-todas') {
                const marcado = e.target.checked;
                document.querySelectorAll('.consolidar-check-renta').forEach(function (cb) {
                    cb.checked = marcado;
                });
                cambioEditadoManualmente = false;
                actualizarPreview();
            }

            // Checkbox individual de una renta
            if (e.target.classList.contains('consolidar-check-renta')) {
                cambioEditadoManualmente = false;
                actualizarPreview();
            }
        });

        // Apply payment
        document.getElementById('consolidar-btn-aplicar').addEventListener('click', function () {
            const monto = parseFloat(document.getElementById('consolidar-monto').value) || 0;
            const usarSaldo = document.getElementById('consolidar-usar-saldo-favor').checked;
            const metodo = document.getElementById('consolidar-metodo').value;
            const seguimiento = document.getElementById('consolidar-seguimiento').value.trim();
            const facturable = document.getElementById('consolidar-facturable').value;
            const cambioDivVisible = document.getElementById('consolidar-cambio-div').style.display !== 'none';
            const cambioEntregado = cambioDivVisible
                ? (parseFloat(document.getElementById('consolidar-cambio-entregado').value) || 0)
                : null;
            const rentaIdsSeleccionados = getRentaIdsSeleccionados();

            if (rentaIdsSeleccionados.length === 0) {
                Swal.fire('Atención', 'Selecciona al menos una renta para aplicar el pago.', 'warning');
                return;
            }
            if (!metodo) {
                Swal.fire('Atención', 'Selecciona un método de pago.', 'warning');
                return;
            }
            if (monto <= 0 && !usarSaldo) {
                Swal.fire('Atención', 'Ingresa el monto a pagar o activa el saldo a favor.', 'warning');
                return;
            }
            if (metodo !== 'EFECTIVO' && !seguimiento) {
                Swal.fire('Atención', 'Ingresa el número de seguimiento para pagos no en efectivo.', 'warning');
                return;
            }

            const todasSeleccionadas = rentaIdsSeleccionados.length === document.querySelectorAll('.consolidar-check-renta').length;
            Swal.fire({
                title: '¿Aplicar pago consolidado?',
                text: todasSeleccionadas
                    ? 'Se distribuirá el pago entre las rentas con saldo pendiente, de la más antigua a la más reciente.'
                    : 'Se distribuirá el pago solo entre las ' + rentaIdsSeleccionados.length + ' renta(s) que seleccionaste, de la más antigua a la más reciente.',
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#23395d',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, aplicar',
                cancelButtonText: 'Cancelar',
                reverseButtons: true
            }).then(function (result) {
                if (!result.isConfirmed) return;

                const btn = document.getElementById('consolidar-btn-aplicar');
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Procesando...';

                fetch('/clientes/api/pago-consolidado/' + clienteId, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        monto: monto,
                        metodo_pago: metodo,
                        numero_seguimiento: seguimiento,
                        usar_saldo_favor: usarSaldo,
                        facturable: parseInt(facturable),
                        cambio_entregado: cambioEntregado,
                        renta_ids: rentaIdsSeleccionados
                    })
                })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Aplicar Pago';
                    if (data.success) {
                        bootstrap.Modal.getInstance(document.getElementById('modalConsolidarPago')).hide();
                        // Abrir comprobante en nueva pestaña
                        if (data.pdf_url) {
                            window.open(data.pdf_url, '_blank');
                        }
                        Swal.fire({
                            title: '¡Pago aplicado!',
                            text: data.message,
                            icon: 'success',
                            confirmButtonText: 'Entendido'
                        }).then(function () { window.location.reload(); });
                    } else {
                        Swal.fire('Error', data.message || 'No se pudo aplicar el pago.', 'error');
                    }
                })
                .catch(function () {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Aplicar Pago';
                    Swal.fire('Error', 'Error de conexión.', 'error');
                });
            });
        });
    });

    // ── Agregar Saldo a Favor ────────────────────────────────────────────────

    let sfClienteId = null;

    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-agregar-saldo-favor');
        if (btn) {
            sfClienteId = btn.getAttribute('data-cliente-id');
            document.getElementById('sf-monto').value = '';
            document.getElementById('sf-concepto').value = '';
            const modal = new bootstrap.Modal(document.getElementById('modalAgregarSaldoFavor'));
            modal.show();
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        const btnGuardar = document.getElementById('sf-btn-guardar');
        if (!btnGuardar) return;

        btnGuardar.addEventListener('click', function () {
            const monto = parseFloat(document.getElementById('sf-monto').value) || 0;
            const concepto = document.getElementById('sf-concepto').value.trim();

            if (monto <= 0) {
                Swal.fire('Atención', 'El monto debe ser mayor a cero.', 'warning');
                return;
            }
            if (!concepto) {
                Swal.fire('Atención', 'El concepto es requerido.', 'warning');
                return;
            }

            btnGuardar.disabled = true;
            btnGuardar.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Guardando...';

            fetch('/clientes/api/saldo-favor/' + sfClienteId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ monto: monto, concepto: concepto })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                btnGuardar.disabled = false;
                btnGuardar.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Guardar';
                if (data.success) {
                    bootstrap.Modal.getInstance(document.getElementById('modalAgregarSaldoFavor')).hide();
                    Swal.fire({
                        title: 'Saldo registrado',
                        text: data.message,
                        icon: 'success',
                        confirmButtonText: 'Entendido'
                    }).then(function () { window.location.reload(); });
                } else {
                    Swal.fire('Error', data.message || 'No se pudo registrar el saldo.', 'error');
                }
            })
            .catch(function () {
                btnGuardar.disabled = false;
                btnGuardar.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Guardar';
                Swal.fire('Error', 'Error de conexión.', 'error');
            });
        });
    });

})();

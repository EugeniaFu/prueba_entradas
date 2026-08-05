/**
 * Consolidación de pagos y saldo a favor por cliente.
 * Depends on: Bootstrap 5, SweetAlert2
 */
(function () {
    'use strict';

    let clienteId = null;
    let estadoCuenta = null; // { rentas, cadenas, ordenRaiz, saldo_favor, total_adeudo }

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

    // Actualiza el checkbox "Seleccionar todas" y el de cada cadena según el
    // estado (marcado/parcial/vacío) de sus eslabones.
    function sincronizarCheckboxesPadre() {
        document.querySelectorAll('.consolidar-check-cadena').forEach(function (cbCadena) {
            const raizId = cbCadena.getAttribute('data-raiz-id');
            const hijos = Array.from(document.querySelectorAll('.consolidar-check-renta[data-raiz-id="' + raizId + '"]'));
            const marcados = hijos.filter(function (h) { return h.checked; }).length;
            cbCadena.checked = marcados === hijos.length;
            cbCadena.indeterminate = marcados > 0 && marcados < hijos.length;
        });

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
        pdfBtn.href = (ids.length > 0 && ids.length < todas)
            ? '/clientes/pdf-estado-cuenta/' + clienteId + '?renta_ids=' + ids.join(',')
            : '/clientes/pdf-estado-cuenta/' + clienteId;
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

        // El total redondeado se muestra en cuanto se elige "Efectivo", sin
        // depender de si ya se escribió el monto (es informativo: así se va
        // a cobrar en cuanto paguen el total).
        const totalRedondeadoInfo = esEfectivo ? redondearEfectivo(totalAdeudo) : totalAdeudo;

        // Para la distribución real entre rentas, el redondeo solo se aplica
        // si el monto disponible efectivamente cubre todo el adeudo.
        const totalACobrar = (esEfectivo && cubreTodo) ? totalRedondeadoInfo : totalAdeudo;

        // Bolsa para pagar deudas (limitada al total ya redondeado)
        let poolDeudas = cubreTodo ? Math.min(disponible, totalACobrar) : disponible;
        let totalAplicar = 0;

        // Distribute per individual renta (oldest-first), solo entre las
        // seleccionadas — las que no están marcadas se muestran en "-".
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

        // Aggregate per chain header
        estadoCuenta.ordenRaiz.forEach(function (raizId) {
            var cadena = estadoCuenta.cadenas[raizId];
            if (cadena.eslabones.length <= 1) return;
            var chainCell = document.getElementById('consolidar-aplicar-cadena-' + raizId);
            if (!chainCell) return;
            var chainTotal = cadena.eslabones.reduce(function (s, e) {
                var c = document.getElementById('consolidar-aplicar-' + e.id);
                return s + (c ? parseFloat(c.textContent) : 0);
            }, 0);
            chainCell.textContent = fmt(chainTotal);
        });

        // Excedente real: se calcula contra totalACobrar (ya redondeado), NO
        // contra totalAplicar. Una renta nunca se puede sobrepagar más allá
        // de su saldo real, así que el ajuste de redondeo (ej. $0.24 si el
        // total subió de $11,530.76 a $11,531.00) nunca llega a aplicarse a
        // ninguna deuda; si se comparara contra totalAplicar esos centavos
        // se colarían como si fueran cambio real que hay que entregar.
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
        document.getElementById('consolidar-preview-disponible').textContent = fmt(disponible);
        document.getElementById('consolidar-preview-adeudo').textContent = fmt(totalAdeudo);

        // Fila de redondeo: visible en cuanto se elige Efectivo, sin importar
        // si ya se escribió el monto — es informativa (así se va a cobrar).
        const redondeoRow = document.getElementById('consolidar-preview-redondeo-row');
        if (esEfectivo && Math.abs(totalRedondeadoInfo - totalAdeudo) > 0.001) {
            redondeoRow.style.display = '';
            document.getElementById('consolidar-preview-total-cobrar').textContent = fmt(totalRedondeadoInfo);
        } else {
            redondeoRow.style.display = 'none';
        }

        const cambioRow = document.getElementById('consolidar-preview-cambio-row');
        if (esEfectivo && excedente > 0.01) {
            cambioRow.style.display = '';
            document.getElementById('consolidar-preview-cambio').textContent = fmt(cambioEntregado);
        } else {
            cambioRow.style.display = 'none';
        }

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

        fetch('/clientes/api/estado-cuenta/' + clienteId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                document.getElementById('consolidar-loading').style.display = 'none';
                if (!data.success) {
                    Swal.fire('Error', data.message || 'No se pudo cargar el estado de cuenta.', 'error');
                    return;
                }
                estadoCuenta = data;

                if (!data.rentas || data.rentas.length === 0) {
                    document.getElementById('consolidar-sin-rentas').style.display = '';
                    return;
                }

                // Agrupar por cadena
                var cadenas = {};
                var ordenRaiz = [];
                data.rentas.forEach(function (r) {
                    var raizId = r.raiz_id;
                    if (!cadenas[raizId]) {
                        cadenas[raizId] = { folio_raiz: r.folio_raiz, eslabones: [] };
                        ordenRaiz.push(raizId);
                    }
                    cadenas[raizId].eslabones.push(r);
                });
                estadoCuenta.cadenas = cadenas;
                estadoCuenta.ordenRaiz = ordenRaiz;

                // Build table
                const tbody = document.getElementById('consolidar-rentas-tbody');
                tbody.innerHTML = '';

                ordenRaiz.forEach(function (raizId) {
                    var cadena = cadenas[raizId];
                    var eslabones = cadena.eslabones;
                    var numReno = eslabones.length - 1;
                    var folioStr = '#' + String(cadena.folio_raiz || raizId).padStart(4, '0');

                    if (eslabones.length > 1) {
                        // Fila encabezado de cadena (selecciona/deselecciona todos sus eslabones)
                        var totalCadena = eslabones.reduce(function(s,e){ return s + e.total; }, 0);
                        var pagadoCadena = eslabones.reduce(function(s,e){ return s + e.pagado; }, 0);
                        var saldoCadena  = eslabones.reduce(function(s,e){ return s + e.saldo_pendiente; }, 0);
                        var renoLabel = numReno + ' renovaci' + (numReno === 1 ? 'ón' : 'ones');
                        var trH = document.createElement('tr');
                        trH.className = 'table-primary fw-semibold';
                        trH.innerHTML =
                            '<td><input type="checkbox" class="form-check-input consolidar-check-cadena" data-raiz-id="' + raizId + '" checked></td>' +
                            '<td colspan="2">' +
                              '<span class="badge bg-primary me-1">' + folioStr + '</span>' +
                              '<span class="badge bg-secondary" style="font-size:.7em;">' + renoLabel + '</span>' +
                            '</td>' +
                            '<td>$' + fmt(totalCadena) + '</td>' +
                            '<td>$' + fmt(pagadoCadena) + '</td>' +
                            '<td class="text-danger">$' + fmt(saldoCadena) + '</td>' +
                            '<td class="text-primary">$<span id="consolidar-aplicar-cadena-' + raizId + '">0.00</span></td>';
                        tbody.appendChild(trH);

                        // Sub-filas por eslabón, cada una con su propio checkbox
                        eslabones.forEach(function (r) {
                            var trE = document.createElement('tr');
                            trE.className = 'small text-muted';
                            trE.innerHTML =
                                '<td><input type="checkbox" class="form-check-input consolidar-check-renta" data-renta-id="' + r.id + '" data-raiz-id="' + raizId + '" checked></td>' +
                                '<td class="ps-1"><span class="badge bg-secondary" style="opacity:.75;">#' + String(r.folio || r.id).padStart(4, '0') + '</span></td>' +
                                '<td>' + (r.fecha_salida || '') + '</td>' +
                                '<td>$' + fmt(r.total) + '</td>' +
                                '<td>$' + fmt(r.pagado) + '</td>' +
                                '<td class="text-danger">$' + fmt(r.saldo_pendiente) + '</td>' +
                                '<td class="text-primary">$<span id="consolidar-aplicar-' + r.id + '">0.00</span></td>';
                            tbody.appendChild(trE);
                        });
                    } else {
                        // Renta sin renovaciones — fila normal
                        var r = eslabones[0];
                        var tr = document.createElement('tr');
                        tr.innerHTML =
                            '<td><input type="checkbox" class="form-check-input consolidar-check-renta" data-renta-id="' + r.id + '" data-raiz-id="' + raizId + '" checked></td>' +
                            '<td><span class="badge bg-secondary">' + folioStr + '</span></td>' +
                            '<td>' + (r.fecha_salida || '') + '</td>' +
                            '<td>$' + fmt(r.total) + '</td>' +
                            '<td>$' + fmt(r.pagado) + '</td>' +
                            '<td class="text-danger fw-bold">$' + fmt(r.saldo_pendiente) + '</td>' +
                            '<td class="text-primary fw-bold">$<span id="consolidar-aplicar-' + r.id + '">0.00</span></td>';
                        tbody.appendChild(tr);
                    }
                });

                document.getElementById('consolidar-badge-rentas').textContent = ordenRaiz.length;
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

            // Checkbox de cadena (marca/desmarca todos sus eslabones)
            if (e.target.classList.contains('consolidar-check-cadena')) {
                const raizId = e.target.getAttribute('data-raiz-id');
                const marcado = e.target.checked;
                document.querySelectorAll('.consolidar-check-renta[data-raiz-id="' + raizId + '"]').forEach(function (cb) {
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

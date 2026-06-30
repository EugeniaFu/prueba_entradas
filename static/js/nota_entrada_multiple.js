document.addEventListener('DOMContentLoaded', function () {
    const modalEl = document.getElementById('modalNotaEntradaMultiple');
    if (!modalEl) return;

    window.notaEntradaMultipleSucursalId = null;
    window.notaEntradaMultipleClienteId = null;
    window.notaEntradaMultiplePiezas = {}; // { renta_id: [pieza, ...] }
    window.notaEntradaMultipleRentasInfo = {}; // { renta_id: {folio, direccion_obra, traslado, ...} }
    window.notaEntradaMultipleRentaIdsSeleccionadas = [];
    window.notaEntradaMultipleModoDespacho = false;

    const buscadorCliente = document.getElementById('nem-buscador-cliente');
    const resultadosCliente = document.getElementById('nem-resultados-cliente');
    const clienteSeleccionadoDiv = document.getElementById('nem-cliente-seleccionado');
    const clienteNombreSpan = document.getElementById('nem-cliente-nombre');
    const btnCambiarCliente = document.getElementById('nem-btn-cambiar-cliente');
    const pasoRentasDiv = document.getElementById('nem-paso-rentas');
    const sinRentasDiv = document.getElementById('nem-sin-rentas');
    const listaRentasDiv = document.getElementById('nem-lista-rentas');
    const pasoPiezasDiv = document.getElementById('nem-paso-piezas');
    const pasoDespachoDiv = document.getElementById('nem-paso-despacho');
    const bloquesPiezasDiv = document.getElementById('nem-bloques-piezas');
    const btnGenerar = document.getElementById('nem-btn-generar');

    const trasladoSectionDiv = document.getElementById('nem-traslado-section');
    const avisoTrasladoPagadoDiv = document.getElementById('nem-aviso-traslado-pagado');
    const trasladoExtraSelect = document.getElementById('nem-traslado-extra-select');
    const costoTrasladoExtraInput = document.getElementById('nem-costo-traslado-extra');
    const divChoferRecoleccion = document.getElementById('nem-div-chofer-recoleccion');
    const selectChoferRecoleccion = document.getElementById('nem-select-chofer-recoleccion');

    const BTN_LABEL_CONSOLIDADA = '<i class="bi bi-check2-circle me-2"></i>Generar Nota de Entrada Consolidada';
    const BTN_LABEL_DESPACHO = '<i class="bi bi-truck me-2"></i>Generar Despacho de Recolección';

    let nemCargadores = null;
    function cargarCargadoresNem() {
        if (nemCargadores) {
            poblarSelectCargadoresNem(selectChoferRecoleccion, nemCargadores);
            return;
        }
        fetch('/notas_entrada/cargadores')
            .then(resp => resp.json())
            .then(cargadores => {
                nemCargadores = cargadores;
                poblarSelectCargadoresNem(selectChoferRecoleccion, cargadores);
            })
            .catch(() => {});
    }
    function poblarSelectCargadoresNem(select, cargadores) {
        select.innerHTML = '<option value="">Selecciona un chofer...</option>';
        cargadores.forEach(c => {
            const option = document.createElement('option');
            option.value = c.id;
            option.textContent = c.sucursal_nombre ? `${c.nombre_completo} (${c.sucursal_nombre})` : c.nombre_completo;
            select.appendChild(option);
        });
    }

    function resetModal() {
        window.notaEntradaMultipleClienteId = null;
        window.notaEntradaMultiplePiezas = {};
        window.notaEntradaMultipleRentasInfo = {};
        window.notaEntradaMultipleRentaIdsSeleccionadas = [];
        window.notaEntradaMultipleModoDespacho = false;
        buscadorCliente.value = '';
        resultadosCliente.style.display = 'none';
        resultadosCliente.innerHTML = '';
        clienteSeleccionadoDiv.classList.add('d-none');
        buscadorCliente.parentElement.classList.remove('d-none');
        pasoRentasDiv.classList.add('d-none');
        pasoPiezasDiv.classList.add('d-none');
        pasoDespachoDiv.classList.add('d-none');
        listaRentasDiv.innerHTML = '';
        bloquesPiezasDiv.innerHTML = '';
        document.getElementById('nem-observaciones').value = '';
        trasladoSectionDiv.classList.add('d-none');
        avisoTrasladoPagadoDiv.classList.add('d-none');
        trasladoExtraSelect.value = 'ninguno';
        costoTrasladoExtraInput.value = 0;
        costoTrasladoExtraInput.disabled = true;
        divChoferRecoleccion.classList.add('d-none');
        selectChoferRecoleccion.value = '';
        btnGenerar.disabled = true;
        btnGenerar.innerHTML = BTN_LABEL_CONSOLIDADA;
    }

    // Abrir modal desde el botón de la barra superior
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-nota-entrada-multiple');
        if (!btn) return;

        const sucursalId = btn.dataset.sucursalId;
        if (!sucursalId) {
            Swal.fire('Selecciona una sucursal', 'Para usar la nota de entrada múltiple primero debes estar viendo una sucursal específica (no "Todas las sucursales").', 'warning');
            return;
        }
        window.notaEntradaMultipleSucursalId = sucursalId;
        resetModal();
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    });

    // Búsqueda de cliente con autocompletado
    let buscarTimeout = null;
    buscadorCliente.addEventListener('input', function () {
        const term = buscadorCliente.value.trim();
        clearTimeout(buscarTimeout);
        if (term.length < 2) {
            resultadosCliente.style.display = 'none';
            resultadosCliente.innerHTML = '';
            return;
        }
        buscarTimeout = setTimeout(() => {
            fetch(`/clientes/buscar?q=${encodeURIComponent(term)}`)
                .then(resp => resp.json())
                .then(clientes => {
                    if (!clientes.length) {
                        resultadosCliente.innerHTML = '<div class="list-group-item text-muted">Sin resultados</div>';
                        resultadosCliente.style.display = 'block';
                        return;
                    }
                    resultadosCliente.innerHTML = clientes.map(c => `
                        <button type="button" class="list-group-item list-group-item-action nem-opcion-cliente"
                            data-id="${c.id}" data-nombre="${c.nombre} ${c.apellido1} ${c.apellido2}">
                            <strong>${c.codigo_cliente}</strong> - ${c.nombre} ${c.apellido1} ${c.apellido2}
                            <small class="text-muted">${c.telefono || ''}</small>
                        </button>
                    `).join('');
                    resultadosCliente.style.display = 'block';
                })
                .catch(() => {
                    resultadosCliente.innerHTML = '<div class="list-group-item text-danger">Error al buscar</div>';
                    resultadosCliente.style.display = 'block';
                });
        }, 300);
    });

    resultadosCliente.addEventListener('click', function (e) {
        const opcion = e.target.closest('.nem-opcion-cliente');
        if (!opcion) return;

        const clienteId = opcion.dataset.id;
        const clienteNombre = opcion.dataset.nombre;

        window.notaEntradaMultipleClienteId = clienteId;
        resultadosCliente.style.display = 'none';
        buscadorCliente.parentElement.classList.add('d-none');
        clienteNombreSpan.textContent = clienteNombre;
        clienteSeleccionadoDiv.classList.remove('d-none');

        cargarRentasPendientes(clienteId);
    });

    btnCambiarCliente.addEventListener('click', function () {
        resetModal();
    });

    function cargarRentasPendientes(clienteId) {
        pasoRentasDiv.classList.remove('d-none');
        listaRentasDiv.innerHTML = '<div class="text-muted">Cargando rentas pendientes...</div>';
        pasoPiezasDiv.classList.add('d-none');
        pasoDespachoDiv.classList.add('d-none');
        trasladoSectionDiv.classList.add('d-none');
        bloquesPiezasDiv.innerHTML = '';
        btnGenerar.disabled = true;

        fetch(`/notas_entrada/pendientes_cliente/${clienteId}?sucursal_id=${window.notaEntradaMultipleSucursalId}`)
            .then(resp => resp.json())
            .then(data => {
                if (data.error) {
                    listaRentasDiv.innerHTML = `<div class="text-danger">${data.error}</div>`;
                    return;
                }
                if (!data.rentas.length) {
                    listaRentasDiv.innerHTML = '';
                    sinRentasDiv.classList.remove('d-none');
                    return;
                }
                sinRentasDiv.classList.add('d-none');

                window.notaEntradaMultipleRentasInfo = {};
                data.rentas.forEach(r => { window.notaEntradaMultipleRentasInfo[r.renta_id] = r; });

                listaRentasDiv.innerHTML = data.rentas.map(r => `
                    <div class="form-check border rounded p-2 mb-2">
                        <input class="form-check-input nem-checkbox-renta" type="checkbox" value="${r.renta_id}" id="nem-renta-${r.renta_id}">
                        <label class="form-check-label w-100" for="nem-renta-${r.renta_id}">
                            <strong>SUC${window.notaEntradaMultipleSucursalId}-${String(r.folio).padStart(4, '0')}</strong>
                            <span class="text-muted">(Folio salida: ${String(r.folio_salida).padStart(5, '0')})</span>
                            &mdash; ${r.direccion_obra || 'Sin dirección'}
                            ${(r.traslado === 'redondo' || r.traslado === 'medio_regreso') ? '<span class="badge bg-info ms-1">Traslado pagado</span>' : ''}
                        </label>
                    </div>
                `).join('');
            })
            .catch(() => {
                listaRentasDiv.innerHTML = '<div class="text-danger">Error al cargar las rentas pendientes.</div>';
            });
    }

    listaRentasDiv.addEventListener('change', function (e) {
        if (!e.target.classList.contains('nem-checkbox-renta')) return;
        actualizarSeleccion();
    });

    trasladoExtraSelect.addEventListener('change', actualizarModo);

    function actualizarSeleccion() {
        const checkboxes = listaRentasDiv.querySelectorAll('.nem-checkbox-renta:checked');
        const rentaIds = Array.from(checkboxes).map(c => c.value);
        window.notaEntradaMultipleRentaIdsSeleccionadas = rentaIds;

        trasladoSectionDiv.classList.add('d-none');
        pasoPiezasDiv.classList.add('d-none');
        pasoDespachoDiv.classList.add('d-none');
        bloquesPiezasDiv.innerHTML = '';
        window.notaEntradaMultiplePiezas = {};

        if (rentaIds.length < 2) {
            btnGenerar.disabled = true;
            if (rentaIds.length === 1) {
                Swal.fire({
                    icon: 'info',
                    title: 'Se necesitan al menos 2 rentas',
                    text: 'Si solo va a devolver una renta, use el botón normal de "Generar Nota de Entrada" en esa renta.',
                    timer: 3500,
                    showConfirmButton: false
                });
            }
            return;
        }

        btnGenerar.disabled = false;
        trasladoSectionDiv.classList.remove('d-none');

        const tienePagado = rentaIds.some(id => {
            const t = (window.notaEntradaMultipleRentasInfo[id].traslado || '').toLowerCase();
            return t === 'redondo' || t === 'medio_regreso';
        });
        avisoTrasladoPagadoDiv.classList.toggle('d-none', !tienePagado);

        actualizarModo();
    }

    // El modal entra en modo "solo despacho" si alguna renta ya tenía traslado
    // pagado, O si el usuario pide ahora un traslado (medio/redondo): en ambos
    // casos sale un chofer físicamente y no se conocen las cantidades todavía.
    function actualizarModo() {
        const rentaIds = window.notaEntradaMultipleRentaIdsSeleccionadas;
        if (rentaIds.length < 2) return;

        const tienePagado = rentaIds.some(id => {
            const t = (window.notaEntradaMultipleRentasInfo[id].traslado || '').toLowerCase();
            return t === 'redondo' || t === 'medio_regreso';
        });
        const trasladoSolicitado = trasladoExtraSelect.value === 'medio' || trasladoExtraSelect.value === 'redondo';
        const modoDespacho = tienePagado || trasladoSolicitado;
        window.notaEntradaMultipleModoDespacho = modoDespacho;

        if (trasladoSolicitado) {
            costoTrasladoExtraInput.disabled = false;
        } else {
            costoTrasladoExtraInput.disabled = true;
            costoTrasladoExtraInput.value = 0;
        }

        if (modoDespacho) {
            divChoferRecoleccion.classList.remove('d-none');
            cargarCargadoresNem();
            pasoPiezasDiv.classList.add('d-none');
            bloquesPiezasDiv.innerHTML = '';
            window.notaEntradaMultiplePiezas = {};
            pasoDespachoDiv.classList.remove('d-none');
            btnGenerar.innerHTML = BTN_LABEL_DESPACHO;
        } else {
            divChoferRecoleccion.classList.add('d-none');
            selectChoferRecoleccion.value = '';
            pasoDespachoDiv.classList.add('d-none');
            pasoPiezasDiv.classList.remove('d-none');
            btnGenerar.innerHTML = BTN_LABEL_CONSOLIDADA;
            renderBloquesPiezas(rentaIds);
        }
    }

    function renderBloquesPiezas(rentaIds) {
        window.notaEntradaMultiplePiezas = {};

        bloquesPiezasDiv.innerHTML = rentaIds.map(rentaId => {
            const renta = window.notaEntradaMultipleRentasInfo[rentaId];
            window.notaEntradaMultiplePiezas[rentaId] = renta.piezas.map(p => ({
                id_pieza: p.id_pieza,
                nombre_pieza: p.nombre_pieza,
                cantidad_esperada: p.cantidad_pendiente,
                cantidad_recibida: p.cantidad_pendiente,
                cantidad_buena: p.cantidad_pendiente,
                cantidad_danada: 0,
                cantidad_sucia: 0,
                cantidad_perdida: 0
            }));

            const filasPiezas = renta.piezas.map((p, idx) => `
                <tr>
                    <td>${p.nombre_pieza}</td>
                    <td>${p.cantidad_pendiente}</td>
                    <td>
                        <input type="number" class="form-control form-control-sm nem-cantidad-buena" min="0"
                            max="${p.cantidad_pendiente}" value="${p.cantidad_pendiente}"
                            data-renta-id="${rentaId}" data-idx="${idx}">
                    </td>
                    <td>
                        <input type="number" class="form-control form-control-sm nem-cantidad-danada" min="0"
                            max="${p.cantidad_pendiente}" value="0" data-renta-id="${rentaId}" data-idx="${idx}">
                    </td>
                    <td>
                        <input type="number" class="form-control form-control-sm nem-cantidad-sucia" min="0"
                            max="${p.cantidad_pendiente}" value="0" data-renta-id="${rentaId}" data-idx="${idx}">
                    </td>
                    <td>
                        <input type="number" class="form-control form-control-sm nem-cantidad-perdida" min="0"
                            max="${p.cantidad_pendiente}" value="0" data-renta-id="${rentaId}" data-idx="${idx}">
                    </td>
                </tr>
            `).join('');

            return `
                <div class="card mb-3">
                    <div class="card-header">
                        <strong>SUC${window.notaEntradaMultipleSucursalId}-${String(renta.folio).padStart(4, '0')}</strong>
                        <span class="text-muted">(Folio salida: ${String(renta.folio_salida).padStart(5, '0')})</span>
                        &mdash; ${renta.direccion_obra || 'Sin dirección'}
                        <span class="badge bg-success float-end">Cierra al 100%</span>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-bordered table-sm mb-0">
                                <thead class="table-dark">
                                    <tr>
                                        <th>Pieza</th>
                                        <th style="width:80px;">Total a regresar</th>
                                        <th style="width:90px;">Buenas</th>
                                        <th style="width:90px;">Dañadas</th>
                                        <th style="width:90px;">Sucias</th>
                                        <th style="width:90px;">Perdidas</th>
                                    </tr>
                                </thead>
                                <tbody>${filasPiezas}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Validar y recalcular cuando cambian las cantidades de estado por pieza
    bloquesPiezasDiv.addEventListener('input', function (e) {
        const target = e.target;
        const rentaId = target.dataset.rentaId;
        const idx = target.dataset.idx;
        if (!rentaId || typeof idx === 'undefined') return;

        const pieza = window.notaEntradaMultiplePiezas[rentaId][idx];
        const total = pieza.cantidad_esperada;

        if (target.classList.contains('nem-cantidad-danada')) pieza.cantidad_danada = parseInt(target.value) || 0;
        if (target.classList.contains('nem-cantidad-sucia')) pieza.cantidad_sucia = parseInt(target.value) || 0;
        if (target.classList.contains('nem-cantidad-perdida')) pieza.cantidad_perdida = parseInt(target.value) || 0;

        const sumaProblemas = pieza.cantidad_danada + pieza.cantidad_sucia + pieza.cantidad_perdida;
        if (sumaProblemas > total) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: `La suma de dañadas, sucias y perdidas no puede ser mayor a ${total}.`
            });
            pieza.cantidad_danada = 0;
            pieza.cantidad_sucia = 0;
            pieza.cantidad_perdida = 0;
            const selector = `[data-renta-id="${rentaId}"][data-idx="${idx}"]`;
            bloquesPiezasDiv.querySelector(`.nem-cantidad-danada${selector}`).value = 0;
            bloquesPiezasDiv.querySelector(`.nem-cantidad-sucia${selector}`).value = 0;
            bloquesPiezasDiv.querySelector(`.nem-cantidad-perdida${selector}`).value = 0;
        }

        pieza.cantidad_buena = total - pieza.cantidad_danada - pieza.cantidad_sucia - pieza.cantidad_perdida;
        if (pieza.cantidad_buena < 0) pieza.cantidad_buena = 0;
        const selectorBuena = `.nem-cantidad-buena[data-renta-id="${rentaId}"][data-idx="${idx}"]`;
        bloquesPiezasDiv.querySelector(selectorBuena).value = pieza.cantidad_buena;
    });

    function mostrarExito(json) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal.hide();
        Swal.fire({
            title: window.notaEntradaMultipleModoDespacho ? '¡Rrecolección generada!' : '¡Nota de entrada consolidada generada!',
            html: `Se guardó correctamente.<br>Folio: <strong>#${String(json.folio).padStart(5, '0')}</strong>`,
            icon: 'success',
            showCancelButton: true,
            confirmButtonText: 'Descargar PDF',
            cancelButtonText: 'Cerrar',
            reverseButtons: true
        }).then(result => {
            if (result.isConfirmed) {
                window.open(`/notas_entrada/pdf/${json.nota_entrada_id}`, '_blank');
            }
            window.location.reload();
        });
    }

    function mostrarErrorSubmit(mensaje) {
        Swal.fire('Error', mensaje || 'No se pudo guardar.', 'error');
        btnGenerar.disabled = false;
        btnGenerar.innerHTML = window.notaEntradaMultipleModoDespacho ? BTN_LABEL_DESPACHO : BTN_LABEL_CONSOLIDADA;
    }

    // Submit
    document.getElementById('form-nota-entrada-multiple').addEventListener('submit', function (e) {
        e.preventDefault();

        const rentaIds = window.notaEntradaMultipleRentaIdsSeleccionadas;
        if (rentaIds.length < 2) {
            Swal.fire('Error', 'Selecciona al menos 2 rentas.', 'error');
            return;
        }

        const observaciones = document.getElementById('nem-observaciones').value;

        if (window.notaEntradaMultipleModoDespacho) {
            // Despacho: recolección obligatoria y/o traslado solicitado
            if (!selectChoferRecoleccion.value) {
                Swal.fire('Error', 'Selecciona el chofer que recolectará el equipo.', 'error');
                return;
            }

            const payload = {
                cliente_id: window.notaEntradaMultipleClienteId,
                sucursal_id: window.notaEntradaMultipleSucursalId,
                observaciones,
                chofer_recoleccion_id: selectChoferRecoleccion.value,
                traslado_extra: trasladoExtraSelect.value,
                costo_traslado_extra: parseFloat(costoTrasladoExtraInput.value) || 0,
                renta_ids: rentaIds
            };

            btnGenerar.disabled = true;
            btnGenerar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generando...';

            fetch('/notas_entrada/crear_recoleccion_multiple', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(resp => resp.json())
                .then(json => {
                    if (json.success) mostrarExito(json);
                    else mostrarErrorSubmit(json.error);
                })
                .catch(() => mostrarErrorSubmit('Error al enviar los datos al servidor.'));
            return;
        }

        // Captura completa de una sola vez (cliente entrega en persona)
        const payload = {
            cliente_id: window.notaEntradaMultipleClienteId,
            sucursal_id: window.notaEntradaMultipleSucursalId,
            observaciones,
            rentas: rentaIds.map(rentaId => ({
                renta_id: rentaId,
                piezas: window.notaEntradaMultiplePiezas[rentaId]
            }))
        };

        btnGenerar.disabled = true;
        btnGenerar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generando...';

        fetch('/notas_entrada/crear_multiple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(resp => resp.json())
            .then(json => {
                if (json.success) mostrarExito(json);
                else mostrarErrorSubmit(json.error);
            })
            .catch(() => mostrarErrorSubmit('Error al enviar los datos al servidor.'));
    });

    modalEl.addEventListener('hidden.bs.modal', resetModal);
});

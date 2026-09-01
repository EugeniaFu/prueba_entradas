document.addEventListener('DOMContentLoaded', function () {
    // Variable global para guardar el rentaId actual
    window.rentaIdNotaEntradaActual = null;
    window.notaEntradaPiezas = [];
    window.notaEntradaNotaSalidaId = null;
    window.notaEntradaEnRecoleccion = false;
    window.notaEntradaCargadores = null;


    function poblarSelectCargadores(select, cargadores) {
        select.innerHTML = '<option value="">Selecciona un chofer...</option>';
        cargadores.forEach(cargador => {
            const option = document.createElement('option');
            option.value = cargador.id;
            option.textContent = cargador.sucursal_nombre
                ? `${cargador.nombre_completo} (${cargador.sucursal_nombre})`
                : cargador.nombre_completo;
            select.appendChild(option);
        });
    }

    function cargarCargadores(selectId = 'select-chofer-recoleccion') {
        const select = document.getElementById(selectId);
        if (window.notaEntradaCargadores) {
            poblarSelectCargadores(select, window.notaEntradaCargadores);
            return Promise.resolve(window.notaEntradaCargadores);
        }
        return fetch('/notas_entrada/cargadores')
            .then(resp => resp.json())
            .then(cargadores => {
                window.notaEntradaCargadores = cargadores;
                poblarSelectCargadores(select, cargadores);
                return cargadores;
            })
            .catch(err => {
                console.error('Error al cargar cargadores:', err);
            });
    }


    function revisarCobroExtra() {
        let cobroExtra = false;

        // Revisa piezas
        window.notaEntradaPiezas.forEach(pieza => {
            if (
                (pieza.cantidad_danada && pieza.cantidad_danada > 0) ||
                (pieza.cantidad_sucia && pieza.cantidad_sucia > 0) ||
                (pieza.cantidad_perdida && pieza.cantidad_perdida > 0)
            ) {
                cobroExtra = true;
            }
        });

        // Revisa traslado extra
        const trasladoExtraSelect = document.getElementById('traslado-extra');
        if (trasladoExtraSelect && (trasladoExtraSelect.value === 'medio' || trasladoExtraSelect.value === 'redondo')) {
            cobroExtra = true;
        }

        // Muestra/oculta aviso
        const aviso = document.getElementById('aviso-cobro-extra');
        if (aviso) {
            if (cobroExtra) {
                aviso.classList.remove('d-none');
            } else {
                aviso.classList.add('d-none');
            }
        }
    }


    function mostrarOpcionesAccionDevolucion() {
        const opcionesDiv = document.getElementById('opciones-accion-devolucion');
        // Verifica si alguna pieza tiene cantidad recibida menor a la esperada
        const hayDevolucionParcial = window.notaEntradaPiezas.some(pieza => pieza.cantidad_recibida < pieza.cantidad_esperada);
        if (hayDevolucionParcial) {
            opcionesDiv.classList.remove('d-none');
        } else {
            opcionesDiv.classList.add('d-none');
            // Opcional: deselecciona radios si no aplica
            document.querySelectorAll('input[name="accion_devolucion"]').forEach(radio => radio.checked = false);
        }
    }



    function actualizarAvisosRetraso(data) {
        // Oculta todos los avisos y opciones (con verificación de seguridad)
        const avisosIds = ['aviso-retraso-ninguno', 'opcion-retraso-medio', 'aviso-retraso-medio', 'aviso-retraso-redondo', 'opcion-retraso-ninguno', 'aviso-retraso-ninguno-decision'];
        avisosIds.forEach(id => {
            const elemento = document.getElementById(id);
            if (elemento) elemento.classList.add('d-none');
        });

        const traslado = (data.traslado_original || '').toLowerCase();
        const estado = data.estado;
        const diasRetraso = data.dias_retraso;

        // Sin importar el tipo de traslado, si hay retraso, mostrar opción de cobro
        if (estado === 'Retrasada' && diasRetraso > 0) {
            const opcion = document.getElementById('opcion-retraso-ninguno');
            if (opcion) opcion.classList.remove('d-none');
            const checkbox = document.getElementById('checkbox-cobrar-retraso-ninguno');
            if (checkbox) {
                checkbox.checked = false;
                // Remover event listeners anteriores para evitar duplicados
                checkbox.removeEventListener('change', checkbox.changeHandler);
                // Crear nuevo handler y guardarlo para poder removerlo después
                checkbox.changeHandler = function () {
                    const aviso = document.getElementById('aviso-retraso-ninguno-decision');
                    if (aviso) {
                        if (checkbox.checked) {
                            aviso.classList.remove('d-none');
                        } else {
                            aviso.classList.add('d-none');
                        }
                    }
                };
                checkbox.addEventListener('change', checkbox.changeHandler);
            }
        }
    }


    // Abrir modal y cargar datos
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-nota-entrada');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            window.rentaIdNotaEntradaActual = rentaId;


            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNotaEntrada'));
            modal.show();

            // Limpia campos
            document.getElementById('folio-entrada').textContent = '-----';
            document.getElementById('folio-salida').textContent = '-----';
            document.getElementById('cliente-nombre').textContent = '---';
            document.getElementById('cliente-telefono').textContent = '---';
            document.getElementById('direccion-obra').textContent = '---';
            document.getElementById('traslado-original').textContent = '---';
            document.getElementById('fecha-hora-entrada').textContent = '--/--/---- --:--';
            document.getElementById('fecha-limite-entrada').textContent = '--/--/---- --:--';
            document.getElementById('estado-renta').textContent = '---';
            document.getElementById('costo-traslado-extra').value = 0;
            document.getElementById('traslado-extra').value = 'ninguno';
            document.getElementById('observaciones-entrada').value = '';
            document.getElementById('tabla-piezas-salieron').innerHTML = '<tr><td colspan="3" class="text-center text-muted">Cargando...</td></tr>';
            document.getElementById('tabla-evaluacion-piezas').innerHTML = '';
            document.getElementById('div-chofer-recoleccion').classList.add('d-none');
            document.getElementById('select-chofer-recoleccion').value = '';
            document.getElementById('checkbox-recoleccion').disabled = false;
            document.getElementById('div-chofer-traslado-extra').classList.add('d-none');
            document.getElementById('select-chofer-traslado-extra').value = '';
            document.getElementById('btn-cancelar-recoleccion').classList.add('d-none');

            // Fetch datos para el modal
            fetch(`/notas_entrada/preview/${rentaId}`)
                .then(resp => {
                    if (!resp.ok) {
                        return resp.json().then(errorData => {
                            throw new Error(errorData.message || errorData.error || 'Error en el servidor');
                        });
                    }
                    return resp.json();
                })
                .then(data => {
                    if (data.error) {
                        document.getElementById('tabla-piezas-salieron').innerHTML = `<tr><td colspan="3" class="text-danger">${data.error}</td></tr>`;
                        return;
                    }


                    if (!data.piezas || data.piezas.length === 0) {
                        document.getElementById('tabla-piezas-salieron').innerHTML = `
                <tr>
                    <td colspan="3" class="text-center text-muted">No hay piezas para mostrar en esta renta.</td>
                </tr>
            `;
                        document.getElementById('tabla-evaluacion-piezas').innerHTML = '';
                        return;
                    }


                    window.notaEntradaNotaSalidaId = data.nota_salida_id;
                    document.getElementById('folio-entrada').textContent = data.folio_entrada;
                    document.getElementById('folio-salida').textContent = data.folio_salida;
                    document.getElementById('cliente-nombre').textContent = data.cliente;
                    document.getElementById('cliente-telefono').textContent = data.telefono;
                    document.getElementById('direccion-obra').textContent = data.direccion_obra;


                    document.getElementById('traslado-original').textContent = data.traslado_original;
                    const divCheckboxRecoleccion = document.getElementById('div-checkbox-recoleccion');
                    const checkboxRecoleccion = document.getElementById('checkbox-recoleccion');
                    const divChofer = document.getElementById('div-chofer-recoleccion');
                    const selectChofer = document.getElementById('select-chofer-recoleccion');

                    if (data.requiere_recoleccion && !data.ya_paso_recoleccion) {
                        // Traslado redondo/medio_regreso y aún no se recolectó: se fuerza la
                        // recolección, no se puede desmarcar ni capturar cantidades a mano.
                        divCheckboxRecoleccion.classList.remove('d-none');
                        checkboxRecoleccion.checked = true;
                        checkboxRecoleccion.disabled = true;
                        window.notaEntradaEnRecoleccion = true;
                        divChofer.classList.remove('d-none');
                        cargarCargadores();
                        document.querySelectorAll('.cantidad-recibida, .cantidad-buena, .cantidad-danada, .cantidad-sucia, .cantidad-perdida').forEach(input => {
                            input.disabled = true;
                            input.value = '';
                        });
                    } else if (data.requiere_recoleccion && data.ya_paso_recoleccion) {
                        // Ya se recolectó: ahora se capturan las cantidades reales que el
                        // chofer reportó manualmente. No se vuelve a pedir recolección.
                        divCheckboxRecoleccion.classList.add('d-none');
                        checkboxRecoleccion.checked = false;
                        checkboxRecoleccion.disabled = false;
                        window.notaEntradaEnRecoleccion = false;
                        divChofer.classList.add('d-none');
                        selectChofer.value = '';
                        // El cliente puede avisar que ya no pasen a recoger el equipo:
                        // se ofrece cancelar el despacho en vez de forzar una captura falsa.
                        document.getElementById('btn-cancelar-recoleccion').classList.remove('d-none');
                    } else if ((data.traslado_original || '').toLowerCase() === 'ninguno') {
                        // Sin traslado: el cliente entrega/recoge el equipo por su cuenta,
                        // no aplica que un chofer nuestro vaya a recolectarlo.
                        divCheckboxRecoleccion.classList.add('d-none');
                        checkboxRecoleccion.checked = false;
                        checkboxRecoleccion.disabled = false;
                        window.notaEntradaEnRecoleccion = false;
                        divChofer.classList.add('d-none');
                        selectChofer.value = '';
                    } else {
                        // No requiere recolección forzada: comportamiento normal/opcional
                        divCheckboxRecoleccion.classList.remove('d-none');
                        checkboxRecoleccion.checked = false;
                        checkboxRecoleccion.disabled = false;
                        window.notaEntradaEnRecoleccion = false;
                    }

                    checkboxRecoleccion.removeEventListener('change', checkboxRecoleccion.changeHandlerRecoleccion);
                    checkboxRecoleccion.changeHandlerRecoleccion = function () {
                        const deshabilitar = checkboxRecoleccion.checked;
                        window.notaEntradaEnRecoleccion = deshabilitar;

                        if (deshabilitar) {
                            divChofer.classList.remove('d-none');
                            cargarCargadores();
                        } else {
                            divChofer.classList.add('d-none');
                            selectChofer.value = '';
                        }

                        // Deshabilita/limpia todos los campos de cantidades
                        document.querySelectorAll('.cantidad-recibida, .cantidad-buena, .cantidad-danada, .cantidad-sucia, .cantidad-perdida').forEach(input => {
                            input.disabled = deshabilitar;
                            if (deshabilitar) input.value = '';
                            else {
                                // Si quieres restaurar valores por defecto al desmarcar, puedes hacerlo aquí
                                const idx = input.dataset.idx;
                                if (typeof idx !== 'undefined') {
                                    if (input.classList.contains('cantidad-recibida') || input.classList.contains('cantidad-buena')) {
                                        input.value = data.piezas[idx].cantidad_esperada;
                                    } else {
                                        input.value = 0;
                                    }
                                }
                            }
                        });
                    };
                    checkboxRecoleccion.addEventListener('change', checkboxRecoleccion.changeHandlerRecoleccion);


                    document.getElementById('fecha-hora-entrada').textContent = data.fecha_hora;
                    document.getElementById('fecha-limite-entrada').textContent = data.fecha_limite;

                    //Mostrar los día de  retraso sin estar guardado en la BD
                    document.getElementById('estado-renta').textContent = data.estado;
                    if (data.estado === 'Retrasada' && data.dias_retraso > 0) {
                        document.getElementById('estado-renta').textContent += ` (${data.dias_retraso} día(s) de retraso)`;
                    }

                    actualizarAvisosRetraso(data)

                    // Piezas que salieron
                    let piezasHtml = '';
                    let evaluacionHtml = '';
                    window.notaEntradaPiezas = [];
                    data.piezas.forEach((pieza, idx) => {
                        piezasHtml += `
                            <tr>
                                <td>${pieza.nombre_pieza}</td>
                                <td class="text-center"><strong style="font-size: 1.05rem;">${pieza.cantidad_esperada}</strong></td>
                                <td>
                                    <input type="number" class="form-control form-control-sm cantidad-recibida" min="0" max="${pieza.cantidad_esperada}" value="${pieza.cantidad_esperada}" data-idx="${idx}">
                                </td>
                            </tr>
                        `;
                        evaluacionHtml += `
                            <tr>
                                <td>
                                    <input type="number" class="form-control form-control-sm cantidad-buena" min="0" value="${pieza.cantidad_esperada}" data-idx="${idx}">
                                </td>
                                <td>
                                    <input type="number" class="form-control form-control-sm cantidad-danada" min="0" value="0" data-idx="${idx}">
                                </td>
                                <td>
                                    <input type="number" class="form-control form-control-sm cantidad-sucia" min="0" value="0" data-idx="${idx}">
                                </td>
                                <td>
                                    <input type="number" class="form-control form-control-sm cantidad-perdida" min="0" value="0" data-idx="${idx}">
                                </td>
                            </tr>
                        `;
                        window.notaEntradaPiezas.push({
                            id_pieza: pieza.id_pieza,
                            nombre_pieza: pieza.nombre_pieza,
                            cantidad_esperada: pieza.cantidad_esperada,
                            cantidad_recibida: pieza.cantidad_esperada,
                            cantidad_buena: pieza.cantidad_esperada,
                            cantidad_danada: 0,
                            cantidad_sucia: 0,
                            cantidad_perdida: 0,
                            observaciones_pieza: ''
                        });
                    });
                    document.getElementById('tabla-piezas-salieron').innerHTML = piezasHtml;
                    document.getElementById('tabla-evaluacion-piezas').innerHTML = evaluacionHtml;

                    // Si la renta está forzada a recolección, las filas recién
                    // creadas arriba deben quedar bloqueadas (no se pudo hacer
                    // antes porque todavía no existían en el DOM).
                    if (window.notaEntradaEnRecoleccion) {
                        document.querySelectorAll('.cantidad-recibida, .cantidad-buena, .cantidad-danada, .cantidad-sucia, .cantidad-perdida').forEach(input => {
                            input.disabled = true;
                            input.value = '';
                        });
                    }
                })
                .catch(err => {
                    console.error('Error al obtener nota de entrada:', err);
                    // Si es una renta asociada, mostrar mensaje específico y cerrar modal
                    if (err.message && err.message.includes('renovación parcial')) {
                        const modal = bootstrap.Modal.getInstance(document.getElementById('modalNotaEntrada'));
                        modal.hide();
                        Swal.fire({
                            title: 'Renta Asociada',
                            text: 'Esta es una renovación parcial. No se puede crear nota de entrada porque el equipo nunca regresó físicamente. Solo se puede generar facturación.',
                            icon: 'info',
                            confirmButtonText: 'Entendido'
                        });
                    } else {
                        document.getElementById('tabla-piezas-salieron').innerHTML = `<tr><td colspan="3" class="text-danger">${err.message || 'Error al cargar la nota de entrada.'}</td></tr>`;
                    }
                });
        }
    });




    document.getElementById('modalNotaEntrada').addEventListener('input', function (e) {
        const idx = e.target.dataset.idx;
        if (typeof idx === 'undefined') return;
        const pieza = window.notaEntradaPiezas[idx];

        // Actualiza valores según inputs
        if (e.target.classList.contains('cantidad-recibida')) {
            pieza.cantidad_recibida = parseInt(e.target.value) || 0;
            const inputPerdida = document.querySelector(`.cantidad-perdida[data-idx="${idx}"]`);
            if (pieza.cantidad_recibida < pieza.cantidad_esperada) {
                // Faltan piezas por regresar: todavía no sabemos si se perdieron
                // definitivamente o solo están pendientes (eso se resuelve con
                // "Renovar Equipo Pendiente" / "Registrar como Pendiente"), así
                // que aquí solo se evalúan dañadas y sucias de lo que sí llegó.
                inputPerdida.disabled = true;
                inputPerdida.value = 0;
                pieza.cantidad_perdida = 0;
            } else {
                inputPerdida.disabled = false;
            }
        }
        if (e.target.classList.contains('cantidad-danada')) {
            pieza.cantidad_danada = parseInt(e.target.value) || 0;
        }
        if (e.target.classList.contains('cantidad-perdida')) {
            pieza.cantidad_perdida = parseInt(e.target.value) || 0;
        }
        if (e.target.classList.contains('cantidad-sucia')) {
            pieza.cantidad_sucia = parseInt(e.target.value) || 0;
        }

        // Recalcula buenas (una pieza recibida es buena solo si no quedó
        // marcada como sucia, dañada o perdida, para no contarla dos veces)
        pieza.cantidad_buena = pieza.cantidad_recibida - pieza.cantidad_danada - pieza.cantidad_perdida - pieza.cantidad_sucia;
        if (pieza.cantidad_buena < 0) pieza.cantidad_buena = 0;
        document.querySelector(`.cantidad-buena[data-idx="${idx}"]`).value = pieza.cantidad_buena;

        // Validación: la suma de todos los estados no puede superar lo recibido
        const sumaEstados = pieza.cantidad_buena + pieza.cantidad_danada + pieza.cantidad_perdida + pieza.cantidad_sucia;
        if (sumaEstados > pieza.cantidad_recibida) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: `La suma de buenas, dañadas, sucias y perdidas no puede ser mayor que las recibidas (${pieza.cantidad_recibida}).`
            });
            // Resetear valores
            pieza.cantidad_danada = 0;
            pieza.cantidad_sucia = 0;
            pieza.cantidad_perdida = 0;
            pieza.cantidad_buena = pieza.cantidad_recibida;
            document.querySelector(`.cantidad-danada[data-idx="${idx}"]`).value = 0;
            document.querySelector(`.cantidad-sucia[data-idx="${idx}"]`).value = 0;
            document.querySelector(`.cantidad-perdida[data-idx="${idx}"]`).value = 0;
            document.querySelector(`.cantidad-buena[data-idx="${idx}"]`).value = pieza.cantidad_buena;
        }

        revisarCobroExtra();
        mostrarOpcionesAccionDevolucion();
    });


    // --- Control de campo traslado extra ---
    const trasladoExtraSelect = document.getElementById('traslado-extra');
    const costoTrasladoExtraDiv = document.getElementById('costo-traslado-extra').parentElement;
    const costoTrasladoExtraInput = document.getElementById('costo-traslado-extra');
    const divChoferTrasladoExtra = document.getElementById('div-chofer-traslado-extra');
    const selectChoferTrasladoExtra = document.getElementById('select-chofer-traslado-extra');

    // Función para mostrar/ocultar el campo de costo y el chofer del traslado extra
    function actualizarTrasladoExtra() {
        if (trasladoExtraSelect.value === 'medio' || trasladoExtraSelect.value === 'redondo') {
            costoTrasladoExtraDiv.style.display = '';
            costoTrasladoExtraInput.disabled = false;
            divChoferTrasladoExtra.classList.remove('d-none');
            cargarCargadores('select-chofer-traslado-extra');
        } else {
            costoTrasladoExtraDiv.style.display = 'none';
            costoTrasladoExtraInput.value = '';
            costoTrasladoExtraInput.disabled = true;
            divChoferTrasladoExtra.classList.add('d-none');
            selectChoferTrasladoExtra.value = '';
        }
    }

    // Inicializa el campo al abrir el modal
    document.getElementById('modalNotaEntrada').addEventListener('show.bs.modal', function () {
        trasladoExtraSelect.value = 'ninguno';
        actualizarTrasladoExtra();
    });

    // Listener para el select
    trasladoExtraSelect.addEventListener('change', function () {
        actualizarTrasladoExtra();
        revisarCobroExtra();
    });

    // Oculta el campo al cargar la página
    actualizarTrasladoExtra();






    // Enviar nota de entrada
    const form = document.getElementById('form-nota-entrada');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            // Si está en recolección, exige seleccionar el chofer/cargador
            const selectChofer = document.getElementById('select-chofer-recoleccion');
            if (window.notaEntradaEnRecoleccion && !selectChofer.value) {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Selecciona al chofer que recogerá el equipo.'
                });
                return;
            }

            // Si hay traslado extra, exige seleccionar el chofer que lo hará
            const trasladoExtraValue = document.getElementById('traslado-extra').value;
            const selectChoferTrasladoExtra = document.getElementById('select-chofer-traslado-extra');
            if ((trasladoExtraValue === 'medio' || trasladoExtraValue === 'redondo') && !selectChoferTrasladoExtra.value) {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Selecciona al chofer que realizará el traslado extra.'
                });
                return;
            }

            const btn = document.getElementById('btn-generar-nota-entrada');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generando...';

            // Construir payload
            const rentaId = window.rentaIdNotaEntradaActual;
            const folio_entrada = document.getElementById('folio-entrada').textContent;
            const nota_salida_id = window.notaEntradaNotaSalidaId;
            const traslado_extra = document.getElementById('traslado-extra').value;
            const costo_traslado_extra = parseFloat(document.getElementById('costo-traslado-extra').value) || 0;
            const observaciones = document.getElementById('observaciones-entrada').value;
            const accionDevolucion = document.querySelector('input[name="accion_devolucion"]:checked')?.value || 'no';

            
            // Armar piezas
            const piezas = window.notaEntradaEnRecoleccion
                ? window.notaEntradaPiezas.map(pieza => ({
                    id_pieza: pieza.id_pieza,
                    cantidad_esperada: pieza.cantidad_esperada,
                    cantidad_recibida: 0,
                    cantidad_buena: 0,
                    cantidad_danada: 0,
                    cantidad_sucia: 0,
                    cantidad_perdida: 0,
                    observaciones_pieza: ''
                }))
                : window.notaEntradaPiezas.map((pieza, idx) => ({
                    id_pieza: pieza.id_pieza,
                    cantidad_esperada: pieza.cantidad_esperada,
                    cantidad_recibida: parseInt(document.querySelector(`.cantidad-recibida[data-idx="${idx}"]`).value) || 0,
                    cantidad_buena: parseInt(document.querySelector(`.cantidad-buena[data-idx="${idx}"]`).value) || 0,
                    cantidad_danada: parseInt(document.querySelector(`.cantidad-danada[data-idx="${idx}"]`).value) || 0,
                    cantidad_sucia: parseInt(document.querySelector(`.cantidad-sucia[data-idx="${idx}"]`).value) || 0,
                    cantidad_perdida: parseInt(document.querySelector(`.cantidad-perdida[data-idx="${idx}"]`).value) || 0,
                    observaciones_pieza: ''
                }));


            const cobrarRetraso = (() => {
                // Sin importar el tipo de traslado, usar el mismo checkbox
                return document.getElementById('checkbox-cobrar-retraso-ninguno')?.checked ? true : false;
            })();

            const payload = {
                folio_entrada,
                nota_salida_id,
                traslado_extra,
                costo_traslado_extra,
                observaciones,
                piezas,
                cobrar_retraso: cobrarRetraso,
                accion_devolucion: accionDevolucion,
                chofer_id: window.notaEntradaEnRecoleccion ? (selectChofer.value || null) : null,
                chofer_traslado_extra_id: (trasladoExtraValue === 'medio' || trasladoExtraValue === 'redondo')
                    ? (selectChoferTrasladoExtra.value || null) : null
            };


            try {
                const res = await fetch(`/notas_entrada/crear/${rentaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const json = await res.json();
                if (json.success) {
                    const notaEntradaId = json.nota_entrada_id;
                    const folioEntrada = json.folio;
                    const modal = bootstrap.Modal.getInstance(document.getElementById('modalNotaEntrada'));
                    modal.hide();

                    // Si la opción es renovacion, mostrar un SweetAlert con botón especial
                    if (accionDevolucion === 'renovacion') {
                        Swal.fire({
                            title: 'Nota de entrada generada',
                            text: '¿Deseas generar la renovación ahora?',
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Generar Renovación',
                            cancelButtonText: 'Cerrar'
                        }).then((result) => {
                            if (result.isConfirmed) {
                                // Simular click en botón de renovación para abrir modal unificado
                                const btnRenovacion = document.querySelector('.btn-abrir-modal-renovacion');
                                if (btnRenovacion) {
                                    btnRenovacion.dataset.rentaId = rentaId;
                                    btnRenovacion.click();
                                } else {
                                    // Si no hay botón visible, trigger el modal directamente
                                    window.abrirModalRenovacion(rentaId, 'parcial');
                                }
                            } else {
                                window.location.reload();
                            }
                        });
                    } else {
                        // Si NO es renovación, mostramos el SweetAlert normal
                        Swal.fire({
                            title: '¡Entrada Exitosa!',
                            html: `La nota de entrada se guardó correctamente.<br>Folio de Entrada: <strong>#${folioEntrada}</strong>`,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
                        }).then((result) => {
                            if (result.isConfirmed) {
                                window.open(`/notas_entrada/pdf/${notaEntradaId}`, '_blank');
                                window.location.reload();
                            } else {
                                window.location.reload();
                            }
                        });
                    }
                } else {
                    Swal.fire('Error', json.error || 'No se pudo guardar la nota de entrada', 'error');
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-arrow-right-circle"></i> Generar Nota de Entrada';
                }
            } catch (err) {
                Swal.fire('Error', 'Error al enviar los datos al servidor', 'error');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-right-circle"></i> Generar Nota de Entrada';
            }
        });
    }

    // Cancelar la recolección: el cliente avisó que ya no pasen a recoger
    // el equipo, así que se anula el despacho del chofer y la renta regresa
    // a su estado anterior.
    document.getElementById('btn-cancelar-recoleccion').addEventListener('click', function () {
        const rentaId = window.rentaIdNotaEntradaActual;
        if (!rentaId) return;

        Swal.fire({
            title: '¿Cancelar recolección?',
            text: 'El chofer ya no pasará a recoger el equipo. La renta regresará a su estado anterior.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc3545',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Sí, cancelar recolección',
            cancelButtonText: 'Volver'
        }).then((result) => {
            if (!result.isConfirmed) return;

            fetch(`/notas_entrada/cancelar_recoleccion/${rentaId}`, { method: 'POST' })
                .then(resp => resp.json())
                .then(json => {
                    if (json.success) {
                        bootstrap.Modal.getInstance(document.getElementById('modalNotaEntrada')).hide();
                        Swal.fire('Recolección cancelada', 'La renta regresó a su estado anterior.', 'success')
                            .then(() => window.location.reload());
                    } else {
                        Swal.fire('Error', json.error || 'No se pudo cancelar la recolección', 'error');
                    }
                })
                .catch(() => {
                    Swal.fire('Error', 'Error al enviar los datos al servidor', 'error');
                });
        });
    });

    // Limpiar rentaId cuando se cierre el modal
    document.getElementById('modalNotaEntrada').addEventListener('hidden.bs.modal', () => {
        window.rentaIdNotaEntradaActual = null;
        window.notaEntradaPiezas = [];
    });
});
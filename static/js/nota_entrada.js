document.addEventListener('DOMContentLoaded', function () {
    // Variable global para guardar el rentaId actual
    window.rentaIdNotaEntradaActual = null;
    window.notaEntradaPiezas = [];
    window.notaEntradaNotaSalidaId = null;


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
        // Oculta todos los avisos y opciones
        document.getElementById('aviso-retraso-ninguno').classList.add('d-none');
        document.getElementById('opcion-retraso-medio').classList.add('d-none');
        document.getElementById('aviso-retraso-medio').classList.add('d-none');
        document.getElementById('aviso-retraso-redondo').classList.add('d-none');

        const traslado = (data.traslado_original || '').toLowerCase();
        const estado = data.estado;
        const diasRetraso = data.dias_retraso;

        if (estado === 'Retrasada' && diasRetraso > 0) {
            if (traslado === 'ninguno') {
                document.getElementById('aviso-retraso-ninguno').classList.remove('d-none');
            } else if (traslado === 'medio') {
                document.getElementById('opcion-retraso-medio').classList.remove('d-none');
                const checkbox = document.getElementById('checkbox-cobrar-retraso-medio');
                checkbox.checked = true;
                checkbox.addEventListener('change', function () {
                    if (checkbox.checked) {
                        document.getElementById('aviso-retraso-medio').classList.remove('d-none');
                    } else {
                        document.getElementById('aviso-retraso-medio').classList.add('d-none');
                    }
                });
                document.getElementById('aviso-retraso-medio').classList.remove('d-none');
            } else if (traslado === 'redondo') {
                document.getElementById('aviso-retraso-redondo').classList.remove('d-none');
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

            // Fetch datos para el modal
            fetch(`/notas_entrada/preview/${rentaId}`)
                .then(resp => resp.json())
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
                                <td>${pieza.cantidad_esperada}</td>
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
                })
                .catch(err => {
                    document.getElementById('tabla-piezas-salieron').innerHTML = '<tr><td colspan="3" class="text-danger">Error al cargar la nota de entrada.</td></tr>';
                    console.error('Error al obtener nota de entrada:', err);
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
            // Habilita/deshabilita perdidas
            if (pieza.cantidad_recibida < pieza.cantidad_esperada) {
                pieza.cantidad_perdida = 0;
                document.querySelector(`.cantidad-perdida[data-idx="${idx}"]`).value = 0;
                document.querySelector(`.cantidad-perdida[data-idx="${idx}"]`).disabled = true;
            } else {
                document.querySelector(`.cantidad-perdida[data-idx="${idx}"]`).disabled = false;
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

        // Recalcula buenas
        pieza.cantidad_buena = pieza.cantidad_recibida - pieza.cantidad_danada - pieza.cantidad_perdida;
        if (pieza.cantidad_buena < 0) pieza.cantidad_buena = 0;
        document.querySelector(`.cantidad-buena[data-idx="${idx}"]`).value = pieza.cantidad_buena;

        // Validación de suma de estados
        pieza.cantidad_buena = pieza.cantidad_recibida - pieza.cantidad_danada - pieza.cantidad_perdida;
        if (pieza.cantidad_buena < 0) pieza.cantidad_buena = 0;
        document.querySelector(`.cantidad-buena[data-idx="${idx}"]`).value = pieza.cantidad_buena;

        // Validación
        const sumaEstados = pieza.cantidad_buena + pieza.cantidad_danada + pieza.cantidad_perdida + pieza.cantidad_sucia;
        if (pieza.cantidad_danada + pieza.cantidad_perdida + pieza.cantidad_sucia > pieza.cantidad_recibida) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: `La suma de dañadas, sucias y perdidas no puede ser mayor que las recibidas (${pieza.cantidad_recibida}).`
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

    // Función para mostrar/ocultar el campo de costo
    function actualizarTrasladoExtra() {
        if (trasladoExtraSelect.value === 'medio' || trasladoExtraSelect.value === 'redondo') {
            costoTrasladoExtraDiv.style.display = '';
            costoTrasladoExtraInput.disabled = false;
        } else {
            costoTrasladoExtraDiv.style.display = 'none';
            costoTrasladoExtraInput.value = '';
            costoTrasladoExtraInput.disabled = true;
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
            const piezas = window.notaEntradaPiezas.map((pieza, idx) => ({
                id_pieza: pieza.id_pieza,
                cantidad_esperada: pieza.cantidad_esperada,
                cantidad_recibida: parseInt(document.querySelector(`.cantidad-recibida[data-idx="${idx}"]`).value) || 0,
                cantidad_buena: parseInt(document.querySelector(`.cantidad-buena[data-idx="${idx}"]`).value) || 0,
                cantidad_danada: parseInt(document.querySelector(`.cantidad-danada[data-idx="${idx}"]`).value) || 0,
                cantidad_sucia: parseInt(document.querySelector(`.cantidad-sucia[data-idx="${idx}"]`).value) || 0,
                cantidad_perdida: parseInt(document.querySelector(`.cantidad-perdida[data-idx="${idx}"]`).value) || 0,
                observaciones_pieza: '' // Si tienes campo de observaciones por pieza, agrégalo aquí
            }));


            const cobrarRetraso = (() => {
                const trasladoOriginal = document.getElementById('traslado-original').textContent.trim().toLowerCase();
                if (trasladoOriginal === 'medio') {
                    return document.getElementById('checkbox-cobrar-retraso-medio')?.checked ? true : false;
                }
                // Si traslado es ninguno y hay retraso, se cobra siempre
                if (trasladoOriginal === 'ninguno') {
                    const estado = document.getElementById('estado-renta').textContent.toLowerCase();
                    return estado.includes('retrasada');
                }
                // En redondo nunca se cobra retraso
                return false;
            })();

            const payload = {
                folio_entrada,
                nota_salida_id,
                traslado_extra,
                costo_traslado_extra,
                observaciones,
                piezas,
                cobrar_retraso: cobrarRetraso,
                accion_devolucion: accionDevolucion
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
                    const modal = bootstrap.Modal.getInstance(document.getElementById('modalNotaEntrada'));
                    modal.hide();
                    Swal.fire({
                        title: 'Nota de entrada generada',
                        text: 'La nota de entrada se guardó correctamente.',
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Ver PDF',
                        cancelButtonText: 'Cerrar'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            window.open(`/notas_entrada/pdf/${notaEntradaId}`, '_blank');
                            window.location.reload();
                        } else {
                            window.location.reload(); // Esto actualiza la tabla y muestra el botón si corresponde
                        }
                    });
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

    // Limpiar rentaId cuando se cierre el modal
    document.getElementById('modalNotaEntrada').addEventListener('hidden.bs.modal', () => {
        window.rentaIdNotaEntradaActual = null;
        window.notaEntradaPiezas = [];
    });
});
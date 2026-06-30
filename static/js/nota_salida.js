document.addEventListener('DOMContentLoaded', function () {
    // Variable global para guardar el rentaId actual
    window.rentaIdNotaSalidaActual = null;
    window.notaSalidaRequiereChofer = false;
    window.notaSalidaCargadores = null;

    function cargarCargadoresSalida() {
        const select = document.getElementById('select-chofer-entrega');
        if (window.notaSalidaCargadores) {
            return Promise.resolve(window.notaSalidaCargadores);
        }
        return fetch('/notas_salida/cargadores')
            .then(resp => resp.json())
            .then(cargadores => {
                window.notaSalidaCargadores = cargadores;
                select.innerHTML = '<option value="">Selecciona un chofer...</option>';
                cargadores.forEach(cargador => {
                    const option = document.createElement('option');
                    option.value = cargador.id;
                    option.textContent = `${cargador.nombre_completo} (${cargador.sucursal_nombre || 'Sin sucursal'})`;
                    select.appendChild(option);
                });
                return cargadores;
            });
    }

    // Abrir modal y cargar datos
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-nota-salida');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            window.rentaIdNotaSalidaActual = rentaId; // Guardamos el rentaId en variable global

            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNotaSalida'));
            modal.show();

            // Limpia campos
            document.getElementById('nota-salida-folio').textContent = '-----';
            document.getElementById('nota-salida-fecha').textContent = '--/--/---- --:--';
            document.getElementById('nota-salida-cliente').textContent = '---';
            document.getElementById('nota-salida-celular').textContent = '---';
            document.getElementById('nota-salida-direccion').textContent = '---';
            document.getElementById('nota-salida-periodo').textContent = '--/--/---- a indefinido';
            document.getElementById('nota-salida-piezas').innerHTML = '<tr><td colspan="2" class="text-center text-muted">Cargando...</td></tr>';

            // Reinicia selección de chofer de entrega y checkbox parcial
            window.notaSalidaRequiereChofer = false;
            document.getElementById('div-chofer-entrega').classList.add('d-none');
            document.getElementById('select-chofer-entrega').value = '';
            document.getElementById('check-entrega-parcial').checked = false;

            fetch(`/notas_salida/preview/${rentaId}`)
                .then(resp => resp.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('nota-salida-piezas').innerHTML = `<tr><td colspan="2" class="text-danger">${data.error}</td></tr>`;
                        return;
                    }

                    document.getElementById('nota-salida-folio').textContent = data.folio;
                    document.getElementById('nota-salida-fecha').textContent = data.fecha;
                    document.getElementById('nota-salida-cliente').textContent = data.cliente;
                    document.getElementById('nota-salida-celular').textContent = data.celular;
                    document.getElementById('nota-salida-direccion').textContent = data.direccion_obra;
                    document.getElementById('nota-salida-periodo').textContent = data.periodo;

                    // Traslado medio_ida o redondo: nuestro chofer va a llevar el equipo
                    window.notaSalidaRequiereChofer = (data.traslado === 'medio_ida' || data.traslado === 'redondo');
                    if (window.notaSalidaRequiereChofer) {
                        document.getElementById('div-chofer-entrega').classList.remove('d-none');
                        cargarCargadoresSalida();
                    } else {
                        document.getElementById('div-chofer-entrega').classList.add('d-none');
                    }

                    let piezasHtml = '';

                    if (data.piezas && data.piezas.length > 0) {
                        data.piezas.forEach(pieza => {
                            const disponibles = pieza.disponibles || 0;
                            const tieneInventario = disponibles >= pieza.cantidad;
                            const badgeClass = tieneInventario ? 'bg-success' : 'bg-danger';
                            const disponiblesTexto = tieneInventario 
                                ? `<span class="badge ${badgeClass}">Disponibles: ${disponibles}</span>` 
                                : `<span class="badge ${badgeClass}">⚠️ Solo hay ${disponibles}</span>`;
                            
                            piezasHtml += `
                                <tr>
                                    <td>
                                        ${pieza.nombre_pieza}
                                        <br><small class="text-muted">${disponiblesTexto}</small>
                                    </td>
                                    <td>
                                        <input type="number"
                                            class="form-control form-control-sm pieza-cantidad"
                                            min="0"
                                            max="${pieza.cantidad}"
                                            value="${pieza.cantidad}"
                                            data-id-pieza="${pieza.id_pieza}"
                                            data-disponibles="${disponibles}">
                                        <small class="text-muted">Máx: ${pieza.cantidad}</small>
                                    </td>
                                </tr>`;
                        });
                    } else {
                        piezasHtml = '<tr><td colspan="2" class="text-center text-muted">Sin piezas asociadas</td></tr>';
                    }

                    document.getElementById('nota-salida-piezas').innerHTML = piezasHtml;

                    // Guardamos también el array de piezas en una variable global si se desea
                    window.piezasNotaSalida = data.piezas.map(p => ({
                        id_pieza: p.id_pieza,
                        cantidad: p.cantidad
                    }));
                })
                .catch(err => {
                    document.getElementById('nota-salida-piezas').innerHTML = '<tr><td colspan="2" class="text-danger">Error al cargar la nota de salida.</td></tr>';
                    console.error('Error al obtener nota de salida:', err);
                });
        }
    });

    // Enviar nota de salida
    const form = document.getElementById('form-nota-salida');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();

            const btn = document.getElementById('btn-generar-nota-salida');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generando...';

            const rentaId = window.rentaIdNotaSalidaActual; // Usamos la variable global confiable

            if (!rentaId) {
                Swal.fire('Error', 'No se pudo determinar la renta asociada.', 'error');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-right-circle"></i> Generar Nota de Salida';
                return;
            }

            const piezas = [];
            document.querySelectorAll('.pieza-cantidad').forEach(input => {
                const id_pieza = input.dataset.idPieza;
                const cantidad = parseInt(input.value);
                if (cantidad > 0) {
                    piezas.push({ id_pieza: parseInt(id_pieza), cantidad });
                }
            });

            const numero_referencia = document.getElementById('nota-salida-referencia').value;
            const observaciones = document.getElementById('nota-salida-observaciones').value;
            const selectChofer = document.getElementById('select-chofer-entrega');

            if (window.notaSalidaRequiereChofer && !selectChofer.value) {
                Swal.fire('Falta información', 'Selecciona el chofer que entregará el equipo.', 'warning');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-right-circle"></i> Generar Nota de Salida';
                return;
            }

            const payload = {
                numero_referencia,
                observaciones,
                piezas,
                chofer_id: window.notaSalidaRequiereChofer ? (selectChofer.value || null) : null,
                es_entrega_parcial: document.getElementById('check-entrega-parcial').checked
            };

            try {
                const res = await fetch(`/notas_salida/crear/${rentaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const json = await res.json();
                if (json.success) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('modalNotaSalida'));
                    modal.hide();

                    Swal.fire({
                        title: '¡Salida Exitosa!',
                        html: `La nota de salida se guardó correctamente.<br>Folio de Salida: <strong>#${json.folio}</strong>`,
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Descargar PDF',
                        cancelButtonText: 'Cerrar',
                        reverseButtons: true
                    }).then(result => {
                        if (result.isConfirmed) {
                            window.open(`/notas_salida/pdf/${json.nota_salida_id}`, '_blank');
                        }
                        window.location.reload();
                    });
                } else {
                    // Si hay piezas faltantes, mostrar mensaje detallado
                    if (json.piezas_faltantes && json.piezas_faltantes.length > 0) {
                        let mensajeDetallado = '<div class="text-start"><strong>No hay inventario suficiente:</strong><ul class="mt-2">';
                        json.piezas_faltantes.forEach(pieza => {
                            mensajeDetallado += `<li><strong>${pieza.nombre}</strong>: se solicitan <span class="text-danger">${pieza.solicitada}</span> pero solo hay <span class="text-warning">${pieza.disponible}</span> disponibles</li>`;
                        });
                        mensajeDetallado += '</ul></div>';
                        
                        Swal.fire({
                            title: 'Inventario insuficiente',
                            html: mensajeDetallado,
                            icon: 'error',
                            confirmButtonText: 'Entendido'
                        });
                    } else {
                        // Otro tipo de error
                        Swal.fire('Error', json.error || 'No se pudo guardar la nota de salida', 'error');
                    }
                    
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-arrow-right-circle"></i> Generar Nota de Salida';
                }
            } catch (err) {
                Swal.fire('Error', 'Error al enviar los datos al servidor', 'error');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-right-circle"></i> Generar Nota de Salida';
            }
        });
    }

    // Limpiar rentaId cuando se cierre el modal
    document.getElementById('modalNotaSalida').addEventListener('hidden.bs.modal', () => {
        window.rentaIdNotaSalidaActual = null;
    });
});
// ========================================
// INVENTARIO - FUNCIONALIDAD PRINCIPAL
// ========================================

// Búsqueda en tabla principal - solo si el elemento existe
const buscadorSucursal = document.getElementById('buscadorSucursal');
if (buscadorSucursal) {
    buscadorSucursal.addEventListener('keyup', function () {
        var filtro = this.value.toLowerCase();
        var rows = document.querySelectorAll('.table-inventario tbody tr');
        rows.forEach(function (row) {
            var texto = row.innerText.toLowerCase();
            row.style.display = texto.includes(filtro) ? '' : 'none';
        });
    });
}

// ========================================
// VARIABLES GLOBALES
// ========================================

let piezasReparacion = [];
let piezasFinalizarReparacion = [];
let piezasAltaEquipo = [];
let piezasMarcarDaniadas = [];
let piezasAgregadas = [];

// ========================================
// MODAL DE REPARACIÓN POR LOTES - FUNCIONALIDAD
// ========================================

// Inicializar funcionalidad del modal de reparación por lotes
document.addEventListener('DOMContentLoaded', function () {
    // Modal de reparación por lotes
    const selectorPiezaReparacion = document.getElementById('selectorPiezaReparacion');
    const btnAgregarReparacion = document.getElementById('btnAgregarPiezaReparacion');
    const infoDivReparacion = document.getElementById('infoPiezaSeleccionadaReparacion');

    if (selectorPiezaReparacion) {
        selectorPiezaReparacion.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];

            if (this.value) {
                const disponibles = parseInt(option.dataset.disponibles);
                const daniadas = parseInt(option.dataset.daniadas);
                const maxCantidad = disponibles + daniadas;

                infoDivReparacion.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${option.dataset.nombre}</strong><br>
                        Disponibles: ${disponibles} | Dañadas: ${daniadas} | <strong>Total para reparar: ${maxCantidad}</strong>
                    </div>
                `;
                infoDivReparacion.style.display = 'block';
                btnAgregarReparacion.disabled = maxCantidad === 0;
            } else {
                infoDivReparacion.style.display = 'none';
                btnAgregarReparacion.disabled = true;
            }
        });
    }

    if (btnAgregarReparacion) {
        btnAgregarReparacion.addEventListener('click', function () {
            const selector = document.getElementById('selectorPiezaReparacion');
            const option = selector.options[selector.selectedIndex];

            if (!selector.value) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = option.dataset.nombre;
            const disponibles = parseInt(option.dataset.disponibles);
            const daniadas = parseInt(option.dataset.daniadas);
            const maxCantidad = disponibles + daniadas;

            // Verificar si ya está agregada
            const yaExiste = piezasReparacion.find(p => p.id === idPieza);
            if (yaExiste) {
                Swal.fire('Error', 'Esta pieza ya está en la lista', 'error');
                return;
            }

            if (maxCantidad === 0) {
                Swal.fire('Error', 'No hay piezas disponibles para reparar', 'error');
                return;
            }

            // Agregar pieza
            piezasReparacion.push({
                id: idPieza,
                nombre: nombrePieza,
                cantidad: 1,
                maxCantidad: maxCantidad
            });

            // Actualizar UI
            actualizarListaPiezasReparacion();
            actualizarResumenReparacion();

            // Limpiar selector
            selector.value = '';
            btnAgregarReparacion.disabled = true;
            infoDivReparacion.style.display = 'none';
        });
    }

    // Modal de finalizar reparaciones
    const selectorPiezaFinalizar = document.getElementById('selectorPiezaFinalizar');
    const btnAgregarFinalizar = document.getElementById('btnAgregarPiezaFinalizar');
    const infoDivFinalizar = document.getElementById('infoPiezaSeleccionadaFinalizar');

    if (selectorPiezaFinalizar) {
        selectorPiezaFinalizar.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];

            if (this.value) {
                const enReparacion = parseInt(option.dataset.en_reparacion);
                infoDivFinalizar.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${option.dataset.nombre}</strong><br>
                        En reparación: <strong>${enReparacion}</strong>
                    </div>
                `;
                infoDivFinalizar.style.display = 'block';
                btnAgregarFinalizar.disabled = enReparacion === 0;
            } else {
                infoDivFinalizar.style.display = 'none';
                btnAgregarFinalizar.disabled = true;
            }
        });
    }

    if (btnAgregarFinalizar) {
        btnAgregarFinalizar.addEventListener('click', function () {
            const selector = document.getElementById('selectorPiezaFinalizar');
            const option = selector.options[selector.selectedIndex];

            if (!selector.value) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = option.dataset.nombre;
            const enReparacion = parseInt(option.dataset.en_reparacion);

            // Verificar si ya está agregada
            const yaExiste = piezasFinalizarReparacion.find(p => p.id === idPieza);
            if (yaExiste) {
                Swal.fire('Error', 'Esta pieza ya está en la lista', 'error');
                return;
            }

            if (enReparacion === 0) {
                Swal.fire('Error', 'No hay piezas en reparación', 'error');
                return;
            }

            // Agregar pieza
            piezasFinalizarReparacion.push({
                id: idPieza,
                nombre: nombrePieza,
                cantidad: 1,
                maxCantidad: enReparacion
            });

            // Actualizar UI
            actualizarListaPiezasFinalizar();
            actualizarResumenFinalizar();

            // Limpiar selector
            selector.value = '';
            btnAgregarFinalizar.disabled = true;
            infoDivFinalizar.style.display = 'none';
        });
    }

    // Limpiar modales cuando se cierren
    const modalReparacion = document.getElementById('modalReparacionLote');
    if (modalReparacion) {
        modalReparacion.addEventListener('hidden.bs.modal', function () {
            piezasReparacion = [];
            document.getElementById('selectorPiezaReparacion').value = '';
            document.getElementById('btnAgregarPiezaReparacion').disabled = true;
            document.getElementById('infoPiezaSeleccionadaReparacion').style.display = 'none';
            document.getElementById('listaPiezasAgregadasReparacion').style.display = 'none';
            document.getElementById('resumenReparacionLote').style.display = 'none';
            document.getElementById('btnConfirmarReparacionLote').disabled = true;
            document.getElementById('observacionesReparacion').value = '';
        });
    }

    const modalFinalizar = document.getElementById('modalFinalizarReparaciones');
    if (modalFinalizar) {
        modalFinalizar.addEventListener('hidden.bs.modal', function () {
            piezasFinalizarReparacion = [];
            document.getElementById('listaPiezasAgregadasFinalizar').style.display = 'none';
            document.getElementById('resumenFinalizarReparaciones').style.display = 'none';
            document.getElementById('btnConfirmarFinalizarReparaciones').disabled = true;
        });
    }

    // Envío de formularios
    const formReparacion = document.getElementById('formReparacionLote');
    if (formReparacion) {
        formReparacion.addEventListener('submit', function (e) {
            e.preventDefault();

            if (piezasReparacion.length === 0) {
                Swal.fire('Error', 'Agrega al menos una pieza', 'error');
                return;
            }

            const sucursalId = formReparacion.dataset.sucursalId;
            const observaciones = document.getElementById('observacionesReparacion').value || '';

            const piezasData = piezasReparacion.map(pieza => ({
                id_pieza: pieza.id,
                cantidad: pieza.cantidad
            }));

            const data = {
                sucursal_id: sucursalId,
                piezas: piezasData,
                observaciones: observaciones
            };

            // Deshabilitar botón y mostrar loading
            const btnConfirmar = document.getElementById('btnConfirmarReparacionLote');
            const originalText = btnConfirmar.innerHTML;
            btnConfirmar.disabled = true;
            btnConfirmar.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Enviando a reparación...';

            // Enviar con AJAX
            fetch('/inventario/reparacion-lote', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            title: '¡Éxito!',
                            text: data.message,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
                        }).then((result) => {
                            if (result.isConfirmed && data.folio_nota_salida) {
                                // Descargar PDF
                                const url = `/inventario/pdf-reparacion-lote/${data.folio_nota_salida}`;
                                window.open(url, '_blank');
                            }
                            // Cerrar modal y recargar página
                            const modal = bootstrap.Modal.getInstance(document.getElementById('modalReparacionLote'));
                            modal.hide();
                            window.location.reload();
                        });
                    } else {
                        Swal.fire('Error', data.error, 'error');
                        btnConfirmar.disabled = false;
                        btnConfirmar.innerHTML = originalText;
                    }
                })
                .catch(error => {
                    Swal.fire('Error', 'Error en la comunicación con el servidor', 'error');
                    btnConfirmar.disabled = false;
                    btnConfirmar.innerHTML = originalText;
                });
        });
    }

    const formFinalizar = document.getElementById('formFinalizarReparaciones');
    if (formFinalizar) {
        formFinalizar.addEventListener('submit', function (e) {
            e.preventDefault();

            if (piezasFinalizarReparacion.length === 0) {
                Swal.fire('Error', 'Selecciona al menos una pieza para finalizar', 'error');
                return;
            }

            const sucursalId = formFinalizar.dataset.sucursalId;

            const piezasData = piezasFinalizarReparacion.map(pieza => ({
                id_pieza: pieza.id,
                cantidad: pieza.cantidad
            }));

            const data = {
                sucursal_id: sucursalId,
                piezas: piezasData
            };

            // Deshabilitar botón y mostrar loading
            const btnConfirmar = document.getElementById('btnConfirmarFinalizarReparaciones');
            const originalText = btnConfirmar.innerHTML;
            btnConfirmar.disabled = true;
            btnConfirmar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Finalizando reparaciones...';

            // Enviar con AJAX
            fetch('/inventario/finalizar-reparaciones', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire('¡Éxito!', data.message, 'success').then(() => {
                            // Cerrar modal y recargar página
                            const modal = bootstrap.Modal.getInstance(document.getElementById('modalFinalizarReparaciones'));
                            modal.hide();
                            window.location.reload();
                        });
                    } else {
                        Swal.fire('Error', data.error, 'error');
                        btnConfirmar.disabled = false;
                        btnConfirmar.innerHTML = originalText;
                    }
                })
                .catch(error => {
                    Swal.fire('Error', 'Error en la comunicación con el servidor', 'error');
                    btnConfirmar.disabled = false;
                    btnConfirmar.innerHTML = originalText;
                });
        });
    }

    // ========================================
    // FUNCIONES DE TRANSFERENCIA - FUNCIONALIDAD EXISTENTE
    // ========================================
    
    // Manejar cambio de tipo de operación
    const radioMandar = document.getElementById('operacion_mandar');
    const radioRecibir = document.getElementById('operacion_recibir');
    const contenidoMandar = document.getElementById('contenido_mandar');
    const contenidoRecibir = document.getElementById('contenido_recibir');
    const btnConfirmar = document.getElementById('btnConfirmarTransferencia');
    const textoBoton = document.getElementById('textoBotonConfirmar');

    function cambiarTipoOperacion() {
        const tituloAgregarPiezas = document.getElementById('tituloAgregarPiezas');
        const labelSelectorPieza = document.getElementById('labelSelectorPieza');
        const tituloListaPiezas = document.getElementById('tituloListaPiezas');
        const selectorPieza = document.getElementById('selectorPieza');
        
        // Cambiar opciones del selector según operación
        const opcionesMandar = selectorPieza.querySelectorAll('.opcion-mandar');
        const opcionesRecibir = selectorPieza.querySelectorAll('.opcion-recibir');
        
        if (radioMandar.checked) {
            contenidoMandar.style.display = 'block';
            contenidoRecibir.style.display = 'none';
            textoBoton.textContent = 'Enviar Equipos';
            
            tituloAgregarPiezas.textContent = 'Equipos a Enviar';
            labelSelectorPieza.textContent = 'Seleccionar equipo disponible:';
            tituloListaPiezas.textContent = 'Equipos que se enviarán:';
            
            // Mostrar solo opciones de mandar
            opcionesMandar.forEach(opt => opt.style.display = 'block');
            opcionesRecibir.forEach(opt => opt.style.display = 'none');
            
        } else {
            contenidoMandar.style.display = 'none';
            contenidoRecibir.style.display = 'block';
            textoBoton.textContent = 'Recibir Equipos';
            
            tituloAgregarPiezas.textContent = 'Equipos a Recibir';
            labelSelectorPieza.textContent = 'Seleccionar equipo a recibir:';
            tituloListaPiezas.textContent = 'Equipos que se recibirán:';
            
            // Mostrar solo opciones de recibir
            opcionesMandar.forEach(opt => opt.style.display = 'none');
            opcionesRecibir.forEach(opt => opt.style.display = 'block');
        }
        
        // Resetear formulario
        piezasAgregadas = [];
        actualizarListaPiezas();
        actualizarResumenTransferencia();
        selectorPieza.value = '';
        document.getElementById('btnAgregarPieza').disabled = true;
        document.getElementById('infoPiezaSeleccionada').style.display = 'none';
    }

    if (radioMandar) radioMandar.addEventListener('change', cambiarTipoOperacion);
    if (radioRecibir) radioRecibir.addEventListener('change', cambiarTipoOperacion);

    // Manejar selección de pieza
    const selectorPieza = document.getElementById('selectorPieza');
    const btnAgregar = document.getElementById('btnAgregarPieza');
    const infoDiv = document.getElementById('infoPiezaSeleccionada');

    // Event listener para el selector
    if (selectorPieza) {
        selectorPieza.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];

            if (this.value) {
                const disponibles = parseInt(option.dataset.disponibles || '0');
                infoDiv.innerHTML = `
                <div class="alert alert-info">
                    <strong>${option.dataset.nombre}</strong><br>
                    Disponibles: <strong>${disponibles}</strong>
                </div>
            `;
                infoDiv.style.display = 'block';
                btnAgregar.disabled = disponibles === 0;
            } else {
                infoDiv.style.display = 'none';
                btnAgregar.disabled = true;
            }
        });
    }

    // Event listener para el botón agregar
    if (btnAgregar) {
        btnAgregar.addEventListener('click', function () {
            const selector = document.getElementById('selectorPieza');
            const option = selector.options[selector.selectedIndex];

            if (!selector.value) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = option.dataset.nombre;
            const disponibles = parseInt(option.dataset.disponibles);

            // Verificar si ya está agregada
            const yaExiste = piezasAgregadas.find(p => p.id === idPieza);
            if (yaExiste) {
                Swal.fire('Error', 'Esta pieza ya está en la lista', 'error');
                return;
            }

            // Agregar directamente con cantidad 1 (se puede ajustar en la tabla)
            piezasAgregadas.push({
                id: idPieza,
                nombre: nombrePieza,
                cantidad: 1,
                disponibles: disponibles
            });

            // Actualizar UI
            actualizarListaPiezas();
            actualizarResumenTransferencia();

            // Limpiar selector
            selector.value = '';
            btnAgregar.disabled = true;
            infoDiv.style.display = 'none';
        });
    }

    // Limpiar modal cuando se cierre
    const modalTransferencia = document.getElementById('modalTransferencia');
    if (modalTransferencia) {
        modalTransferencia.addEventListener('hidden.bs.modal', function () {
            piezasAgregadas = [];
            if (document.getElementById('selectorPieza')) {
                document.getElementById('selectorPieza').value = '';
                document.getElementById('btnAgregarPieza').disabled = true;
                document.getElementById('infoPiezaSeleccionada').style.display = 'none';
                document.getElementById('listaPiezasAgregadas').style.display = 'none';
                document.getElementById('resumenTransferencia').style.display = 'none';
                document.getElementById('btnConfirmarTransferencia').disabled = true;
                document.getElementById('observaciones').value = '';
                
                // Resetear a modo MANDAR por defecto
                document.getElementById('operacion_mandar').checked = true;
                document.getElementById('id_sucursal_destino').value = '';
                document.getElementById('id_sucursal_origen_recibir').value = '';
                cambiarTipoOperacion();
            }
        });
    }

    // ========================================
    // FORMULARIO DE TRANSFERENCIA - SUBMIT
    // ========================================
    
    const formTransferencia = document.getElementById('formTransferencia');
    if (formTransferencia) {
        formTransferencia.addEventListener('submit', function (e) {
            e.preventDefault();

            // Determinar tipo de operación y datos según el modo
            const esEnvio = document.getElementById('operacion_mandar').checked;

            if (piezasAgregadas.length === 0) {
                Swal.fire('Error', 'Agrega al menos una pieza', 'error');
                return;
            }

            let sucursalOrigenId, sucursalDestinoId, endpoint;

            if (esEnvio) {
                // Modo MANDAR: esta sucursal es origen
                sucursalOrigenId = formTransferencia.dataset.sucursalId;
                sucursalDestinoId = document.getElementById('id_sucursal_destino').value;
                endpoint = '/inventario/enviar-equipos';

                if (!sucursalDestinoId) {
                    Swal.fire('Error', 'Selecciona la sucursal de destino', 'error');
                    return;
                }
            } else {
                // Modo RECIBIR: esta sucursal es destino
                sucursalOrigenId = document.getElementById('id_sucursal_origen_recibir').value;
                sucursalDestinoId = formTransferencia.dataset.sucursalId;
                endpoint = '/inventario/recibir-equipos';

                if (!sucursalOrigenId) {
                    Swal.fire('Error', 'Selecciona la sucursal de origen', 'error');
                    return;
                }
            }

            const observaciones = document.getElementById('observaciones').value || '';

            // Preparar datos para JSON
            const piezasData = piezasAgregadas.map(pieza => ({
                id_pieza: pieza.id,
                cantidad: pieza.cantidad
            }));

            const transferData = {
                sucursal_origen_id: sucursalOrigenId,
                sucursal_destino_id: sucursalDestinoId,
                piezas: piezasData,
                observaciones: observaciones
            };

            // Deshabilitar botón y mostrar loading
            const btnConfirmar = document.getElementById('btnConfirmarTransferencia');
            const originalText = btnConfirmar.innerHTML;
            btnConfirmar.disabled = true;
            
            if (esEnvio) {
                btnConfirmar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando equipos...';
            } else {
                btnConfirmar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Recibiendo equipos...';
            }

            // Enviar con AJAX a la ruta correcta
            fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(transferData)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const mensaje = esEnvio ? 
                            `¡Equipos enviados exitosamente!<br>Folio de nota de salida: <strong>#${data.folio_nota_salida}</strong>` :
                            `¡Equipos recibidos exitosamente!<br>Folio de nota de entrada: <strong>#${data.folio_nota_entrada}</strong>`;
                        
                        Swal.fire({
                            title: '¡Éxito!',
                            html: mensaje,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
                        }).then((result) => {
                            if (result.isConfirmed) {
                                // Descargar PDF según el tipo de operación
                                if (esEnvio) {
                                    const url = `/inventario/pdf-transferencia-salida/${data.folio_nota_salida}`;
                                    window.open(url, '_blank');
                                } else {
                                    const url = `/inventario/pdf-transferencia-entrada/${data.folio_nota_entrada}`;
                                    window.open(url, '_blank');
                                }
                            }
                            
                            // Cerrar modal y recargar página
                            const modal = bootstrap.Modal.getInstance(document.getElementById('modalTransferencia'));
                            modal.hide();
                            setTimeout(() => {
                                window.location.reload();
                            }, 500);
                        });
                    } else {
                        Swal.fire('Error', data.error, 'error');
                    }
                })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire('Error', 'Error en la comunicación con el servidor', 'error');
            })
            .finally(() => {
                btnConfirmar.disabled = false;
                btnConfirmar.innerHTML = originalText;
            });
        });
    }
    
    // ========================================
    // MODAL DE ALTA DE EQUIPO NUEVO
    // ========================================

    // Event listeners para modal de alta de equipo
    const selectorPiezaAlta = document.getElementById('selectorPiezaAlta');
    const btnAgregarAlta = document.getElementById('btnAgregarPiezaAlta');
    const infoDivAlta = document.getElementById('infoPiezaSeleccionadaAlta');

    if (selectorPiezaAlta) {
        selectorPiezaAlta.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];

            if (this.value) {
                infoDivAlta.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${option.dataset.nombre}</strong><br>
                        Categoría: <span class="badge bg-secondary">${option.dataset.categoria}</span>
                    </div>
                `;
                infoDivAlta.style.display = 'block';
                btnAgregarAlta.disabled = false;
            } else {
                infoDivAlta.style.display = 'none';
                btnAgregarAlta.disabled = true;
            }
        });
    }

    if (btnAgregarAlta) {
        btnAgregarAlta.addEventListener('click', function () {
            const selector = document.getElementById('selectorPiezaAlta');
            const option = selector.options[selector.selectedIndex];

            if (!selector.value) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = option.dataset.nombre;
            const categoria = option.dataset.categoria;

            // Verificar si ya está agregada
            const yaExiste = piezasAltaEquipo.find(p => p.id === idPieza);
            if (yaExiste) {
                Swal.fire('Error', 'Esta pieza ya está en la lista', 'error');
                return;
            }

            // Agregar pieza
            piezasAltaEquipo.push({
                id: idPieza,
                nombre: nombrePieza,
                categoria: categoria,
                cantidad: 1
            });

            // Actualizar UI
            actualizarListaPiezasAlta();
            actualizarResumenAltaEquipo();

            // Limpiar selector
            selector.value = '';
            btnAgregarAlta.disabled = true;
            infoDivAlta.style.display = 'none';
        });
    }

    // Limpiar modal cuando se cierre
    const modalAltaEquipo = document.getElementById('modalAltaEquipoNuevo');
    if (modalAltaEquipo) {
        modalAltaEquipo.addEventListener('hidden.bs.modal', function () {
            piezasAltaEquipo = [];
            document.getElementById('listaPiezasAgregadasAlta').style.display = 'none';
            document.getElementById('resumenAltaEquipo').style.display = 'none';
            document.getElementById('btnConfirmarAltaEquipo').disabled = true;
            document.getElementById('observacionesAlta').value = '';
        });
    }

    // Event listener para el formulario de alta
    const formAltaEquipo = document.getElementById('formAltaEquipoNuevo');
    if (formAltaEquipo) {
        formAltaEquipo.addEventListener('submit', function (e) {
            e.preventDefault();

            if (piezasAltaEquipo.length === 0) {
                Swal.fire('Error', 'Agrega al menos una pieza', 'error');
                return;
            }

            const sucursalId = formAltaEquipo.dataset.sucursalId;
            const observaciones = document.getElementById('observacionesAlta').value || '';

            const piezasData = piezasAltaEquipo.map(pieza => ({
                id_pieza: pieza.id,
                cantidad: pieza.cantidad
            }));

            const data = {
                id_sucursal: sucursalId,
                piezas: piezasData,
                observaciones: observaciones,
                tipo_origen: 'inventario_sucursal'
            };

            // Deshabilitar botón y mostrar loading
            const btnConfirmar = document.getElementById('btnConfirmarAltaEquipo');
            const originalText = btnConfirmar.innerHTML;
            btnConfirmar.disabled = true;
            btnConfirmar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registrando equipos...';

            // Enviar con AJAX
            fetch('/inventario/alta-equipo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            title: '¡Éxito!',
                            html: `¡Equipos dados de alta exitosamente!<br>Folio de nota de entrada: <strong>#${data.folio_nota_entrada}</strong>`,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
                        }).then((result) => {
                            if (result.isConfirmed) {
                                const url = `/inventario/pdf-alta-equipo/${data.folio_nota_entrada}`;
                                window.open(url, '_blank');
                            }
                            
                            // Cerrar modal y recargar página
                            const modal = bootstrap.Modal.getInstance(document.getElementById('modalAltaEquipoNuevo'));
                            modal.hide();
                            setTimeout(() => {
                                window.location.reload();
                            }, 500);
                        });
                    } else {
                        Swal.fire('Error', data.error, 'error');
                        btnConfirmar.disabled = false;
                        btnConfirmar.innerHTML = originalText;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    Swal.fire('Error', 'Error en la comunicación con el servidor', 'error');
                    btnConfirmar.disabled = false;
                    btnConfirmar.innerHTML = originalText;
                });
        });
    }
    
    // ========================================
    // MODAL DE MARCAR COMO DAÑADAS - FUNCIONALIDAD
    // ========================================
    
    // Event listeners para modal de marcar como dañadas
    const selectorPiezaDaniada = document.getElementById('selectorPiezaDaniada');
    const btnAgregarDaniada = document.getElementById('btnAgregarPiezaDaniada');
    const infoDivDaniada = document.getElementById('infoPiezaSeleccionadaDaniada');

    if (selectorPiezaDaniada) {
        selectorPiezaDaniada.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];

            if (this.value) {
                const disponibles = parseInt(option.dataset.disponibles);
                infoDivDaniada.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${option.dataset.nombre}</strong><br>
                        Disponibles: <strong>${disponibles}</strong>
                    </div>
                `;
                infoDivDaniada.style.display = 'block';
                btnAgregarDaniada.disabled = disponibles === 0;
            } else {
                infoDivDaniada.style.display = 'none';
                btnAgregarDaniada.disabled = true;
            }
        });
    }

    if (btnAgregarDaniada) {
        btnAgregarDaniada.addEventListener('click', function () {
            const selector = document.getElementById('selectorPiezaDaniada');
            const option = selector.options[selector.selectedIndex];

            if (!selector.value) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = option.dataset.nombre;
            const disponibles = parseInt(option.dataset.disponibles);

            // Verificar si ya está agregada
            const yaExiste = piezasMarcarDaniadas.find(p => p.id === idPieza);
            if (yaExiste) {
                Swal.fire('Error', 'Esta pieza ya está en la lista', 'error');
                return;
            }

            if (disponibles === 0) {
                Swal.fire('Error', 'No hay piezas disponibles', 'error');
                return;
            }

            // Agregar pieza
            piezasMarcarDaniadas.push({
                id: idPieza,
                nombre: nombrePieza,
                cantidad: 1,
                maxCantidad: disponibles
            });

            // Actualizar UI
            actualizarListaPiezasDaniadas();
            actualizarResumenMarcarDaniadas();

            // Limpiar selector
            selector.value = '';
            btnAgregarDaniada.disabled = true;
            infoDivDaniada.style.display = 'none';
        });
    }
    
    // Limpiar modal cuando se cierre
    const modalMarcarDaniadas = document.getElementById('modalMarcarDaniadas');
    if (modalMarcarDaniadas) {
        modalMarcarDaniadas.addEventListener('hidden.bs.modal', function () {
            piezasMarcarDaniadas = [];
            document.getElementById('listaPiezasAgregadasDaniadas').style.display = 'none';
            document.getElementById('resumenMarcarDaniadas').style.display = 'none';
            document.getElementById('btnConfirmarMarcarDaniadas').disabled = true;
            document.getElementById('observacionesDaniadas').value = '';
        });
    }
    
    // Event listener para el formulario de marcar como dañadas
    const formMarcarDaniadas = document.getElementById('formMarcarDaniadas');
    if (formMarcarDaniadas) {
        formMarcarDaniadas.addEventListener('submit', function (e) {
            e.preventDefault();
            console.log('Formulario de marcar dañadas enviado'); // Debug

            if (piezasMarcarDaniadas.length === 0) {
                Swal.fire('Error', 'Selecciona al menos una pieza para marcar como dañada', 'error');
                return;
            }

            const sucursalId = formMarcarDaniadas.dataset.sucursalId;
            const observaciones = document.getElementById('observacionesDaniadas').value || '';
            
            console.log('Datos:', { sucursalId, observaciones, piezas: piezasMarcarDaniadas }); // Debug

            const piezasData = piezasMarcarDaniadas.map(pieza => ({
                id_pieza: pieza.id,
                cantidad: pieza.cantidad
            }));

            const data = {
                sucursal_id: sucursalId,
                piezas: piezasData,
                observaciones: observaciones
            };

            // Deshabilitar botón y mostrar loading
            const btnConfirmar = document.getElementById('btnConfirmarMarcarDaniadas');
            const originalText = btnConfirmar.innerHTML;
            btnConfirmar.disabled = true;
            btnConfirmar.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Marcando como dañadas...';

            // Enviar con AJAX
            fetch('/inventario/marcar-daniadas', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire('¡Éxito!', data.message, 'success').then(() => {
                            // Cerrar modal y recargar página
                            const modal = bootstrap.Modal.getInstance(document.getElementById('modalMarcarDaniadas'));
                            modal.hide();
                            window.location.reload();
                        });
                    } else {
                        Swal.fire('Error', data.error, 'error');
                        btnConfirmar.disabled = false;
                        btnConfirmar.innerHTML = originalText;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    Swal.fire('Error', 'Error en la comunicación con el servidor', 'error');
                    btnConfirmar.disabled = false;
                    btnConfirmar.innerHTML = originalText;
                });
        });
    }
});

// ========================================
// FUNCIONES AUXILIARES DE TRANSFERENCIA
// ========================================

// Actualizar lista de piezas agregadas
function actualizarListaPiezas() {
    const lista = document.getElementById('listaPiezasAgregadas');
    const tabla = document.getElementById('tablaPiezasAgregadas');

    if (piezasAgregadas.length === 0) {
        lista.style.display = 'none';
        return;
    }

    lista.style.display = 'block';

    let html = '';
    piezasAgregadas.forEach((pieza, index) => {
        html += `
      <tr>
        <td>${pieza.nombre}</td>
        <td>
          <input type="number" class="form-control form-control-sm" 
                 value="${pieza.cantidad}" min="1" max="${pieza.disponibles}"
                 onchange="actualizarCantidadPieza(${index}, this.value)">
        </td>
        <td>
          <button type="button" class="btn btn-danger btn-sm" 
                  onclick="eliminarPieza(${index})">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>
    `;
    });

    tabla.innerHTML = html;
}

// Actualizar cantidad de una pieza
function actualizarCantidadPieza(index, nuevaCantidad) {
    const cantidad = parseInt(nuevaCantidad);
    const pieza = piezasAgregadas[index];

    if (cantidad < 1 || cantidad > pieza.disponibles) {
        Swal.fire('Error', `La cantidad debe estar entre 1 y ${pieza.disponibles}`, 'error');
        actualizarListaPiezas(); // Reset
        return;
    }

    piezasAgregadas[index].cantidad = cantidad;
    actualizarResumenTransferencia();
}

// Eliminar pieza de la lista
function eliminarPieza(index) {
    piezasAgregadas.splice(index, 1);
    actualizarListaPiezas();
    actualizarResumenTransferencia();
}

// Actualizar resumen de transferencia
function actualizarResumenTransferencia() {
    const resumenDiv = document.getElementById('resumenTransferencia');
    const contenido = document.getElementById('resumenContenido');
    const btnConfirmar = document.getElementById('btnConfirmarTransferencia');

    if (piezasAgregadas.length === 0) {
        resumenDiv.style.display = 'none';
        btnConfirmar.disabled = true;
        return;
    }

    resumenDiv.style.display = 'block';
    btnConfirmar.disabled = false;

    let html = '<ul class="list-unstyled mb-0">';
    piezasAgregadas.forEach(pieza => {
        html += `<li><strong>${pieza.nombre}:</strong> ${pieza.cantidad} piezas</li>`;
    });
    html += '</ul>';

    contenido.innerHTML = html;
}

// ========================================
// FUNCIONES DE DESCARGA PDF
// ========================================

// Función para descargar PDF de transferencia (envío)
function descargarPDFTransferencia(folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de transferencia no disponible', 'error');
        return;
    }
    
    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-transferencia-salida/${folio}`;
    window.open(url, '_blank');
}

// Función para descargar PDF de recepción
function descargarPDFRecepcion(folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de recepción no disponible', 'error');
        return;
    }
    
    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-transferencia-entrada/${folio}`;
    window.open(url, '_blank');
}

// Función para descargar PDF de alta de equipo
function descargarPDFAltaEquipo(folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de alta no disponible', 'error');
        return;
    }
    
    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-alta-equipo/${folio}`;
    window.open(url, '_blank');
}

// Función para descargar PDF de reparación
function descargarPDFReparacion(folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de reparación no disponible', 'error');
        return;
    }
    
    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-reparacion-lote/${folio}`;
    window.open(url, '_blank');
}

// ========================================
// FUNCIONES AUXILIARES DE REPARACIÓN
// ========================================

// Actualizar lista de piezas para reparación
function actualizarListaPiezasReparacion() {
    const lista = document.getElementById('listaPiezasAgregadasReparacion');
    const tabla = document.getElementById('tablaPiezasAgregadasReparacion');

    if (piezasReparacion.length === 0) {
        lista.style.display = 'none';
        return;
    }

    lista.style.display = 'block';

    let html = '';
    piezasReparacion.forEach((pieza, index) => {
        html += `
            <tr>
                <td>${pieza.nombre}</td>
                <td>
                    <input type="number" class="form-control form-control-sm" 
                           value="${pieza.cantidad}" min="1" max="${pieza.maxCantidad}"
                           onchange="actualizarCantidadPiezaReparacion(${index}, this.value)">
                </td>
                <td>
                    <button type="button" class="btn btn-danger btn-sm" 
                            onclick="eliminarPiezaReparacion(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tabla.innerHTML = html;
}

// Actualizar cantidad de una pieza en reparación
function actualizarCantidadPiezaReparacion(index, nuevaCantidad) {
    const cantidad = parseInt(nuevaCantidad);
    const pieza = piezasReparacion[index];

    if (cantidad < 1 || cantidad > pieza.maxCantidad) {
        Swal.fire('Error', `La cantidad debe estar entre 1 y ${pieza.maxCantidad}`, 'error');
        actualizarListaPiezasReparacion(); // Reset
        return;
    }

    piezasReparacion[index].cantidad = cantidad;
    actualizarResumenReparacion();
}

// Eliminar pieza de la lista de reparación
function eliminarPiezaReparacion(index) {
    piezasReparacion.splice(index, 1);
    actualizarListaPiezasReparacion();
    actualizarResumenReparacion();
}

// Actualizar resumen de reparación
function actualizarResumenReparacion() {
    const resumenDiv = document.getElementById('resumenReparacionLote');
    const contenido = document.getElementById('resumenContenidoReparacion');
    const btnConfirmar = document.getElementById('btnConfirmarReparacionLote');

    if (piezasReparacion.length === 0) {
        resumenDiv.style.display = 'none';
        btnConfirmar.disabled = true;
        return;
    }

    resumenDiv.style.display = 'block';
    btnConfirmar.disabled = false;

    let html = '<ul class="list-unstyled mb-0">';
    piezasReparacion.forEach(pieza => {
        html += `<li><strong>${pieza.nombre}:</strong> ${pieza.cantidad} piezas</li>`;
    });
    html += '</ul>';

    contenido.innerHTML = html;
}

// Actualizar lista de piezas para finalizar
function actualizarListaPiezasFinalizar() {
    const lista = document.getElementById('listaPiezasAgregadasFinalizar');
    const tabla = document.getElementById('tablaPiezasAgregadasFinalizar');

    if (piezasFinalizarReparacion.length === 0) {
        lista.style.display = 'none';
        return;
    }

    lista.style.display = 'block';

    let html = '';
    piezasFinalizarReparacion.forEach((pieza, index) => {
        html += `
            <tr>
                <td>${pieza.nombre}</td>
                <td>
                    <input type="number" class="form-control form-control-sm" 
                           value="${pieza.cantidad}" min="1" max="${pieza.maxCantidad}"
                           onchange="actualizarCantidadPiezaFinalizar(${index}, this.value)">
                </td>
                <td>
                    <button type="button" class="btn btn-danger btn-sm" 
                            onclick="eliminarPiezaFinalizar(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tabla.innerHTML = html;
}

// Actualizar cantidad de una pieza para finalizar
function actualizarCantidadPiezaFinalizar(index, nuevaCantidad) {
    const cantidad = parseInt(nuevaCantidad);
    const pieza = piezasFinalizarReparacion[index];

    if (cantidad < 1 || cantidad > pieza.maxCantidad) {
        Swal.fire('Error', `La cantidad debe estar entre 1 y ${pieza.maxCantidad}`, 'error');
        actualizarListaPiezasFinalizar(); // Reset
        return;
    }

    piezasFinalizarReparacion[index].cantidad = cantidad;
    actualizarResumenFinalizar();
}

// Eliminar pieza de la lista de finalizar
function eliminarPiezaFinalizar(index) {
    piezasFinalizarReparacion.splice(index, 1);
    actualizarListaPiezasFinalizar();
    actualizarResumenFinalizar();
}

// Actualizar resumen de finalizar
function actualizarResumenFinalizar() {
    const resumenDiv = document.getElementById('resumenFinalizarReparaciones');
    const contenido = document.getElementById('resumenContenidoFinalizar');
    const btnConfirmar = document.getElementById('btnConfirmarFinalizarReparaciones');

    if (piezasFinalizarReparacion.length === 0) {
        resumenDiv.style.display = 'none';
        btnConfirmar.disabled = true;
        return;
    }

    resumenDiv.style.display = 'block';
    btnConfirmar.disabled = false;

    let html = '<ul class="list-unstyled mb-0">';
    piezasFinalizarReparacion.forEach(pieza => {
        html += `<li><strong>${pieza.nombre}:</strong> ${pieza.cantidad} piezas</li>`;
    });
    html += '</ul>';

    contenido.innerHTML = html;
}

// ========================================
// FUNCIONES AUXILIARES DE ALTA DE EQUIPO
// ========================================

// Actualizar lista de piezas para alta
function actualizarListaPiezasAlta() {
    const lista = document.getElementById('listaPiezasAgregadasAlta');
    const tabla = document.getElementById('tablaPiezasAgregadasAlta');

    if (piezasAltaEquipo.length === 0) {
        lista.style.display = 'none';
        return;
    }

    lista.style.display = 'block';

    let html = '';
    piezasAltaEquipo.forEach((pieza, index) => {
        html += `
            <tr>
                <td><strong>${pieza.nombre}</strong></td>
                <td><span class="badge bg-secondary">${pieza.categoria}</span></td>
                <td>
                    <input type="number" class="form-control form-control-sm" 
                           value="${pieza.cantidad}" min="1" max="999"
                           onchange="actualizarCantidadPiezaAlta(${index}, this.value)">
                </td>
                <td>
                    <button type="button" class="btn btn-danger btn-sm" 
                            onclick="eliminarPiezaAlta(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tabla.innerHTML = html;
}

// Actualizar cantidad de una pieza en alta
function actualizarCantidadPiezaAlta(index, nuevaCantidad) {
    const cantidad = parseInt(nuevaCantidad);

    if (cantidad < 1 || cantidad > 999) {
        Swal.fire('Error', 'La cantidad debe estar entre 1 y 999', 'error');
        actualizarListaPiezasAlta(); // Reset
        return;
    }

    piezasAltaEquipo[index].cantidad = cantidad;
    actualizarResumenAltaEquipo();
}

// Eliminar pieza de la lista de alta
function eliminarPiezaAlta(index) {
    piezasAltaEquipo.splice(index, 1);
    actualizarListaPiezasAlta();
    actualizarResumenAltaEquipo();
}

// Actualizar resumen de alta de equipo
function actualizarResumenAltaEquipo() {
    const resumenDiv = document.getElementById('resumenAltaEquipo');
    const contenido = document.getElementById('resumenContenidoAlta');
    const btnConfirmar = document.getElementById('btnConfirmarAltaEquipo');

    if (piezasAltaEquipo.length === 0) {
        resumenDiv.style.display = 'none';
        btnConfirmar.disabled = true;
        return;
    }

    resumenDiv.style.display = 'block';
    btnConfirmar.disabled = false;

    const totalPiezas = piezasAltaEquipo.reduce((total, pieza) => total + pieza.cantidad, 0);

    let html = `
        <div class="row">
            <div class="col-md-6">
                <strong>Total de piezas diferentes:</strong> ${piezasAltaEquipo.length}
            </div>
            <div class="col-md-6">
                <strong>Cantidad total de equipos:</strong> ${totalPiezas}
            </div>
        </div>
        <hr>
        <strong>Detalle:</strong>
        <ul class="list-unstyled mb-0 mt-2">
    `;
    
    piezasAltaEquipo.forEach(pieza => {
        html += `<li><strong>${pieza.nombre}:</strong> ${pieza.cantidad} unidad${pieza.cantidad > 1 ? 'es' : ''} <span class="badge bg-secondary">${pieza.categoria}</span></li>`;
    });
    
    html += '</ul>';

    contenido.innerHTML = html;
}

// ========================================
// FUNCIONES AUXILIARES DE MARCAR COMO DAÑADAS
// ========================================

// Actualizar lista de piezas para marcar como dañadas
function actualizarListaPiezasDaniadas() {
    const lista = document.getElementById('listaPiezasAgregadasDaniadas');
    const tabla = document.getElementById('tablaPiezasAgregadasDaniadas');

    if (piezasMarcarDaniadas.length === 0) {
        lista.style.display = 'none';
        return;
    }

    lista.style.display = 'block';

    let html = '';
    piezasMarcarDaniadas.forEach((pieza, index) => {
        html += `
            <tr>
                <td>${pieza.nombre}</td>
                <td>
                    <input type="number" class="form-control form-control-sm" 
                           value="${pieza.cantidad}" min="1" max="${pieza.maxCantidad}"
                           onchange="actualizarCantidadPiezaDaniada(${index}, this.value)">
                </td>
                <td>
                    <button type="button" class="btn btn-danger btn-sm" 
                            onclick="eliminarPiezaDaniada(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tabla.innerHTML = html;
}

// Actualizar cantidad de una pieza a dañar
function actualizarCantidadPiezaDaniada(index, nuevaCantidad) {
    const cantidad = parseInt(nuevaCantidad);
    const pieza = piezasMarcarDaniadas[index];

    if (cantidad < 1 || cantidad > pieza.maxCantidad) {
        Swal.fire('Error', `La cantidad debe estar entre 1 y ${pieza.maxCantidad}`, 'error');
        actualizarListaPiezasDaniadas(); // Reset
        return;
    }

    piezasMarcarDaniadas[index].cantidad = cantidad;
    actualizarResumenMarcarDaniadas();
}

// Eliminar pieza de la lista a dañar
function eliminarPiezaDaniada(index) {
    piezasMarcarDaniadas.splice(index, 1);
    actualizarListaPiezasDaniadas();
    actualizarResumenMarcarDaniadas();
}

// Actualizar resumen de marcar como dañadas
function actualizarResumenMarcarDaniadas() {
    const resumenDiv = document.getElementById('resumenMarcarDaniadas');
    const contenido = document.getElementById('resumenContenidoDaniadas');
    const btnConfirmar = document.getElementById('btnConfirmarMarcarDaniadas');

    if (piezasMarcarDaniadas.length === 0) {
        resumenDiv.style.display = 'none';
        btnConfirmar.disabled = true;
        return;
    }

    resumenDiv.style.display = 'block';
    btnConfirmar.disabled = false;

    let html = '<ul class="list-unstyled mb-0">';
    piezasMarcarDaniadas.forEach(pieza => {
        html += `<li><strong>${pieza.nombre}:</strong> ${pieza.cantidad} unidad${pieza.cantidad > 1 ? 'es' : ''}</li>`;
    });
    html += '</ul>';

    contenido.innerHTML = html;
}






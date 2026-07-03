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
let piezasParaTransferenciaData = []; // Datos originales del selector de transferencia (id, nombre, categoria, disponibles, todasDisponibles)

// ========================================
// BUSCADOR EN SELECTS DE PIEZAS (Choices.js)
// ========================================

const choicesInstancias = {};

// Envuelve un <select> con Choices.js para agregar buscador, manteniendo
// el select nativo sincronizado (value/change) para no romper el resto del código.
function initChoicesPieza(id) {
    const el = document.getElementById(id);
    if (!el || typeof Choices === 'undefined') return null;

    const instancia = new Choices(el, {
        searchEnabled: true,
        searchPlaceholderValue: 'Buscar pieza...',
        noResultsText: 'No se encontraron piezas',
        noChoicesText: 'No hay piezas disponibles',
        itemSelectText: '',
        shouldSort: false,
        allowHTML: false,
        position: 'bottom'
    });

    choicesInstancias[id] = instancia;
    liberarOverflowAlAbrirDropdown(el, instancia);

    // Choices genera un <input> de búsqueda sin id/name propio; se le asigna
    // uno para evitar advertencias de accesibilidad/autofill del navegador.
    if (instancia.input && instancia.input.element) {
        instancia.input.element.id = id + '_buscador';
        instancia.input.element.name = id + '_buscador';
    }

    return instancia;
}

// Las tarjetas del modal usan "overflow: hidden" para redondear sus esquinas,
// lo que recorta el dropdown de piezas aunque tenga z-index alto. Además,
// las tarjetas tienen un efecto ":hover { transform: translateY(-2px) }" que,
// al pasar el cursor sobre las piezas (siguen siendo descendientes de la
// tarjeta aunque se pinten "afuera"), crea un nuevo contexto de apilamiento y
// atrapa el z-index del dropdown por debajo de la tarjeta de Observaciones.
// Mientras el dropdown está abierto, se libera el overflow y se anula
// cualquier transform de los contenedores ancestros; al cerrarse se restaura.
function liberarOverflowAlAbrirDropdown(el, instancia) {
    const wrapper = instancia.containerOuter.element;
    let ancestrosModificados = [];

    el.addEventListener('showDropdown', function () {
        let nodo = wrapper.parentElement;
        while (nodo && nodo !== document.body) {
            const estilo = getComputedStyle(nodo);
            if (['hidden', 'auto', 'scroll', 'clip'].includes(estilo.overflowX) ||
                ['hidden', 'auto', 'scroll', 'clip'].includes(estilo.overflowY)) {
                nodo.style.setProperty('overflow', 'visible', 'important');
            }
            // Anular transform (propio o disparado por :hover) para que el
            // contenedor no genere un nuevo stacking context.
            nodo.style.setProperty('transform', 'none', 'important');
            ancestrosModificados.push(nodo);
            nodo = nodo.parentElement;
        }
    });

    el.addEventListener('hideDropdown', function () {
        ancestrosModificados.forEach(nodo => {
            nodo.style.removeProperty('overflow');
            nodo.style.removeProperty('transform');
        });
        ancestrosModificados = [];
    });
}

// Limpia la selección de un selector envuelto por Choices (equivalente a selector.value = '')
function resetChoicesPieza(id) {
    const instancia = choicesInstancias[id];
    if (instancia) {
        instancia.removeActiveItems();
    } else {
        const el = document.getElementById(id);
        if (el) el.value = '';
    }
}

// Choices.js reconstruye internamente los <option> del select y no conserva
// los atributos data-* originales (solo value y texto). Por eso, antes de
// envolver un select con Choices, se capturan sus datasets en un mapa
// {valor: {...dataset}} para poder seguir leyéndolos después del selector.
function capturarDatosOpciones(id) {
    const selectEl = document.getElementById(id);
    const datos = {};
    if (!selectEl) return datos;
    selectEl.querySelectorAll('option').forEach(opt => {
        if (opt.value === '') return;
        datos[opt.value] = Object.assign({}, opt.dataset);
    });
    return datos;
}

// ========================================
// MODAL DE REPARACIÓN POR LOTES - FUNCIONALIDAD
// ========================================

// Inicializar funcionalidad del modal de reparación por lotes
document.addEventListener('DOMContentLoaded', function () {
    // Modal de reparación por lotes
    const selectorPiezaReparacion = document.getElementById('selectorPiezaReparacion');
    const btnAgregarReparacion = document.getElementById('btnAgregarPiezaReparacion');
    const infoDivReparacion = document.getElementById('infoPiezaSeleccionadaReparacion');

    const datosPiezaReparacion = capturarDatosOpciones('selectorPiezaReparacion');
    initChoicesPieza('selectorPiezaReparacion');

    if (selectorPiezaReparacion) {
        selectorPiezaReparacion.addEventListener('change', function () {
            const datos = datosPiezaReparacion[this.value];

            if (this.value && datos) {
                const disponibles = parseInt(datos.disponibles);
                const daniadas = parseInt(datos.daniadas);
                const maxCantidad = disponibles + daniadas;

                infoDivReparacion.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${datos.nombre}</strong><br>
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
            const datos = datosPiezaReparacion[selector.value];

            if (!selector.value || !datos) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = datos.nombre;
            const disponibles = parseInt(datos.disponibles);
            const daniadas = parseInt(datos.daniadas);
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
            resetChoicesPieza('selectorPiezaReparacion');
            btnAgregarReparacion.disabled = true;
            infoDivReparacion.style.display = 'none';
        });
    }

    // Modal de finalizar reparaciones
    const selectorPiezaFinalizar = document.getElementById('selectorPiezaFinalizar');
    const btnAgregarFinalizar = document.getElementById('btnAgregarPiezaFinalizar');
    const infoDivFinalizar = document.getElementById('infoPiezaSeleccionadaFinalizar');

    const datosPiezaFinalizar = capturarDatosOpciones('selectorPiezaFinalizar');
    initChoicesPieza('selectorPiezaFinalizar');

    if (selectorPiezaFinalizar) {
        selectorPiezaFinalizar.addEventListener('change', function () {
            const datos = datosPiezaFinalizar[this.value];

            if (this.value && datos) {
                const enReparacion = parseInt(datos.en_reparacion);
                infoDivFinalizar.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${datos.nombre}</strong><br>
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
            const datos = datosPiezaFinalizar[selector.value];

            if (!selector.value || !datos) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = datos.nombre;
            const enReparacion = parseInt(datos.en_reparacion);

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
            resetChoicesPieza('selectorPiezaFinalizar');
            btnAgregarFinalizar.disabled = true;
            infoDivFinalizar.style.display = 'none';
        });
    }

    // Limpiar modales cuando se cierren
    const modalReparacion = document.getElementById('modalReparacionLote');
    if (modalReparacion) {
        modalReparacion.addEventListener('hidden.bs.modal', function () {
            piezasReparacion = [];
            resetChoicesPieza('selectorPiezaReparacion');
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
                            title: '¡Equipo Enviado a Reparación!',
                            html: `Equipo enviado a reparación correctamente.<br>Folio de Salida: <strong>#${data.folio_nota_salida}</strong>`,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
                        }).then((result) => {
                            if (result.isConfirmed && data.folio_nota_salida) {
                                // Descargar PDF
                                const url = `/inventario/pdf-reparacion-lote/${sucursalId}/${data.folio_nota_salida}`;
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
                        Swal.fire({
                            title: '¡Reparación Finalizada!',
                            html: `Las piezas regresaron a disponibles correctamente.<br>Folio de Entrada: <strong>#${data.folio_nota_entrada}</strong>`,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
                        }).then((result) => {
                            if (result.isConfirmed && data.pdf_url) {
                                // Abrir PDF en nueva ventana
                                window.open(data.pdf_url, '_blank');
                            }
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

    // Capturar los datos originales del select ANTES de que Choices.js lo envuelva,
    // ya que luego se reconstruye su lista de opciones dinámicamente (modo Mandar/Recibir).
    const selectorPiezaTransferenciaEl = document.getElementById('selectorPieza');
    if (selectorPiezaTransferenciaEl) {
        selectorPiezaTransferenciaEl.querySelectorAll('option').forEach(opt => {
            if (opt.value === '') return;
            piezasParaTransferenciaData.push({
                value: opt.value,
                nombre: opt.dataset.nombre || '',
                categoria: opt.dataset.categoria || '',
                disponibles: parseInt(opt.dataset.disponibles || '0'),
                todasDisponibles: parseInt(opt.dataset.todasDisponibles || '999')
            });
        });
    }
    initChoicesPieza('selectorPieza');

    function cambiarTipoOperacion() {
        const tituloAgregarPiezas = document.getElementById('tituloAgregarPiezas');
        const labelSelectorPieza = document.getElementById('labelSelectorPieza');
        const tituloListaPiezas = document.getElementById('tituloListaPiezas');
        const instanciaSelectorPieza = choicesInstancias['selectorPieza'];

        const nuevasOpciones = [{ value: '', label: 'Buscar y seleccionar pieza...', selected: true }];

        if (radioMandar.checked) {
            contenidoMandar.style.display = 'block';
            contenidoRecibir.style.display = 'none';
            textoBoton.textContent = 'Enviar Equipos';

            tituloAgregarPiezas.textContent = 'Equipos a Enviar';
            labelSelectorPieza.textContent = 'Seleccionar equipo disponible:';
            tituloListaPiezas.textContent = 'Equipos que se enviarán:';

            // Para MANDAR: solo piezas con disponibles > 0
            piezasParaTransferenciaData.filter(p => p.disponibles > 0).forEach(p => {
                nuevasOpciones.push({
                    value: p.value,
                    label: `${p.nombre}${p.categoria ? ' (' + p.categoria + ')' : ''} - ${p.disponibles} disponibles`
                });
            });

        } else {
            contenidoMandar.style.display = 'none';
            contenidoRecibir.style.display = 'block';
            textoBoton.textContent = 'Recibir Equipos';

            tituloAgregarPiezas.textContent = 'Equipos a Recibir';
            labelSelectorPieza.textContent = 'Seleccionar equipo a recibir:';
            tituloListaPiezas.textContent = 'Equipos que se recibirán:';

            // Para RECIBIR: mostrar todas las piezas
            piezasParaTransferenciaData.forEach(p => {
                nuevasOpciones.push({
                    value: p.value,
                    label: `${p.nombre}${p.categoria ? ' (' + p.categoria + ')' : ''} - Recibir equipos`
                });
            });
        }

        if (instanciaSelectorPieza) {
            instanciaSelectorPieza.clearStore();
            instanciaSelectorPieza.setChoices(nuevasOpciones, 'value', 'label', true);
        }

        // Resetear formulario
        piezasAgregadas = [];
        actualizarListaPiezas();
        actualizarResumenTransferencia();
        resetChoicesPieza('selectorPieza');
        document.getElementById('btnAgregarPieza').disabled = true;
        document.getElementById('infoPiezaSeleccionada').style.display = 'none';
    }

    if (radioMandar) radioMandar.addEventListener('change', cambiarTipoOperacion);
    if (radioRecibir) radioRecibir.addEventListener('change', cambiarTipoOperacion);

    // Aplicar el filtrado de piezas y los títulos correctos desde la primera
    // apertura del modal (antes solo se aplicaban al cambiar el radio o cerrar el modal).
    if (selectorPiezaTransferenciaEl) cambiarTipoOperacion();

    // Manejar selección de pieza
    const selectorPieza = document.getElementById('selectorPieza');
    const btnAgregar = document.getElementById('btnAgregarPieza');
    const infoDiv = document.getElementById('infoPiezaSeleccionada');

    // Event listener para el selector
    if (selectorPieza) {
        selectorPieza.addEventListener('change', function () {
            const piezaInfo = piezasParaTransferenciaData.find(p => p.value === this.value);

            if (this.value && piezaInfo) {
                // Determinar disponibles según el modo actual
                let disponibles;
                if (radioRecibir && radioRecibir.checked) {
                    // Modo RECIBIR: permitir cualquier cantidad
                    disponibles = piezaInfo.todasDisponibles;
                } else {
                    // Modo MANDAR: usar disponibles reales
                    disponibles = piezaInfo.disponibles;
                }

                infoDiv.innerHTML = `
                <div class="alert alert-info">
                    <strong>${piezaInfo.nombre}</strong><br>
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
            const piezaInfo = piezasParaTransferenciaData.find(p => p.value === selector.value);

            if (!selector.value || !piezaInfo) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = piezaInfo.nombre;

            // Determinar disponibles según el modo actual
            let disponibles;
            if (radioRecibir && radioRecibir.checked) {
                // Modo RECIBIR: permitir cualquier cantidad
                disponibles = piezaInfo.todasDisponibles;
            } else {
                // Modo MANDAR: usar disponibles reales
                disponibles = piezaInfo.disponibles;
            }

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
            resetChoicesPieza('selectorPieza');
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
                resetChoicesPieza('selectorPieza');
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
                            `¡Equipo enviado correctamente!<br>Folio de Salida: <strong>#${data.folio_nota_salida}</strong>` :
                            `¡Equipo recibido correctamente!<br>Folio de Entrada: <strong>#${data.folio_nota_entrada}</strong>`;

                        Swal.fire({
                            title: esEnvio ? '¡Transferencia Enviada!' : '¡Transferencia Recibida!',
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
                                    const url = `/inventario/pdf-transferencia-salida/${sucursalOrigenId}/${data.folio_nota_salida}`;
                                    window.open(url, '_blank');
                                } else {
                                    const url = `/inventario/pdf-transferencia-entrada/${sucursalDestinoId}/${data.folio_nota_entrada}`;
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

    const datosPiezaAlta = capturarDatosOpciones('selectorPiezaAlta');
    initChoicesPieza('selectorPiezaAlta');

    if (selectorPiezaAlta) {
        selectorPiezaAlta.addEventListener('change', function () {
            const datos = datosPiezaAlta[this.value];

            if (this.value && datos) {
                infoDivAlta.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${datos.nombre}</strong><br>
                        Categoría: <span class="badge bg-secondary">${datos.categoria}</span>
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
            const datos = datosPiezaAlta[selector.value];

            if (!selector.value || !datos) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = datos.nombre;
            const categoria = datos.categoria;

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
            resetChoicesPieza('selectorPiezaAlta');
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
                            title: '¡Alta Exitosa!',
                            html: `¡Equipos dados de alta correctamente!<br>Folio de Entrada: <strong>#${data.folio_nota_entrada}</strong>`,
                            icon: 'success',
                            showCancelButton: true,
                            confirmButtonText: 'Descargar PDF',
                            cancelButtonText: 'Cerrar',
                            reverseButtons: true
                        }).then((result) => {
                            if (result.isConfirmed) {
                                const url = `/inventario/pdf-alta-equipo/${sucursalId}/${data.folio_nota_entrada}`;
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

    const datosPiezaDaniada = capturarDatosOpciones('selectorPiezaDaniada');
    initChoicesPieza('selectorPiezaDaniada');

    if (selectorPiezaDaniada) {
        selectorPiezaDaniada.addEventListener('change', function () {
            const datos = datosPiezaDaniada[this.value];

            if (this.value && datos) {
                const disponibles = parseInt(datos.disponibles);
                infoDivDaniada.innerHTML = `
                    <div class="alert alert-info">
                        <strong>${datos.nombre}</strong><br>
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
            const datos = datosPiezaDaniada[selector.value];

            if (!selector.value || !datos) {
                Swal.fire('Error', 'Selecciona una pieza', 'error');
                return;
            }

            const idPieza = selector.value;
            const nombrePieza = datos.nombre;
            const disponibles = parseInt(datos.disponibles);

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
            resetChoicesPieza('selectorPiezaDaniada');
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
                        Swal.fire({
                            title: '¡Piezas Dañadas!',
                            html: `¡Equipo marcado como dañado correctamente!`,
                            text: data.message,
                            icon: 'success',
                            confirmButtonText: 'Entendido'
                        }).then(() => {
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
function descargarPDFTransferencia(sucursalId, folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de transferencia no disponible', 'error');
        return;
    }

    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-transferencia-salida/${sucursalId}/${folio}`;
    window.open(url, '_blank');
}

// Función para descargar PDF de recepción
function descargarPDFRecepcion(sucursalId, folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de recepción no disponible', 'error');
        return;
    }

    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-transferencia-entrada/${sucursalId}/${folio}`;
    window.open(url, '_blank');
}

// Función para descargar PDF de alta de equipo
function descargarPDFAltaEquipo(sucursalId, folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de alta no disponible', 'error');
        return;
    }

    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-alta-equipo/${sucursalId}/${folio}`;
    window.open(url, '_blank');
}

// Función para descargar PDF de reparación
function descargarPDFReparacion(sucursalId, folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de reparación no disponible', 'error');
        return;
    }

    // Abrir PDF en nueva ventana
    const url = `/inventario/pdf-reparacion-lote/${sucursalId}/${folio}`;
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






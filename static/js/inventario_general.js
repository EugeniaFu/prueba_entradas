// ========================================
// INVENTARIO GENERAL - CÓDIGO LIMPIO Y FUNCIONAL
// ========================================

// Variables globales para filtros
let filtroEstatusActual = 'todos';

// Variables globales para alta de equipo general (código limpio)
let piezasAltaEquipoGeneral = [];

// Variables globales para baja de equipo general
let piezasBajaEquipoGeneral = [];

// ========================================
// FUNCIONES DE FILTRADO POR ESTATUS
// ========================================

// Función para filtrar por estatus
function filtrarPorEstatus(estatus) {
  filtroEstatusActual = estatus;
  
  // Actualizar botones activos - con verificación de existencia
  document.querySelectorAll('[id^="filtro-"]').forEach(btn => btn.classList.remove('active'));
  const filtroBtn = document.getElementById(`filtro-${estatus}`);
  if (filtroBtn) {
    filtroBtn.classList.add('active');
  }
  
  // Aplicar filtros
  aplicarFiltros();
}

// Función unificada para aplicar filtros
function aplicarFiltros() {
  const buscadorPiezas = document.getElementById('buscadorPiezas');
  const textoBusqueda = buscadorPiezas ? buscadorPiezas.value.toLowerCase() : '';
  const filas = document.querySelectorAll('.table-inventario tbody tr');
  
  filas.forEach(fila => {
    const estatusFila = fila.getAttribute('data-estatus') || 'activo';
    const textoFila = fila.textContent.toLowerCase();
    
    const coincideEstatus = filtroEstatusActual === 'todos' || estatusFila === filtroEstatusActual;
    const coincideTexto = textoFila.includes(textoBusqueda);
    
    fila.style.display = (coincideEstatus && coincideTexto) ? '' : 'none';
  });
}

// ========================================
// ALTA DE EQUIPO GENERAL - CÓDIGO LIMPIO Y FUNCIONAL
// ========================================

// ========================================
// INICIALIZACIÓN DE ALTA GENERAL
// ========================================
 
document.addEventListener('DOMContentLoaded', function () {
    // Actualizar buscador para usar filtros unificados
    const buscador = document.getElementById('buscadorPiezas');
    if (buscador) {
        buscador.addEventListener('keyup', aplicarFiltros);
    }
    
    // Cargar todas las piezas al inicializar
    cargarTodasLasPiezasParaAlta();
    
    // Manejo del selector de sucursal
    const sucursalSelector = document.getElementById('sucursalDestinoGeneral');
    if (sucursalSelector) {
        sucursalSelector.addEventListener('change', function() {
            actualizarEstadoBotonAgregarAltaGeneral();
        });
    }

    // Manejo del selector de piezas para alta general
    const selectorPiezaAltaGeneral = document.getElementById('selectorPiezaAltaGeneral');
    const btnAgregarAltaGeneral = document.getElementById('btnAgregarPiezaAltaGeneral');
    const infoDivAltaGeneral = document.getElementById('infoPiezaSeleccionadaAltaGeneral');

    if (selectorPiezaAltaGeneral) {
        selectorPiezaAltaGeneral.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];

            if (this.value) {
                document.getElementById('nombrePiezaInfoAltaGeneral').textContent = option.dataset.nombre;
                document.getElementById('categoriaPiezaInfoAltaGeneral').textContent = option.dataset.categoria;
                infoDivAltaGeneral.style.display = 'block';
            } else {
                infoDivAltaGeneral.style.display = 'none';
            }
            
            actualizarEstadoBotonAgregarAltaGeneral();
        });
    }

    if (btnAgregarAltaGeneral) {
        btnAgregarAltaGeneral.addEventListener('click', function () {
            agregarEquipoAltaGeneral();
        });
    }

    // Limpiar modal cuando se cierre
    const modalAltaEquipoGeneral = document.getElementById('modalAltaEquipoGeneral');
    if (modalAltaEquipoGeneral) {
        modalAltaEquipoGeneral.addEventListener('hidden.bs.modal', function () {
            limpiarFormularioAltaGeneral();
        });
    }

    // Event listener para el formulario de alta general
    const formAltaEquipoGeneral = document.getElementById('formAltaEquipoGeneral');
    if (formAltaEquipoGeneral) {
        formAltaEquipoGeneral.addEventListener('submit', function (e) {
            e.preventDefault();
            procesarAltaEquipoGeneral();
        });
    }

    // ========================================
    // INICIALIZACIÓN DE BAJA GENERAL
    // ========================================
    
    // Manejo del selector de sucursal para bajas
    const sucursalSelectorBaja = document.getElementById('sucursalOrigenBajaGeneral');
    if (sucursalSelectorBaja) {
        sucursalSelectorBaja.addEventListener('change', function() {
            const sucursalId = this.value;
            if (sucursalId) {
                cargarPiezasDisponiblesParaBaja(sucursalId);
            } else {
                const selectorPieza = document.getElementById('selectorPiezaBajaGeneral');
                selectorPieza.innerHTML = '<option value="">Primero selecciona la sucursal...</option>';
                selectorPieza.disabled = true;
                actualizarEstadoBotonAgregarBajaGeneral();
            }
        });
    }

    // Manejo del selector de piezas para baja general
    const selectorPiezaBajaGeneral = document.getElementById('selectorPiezaBajaGeneral');
    const btnAgregarBajaGeneral = document.getElementById('btnAgregarPiezaBajaGeneral');
    const infoDivBajaGeneral = document.getElementById('infoPiezaSeleccionadaBajaGeneral');

    if (selectorPiezaBajaGeneral) {
        selectorPiezaBajaGeneral.addEventListener('change', function () {
            const option = this.options[this.selectedIndex];

            if (this.value) {
                document.getElementById('nombrePiezaInfoBajaGeneral').textContent = option.dataset.nombre;
                document.getElementById('categoriaPiezaInfoBajaGeneral').textContent = option.dataset.categoria;
                document.getElementById('disponiblesPiezaInfoBajaGeneral').textContent = option.dataset.disponibles;
                infoDivBajaGeneral.style.display = 'block';
            } else {
                infoDivBajaGeneral.style.display = 'none';
            }
            
            actualizarEstadoBotonAgregarBajaGeneral();
        });
    }

    if (btnAgregarBajaGeneral) {
        btnAgregarBajaGeneral.addEventListener('click', function () {
            agregarEquipoBajaGeneral();
        });
    }

    // Limpiar modal de baja cuando se cierre
    const modalBajaEquipoGeneral = document.getElementById('modalBajaEquipoGeneral');
    if (modalBajaEquipoGeneral) {
        modalBajaEquipoGeneral.addEventListener('hidden.bs.modal', function () {
            limpiarFormularioBajaGeneral();
        });
    }

    // Event listener para el formulario de baja general
    const formBajaEquipoGeneral = document.getElementById('formBajaEquipoGeneral');
    if (formBajaEquipoGeneral) {
        formBajaEquipoGeneral.addEventListener('submit', function (e) {
            e.preventDefault();
            procesarBajaEquipoGeneral();
        });
    }
});

// ========================================
// FUNCIONES DE CARGA DE DATOS
// ========================================

// Función para cargar todas las piezas activas para altas
function cargarTodasLasPiezasParaAlta() {
    fetch('/inventario/todas-piezas-activas')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const selector = document.getElementById('selectorPiezaAltaGeneral');
                if (selector) {
                    selector.innerHTML = '<option value="">Selecciona un tipo de equipo...</option>';
                    data.piezas.forEach(pieza => {
                        const option = document.createElement('option');
                        option.value = pieza.id_pieza;
                        option.textContent = `${pieza.nombre_pieza} - ${pieza.categoria || 'Sin categoría'}`;
                        option.dataset.nombre = pieza.nombre_pieza;
                        option.dataset.categoria = pieza.categoria || 'Sin categoría';
                        selector.appendChild(option);
                    });
                }
            }
        })
        .catch(error => {
            console.error('Error cargando piezas:', error);
        });
}

// ========================================
// FUNCIONES DE MANEJO DE PIEZAS
// ========================================

// Función para actualizar estado del botón agregar
function actualizarEstadoBotonAgregarAltaGeneral() {
    const sucursalSelector = document.getElementById('sucursalDestinoGeneral');
    const piezaSelector = document.getElementById('selectorPiezaAltaGeneral');
    const btnAgregar = document.getElementById('btnAgregarPiezaAltaGeneral');
    
    if (btnAgregar && sucursalSelector && piezaSelector) {
        btnAgregar.disabled = !(sucursalSelector.value && piezaSelector.value);
    }
}

// Función para agregar equipo a la lista
function agregarEquipoAltaGeneral() {
    const sucursalSelector = document.getElementById('sucursalDestinoGeneral');
    const piezaSelector = document.getElementById('selectorPiezaAltaGeneral');
    
    if (!sucursalSelector.value || !piezaSelector.value) {
        Swal.fire('Error', 'Selecciona la sucursal y la pieza', 'error');
        return;
    }

    const option = piezaSelector.options[piezaSelector.selectedIndex];
    const idPieza = piezaSelector.value;
    const nombrePieza = option.dataset.nombre;
    const categoria = option.dataset.categoria;

    // Verificar si ya está agregada
    const yaExiste = piezasAltaEquipoGeneral.find(p => p.id === idPieza);
    if (yaExiste) {
        Swal.fire('Error', 'Esta pieza ya está en la lista', 'error');
        return;
    }

    // Agregar pieza al array con cantidad por defecto 1
    piezasAltaEquipoGeneral.push({
        id: idPieza,
        nombre: nombrePieza,
        categoria: categoria,
        cantidad: 1
    });

    // Actualizar UI
    actualizarListaPiezasAltaGeneral();
    actualizarResumenAltaEquipoGeneral();

    // Limpiar selector
    piezaSelector.value = '';
    document.getElementById('infoPiezaSeleccionadaAltaGeneral').style.display = 'none';
    actualizarEstadoBotonAgregarAltaGeneral();
}

// ========================================
// FUNCIONES DE ACTUALIZACIÓN DE UI
// ========================================

// Actualizar lista de piezas para alta general
function actualizarListaPiezasAltaGeneral() {
    const lista = document.getElementById('listaPiezasAgregadasAltaGeneral');
    const tabla = document.getElementById('tablaPiezasAgregadasAltaGeneral');

    if (piezasAltaEquipoGeneral.length === 0) {
        lista.style.display = 'none';
        return;
    }

    lista.style.display = 'block';

    let html = '';
    piezasAltaEquipoGeneral.forEach((pieza, index) => {
        html += `
            <tr>
                <td><strong>${pieza.nombre}</strong></td>
                <td><span class="badge bg-secondary">${pieza.categoria}</span></td>
                <td>
                    <input type="number" class="form-control form-control-sm" 
                           value="${pieza.cantidad}" min="1" max="999"   
                           onchange="actualizarCantidadPiezaAltaGeneral(${index}, this.value)">
                </td>
                <td>
                    <button type="button" class="btn btn-danger btn-sm" 
                            onclick="eliminarPiezaAltaGeneral(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tabla.innerHTML = html;
}

// Actualizar cantidad de una pieza en alta general
function actualizarCantidadPiezaAltaGeneral(index, nuevaCantidad) {
    const cantidad = parseInt(nuevaCantidad);

    if (cantidad < 1 || cantidad > 999) {
        Swal.fire('Error', 'La cantidad debe estar entre 1 y 999', 'error');
        actualizarListaPiezasAltaGeneral(); // Reset
        return;
    }

    piezasAltaEquipoGeneral[index].cantidad = cantidad;
    actualizarResumenAltaEquipoGeneral();
}

// Eliminar pieza de la lista de alta general
function eliminarPiezaAltaGeneral(index) {
    piezasAltaEquipoGeneral.splice(index, 1);
    actualizarListaPiezasAltaGeneral();
    actualizarResumenAltaEquipoGeneral();
}

// Actualizar resumen de alta de equipo general
function actualizarResumenAltaEquipoGeneral() {
    const resumenDiv = document.getElementById('resumenAltaEquipoGeneral');
    const contenido = document.getElementById('resumenContenidoAltaGeneral');
    const btnConfirmar = document.getElementById('btnConfirmarAltaEquipoGeneral');

    if (piezasAltaEquipoGeneral.length === 0) {
        resumenDiv.style.display = 'none';
        if (btnConfirmar) btnConfirmar.disabled = true;
        return;
    }

    resumenDiv.style.display = 'block';
    if (btnConfirmar) btnConfirmar.disabled = false;

    const totalPiezas = piezasAltaEquipoGeneral.reduce((total, pieza) => total + pieza.cantidad, 0);

    let html = `
        <div class="row">
            <div class="col-md-6">
                <strong>Total de piezas diferentes:</strong> ${piezasAltaEquipoGeneral.length}
            </div>
            <div class="col-md-6">
                <strong>Cantidad total de equipos:</strong> ${totalPiezas}
            </div>
        </div>
        <hr>
        <strong>Detalle:</strong>
        <ul class="list-unstyled mb-0 mt-2">
    `;
    
    piezasAltaEquipoGeneral.forEach(pieza => {
        html += `<li><strong>${pieza.nombre}:</strong> ${pieza.cantidad} unidad${pieza.cantidad > 1 ? 'es' : ''} <span class="badge bg-secondary">${pieza.categoria}</span></li>`;
    });
    
    html += '</ul>';

    contenido.innerHTML = html;
}

// ========================================
// FUNCIÓN DE PROCESAMIENTO
// ========================================

// Procesar alta de equipo general
function procesarAltaEquipoGeneral() {
    if (piezasAltaEquipoGeneral.length === 0) {
        Swal.fire('Error', 'Agrega al menos una pieza', 'error');
        return;
    }

    const sucursalSelector = document.getElementById('sucursalDestinoGeneral');
    const observacionesTextarea = document.getElementById('observacionesAltaGeneral');
    
    if (!sucursalSelector.value) {
        Swal.fire('Error', 'Selecciona la sucursal de destino', 'error');
        return;
    }

    const sucursalId = sucursalSelector.value;
    const observaciones = observacionesTextarea.value || '';

    const piezasData = piezasAltaEquipoGeneral.map(pieza => ({
        id_pieza: pieza.id,
        cantidad: pieza.cantidad
    }));

    const data = {
        id_sucursal: sucursalId,
        piezas: piezasData,
        observaciones: observaciones,
        tipo_origen: 'inventario_general'
    };

    // Deshabilitar botón y mostrar loading
    const btnConfirmar = document.getElementById('btnConfirmarAltaEquipoGeneral');
    const originalText = btnConfirmar.innerHTML;
    btnConfirmar.disabled = true;
    btnConfirmar.innerHTML = '<i class="bi bi-spinner spinning"></i> Registrando equipos...';

    // Enviar con AJAX
    fetch('/inventario/alta-equipo', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
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
                const modal = bootstrap.Modal.getInstance(document.getElementById('modalAltaEquipoGeneral'));
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
}

// ========================================
// FUNCIÓN DE LIMPIEZA
// ========================================

// Limpiar formulario de alta general
function limpiarFormularioAltaGeneral() {
    // Limpiar arrays
    piezasAltaEquipoGeneral = [];
    
    // Resetear selectores
    const sucursalSelector = document.getElementById('sucursalDestinoGeneral');
    const piezaSelector = document.getElementById('selectorPiezaAltaGeneral');
    const observaciones = document.getElementById('observacionesAltaGeneral');
    
    if (sucursalSelector) sucursalSelector.value = '';
    if (piezaSelector) piezaSelector.value = '';
    if (observaciones) observaciones.value = '';
    
    // Ocultar elementos
    document.getElementById('infoPiezaSeleccionadaAltaGeneral').style.display = 'none';
    document.getElementById('listaPiezasAgregadasAltaGeneral').style.display = 'none';
    document.getElementById('resumenAltaEquipoGeneral').style.display = 'none';
    
    // Deshabilitar botones
    const btnAgregar = document.getElementById('btnAgregarPiezaAltaGeneral');
    const btnConfirmar = document.getElementById('btnConfirmarAltaEquipoGeneral');
    
    if (btnAgregar) btnAgregar.disabled = true;
    if (btnConfirmar) btnConfirmar.disabled = true;
}

// ========================================
// BAJA DE EQUIPO GENERAL - CÓDIGO LIMPIO Y FUNCIONAL
// ========================================

// Función para cargar piezas disponibles para baja
function cargarPiezasDisponiblesParaBaja(sucursalId) {
    fetch(`/inventario/piezas-sucursal/${sucursalId}`)
        .then(response => response.json())
        .then(data => {
            const selector = document.getElementById('selectorPiezaBajaGeneral');
            selector.innerHTML = '<option value="">Selecciona un tipo de equipo...</option>';
            
            if (data.success && data.piezas.length > 0) {
                data.piezas.forEach(pieza => {
                    if (pieza.disponibles > 0) {
                        selector.innerHTML += `
                            <option value="${pieza.id_pieza}" 
                                    data-nombre="${pieza.nombre_pieza}"
                                    data-categoria="${pieza.categoria || 'Sin categoría'}"
                                    data-disponibles="${pieza.disponibles}">
                                ${pieza.nombre_pieza} (${pieza.disponibles} disponibles)
                            </option>
                        `;
                    }
                });
                selector.disabled = false;
            } else {
                selector.innerHTML = '<option value="">No hay piezas disponibles en esta sucursal</option>';
                selector.disabled = true;
            }
            
            actualizarEstadoBotonAgregarBajaGeneral();
        })
        .catch(error => {
            console.error('Error cargando piezas para baja:', error);
            const selector = document.getElementById('selectorPiezaBajaGeneral');
            selector.innerHTML = '<option value="">Error al cargar piezas</option>';
            selector.disabled = true;
        });
}

// Función para actualizar estado del botón agregar baja
function actualizarEstadoBotonAgregarBajaGeneral() {
    const sucursalSelector = document.getElementById('sucursalOrigenBajaGeneral');
    const piezaSelector = document.getElementById('selectorPiezaBajaGeneral');
    const btnAgregar = document.getElementById('btnAgregarPiezaBajaGeneral');
    
    if (btnAgregar && sucursalSelector && piezaSelector) {
        btnAgregar.disabled = !(sucursalSelector.value && piezaSelector.value);
    }
}

// Función para agregar equipo a la lista de baja
function agregarEquipoBajaGeneral() {
    const sucursalSelector = document.getElementById('sucursalOrigenBajaGeneral');
    const piezaSelector = document.getElementById('selectorPiezaBajaGeneral');
    
    if (!sucursalSelector.value || !piezaSelector.value) {
        Swal.fire('Error', 'Selecciona la sucursal y la pieza', 'error');
        return;
    }

    const option = piezaSelector.options[piezaSelector.selectedIndex];
    const idPieza = piezaSelector.value;
    const nombrePieza = option.dataset.nombre;
    const categoria = option.dataset.categoria;
    const disponibles = parseInt(option.dataset.disponibles);

    // Verificar si ya está agregada
    const yaExiste = piezasBajaEquipoGeneral.find(p => p.id === idPieza);
    if (yaExiste) {
        Swal.fire('Error', 'Esta pieza ya está en la lista', 'error');
        return;
    }

    // Agregar pieza al array con cantidad por defecto 1
    piezasBajaEquipoGeneral.push({
        id: idPieza,
        nombre: nombrePieza,
        categoria: categoria,
        cantidad: 1,
        disponibles: disponibles
    });

    // Actualizar UI
    actualizarListaPiezasBajaGeneral();
    actualizarResumenBajaEquipoGeneral();

    // Limpiar selector
    piezaSelector.value = '';
    document.getElementById('infoPiezaSeleccionadaBajaGeneral').style.display = 'none';
    actualizarEstadoBotonAgregarBajaGeneral();
}

// Actualizar lista de piezas para baja general
function actualizarListaPiezasBajaGeneral() {
    const lista = document.getElementById('listaPiezasAgregadasBajaGeneral');
    const tabla = document.getElementById('tablaPiezasAgregadasBajaGeneral');

    if (piezasBajaEquipoGeneral.length === 0) {
        lista.style.display = 'none';
        return;
    }

    lista.style.display = 'block';

    let html = '';
    piezasBajaEquipoGeneral.forEach((pieza, index) => {
        html += `
            <tr>
                <td><strong>${pieza.nombre}</strong></td>
                <td><span class="badge bg-secondary">${pieza.categoria}</span></td>
                <td>
                    <input type="number" class="form-control form-control-sm" 
                           value="${pieza.cantidad}" min="1" max="${pieza.disponibles}"   
                           onchange="actualizarCantidadPiezaBajaGeneral(${index}, this.value)">
                    <small class="text-muted">Máx: ${pieza.disponibles}</small>
                </td>
                <td>
                    <button type="button" class="btn btn-danger btn-sm" 
                            onclick="eliminarPiezaBajaGeneral(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    tabla.innerHTML = html;
}

// Actualizar cantidad de una pieza en baja general
function actualizarCantidadPiezaBajaGeneral(index, nuevaCantidad) {
    const cantidad = parseInt(nuevaCantidad);
    const pieza = piezasBajaEquipoGeneral[index];

    if (cantidad < 1 || cantidad > pieza.disponibles) {
        Swal.fire('Error', `La cantidad debe estar entre 1 y ${pieza.disponibles}`, 'error');
        actualizarListaPiezasBajaGeneral(); // Reset
        return;
    }

    piezasBajaEquipoGeneral[index].cantidad = cantidad;
    actualizarResumenBajaEquipoGeneral();
}

// Eliminar pieza de la lista de baja general
function eliminarPiezaBajaGeneral(index) {
    piezasBajaEquipoGeneral.splice(index, 1);
    actualizarListaPiezasBajaGeneral();
    actualizarResumenBajaEquipoGeneral();
}

// Actualizar resumen de baja de equipo general
function actualizarResumenBajaEquipoGeneral() {
    const resumenDiv = document.getElementById('resumenBajaEquipoGeneral');
    const contenido = document.getElementById('resumenContenidoBajaGeneral');
    const btnConfirmar = document.getElementById('btnConfirmarBajaEquipoGeneral');

    if (piezasBajaEquipoGeneral.length === 0) {
        resumenDiv.style.display = 'none';
        if (btnConfirmar) btnConfirmar.disabled = true;
        return;
    }

    resumenDiv.style.display = 'block';
    if (btnConfirmar) btnConfirmar.disabled = false;

    const totalPiezas = piezasBajaEquipoGeneral.reduce((total, pieza) => total + pieza.cantidad, 0);

    let html = `
        <div class="row">
            <div class="col-md-6">
                <strong>Total de piezas diferentes:</strong> ${piezasBajaEquipoGeneral.length}
            </div>
            <div class="col-md-6">
                <strong>Cantidad total de equipos:</strong> ${totalPiezas}
            </div>
        </div>
        <hr>
        <strong>Detalle:</strong>
        <ul class="list-unstyled mb-0 mt-2">
    `;
    
    piezasBajaEquipoGeneral.forEach(pieza => {
        html += `<li><strong>${pieza.nombre}:</strong> ${pieza.cantidad} unidad${pieza.cantidad > 1 ? 'es' : ''} <span class="badge bg-secondary">${pieza.categoria}</span></li>`;
    });
    
    html += '</ul>';

    contenido.innerHTML = html;
}

// Procesar baja de equipo general
function procesarBajaEquipoGeneral() {
    if (piezasBajaEquipoGeneral.length === 0) {
        Swal.fire('Error', 'Agrega al menos una pieza', 'error');
        return;
    }

    const sucursalSelector = document.getElementById('sucursalOrigenBajaGeneral');
    const observacionesTextarea = document.getElementById('observacionesBajaGeneral');
    
    if (!sucursalSelector.value) {
        Swal.fire('Error', 'Selecciona la sucursal de origen', 'error');
        return;
    }

    if (!observacionesTextarea.value.trim()) {
        Swal.fire('Error', 'Especifica el motivo de la baja', 'error');
        return;
    }

    const sucursalId = sucursalSelector.value;
    const observaciones = observacionesTextarea.value.trim();

    const piezasData = piezasBajaEquipoGeneral.map(pieza => ({
        id_pieza: pieza.id,
        cantidad: pieza.cantidad
    }));

    const data = {
        id_sucursal: sucursalId,
        piezas: piezasData,
        observaciones: observaciones
    };

    // Deshabilitar botón y mostrar loading
    const btnConfirmar = document.getElementById('btnConfirmarBajaEquipoGeneral');
    const originalText = btnConfirmar.innerHTML;
    btnConfirmar.disabled = true;
    btnConfirmar.innerHTML = '<i class="bi bi-hourglass-split"></i> Procesando baja...';

    // Enviar con AJAX
    fetch('/inventario/baja-equipo-nuevo', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({
                title: '¡Baja registrada!',
                html: `¡Equipos dados de baja exitosamente!<br>Folio de nota de salida: <strong>#${data.folio_nota_salida}</strong>`,
                icon: 'success',
                showCancelButton: true,
                confirmButtonText: 'Descargar PDF',
                cancelButtonText: 'Cerrar',
                reverseButtons: true
            }).then((result) => {
                if (result.isConfirmed) {
                    window.open(`/inventario/pdf-baja-equipo/${data.folio_nota_salida}`, '_blank');
                }
                
                // Cerrar modal y recargar página
                const modal = bootstrap.Modal.getInstance(document.getElementById('modalBajaEquipoGeneral'));
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
}

// Limpiar formulario de baja general
function limpiarFormularioBajaGeneral() {
    // Limpiar arrays
    piezasBajaEquipoGeneral = [];
    
    // Resetear selectores
    const sucursalSelector = document.getElementById('sucursalOrigenBajaGeneral');
    const piezaSelector = document.getElementById('selectorPiezaBajaGeneral');
    const observaciones = document.getElementById('observacionesBajaGeneral');
    
    if (sucursalSelector) sucursalSelector.value = '';
    if (piezaSelector) {
        piezaSelector.innerHTML = '<option value="">Primero selecciona la sucursal...</option>';
        piezaSelector.disabled = true;
    }
    if (observaciones) observaciones.value = '';
    
    // Ocultar elementos
    document.getElementById('infoPiezaSeleccionadaBajaGeneral').style.display = 'none';
    document.getElementById('listaPiezasAgregadasBajaGeneral').style.display = 'none';
    document.getElementById('resumenBajaEquipoGeneral').style.display = 'none';
    
    // Deshabilitar botones
    const btnAgregar = document.getElementById('btnAgregarPiezaBajaGeneral');
    const btnConfirmar = document.getElementById('btnConfirmarBajaEquipoGeneral');
    
    if (btnAgregar) btnAgregar.disabled = true;
    if (btnConfirmar) btnConfirmar.disabled = true;
}

// ========================================
// FUNCIONES DE DESCONTINUACIÓN DE PIEZAS
// ========================================

// Función para verificar productos asociados y descontinuar pieza
function verificarYDescontinuarPieza(idPieza, nombrePieza) {
  // Primero verificar si hay productos asociados
  fetch(`/inventario/verificar-productos-asociados/${idPieza}`)
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        if (data.total > 0) {
          Swal.fire({
            title: '⚠️ Productos Asociados',
            html: `
              <div class="text-start">
                <p>La pieza <strong>"${nombrePieza}"</strong> tiene <strong>${data.total} producto(s) asociado(s)</strong>:</p>
                <ul class="text-start mb-3">
                  ${data.productos.map(p => `<li>${p.nombre_producto} - ${p.nombre_categoria}</li>`).join('')}
                </ul>
                <p><strong>¿Qué deseas hacer?</strong></p>
                <div class="alert alert-warning">
                  <small><i class="bi bi-info-circle"></i> Si descontinúas la pieza, estos productos ya no podrán usarla en su configuración.</small>
                </div>
              </div>
            `,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Descontinuar de todas formas',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#dc3545',
            cancelButtonColor: '#6c757d'
          }).then((result) => {
            if (result.isConfirmed) {
              descontinuarPieza(idPieza, nombrePieza);
            }
          });
        } else {
          descontinuarPieza(idPieza, nombrePieza);
        }
      } else {
        Swal.fire('Error', data.error, 'error');
      }
    })
    .catch(error => {
      console.error('Error:', error);
      Swal.fire('Error', 'Ocurrió un error al verificar los productos asociados', 'error');
    });
}

// Función para descontinuar pieza
function descontinuarPieza(idPieza, nombrePieza) {
  fetch(`/inventario/descontinuar-pieza/${idPieza}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        Swal.fire({
          title: '¡Pieza descontinuada!',
          text: data.message,
          icon: 'success',
          confirmButtonText: 'Entendido',
          confirmButtonColor: '#0d6efd'
        }).then(() => {
          window.location.reload();
        });
      } else {
        Swal.fire('Error', data.error, 'error');
      }
    })
    .catch(error => {
      console.error('Error:', error);
      Swal.fire('Error', 'Ocurrió un error al descontinuar la pieza', 'error');
    });
}

// Función para reactivar pieza
function reactivarPieza(idPieza, nombrePieza) {
  Swal.fire({
    title: '¿Reactivar pieza?',
    html: `¿Estás seguro que deseas reactivar la pieza <strong>"${nombrePieza}"</strong>?<br><br>
           <small class="text-muted">La pieza volverá a estar disponible para asociar a productos.</small>`,
    icon: 'question',
    showCancelButton: true,
    confirmButtonColor: '#28a745',
    cancelButtonColor: '#6c757d',
    confirmButtonText: 'Sí, reactivar',
    cancelButtonText: 'Cancelar'
  }).then((result) => {
    if (result.isConfirmed) {
      fetch(`/inventario/reactivar-pieza/${idPieza}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            Swal.fire({
              title: '¡Pieza reactivada!',
              text: data.message,
              icon: 'success',
              confirmButtonText: 'Entendido',
              confirmButtonColor: '#0d6efd'
            }).then(() => {
              window.location.reload();
            });
          } else {
            Swal.fire('Error', data.error, 'error');
          }
        })
        .catch(error => {
          console.error('Error:', error);
          Swal.fire('Error', 'Ocurrió un error al reactivar la pieza', 'error');
        });
    }
  });
}

// Función para eliminación definitiva
function eliminarPiezaDefinitivamente(idPieza, nombrePieza) {
  Swal.fire({
    title: '⚠️ ¡ELIMINACIÓN DEFINITIVA!',
    html: `
      <div class="text-start">
        <p>Estás a punto de <strong>eliminar definitivamente</strong> la pieza:</p>
        <div class="alert alert-danger">
          <strong>${nombrePieza}</strong>
        </div>
        <p><strong>⚠️ ADVERTENCIA:</strong></p>
        <ul class="text-start">
          <li>Esta acción <strong>NO se puede deshacer</strong></li>
          <li>La pieza se eliminará del sistema para siempre</li>
          <li>Solo es posible si no tiene inventario ni historial</li>
        </ul>
        <p>¿Estás <strong>completamente seguro</strong>?</p>
      </div>
    `,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#dc3545',
    cancelButtonColor: '#6c757d',
    confirmButtonText: 'SÍ, ELIMINAR DEFINITIVAMENTE',
    cancelButtonText: 'Cancelar',
    focusCancel: true
  }).then((result) => {
    if (result.isConfirmed) {
      // Segunda confirmación
      Swal.fire({
        title: '¿Estás 100% seguro?',
        text: 'Esta es tu última oportunidad para cancelar',
        icon: 'error',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#28a745',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'No, cancelar'
      }).then((segundaConfirmacion) => {
        if (segundaConfirmacion.isConfirmed) {
          ejecutarEliminacionDefinitiva(idPieza, nombrePieza);
        }
      });
    }
  });
}

function ejecutarEliminacionDefinitiva(idPieza, nombrePieza) {
  fetch(`/inventario/eliminar-pieza-definitivamente/${idPieza}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        Swal.fire({
          title: '¡Eliminada!',
          text: data.message,
          icon: 'success',
          confirmButtonText: 'Entendido',
          confirmButtonColor: '#0d6efd'
        }).then(() => {
          window.location.reload();
        });
      } else {
        Swal.fire('No se puede eliminar', data.error, 'warning');
      }
    })
    .catch(error => {
      console.error('Error:', error);
      Swal.fire('Error', 'Ocurrió un error al eliminar la pieza', 'error');
    });
}

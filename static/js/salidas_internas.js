document.addEventListener('DOMContentLoaded', function () {

    // Variables globales
    let productosSeleccionados = [];

    // ========================================
    // INICIALIZACIÓN
    // ========================================
    
    // Configurar fecha automática
    const fechaAutomatica = document.getElementById('fecha_automatica');
    if (fechaAutomatica) {
        fechaAutomatica.value = new Date().toLocaleString('es-MX');
    }

    // ========================================
    // MODAL DE NUEVA SALIDA INTERNA
    // ========================================

    const selectProducto = document.getElementById('producto_select_salida');
    const inputCantidad = document.getElementById('cantidad_producto_salida');
    const btnAgregar = document.getElementById('agregar_producto_salida');
    const tablaProductos = document.getElementById('tabla-productos-salida');
    const contenedorProductos = document.getElementById('productos-seleccionados');

    // Agregar producto a la lista
    if (btnAgregar) {
        btnAgregar.addEventListener('click', function () {
            const productoId = selectProducto.value;
            const productoOption = selectProducto.options[selectProducto.selectedIndex];
            const productoNombre = productoOption.text.split(' - ')[0]; // Solo el nombre, sin "Disponibles:"
            const disponibles = parseInt(productoOption.dataset.disponibles) || 0;
            const cantidad = parseInt(inputCantidad.value) || 1;

            if (!productoId) {
                Swal.fire('Error', 'Debe seleccionar un producto', 'error');
                return;
            }

            if (cantidad < 1) {
                Swal.fire('Error', 'La cantidad debe ser mayor a 0', 'error');
                return;
            }

            if (cantidad > disponibles) {
                Swal.fire('Error', `No hay suficiente inventario. Disponibles: ${disponibles}`, 'error');
                return;
            }

            // Verificar si ya está agregado
            const yaExiste = productosSeleccionados.find(p => p.id_pieza === productoId);
            if (yaExiste) {
                Swal.fire('Error', 'Este producto ya está en la lista', 'error');
                return;
            }

            // Agregar a la lista
            productosSeleccionados.push({
                id_pieza: productoId,
                nombre: productoNombre,
                cantidad: cantidad,
                disponibles: disponibles
            });

            actualizarTablaProductos();
            
            // Limpiar selección
            selectProducto.value = '';
            inputCantidad.value = '';
        });
    }

    // Actualizar tabla de productos seleccionados
    function actualizarTablaProductos() {
        const tbody = tablaProductos.querySelector('tbody');
        
        if (productosSeleccionados.length === 0) {
            contenedorProductos.style.display = 'none';
            return;
        }

        contenedorProductos.style.display = 'block';
        
        let html = '';
        productosSeleccionados.forEach((producto, index) => {
            html += `
                <tr>
                    <td>${producto.nombre}</td>
                    <td>
                        <input type="number" class="form-control form-control-sm" 
                               value="${producto.cantidad}" min="1" max="${producto.disponibles}"
                               onchange="actualizarCantidadProducto(${index}, this.value)"
                               style="width: 80px;">
                    </td>
                    <td>
                        <button type="button" class="btn btn-sm btn-danger" 
                                onclick="eliminarProducto(${index})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    }

    // Actualizar cantidad de producto
    window.actualizarCantidadProducto = function(index, nuevaCantidad) {
        const cantidad = parseInt(nuevaCantidad);
        const producto = productosSeleccionados[index];
        
        if (cantidad < 1 || cantidad > producto.disponibles) {
            Swal.fire('Error', `La cantidad debe estar entre 1 y ${producto.disponibles}`, 'error');
            actualizarTablaProductos(); // Revertir cambio
            return;
        }
        
        productosSeleccionados[index].cantidad = cantidad;
    };

    // Eliminar producto de la lista
    window.eliminarProducto = function(index) {
        productosSeleccionados.splice(index, 1);
        actualizarTablaProductos();
    };

    // Enviar formulario de nueva salida interna
    const formNuevaSalida = document.getElementById('form-nueva-salida-interna');
    if (formNuevaSalida) {
        formNuevaSalida.addEventListener('submit', function (e) {
            e.preventDefault();

            const responsable = document.getElementById('responsable_entrega').value.trim();
            const observaciones = document.getElementById('observaciones_salida').value.trim();

            if (!responsable) {
                Swal.fire('Error', 'Debe ingresar el nombre del responsable', 'error');
                return;
            }

            if (productosSeleccionados.length === 0) {
                Swal.fire('Error', 'Debe agregar al menos un producto', 'error');
                return;
            }

            const data = {
                sucursal_id: window.sucursalData.id_sucursal,
                responsable_entrega: responsable,
                observaciones: observaciones,
                productos: productosSeleccionados
            };

            Swal.fire({
                title: '¿Confirmar salida interna?',
                text: `Se registrará la salida de ${productosSeleccionados.length} tipo(s) de productos`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, crear salida',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    crearSalidaInterna(data);
                }
            });
        });
    }

    // Función para crear salida interna
    function crearSalidaInterna(data) {
        // Mostrar loading
        Swal.fire({
            title: 'Procesando...',
            text: 'Creando salida interna',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch('/salidas-internas/crear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                Swal.fire({
                    title: '¡Éxito!',
                    html: `${result.message}<br><strong>Folio de nota de salida: #${result.folio_nota_salida}</strong>`,
                    icon: 'success',
                    showCancelButton: true,
                    confirmButtonText: 'Descargar PDF',
                    cancelButtonText: 'Cerrar',
                    reverseButtons: true
                }).then((swalResult) => {
                    if (swalResult.isConfirmed && result.folio_nota_salida) {
                        // Abrir PDF en nueva ventana
                        const url = `/salidas-internas/pdf-salida/${result.folio_nota_salida}`;
                        window.open(url, '_blank');
                    }
                    // Cerrar modal y recargar página
                    document.getElementById('modalNuevaSalidaInterna').querySelector('[data-bs-dismiss="modal"]').click();
                    location.reload();
                });
            } else {
                Swal.fire('Error', result.error || 'Error al crear la salida interna', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire('Error', 'Error de conexión al crear la salida interna', 'error');
        });
    }

    // Limpiar modal cuando se cierre
    const modalNuevaSalida = document.getElementById('modalNuevaSalidaInterna');
    if (modalNuevaSalida) {
        modalNuevaSalida.addEventListener('hidden.bs.modal', function () {
            productosSeleccionados = [];
            document.getElementById('responsable_entrega').value = '';
            document.getElementById('observaciones_salida').value = '';
            document.getElementById('producto_select_salida').value = '';
            document.getElementById('cantidad_producto_salida').value = '';
            contenedorProductos.style.display = 'none';
        });
    }

    // ========================================
    // MODAL DE FINALIZAR SALIDA
    // ========================================

    // Abrir modal de finalizar salida
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-finalizar-salida');
        if (btn) {
            const salidaId = btn.dataset.salidaId;
            const folio = btn.dataset.folio;
            
            document.getElementById('salida_id_finalizar').value = salidaId;
            document.getElementById('folio_finalizar').textContent = folio;
            document.getElementById('observaciones_finalizacion').value = '';
            document.getElementById('tipo_regreso').checked = true;
            
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalFinalizarSalida'));
            modal.show();
        }
    });

    // Enviar formulario de finalizar salida
    const formFinalizarSalida = document.getElementById('form-finalizar-salida');
    if (formFinalizarSalida) {
        formFinalizarSalida.addEventListener('submit', function (e) {
            e.preventDefault();

            const salidaId = document.getElementById('salida_id_finalizar').value;
            const tipoFinalizacion = document.querySelector('input[name="tipo_finalizacion"]:checked').value;
            const observaciones = document.getElementById('observaciones_finalizacion').value.trim();

            const data = {
                tipo: tipoFinalizacion,
                observaciones: observaciones
            };

            const tipoTexto = tipoFinalizacion === 'regreso' ? 'con regreso de equipo' : 'sin regreso de equipo';

            Swal.fire({
                title: '¿Confirmar finalización?',
                text: `Se finalizará la salida ${tipoTexto}`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, finalizar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    finalizarSalida(salidaId, data);
                }
            });
        });
    }

    // Función para finalizar salida
    function finalizarSalida(salidaId, data) {
        // Mostrar loading
        Swal.fire({
            title: 'Procesando...',
            text: 'Finalizando salida interna',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch(`/salidas-internas/finalizar/${salidaId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                // Mostrar SweetAlert con opción de PDF solo si hay folio_nota_entrada (regreso)
                const tieneRegreso = result.folio_nota_entrada;
                
                if (tieneRegreso) {
                    Swal.fire({
                        title: '¡Éxito!',
                        html: `${result.message}<br><strong>Folio de nota de entrada: #${result.folio_nota_entrada}</strong>`,
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Descargar PDF',
                        cancelButtonText: 'Cerrar',
                        reverseButtons: true
                    }).then((swalResult) => {
                        if (swalResult.isConfirmed) {
                            // Abrir PDF en nueva ventana
                            const url = `/salidas-internas/pdf-entrada/${result.folio_nota_entrada}`;
                            window.open(url, '_blank');
                        }
                        // Cerrar modal y recargar página
                        document.getElementById('modalFinalizarSalida').querySelector('[data-bs-dismiss="modal"]').click();
                        location.reload();
                    });
                } else {
                    // Si no hay regreso, mostrar mensaje normal
                    Swal.fire({
                        title: '¡Éxito!',
                        text: result.message,
                        icon: 'success',
                        confirmButtonText: 'Aceptar'
                    }).then(() => {
                        // Cerrar modal y recargar página
                        document.getElementById('modalFinalizarSalida').querySelector('[data-bs-dismiss="modal"]').click();
                        location.reload();
                    });
                }
            } else {
                Swal.fire('Error', result.error || 'Error al finalizar la salida', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire('Error', 'Error de conexión al finalizar la salida', 'error');
        });
    }

    // ========================================
    // MODAL DE VER DETALLE
    // ========================================

    // Abrir modal de ver detalle
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-ver-detalle');
        if (btn) {
            const salidaId = btn.dataset.salidaId;
            cargarDetalleSalida(salidaId);
        }
    });

    // Función para cargar detalle de salida
    function cargarDetalleSalida(salidaId) {
        // Mostrar loading en modal
        const modalDetalle = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalDetalleSalida'));
        const contenido = document.getElementById('contenido-detalle-salida');
        
        contenido.innerHTML = '<div class="text-center"><div class="spinner-border"></div><br>Cargando...</div>';
        modalDetalle.show();

        fetch(`/salidas-internas/detalle/${salidaId}`)
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    mostrarDetalleSalida(result.salida, result.productos);
                } else {
                    contenido.innerHTML = '<div class="alert alert-danger">Error al cargar el detalle</div>';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                contenido.innerHTML = '<div class="alert alert-danger">Error de conexión</div>';
            });
    }

    // Función para mostrar detalle de salida
    function mostrarDetalleSalida(salida, productos) {
        const contenido = document.getElementById('contenido-detalle-salida');
        
        let estadoBadge = '';
        switch(salida.estado) {
            case 'activa':
                estadoBadge = '<span class="badge bg-warning text-dark">Activa</span>';
                break;
            case 'finalizada_regreso':
                estadoBadge = '<span class="badge bg-success">Finalizada - Con Regreso</span>';
                break;
            case 'finalizada_no_regreso':
                estadoBadge = '<span class="badge bg-danger">Finalizada - Sin Regreso</span>';
                break;
            default:
                estadoBadge = `<span class="badge bg-secondary">${salida.estado}</span>`;
        }

        let html = `
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="bi bi-info-circle"></i> Información General</h6>
                    <table class="table table-sm">
                        <tr><th>Folio:</th><td><strong>SUC${salida.id_sucursal}-${String(salida.folio_sucursal).padStart(4, '0')}</strong></td></tr>
                        <tr><th>Sucursal:</th><td>${salida.sucursal_nombre}</td></tr>
                        <tr><th>Fecha de Salida:</th><td>${new Date(salida.fecha_salida).toLocaleString('es-MX')}</td></tr>
                        <tr><th>Responsable:</th><td><strong>${salida.responsable_entrega}</strong></td></tr>
                        <tr><th>Estado:</th><td>${estadoBadge}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6><i class="bi bi-chat-text"></i> Observaciones</h6>
                    <div class="border rounded p-2 mb-3" style="min-height: 80px;">
                        ${salida.observaciones || '<small class="text-muted">Sin observaciones</small>'}
                    </div>
                    ${salida.observaciones_finalizacion ? `
                        <h6><i class="bi bi-check-circle"></i> Observaciones de Finalización</h6>
                        <div class="border rounded p-2" style="min-height: 60px;">
                            ${salida.observaciones_finalizacion}
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <hr>
            
            <h6><i class="bi bi-boxes"></i> Productos Entregados</h6>
            <div class="table-responsive">
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>Código</th>
                            <th>Producto</th>
                            <th>Cantidad</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        let totalCantidad = 0;
        productos.forEach(producto => {
            html += `
                <tr>
                    <td><small class="text-muted">${producto.codigo_pieza || 'N/A'}</small></td>
                    <td>${producto.nombre_pieza}</td>
                    <td><span class="badge bg-primary">${producto.cantidad}</span></td>
                </tr>
            `;
            totalCantidad += producto.cantidad;
        });

        html += `
                    </tbody>
                    <tfoot>
                        <tr class="table-secondary">
                            <th colspan="2">Total de equipos:</th>
                            <th><span class="badge bg-dark">${totalCantidad}</span></th>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;

        if (salida.fecha_finalizacion) {
            html += `
                <hr>
                <small class="text-muted">
                    <i class="bi bi-calendar-check"></i> 
                    Finalizada el: ${new Date(salida.fecha_finalizacion).toLocaleString('es-MX')}
                </small>
            `;
        }

        contenido.innerHTML = html;
    }

    // ========================================
    // GESTIÓN DE MODALES Y ACCESIBILIDAD
    // ========================================
    
    // Función para limpiar el estado de los modales al cargar la página
    function limpiarEstadoModales() {
        const modales = ['modalNuevaSalidaInterna', 'modalFinalizarSalida', 'modalDetalleSalida'];
        
        modales.forEach(modalId => {
            const modalElement = document.getElementById(modalId);
            if (modalElement) {
                // Asegurar que el modal esté cerrado y sin conflictos de aria-hidden
                modalElement.classList.remove('show');
                modalElement.style.display = 'none';
                modalElement.setAttribute('aria-hidden', 'true');
                modalElement.removeAttribute('aria-modal');
                modalElement.removeAttribute('role');
                
                // Limpiar backdrop si existe
                const backdrop = document.querySelector('.modal-backdrop');
                if (backdrop) {
                    backdrop.remove();
                }
            }
        });

        // Remover cualquier clase modal-open del body
        document.body.classList.remove('modal-open');
    }

    // Limpiar estado al cargar la página
    limpiarEstadoModales();

    // Event listeners para manejar el estado de los modales correctamente
    const modalNueva = document.getElementById('modalNuevaSalidaInterna');
    if (modalNueva) {
        modalNueva.addEventListener('show.bs.modal', function () {
            // Asegurar que la fecha automática se actualice
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            document.getElementById('fecha_automatica').value = `${year}-${month}-${day}T${hours}:${minutes}`;
        });

        modalNueva.addEventListener('hidden.bs.modal', function () {
            // Limpiar formulario
            document.getElementById('form-nueva-salida-interna').reset();
            productosSeleccionados = [];
            actualizarTablaProductos();
        });
    }

    const modalFinalizar = document.getElementById('modalFinalizarSalida');
    if (modalFinalizar) {
        modalFinalizar.addEventListener('hidden.bs.modal', function () {
            // Limpiar formulario
            document.getElementById('form-finalizar-salida').reset();
        });
    }

});

// ========================================
// FUNCIONES DE DESCARGA PDF
// ========================================

// Función para descargar PDF de salida interna
function descargarPDFSalida(folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de salida no disponible', 'error');
        return;
    }
    
    // Abrir PDF en nueva ventana
    const url = `/salidas-internas/pdf-salida/${folio}`;
    window.open(url, '_blank');
}

// Función para descargar PDF de entrada interna (cuando hay regreso)
function descargarPDFEntrada(folio) {
    if (!folio) {
        Swal.fire('Error', 'Folio de entrada no disponible', 'error');
        return;
    }
    
    // Abrir PDF en nueva ventana
    const url = `/salidas-internas/pdf-entrada/${folio}`;
    window.open(url, '_blank');
}

// ========================================
// MANEJO DE BOTONES PDF EN TABLA
// ========================================

// Event listener para botones PDF de entrada
document.body.addEventListener('click', function (e) {
    const btn = e.target.closest('.btn-pdf-entrada');
    if (btn) {
        const salidaId = btn.dataset.salidaId;
        obtenerFolioEntrada(salidaId);
    }
});

// Función para obtener folio de entrada desde el backend
function obtenerFolioEntrada(salidaId) {
    fetch(`/salidas-internas/folio-entrada/${salidaId}`)
        .then(response => response.json())
        .then(result => {
            if (result.success && result.folio_nota_entrada) {
                descargarPDFEntrada(result.folio_nota_entrada);
            } else {
                Swal.fire('Error', 'No se encontró el folio de entrada', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire('Error', 'Error al obtener el folio de entrada', 'error');
        });
}
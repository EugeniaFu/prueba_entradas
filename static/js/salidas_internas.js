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
    const mensajeProductosVacio = document.getElementById('productos-seleccionados-vacio');

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

            // Limpiar selección (usa jQuery para que select2 también se actualice visualmente)
            if (window.jQuery) $(selectProducto).val('').trigger('change');
            else selectProducto.value = '';
            inputCantidad.value = '';
        });
    }

    // Actualizar tabla de productos seleccionados
    function actualizarTablaProductos() {
        const tbody = tablaProductos.querySelector('tbody');

        if (productosSeleccionados.length === 0) {
            tbody.innerHTML = '';
            mensajeProductosVacio.style.display = 'block';
            return;
        }

        mensajeProductosVacio.style.display = 'none';

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
                title: '¿Confirmar Salida Interna?',
                text: `Se registrará la salida de ${productosSeleccionados.length} tipo(s) de productos`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#28a745',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, crear salida',
                cancelButtonText: 'Cancelar',
                reverseButtons: true
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
                    title: '¡Salida Interna Exitosa!',
                    html: `Salida registrada correctamente.<br>Folio de Salida: <strong>#${result.folio_nota_salida}</strong>`,
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
            if (window.jQuery) $('#producto_select_salida').val('').trigger('change');
            else document.getElementById('producto_select_salida').value = '';
            document.getElementById('cantidad_producto_salida').value = '';
            tablaProductos.querySelector('tbody').innerHTML = '';
            mensajeProductosVacio.style.display = 'block';
        });
    }

    // ========================================
    // MODAL DE FINALIZAR SALIDA
    // ========================================

    // Abrir modal de registrar entrada (regreso de equipo)
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-finalizar-salida');
        if (btn) {
            const salidaId = btn.dataset.salidaId;
            const folio = btn.dataset.folio;

            document.getElementById('salida_id_finalizar').value = salidaId;
            document.getElementById('folio_finalizar').textContent = folio;
            document.getElementById('observaciones_finalizacion').value = '';

            const tbody = document.querySelector('#tabla-piezas-finalizar tbody');
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Cargando...</td></tr>';

            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalFinalizarSalida'));
            modal.show();

            fetch(`/salidas-internas/pendientes/${salidaId}`)
                .then(resp => resp.json())
                .then(result => {
                    if (!result.success) {
                        tbody.innerHTML = `<tr><td colspan="4" class="text-danger text-center">${result.error}</td></tr>`;
                        return;
                    }
                    let html = '';
                    result.piezas.forEach(pieza => {
                        html += `
                            <tr data-id-pieza="${pieza.id_pieza}">
                                <td>${pieza.nombre_pieza}</td>
                                <td class="text-center">
                                    <span class="badge bg-secondary cantidad-pendiente-badge">${pieza.cantidad_pendiente}</span>
                                </td>
                                <td>
                                    <input type="number" class="form-control form-control-sm input-recibida"
                                           min="0" max="${pieza.cantidad_pendiente}" value="0" data-pendiente="${pieza.cantidad_pendiente}">
                                </td>
                                <td>
                                    <input type="number" class="form-control form-control-sm input-perdida"
                                           min="0" max="${pieza.cantidad_pendiente}" value="0" data-pendiente="${pieza.cantidad_pendiente}">
                                </td>
                            </tr>
                        `;
                    });
                    tbody.innerHTML = html;
                })
                .catch(() => {
                    tbody.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Error al cargar las piezas pendientes.</td></tr>';
                });
        }
    });

    // Validar que recibida + perdida no exceda lo pendiente de cada fila
    document.querySelector('#tabla-piezas-finalizar tbody')?.addEventListener('input', function (e) {
        if (!e.target.classList.contains('input-recibida') && !e.target.classList.contains('input-perdida')) return;
        const fila = e.target.closest('tr');
        const pendiente = parseInt(e.target.dataset.pendiente) || 0;
        const recibida = parseInt(fila.querySelector('.input-recibida').value) || 0;
        const perdida = parseInt(fila.querySelector('.input-perdida').value) || 0;
        if (recibida + perdida > pendiente) {
            Swal.fire('Error', `La suma de "regresan ahora" y "se dan de baja" no puede ser mayor a lo pendiente (${pendiente}).`, 'warning');
            e.target.value = 0;
        }
    });

    // Enviar formulario de registrar entrada
    const formFinalizarSalida = document.getElementById('form-finalizar-salida');
    if (formFinalizarSalida) {
        formFinalizarSalida.addEventListener('submit', function (e) {
            e.preventDefault();

            const salidaId = document.getElementById('salida_id_finalizar').value;
            const observaciones = document.getElementById('observaciones_finalizacion').value.trim();

            const piezas = [];
            document.querySelectorAll('#tabla-piezas-finalizar tbody tr').forEach(fila => {
                const idPieza = fila.dataset.idPieza;
                if (!idPieza) return;
                const cantidadRecibida = parseInt(fila.querySelector('.input-recibida').value) || 0;
                const cantidadPerdida = parseInt(fila.querySelector('.input-perdida').value) || 0;
                if (cantidadRecibida > 0 || cantidadPerdida > 0) {
                    piezas.push({ id_pieza: idPieza, cantidad_recibida: cantidadRecibida, cantidad_perdida: cantidadPerdida });
                }
            });

            if (piezas.length === 0) {
                Swal.fire('Error', 'Captura al menos una pieza que regrese o se dé de baja.', 'error');
                return;
            }

            Swal.fire({
                title: '¿Confirmar Entrada?',
                text: 'Se registrará esta entrada y se actualizará el inventario.',
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#28a745',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, registrar',
                cancelButtonText: 'Cancelar',
                reverseButtons: true
            }).then((result) => {
                if (result.isConfirmed) {
                    finalizarSalida(salidaId, { piezas, observaciones });
                }
            });
        });
    }

    // Función para registrar la entrada (regreso) de una salida interna
    function finalizarSalida(salidaId, data) {
        Swal.fire({
            title: 'Procesando...',
            text: 'Registrando entrada',
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
                Swal.fire({
                    title: '¡Salida Interna Finalizada!',
                    html: `Entrada registrada correctamente.<br>Folio de Entrada: <strong>#${result.folio_nota_entrada}</strong>`,
                    icon: 'success',
                    showCancelButton: true,
                    confirmButtonText: 'Descargar PDF',
                    cancelButtonText: 'Cerrar',
                    reverseButtons: true
                }).then((swalResult) => {
                    if (swalResult.isConfirmed) {
                        window.open(`/salidas-internas/pdf-entrada/${result.entrada_id}`, '_blank');
                    }
                    document.getElementById('modalFinalizarSalida').querySelector('[data-bs-dismiss="modal"]').click();
                    location.reload();
                });
            } else {
                Swal.fire('Error', result.error || 'Error al registrar la entrada', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire('Error', 'Error de conexión al registrar la entrada', 'error');
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
        const modalDetalle = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalDetalleSalida'));

        // Reset visual mientras carga
        ['detalle-salida-folio', 'detalle-salida-sucursal', 'detalle-salida-fecha', 'detalle-salida-responsable',
         'detalle-salida-total-salida', 'detalle-salida-total-recibido', 'detalle-salida-total-perdido',
         'detalle-salida-total-pendiente', 'detalle-salida-folio-header'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '...';
        });
        document.getElementById('detalle-salida-observaciones').textContent = 'Cargando...';
        document.getElementById('detalle-salida-productos-tabla').innerHTML = '<tr><td colspan="5" class="text-center text-muted">Cargando...</td></tr>';
        document.getElementById('detalle-salida-nota-salida-tabla').innerHTML = '<tr><td colspan="3" class="text-center text-muted">Cargando...</td></tr>';
        document.getElementById('detalle-salida-entradas-tabla').innerHTML = '<tr><td colspan="4" class="text-center text-muted">Cargando...</td></tr>';
        document.getElementById('detalle-salida-finalizacion-row').style.display = 'none';

        modalDetalle.show();

        fetch(`/salidas-internas/detalle/${salidaId}`)
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    mostrarDetalleSalida(result.salida, result.productos, result.entradas);
                } else {
                    document.getElementById('detalle-salida-observaciones').textContent = 'Error al cargar el detalle';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('detalle-salida-observaciones').textContent = 'Error de conexión';
            });
    }

    // Función para mostrar detalle de salida (llena los elementos fijos del modal,
    // igual que el modal de Detalle de Renta)
    function mostrarDetalleSalida(salida, productos, entradas) {
        const folioDisplay = `SUC${salida.id_sucursal}-${String(salida.folio_sucursal).padStart(4, '0')}`;

        document.getElementById('detalle-salida-folio-header').textContent = folioDisplay;
        document.getElementById('detalle-salida-folio').innerHTML = `<strong>${folioDisplay}</strong>`;
        document.getElementById('detalle-salida-sucursal').textContent = salida.sucursal_nombre;
        document.getElementById('detalle-salida-fecha').textContent = new Date(salida.fecha_salida).toLocaleString('es-MX');
        document.getElementById('detalle-salida-responsable').innerHTML = `<strong>${salida.responsable_entrega}</strong>`;
        document.getElementById('detalle-salida-observaciones').textContent = salida.observaciones || 'Sin observaciones';

        const estadoBadge = document.getElementById('detalle-salida-estado');
        const estadosInfo = {
            activa: ['bg-warning text-dark', 'Activa'],
            parcial: ['bg-info text-white', 'Parcial - Falta equipo'],
            finalizada: ['bg-success', 'Finalizada'],
            cancelada: ['bg-dark', 'Cancelada']
        };
        const [clase, texto] = estadosInfo[salida.estado] || ['bg-secondary', salida.estado];
        estadoBadge.className = `badge ${clase}`;
        estadoBadge.textContent = texto;

        // Totales acumulados
        let totalSalida = 0, totalRecibido = 0, totalPerdido = 0, totalPendiente = 0;
        productos.forEach(p => {
            totalSalida += p.cantidad_salida;
            totalRecibido += p.ya_recibido;
            totalPerdido += p.ya_perdido;
            totalPendiente += p.cantidad_pendiente;
        });
        document.getElementById('detalle-salida-total-salida').textContent = totalSalida;
        document.getElementById('detalle-salida-total-recibido').textContent = totalRecibido;
        document.getElementById('detalle-salida-total-perdido').textContent = totalPerdido;
        document.getElementById('detalle-salida-total-pendiente').textContent = totalPendiente;

        if (salida.fecha_finalizacion) {
            document.getElementById('detalle-salida-finalizacion-row').style.display = '';
            document.getElementById('detalle-salida-fecha-finalizacion').textContent = new Date(salida.fecha_finalizacion).toLocaleString('es-MX');
        }

        // Tabla de productos (salida vs. regresado)
        const tablaProductos = document.getElementById('detalle-salida-productos-tabla');
        if (!productos || productos.length === 0) {
            tablaProductos.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Sin productos</td></tr>';
        } else {
            tablaProductos.innerHTML = productos.map(p => `
                <tr>
                    <td>${p.nombre_pieza}</td>
                    <td><span class="badge bg-primary">${p.cantidad_salida}</span></td>
                    <td><span class="badge bg-success">${p.ya_recibido}</span></td>
                    <td><span class="badge bg-danger">${p.ya_perdido}</span></td>
                    <td><span class="badge ${p.cantidad_pendiente > 0 ? 'bg-warning text-dark' : 'bg-success'}">${p.cantidad_pendiente}</span></td>
                </tr>
            `).join('');
        }

        // Nota de salida (un solo registro, igual estructura que la tabla de notas de renta)
        document.getElementById('detalle-salida-nota-salida-tabla').innerHTML = `
            <tr>
                <td><strong>${folioDisplay}</strong></td>
                <td>${new Date(salida.fecha_salida).toLocaleString('es-MX')}</td>
                <td>
                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="descargarPDFSalida('${salida.folio_sucursal}')">
                        <i class="bi bi-file-earmark-pdf"></i>
                    </button>
                </td>
            </tr>
        `;

        // Historial de entradas (visitas registradas)
        const tablaEntradas = document.getElementById('detalle-salida-entradas-tabla');
        if (!entradas || entradas.length === 0) {
            tablaEntradas.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Aún no se ha registrado ninguna entrada</td></tr>';
        } else {
            tablaEntradas.innerHTML = entradas.map(entrada => `
                <tr>
                    <td><strong>#${entrada.folio}</strong></td>
                    <td>${new Date(entrada.fecha).toLocaleString('es-MX')}</td>
                    <td><small>${entrada.observaciones || '-'}</small></td>
                    <td>
                        <button type="button" class="btn btn-sm btn-outline-success" onclick="window.open('/salidas-internas/pdf-entrada/${entrada.id}', '_blank')">
                            <i class="bi bi-file-earmark-pdf"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        }
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

// Nota: el PDF de cada entrada (visita de regreso de equipo) se descarga directamente
// desde el modal de "Ver Detalle", ya que una misma salida interna puede tener varias.
document.addEventListener('DOMContentLoaded', function () {
    let productosAgregados = [];
    let trasladoAgregado = null;
    let productoCounter = 0;

    // Elementos del DOM
    const diasRentaInput = document.getElementById('dias_renta');
    const requiereTrasladoCheck = document.getElementById('requiere_traslado');
    const tipoTrasladoContainer = document.getElementById('tipo_traslado_container');
    const costoTrasladoContainer = document.getElementById('costo_traslado_container');
    const tipoTrasladoSelect = document.getElementById('tipo_traslado');
    const costoTrasladoInput = document.getElementById('costo_traslado');
    const agregarTrasladoBtn = document.getElementById('agregar_traslado');
    const productoSelect = document.getElementById('producto_select');
    const cantidadInput = document.getElementById('cantidad_input');
    const agregarProductoBtn = document.getElementById('agregar_producto_btn');
    const productosTableBody = document.getElementById('productos_tbody');
    const mensajeSinProductos = document.getElementById('mensaje_sin_productos');
    const btnCrearCotizacion = document.getElementById('btn_crear_cotizacion');
    const productosHiddenInputs = document.getElementById('productos_hidden_inputs');

    // Establecer valor inicial de días
    diasRentaInput.value = 1;

    // ===============================================
    // INICIALIZAR TOOLTIPS
    // ===============================================
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            trigger: 'hover focus',
            delay: { show: 300, hide: 100 },
            html: true,
            placement: 'auto'
        });
    });

    // ===============================================
    // BUSCADOR EN TIEMPO REAL
    // ===============================================
    const searchBox = document.querySelector('.search-cotizaciones-box');
    if (searchBox) {
        searchBox.addEventListener('keyup', function () {
            var filtro = this.value.toLowerCase();
            document.querySelectorAll('#tablaCotizaciones tbody tr').forEach(function (row) {
                var texto = row.innerText.toLowerCase();
                row.style.display = texto.includes(filtro) ? '' : 'none';
            });
            
            // Recalcular paginación después del filtro
            if (window.recalcularPaginacion) {
                window.recalcularPaginacion();
            }
        });
    }

    // Filtro por select (opcional para filtrado en tiempo real)
    const filtroSelect = document.querySelector('select[name="filtro"]');
    if (filtroSelect) {
        filtroSelect.addEventListener('change', function () {
            const filtroValue = this.value.toLowerCase();
            if (filtroValue === '') {
                // Mostrar todas las filas
                document.querySelectorAll('#tablaCotizaciones tbody tr').forEach(function (row) {
                    row.style.display = '';
                });
            } else {
                // Filtrar por estado
                document.querySelectorAll('#tablaCotizaciones tbody tr').forEach(function (row) {
                    const estadoCell = row.querySelector('td:nth-child(8)'); // Columna de estado
                    if (estadoCell) {
                        const estadoTexto = estadoCell.innerText.toLowerCase();
                        row.style.display = estadoTexto.includes(filtroValue) ? '' : 'none';
                    }
                });
            }
            
            // Recalcular paginación después del filtro
            if (window.recalcularPaginacion) {
                window.recalcularPaginacion();
            }
        });
    }

    // ===============================================
    // LÓGICA DEL MODAL DE NUEVA COTIZACIÓN
    // ===============================================

    // Mostrar/ocultar campos de traslado
    requiereTrasladoCheck.addEventListener('change', function () {
        if (this.checked) {
            tipoTrasladoContainer.style.display = 'block';
            costoTrasladoContainer.style.display = 'block';
        } else {
            tipoTrasladoContainer.style.display = 'none';
            costoTrasladoContainer.style.display = 'none';
            costoTrasladoInput.value = '';
            // Eliminar traslado si existe
            if (trasladoAgregado) {
                eliminarTraslado();
            }
        }
        validarFormularioTraslado();
    });

    // Validar formulario de traslado
    function validarFormularioTraslado() {
        const valido = requiereTrasladoCheck.checked &&
            tipoTrasladoSelect.value &&
            costoTrasladoInput.value &&
            parseFloat(costoTrasladoInput.value) > 0 &&
            !trasladoAgregado;

        agregarTrasladoBtn.disabled = !valido;
    }

    // Listeners para validar traslado
    tipoTrasladoSelect.addEventListener('change', validarFormularioTraslado);
    costoTrasladoInput.addEventListener('input', validarFormularioTraslado);

    // Agregar traslado a la tabla
    agregarTrasladoBtn.addEventListener('click', function () {
        const tipoTraslado = tipoTrasladoSelect.value;
        const costoTraslado = parseFloat(costoTrasladoInput.value);

        const conceptoTraslado = `TRASLADO ${tipoTraslado.toUpperCase()}`;

        // Crear objeto de traslado
        trasladoAgregado = {
            tipo: 'traslado',
            concepto: conceptoTraslado,
            tipo_traslado: tipoTraslado,
            costo: costoTraslado
        };

        // Agregar fila a la tabla (solo concepto y precio para traslado)
        const fila = document.createElement('tr');
        fila.setAttribute('data-tipo', 'traslado');
        fila.innerHTML = `
            <td><strong>${conceptoTraslado}</strong></td>
            <td colspan="3" class="text-center text-muted">-</td>
            <td>$${costoTraslado.toFixed(2)}</td>
            <td>
                <button type="button" class="btn btn-danger btn-sm" onclick="eliminarTraslado()">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        `;
        productosTableBody.appendChild(fila);

        // Deshabilitar el botón
        agregarTrasladoBtn.disabled = true;

        // Ocultar mensaje sin productos
        mensajeSinProductos.style.display = 'none';

        // Recalcular totales
        calcularTotales();
        actualizarHiddenInputs();
        validarFormularioCompleto();
    });

    // Eliminar traslado
    window.eliminarTraslado = function () {
        // Remover de la tabla
        const fila = document.querySelector('tr[data-tipo="traslado"]');
        if (fila) {
            fila.remove();
        }

        // Limpiar objeto
        trasladoAgregado = null;

        // Mostrar mensaje si no hay productos
        if (productosAgregados.length === 0) {
            mensajeSinProductos.style.display = 'block';
        }

        // Habilitar botón de agregar traslado
        validarFormularioTraslado();

        // Recalcular totales
        calcularTotales();
        actualizarHiddenInputs();
        validarFormularioCompleto();
    };

    // Cuando cambie el producto seleccionado
    productoSelect.addEventListener('change', function () {
        const productoId = this.value;
        const diasRenta = parseInt(diasRentaInput.value) || 1;

        // El precio se obtendrá automáticamente al agregar el producto
        validarFormularioProducto();
    });

    // Cuando cambien los días de renta
    diasRentaInput.addEventListener('change', function () {
        const diasRenta = parseInt(this.value) || 1;

        // Actualizar precios de productos existentes
        productosAgregados.forEach(producto => {
            if (producto.tipo === 'producto') {
                fetch(`/cotizaciones/precios/${producto.producto_id}/${diasRenta}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.precio) {
                            producto.precio_unitario = data.precio;
                            producto.dias = diasRenta;
                            // Recalcular subtotal con la nueva fórmula
                            producto.subtotal = producto.cantidad * producto.precio_unitario * diasRenta;

                            // Actualizar en la tabla
                            const fila = document.querySelector(`tr[data-producto-id="${producto.producto_id}"]`);
                            if (fila) {
                                fila.querySelector('.dias').textContent = diasRenta;
                                fila.querySelector('.precio-unitario').textContent = `$${producto.precio_unitario.toFixed(2)}`;
                                fila.querySelector('.subtotal').textContent = `$${producto.subtotal.toFixed(2)}`;
                            }
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
        });

        // Recalcular precio del producto seleccionado si hay uno seleccionado
        if (productoSelect.value) {
            // Se validará al agregar el producto
        }

        // Recalcular totales después de un pequeño delay
        setTimeout(() => {
            calcularTotales();
            actualizarHiddenInputs();
        }, 100);
    });

    // Cuando cambie la cantidad
    cantidadInput.addEventListener('input', function () {
        validarFormularioProducto();
    });

    // Validar formulario de producto
    function validarFormularioProducto() {
        const valido = productoSelect.value &&
            cantidadInput.value &&
            parseFloat(cantidadInput.value) > 0;

        agregarProductoBtn.disabled = !valido;
    }

    // Agregar producto a la tabla
    agregarProductoBtn.addEventListener('click', function () {
        const productoId = productoSelect.value;
        const productoNombre = productoSelect.options[productoSelect.selectedIndex].text;
        const cantidad = parseFloat(cantidadInput.value);
        const diasRenta = parseInt(diasRentaInput.value) || 1;

        // Obtener precio base del servidor
        fetch(`/cotizaciones/precios/${productoId}/${diasRenta}`)
            .then(response => response.json())
            .then(data => {
                if (data.precio) {
                    const precioBase = data.precio;

                    // Detectar sucursal Escárcega (ID 4) y permisos
                    const sucursalSelect = document.getElementById('id_sucursal');
                    const sucursalId = sucursalSelect ? sucursalSelect.value : null;
                    const esEscarcega = (sucursalId === '4');
                    const puedeAjustar = window.puedeAjustarPrecios || false;

                    let ajusteTipoDefault, ajusteValorDefault, ajusteValorDisabled, selectDisabled, precioFinal;
                    if (esEscarcega) {
                        ajusteTipoDefault = 'porcentaje';
                        ajusteValorDefault = '10';
                        ajusteValorDisabled = 'disabled';
                        selectDisabled = 'disabled';
                        precioFinal = precioBase * 1.10; // SIEMPRE 10% de aumento
                    } else {
                        if (puedeAjustar) {
                            ajusteTipoDefault = 'ninguno';
                            ajusteValorDefault = '0';
                            ajusteValorDisabled = '';
                            selectDisabled = '';
                        } else {
                            ajusteTipoDefault = 'ninguno';
                            ajusteValorDefault = '0';
                            ajusteValorDisabled = 'disabled';
                            selectDisabled = 'disabled';
                        }
                        // Calcular precio final con ajuste
                        precioFinal = precioBase;
                        if (ajusteTipoDefault === 'porcentaje' && ajusteValorDefault !== '0') {
                            precioFinal = precioBase * (1 + parseFloat(ajusteValorDefault) / 100);
                        } else if (ajusteTipoDefault === 'fijo' && ajusteValorDefault !== '0') {
                            precioFinal = precioBase + parseFloat(ajusteValorDefault);
                        }
                    }

                    const subtotal = cantidad * precioFinal * diasRenta;

                    // Verificar si el producto ya existe
                    const productoExistente = productosAgregados.find(p => p.producto_id === productoId);

                    if (productoExistente) {
                        // Actualizar cantidad y subtotal
                        productoExistente.cantidad += cantidad;
                        productoExistente.subtotal = productoExistente.cantidad * productoExistente.precio_final * diasRenta;
                        // Actualizar en la tabla
                        const fila = document.querySelector(`tr[data-producto-id="${productoId}"]`);
                        fila.querySelector('.cantidad').textContent = productoExistente.cantidad;
                        fila.querySelector('.subtotal').textContent = `$${productoExistente.subtotal.toFixed(2)}`;
                    } else {
                        // Agregar nuevo producto
                        const producto = {
                            tipo: 'producto',
                            producto_id: productoId,
                            nombre: productoNombre,
                            cantidad: cantidad,
                            precio_base: precioBase,
                            ajuste_tipo: ajusteTipoDefault,
                            ajuste_valor: parseFloat(ajusteValorDefault),
                            precio_final: precioFinal,
                            subtotal: subtotal,
                            dias: diasRenta,
                            index: productoCounter++
                        };
                        productosAgregados.push(producto);

                        // Agregar fila a la tabla
                        const fila = document.createElement('tr');
                        fila.setAttribute('data-producto-id', productoId);
                        fila.innerHTML = `
                            <td>${productoNombre}</td>
                            <td><input type="number" class="form-control form-control-sm cantidad-editable" min="1" value="${cantidad}" style="width: 60px;"></td>
                            <td class="dias">${diasRenta}</td>
                            <td class="precio-base">$${precioBase.toFixed(2)}</td>
                            <td>
                                <select class="ajuste-tipo form-select form-select-sm" style="width: 60px; display:inline-block;" ${selectDisabled}>
                                    <option value="ninguno" ${ajusteTipoDefault==='ninguno'?'selected':''}>S/A</option>
                                    <option value="porcentaje" ${ajusteTipoDefault==='porcentaje'?'selected':''}>%</option>
                                    <option value="fijo" ${ajusteTipoDefault==='fijo'?'selected':''}>$</option>
                                </select>
                            </td>
                            <td>
                                <input type="number" class="ajuste-valor form-control form-control-sm" style="width: 60px; display:inline-block;" value="${ajusteValorDefault}" ${ajusteValorDisabled}>
                            </td>
                            <td class="precio-final">$${precioFinal.toFixed(2)}</td>
                            <td class="subtotal">$${subtotal.toFixed(2)}</td>
                            <td>
                                <button type="button" class="btn btn-danger btn-sm" onclick="eliminarProducto('${productoId}')">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </td>
                        `;
                        productosTableBody.appendChild(fila);

                        // Listener para cantidad editable
                        const cantidadEditable = fila.querySelector('.cantidad-editable');
                        cantidadEditable.addEventListener('input', function() {
                            const nuevaCantidad = parseFloat(this.value) || 1;
                            producto.cantidad = nuevaCantidad;
                            producto.subtotal = nuevaCantidad * producto.precio_final * producto.dias;
                            fila.querySelector('.subtotal').textContent = `$${producto.subtotal.toFixed(2)}`;
                            calcularTotales();
                            actualizarHiddenInputs();
                        });

                        // Listeners para recalcular precio final y subtotal al cambiar ajuste
                        const selectAjuste = fila.querySelector('.ajuste-tipo');
                        const inputAjuste = fila.querySelector('.ajuste-valor');
                        selectAjuste.addEventListener('change', function() {
                            if (this.value === 'ninguno') {
                                inputAjuste.value = 0;
                                inputAjuste.disabled = true;
                            } else {
                                inputAjuste.disabled = false;
                            }
                            recalcularFilaConAjuste(fila, producto);
                        });
                        inputAjuste.addEventListener('input', function() {
                            recalcularFilaConAjuste(fila, producto);
                        });
                    }

                    // Limpiar formulario
                    productoSelect.value = '';
                    cantidadInput.value = '';
                    agregarProductoBtn.disabled = true;

                    // Ocultar mensaje sin productos
                    mensajeSinProductos.style.display = 'none';

                    // Recalcular totales
                    calcularTotales();
                    actualizarHiddenInputs();
                    validarFormularioCompleto();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error al obtener el precio del producto');
            });
    });

    // Eliminar producto
    window.eliminarProducto = function (productoId) {
        // Remover del array
        productosAgregados = productosAgregados.filter(p => p.producto_id !== productoId);

        // Remover de la tabla
        const fila = document.querySelector(`tr[data-producto-id="${productoId}"]`);
        fila.remove();

        // Mostrar mensaje si no hay productos ni traslado
        if (productosAgregados.length === 0 && !trasladoAgregado) {
            mensajeSinProductos.style.display = 'block';
        }

        // Recalcular totales
        calcularTotales();
        actualizarHiddenInputs();
        validarFormularioCompleto();
    };

    // Calcular totales
    function calcularTotales() {
        let subtotalTotal = 0;
        // Sumar productos
        productosAgregados.forEach(producto => {
            subtotalTotal += producto.subtotal;
        });
        // Sumar traslado
        if (trasladoAgregado) {
            subtotalTotal += trasladoAgregado.costo;
        }
        const iva = subtotalTotal * 0.16;
        const total = subtotalTotal + iva;
        // Actualizar displays
        document.getElementById('subtotal-display').textContent = `$${subtotalTotal.toFixed(2)}`;
        document.getElementById('iva-display').textContent = `$${iva.toFixed(2)}`;
        document.getElementById('total-display').textContent = `$${total.toFixed(2)}`;
    }

    // Recalcular fila con ajuste
    function recalcularFilaConAjuste(fila, producto) {
        const cantidad = producto.cantidad;
        const dias = producto.dias;
        const precioBase = producto.precio_base;
        const tipoAjuste = fila.querySelector('.ajuste-tipo').value;
        const valorAjuste = parseFloat(fila.querySelector('.ajuste-valor').value) || 0;
        let precioFinal = precioBase;
        if (tipoAjuste === 'porcentaje') {
            precioFinal = precioBase * (1 + valorAjuste / 100);
        } else if (tipoAjuste === 'fijo') {
            precioFinal = precioBase + valorAjuste;
        }
        if (precioFinal < 0) precioFinal = 0;
        producto.ajuste_tipo = tipoAjuste;
        producto.ajuste_valor = valorAjuste;
        producto.precio_final = precioFinal;
        producto.subtotal = cantidad * dias * precioFinal;
        fila.querySelector('.precio-final').textContent = `$${precioFinal.toFixed(2)}`;
        fila.querySelector('.subtotal').textContent = `$${producto.subtotal.toFixed(2)}`;
        calcularTotales();
        actualizarHiddenInputs();
    }

    // Actualizar inputs ocultos
    function actualizarHiddenInputs() {
        productosHiddenInputs.innerHTML = '';
        // Agregar productos
        productosAgregados.forEach((producto, index) => {
            productosHiddenInputs.innerHTML += `
                <input type="hidden" name="productos[${index}][producto_id]" value="${producto.producto_id}">
                <input type="hidden" name="productos[${index}][cantidad]" value="${producto.cantidad}">
                <input type="hidden" name="productos[${index}][precio_base]" value="${producto.precio_base}">
                <input type="hidden" name="productos[${index}][ajuste_tipo]" value="${producto.ajuste_tipo}">
                <input type="hidden" name="productos[${index}][ajuste_valor]" value="${producto.ajuste_valor}">
                <input type="hidden" name="productos[${index}][precio_final]" value="${producto.precio_final}">
                <input type="hidden" name="productos[${index}][subtotal]" value="${producto.subtotal}">
            `;
        });
    }

    // Validar formulario completo
    function validarFormularioCompleto() {
        const valido = productosAgregados.length > 0 || trasladoAgregado;
        btnCrearCotizacion.disabled = !valido;
    }

    // Manejar el envío del formulario de nueva cotización
    document.getElementById('form-nueva-cotizacion').addEventListener('submit', function (e) {
        e.preventDefault(); // Prevenir el envío normal del formulario

        const form = e.target;
        const btnCrear = document.getElementById('btn_crear_cotizacion');

        // Deshabilitar botón y mostrar loading
        btnCrear.disabled = true;
        btnCrear.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creando cotización...';

        // Enviar datos via fetch pero esperando JSON con la URL
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(response => response.json())
            .then(data => {
                console.log('Respuesta del servidor:', data); // Para debug
                
                if (data.success) {
                    // Cerrar modal
                    bootstrap.Modal.getInstance(document.getElementById('modalNuevaCotizacion')).hide();

                    // Mostrar SweetAlert con opción de ver PDF
                    Swal.fire({
                        title: '¡Cotización Exitosa!',
                        html: `Cotización creada correctamente.<br>Folio: <strong>#${data.numero_cotizacion}</strong>`,
                        icon: 'success',
                        showCancelButton: true,
                        confirmButtonText: 'Descargar PDF',
                        cancelButtonText: 'Cerrar',
                        reverseButtons: true,
                        allowOutsideClick: false,
                        allowEscapeKey: false
                    }).then((result) => {
                        if (result.isConfirmed) {
                            // Abrir PDF en nueva pestaña usando la URL del servidor
                            console.log('PDF URL:', data.pdf_url); // Para debug
                            window.open(data.pdf_url, '_blank');
                        }
                        
                        // Recargar la página solo después de que el usuario tome una decisión
                        location.reload();
                    });
                } else {
                    Swal.fire('Error', data.error || 'Error al crear cotización', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire('Error', 'Hubo un error al crear la cotización', 'error');
            })
            .finally(() => {
                // Restaurar botón
                btnCrear.disabled = false;
                btnCrear.innerHTML = 'Crear Cotización';
            });
    });



});

// ===============================================
// FUNCIONES GLOBALES PARA CAMBIAR ESTADOS
// ===============================================

// Función para cambiar estado de cotización
function cambiarEstado(cotizacionId, nuevoEstado) {
    fetch(`/cotizaciones/${cotizacionId}/cambiar-estado`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            estado: nuevoEstado,
            comentarios: `Estado cambiado a ${nuevoEstado}`
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload(); // Recargar la página para ver los cambios
            } else {
                alert('Error al cambiar el estado: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error al cambiar el estado');
        });
}

// ===============================================
// Función para convertir cotización a renta
// ===============================================

// Función para convertir cotización a renta (VERSIÓN SIMPLE)
function convertirARenta(cotizacionId) {
    Swal.fire({
        title: '¿Convertir a renta?',
        text: 'Esta acción marcará la cotización como convertida a renta para fines estadísticos.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#28a745',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, convertir',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/cotizaciones/${cotizacionId}/convertir-renta`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    estado: 'renta',
                    comentarios: 'Cotización convertida a renta'
                })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            title: '¡Convertida!',
                            text: 'La cotización ha sido marcada como renta exitosamente.',
                            icon: 'success',
                            confirmButtonText: 'Entendido'
                        }).then(() => {
                            location.reload();
                        });
                    } else {
                        Swal.fire('Error', data.error || 'Error al convertir a renta', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    Swal.fire('Error', 'Hubo un error al convertir a renta', 'error');
                });
        }
    });
}




// ===============================================
//  FUNCIÓN ELIMINAR COTIZACIONES
// ===============================================


// Función para eliminar cotización
function eliminarCotizacion(cotizacionId) {
    Swal.fire({
        title: '¿Eliminar cotización?',
        text: 'Esta acción no se puede deshacer.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/cotizaciones/${cotizacionId}/eliminar`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            title: '¡Cotización Eliminada!',
                            text: 'La cotización ha sido eliminada exitosamente.',
                            icon: 'success',
                            confirmButtonText: 'Entendido'
                        }).then(() => {
                            location.reload();
                        });
                    } else {
                        Swal.fire('Error', data.error || 'Error al eliminar la cotización', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    Swal.fire('Error', 'Hubo un error al eliminar la cotización', 'error');
                });
        }
    });
}
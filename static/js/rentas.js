document.addEventListener('DOMContentLoaded', function () {

    // Mostrar/ocultar fecha programada
    const chkProgramada = document.getElementById('renta_programada');
    const grupoProgramada = document.getElementById('fecha_programada_group');
    if (chkProgramada && grupoProgramada) {
        chkProgramada.addEventListener('change', function () {
            grupoProgramada.style.display = this.checked ? '' : 'none';
        });
    }

    // Mostrar/ocultar costo traslado
    const traslado = document.getElementById('traslado');
    const grupoTraslado = document.getElementById('costo_traslado_group');
    if (traslado && grupoTraslado) {
        traslado.addEventListener('change', function () {
            grupoTraslado.style.display = (this.value !== 'ninguno') ? '' : 'none';
        });
    }

    // Cancelar renta: abrir modal y enviar solicitud SOLO si el modal existe
    const modalCancelarElem = document.getElementById('modalCancelarRenta');
    if (modalCancelarElem) {
        let rentaIdCancelar = null;
        const modalCancelar = new bootstrap.Modal(modalCancelarElem);
        document.body.addEventListener('click', function (e) {
            const btn = e.target.closest('.btn-cancelar-renta');
            if (btn) {
                rentaIdCancelar = btn.getAttribute('data-renta-id');
                document.getElementById('renta-id-cancelar').value = rentaIdCancelar;
                document.getElementById('motivo-cancelacion').value = '';
                document.getElementById('monto-reembolso').value = '';
                modalCancelar.show();
            }
        });

        document.getElementById('form-cancelar-renta').addEventListener('submit', function (e) {
            e.preventDefault();
            const motivo = document.getElementById('motivo-cancelacion').value.trim();
            const monto = document.getElementById('monto-reembolso').value;
            if (!motivo || monto === '') {
                Swal.fire('Error', 'Debes ingresar el motivo y el monto de reembolso.', 'warning');
                return;
            }
            const rentaId = document.getElementById('renta-id-cancelar').value;
            fetch(`/rentas/cancelar/${rentaId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `motivo_cancelacion=${encodeURIComponent(motivo)}&monto_reembolso=${encodeURIComponent(monto)}`
            })
            .then(resp => resp.json())
            .then(data => {
                if (data.status === 'ok') {
                    Swal.fire('Cancelada', data.mensaje, 'success').then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Error', data.mensaje || 'No se pudo cancelar la renta.', 'error');
                }
            })
            .catch(() => {
                Swal.fire('Error', 'Error inesperado al cancelar.', 'error');
            });
        });
    }

    // Calcular días de renta
    function calcularDiasRenta() {
        const fechaInicio = document.getElementById('fecha_salida').value;
        const fechaFin = document.getElementById('fecha_entrada').value;
        if (!fechaFin) return null; // Sin fecha fin, días indefinidos
        let dias = 1;
        if (fechaInicio && fechaFin) {
            const inicio = new Date(fechaInicio);
            const fin = new Date(fechaFin);
            dias = Math.floor((fin - inicio) / (1000 * 60 * 60 * 24)) + 1;
            if (dias < 1) dias = 1;
        }
        return dias;
    }

    // Obtener precio correcto según días
    function obtenerPrecioProducto(productoId, dias) {
        const precios = window.preciosProductos ? window.preciosProductos[String(productoId)] : null;
        if (!precios) return 0;
        if (precios.precio_unico === 1) {
            return precios.precio_dia; // Siempre usa precio_dia, sin importar los días
        }
        if (dias <= 2) return precios.precio_dia;                      // 1-2 días
        if (dias >= 3 && dias <= 14) return precios.precio_14_dias;    // 3-14 días
        if (dias >= 15 && dias <= 29) return precios.precio_29_dias;   // 15-29 días
        if (dias >= 30) return precios.precio_30_dias;                 // 30+ días
        return precios.precio_dia;
    }

    // Actualizar días y precios en la tabla de productos
    function actualizarDiasYPrecios() {
        const dias = calcularDiasRenta();
        document.querySelectorAll('#tabla-productos .dias').forEach(input => {
            if (dias === null) {
                input.value = '';
                input.placeholder = 'Indefinido';
            } else {
                input.value = dias;
                input.placeholder = '';
            }
        });
        document.querySelectorAll('#tabla-productos tr').forEach(fila => {
            const productoIdInput = fila.querySelector('input[name="producto_id[]"]');
            const costoInput = fila.querySelector('.costo');
            const cantidadInput = fila.querySelector('.cantidad');
            const subtotalInput = fila.querySelector('.subtotal');
            if (productoIdInput && costoInput && cantidadInput && subtotalInput) {
                const productoId = productoIdInput.value;
                let precio = 0;
                let subtotal = 0;
                if (dias !== null) {
                    precio = obtenerPrecioProducto(productoId, dias);
                    subtotal = (parseFloat(cantidadInput.value) * dias * precio);
                }
                costoInput.value = precio.toFixed(2);
                subtotalInput.value = subtotal.toFixed(2);
            }
        });
        calcularTotales();
    }

    // Listeners para fechas
    const fechaSalida = document.getElementById('fecha_salida');
    const fechaEntrada = document.getElementById('fecha_entrada');
    if (fechaSalida) fechaSalida.addEventListener('change', actualizarDiasYPrecios);
    if (fechaEntrada) fechaEntrada.addEventListener('change', actualizarDiasYPrecios);

    // Agregar productos a la tabla
    const btnAgregar = document.getElementById('agregar_producto');
    const selectProducto = document.getElementById('producto_select');
    const inputCantidad = document.getElementById('cantidad_producto');
    const tbody = document.querySelector('#tabla-productos tbody');

    
    if (btnAgregar && selectProducto && inputCantidad && tbody) {
        btnAgregar.addEventListener('click', function () {
            const productoId = selectProducto.value;
            const productoNombre = selectProducto.options[selectProducto.selectedIndex].text;
            const cantidad = parseInt(inputCantidad.value) || 1;
            const dias = calcularDiasRenta();
            const precio = obtenerPrecioProducto(productoId, dias);

            if (!productoId) return;

            const row = document.createElement('tr');
            row.innerHTML = `
        <td>
          <input type="hidden" name="producto_id[]" value="${productoId}">
          ${productoNombre}
        </td>
        <td><input type="number" name="cantidad[]" class="form-control cantidad" min="1" value="${cantidad}"></td>
        <td><input type="number" name="dias_renta[]" class="form-control dias" min="1" value="${dias}" readonly></td>
        <td><input type="number" name="costo_unitario[]" class="form-control costo" step="0.01" min="0" value="${precio.toFixed(2)}" readonly></td>
        <td><input type="number" class="form-control subtotal" step="0.01" min="0" value="${(cantidad * dias * precio).toFixed(2)}" readonly></td>
        <td><button type="button" class="btn btn-danger btn-sm btn-eliminar-producto"><i class="bi bi-trash"></i></button></td>
      `;
            tbody.appendChild(row);
            calcularTotales();
        });

        // Eliminar producto
        tbody.addEventListener('click', function (e) {
            if (e.target.closest('.btn-eliminar-producto')) {
                e.target.closest('tr').remove();
                calcularTotales();
            }
        });

        // Recalcular subtotales y totales al cambiar cantidad o costo (NO días)
        tbody.addEventListener('input', function (e) {
            if (e.target.classList.contains('cantidad') || e.target.classList.contains('costo')) {
                const fila = e.target.closest('tr');
                const cantidad = parseFloat(fila.querySelector('.cantidad').value) || 0;
                const dias = parseFloat(fila.querySelector('.dias').value) || 0;
                const costo = parseFloat(fila.querySelector('.costo').value) || 0;
                fila.querySelector('.subtotal').value = (cantidad * dias * costo).toFixed(2);
                calcularTotales();
            }
        });
    }

    function calcularTotales() {
        let subtotal = 0;
        document.querySelectorAll('#tabla-productos .subtotal').forEach(input => {
            subtotal += parseFloat(input.value) || 0;
        });
        // Obtén el traslado
        const traslado = parseFloat(document.getElementById('costo_traslado').value) || 0;
        const subtotalConTraslado = subtotal + traslado;
        const iva = subtotalConTraslado * 0.16;
        const total = subtotalConTraslado + iva;

        document.getElementById('subtotal_general').textContent = `$${subtotal.toFixed(2)}`;
        document.getElementById('traslado_general').textContent = `$${traslado.toFixed(2)}`;
        document.getElementById('iva_general').textContent = `$${iva.toFixed(2)}`;
        document.getElementById('total_general').textContent = `$${total.toFixed(2)}`;
    }

    // Asegúrate de recalcular totales cuando cambie el traslado
    const trasladoInput = document.getElementById('costo_traslado');
    if (trasladoInput) {
        trasladoInput.addEventListener('input', calcularTotales);
    }

    const trasladoSelect = document.getElementById('traslado');
    const tipoTrasladoLabel = document.getElementById('tipo_traslado_label');
    function actualizarTipoTraslado() {
        let texto = '';
        if (trasladoSelect) {
            if (trasladoSelect.value === 'medio') texto = '(Medio)';
            else if (trasladoSelect.value === 'redondo') texto = '(Redondo)';
            else texto = '(Ninguno)';
        }
        if (tipoTrasladoLabel) tipoTrasladoLabel.textContent = texto;
    }
    if (trasladoSelect) trasladoSelect.addEventListener('change', actualizarTipoTraslado);
    // Llama una vez al cargar
    actualizarTipoTraslado();





    // Listener para abrir el modal de Nota de Entrada desde la tabla de rentas
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-nota-entrada');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            window.rentaIdNotaEntradaActual = rentaId; // Relación global para nota_entrada.js

            // Si tienes una función para llenar el modal con datos, llámala aquí:
            if (window.llenarModalNotaEntrada) {
                window.llenarModalNotaEntrada(rentaId);
            }
            // Abre el modal
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalNotaEntrada'));
            modal.show();
        }
    });


    // Listener para abrir el modal de Cobro Extra desde la tabla de rentas/notas
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-cobro-extra');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            window.rentaIdCobroExtraActual = rentaId; // Puedes usar esto para cargar detalles en el modal

            // Si tienes una función para llenar el modal con datos, llámala aquí:
            if (window.llenarModalCobroExtra) {
                window.llenarModalCobroExtra(rentaId);
            }
            // Abre el modal
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCobroExtra'));
            modal.show();
        }
    });

    const formNuevaRenta = document.getElementById('form-nueva-renta');
    const btnGuardarRenta = document.getElementById('btn-guardar-renta');
    if (formNuevaRenta && btnGuardarRenta) {
        formNuevaRenta.addEventListener('submit', function () {
            btnGuardarRenta.disabled = true;
            btnGuardarRenta.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';
        });
    }

    // ===============================================
    // FUNCIONALIDAD DE FILTROS Y BÚSQUEDA
    // ===============================================
    const buscadorRentas = document.getElementById('buscadorRentas');
    const filtroEstado = document.getElementById('filtroEstado');
    const btnLimpiarFiltros = document.getElementById('btnLimpiarFiltros');
    const tablaRentas = document.getElementById('tablaRentas');
    const tbodyRentas = tablaRentas ? tablaRentas.querySelector('tbody') : null;

    // Función para filtrar tabla
    function filtrarTabla() {
        if (!tbodyRentas) return;

        const textoBusqueda = (buscadorRentas.value || '').toLowerCase().trim();
        const estadoSeleccionado = (filtroEstado.value || '').toLowerCase().trim();
        const filas = tbodyRentas.querySelectorAll('tr');
        let filasVisibles = 0;

        filas.forEach(fila => {
            const celdas = fila.querySelectorAll('td');
            if (celdas.length === 0) return;

            // Detectar si existe la columna de sucursal para ajustar índices
            const tieneSucursal = celdas.length > 13; // Si hay más de 13 columnas, incluye sucursal
            
            // Definir índices de columnas según si tiene sucursal o no
            const indices = {
                folio: 0,
                fechaRegistro: tieneSucursal ? 2 : 1,
                nombreCliente: tieneSucursal ? 3 : 2,
                fechaSalida: tieneSucursal ? 5 : 4,
                fechaEntrada: tieneSucursal ? 6 : 5,
                direccionObra: tieneSucursal ? 7 : 6,
                estadoRenta: tieneSucursal ? 8 : 7,
                estadoPago: tieneSucursal ? 9 : 8
            };

            // Extraer texto solo de las columnas específicas para búsqueda
            const textosBusqueda = [
                celdas[indices.folio]?.textContent || '',          // Folio
                celdas[indices.fechaRegistro]?.textContent || '',  // Fecha de registro
                celdas[indices.nombreCliente]?.textContent || '',  // Nombre del cliente
                celdas[indices.fechaSalida]?.textContent || '',    // Fecha de salida
                celdas[indices.fechaEntrada]?.textContent || '',   // Fecha de entrada
                celdas[indices.direccionObra]?.textContent || ''   // Dirección de obra
            ];
            
            const textoFila = textosBusqueda.join(' ').toLowerCase().trim();

            // Verificar búsqueda por texto
            const coincideTexto = !textoBusqueda || textoFila.includes(textoBusqueda);

            // Verificar filtro por estado
            let coincideEstado = true;
            if (estadoSeleccionado) {
                const estadoRenta = celdas[indices.estadoRenta]?.textContent.toLowerCase().trim() || '';
                const estadoPago = celdas[indices.estadoPago]?.textContent.toLowerCase().trim() || '';
                
                // Estados específicos que requieren lógica especial
                if (estadoSeleccionado === 'activo') {
                    coincideEstado = estadoRenta.includes('activo');
                } else if (estadoSeleccionado === 'en curso') {
                    coincideEstado = estadoRenta.includes('en curso');
                } else if (estadoSeleccionado === 'programada') {
                    coincideEstado = estadoRenta.includes('programada');
                } else if (estadoSeleccionado === 'finalizadas') {
                    coincideEstado = estadoRenta.includes('finalizada');
                } else if (estadoSeleccionado === 'cancelada') {
                    coincideEstado = estadoRenta.includes('cancelada');
                } else if (estadoSeleccionado === 'en recolección') {
                    coincideEstado = estadoRenta.includes('en recolección');
                } else if (estadoSeleccionado === 'renta parcial') {
                    coincideEstado = estadoRenta.includes('renta parcial');
                } else if (estadoSeleccionado === 'activa renovación') {
                    coincideEstado = estadoRenta.includes('activa renovación');
                } else if (estadoSeleccionado === 'renta en renovación') {
                    coincideEstado = textoFila.includes('renta en renovación');
                } else if (estadoSeleccionado === 'piezas pendientes') {
                    coincideEstado = estadoRenta.includes('piezas pendientes');
                } else if (estadoSeleccionado === 'pago pendiente') {
                    coincideEstado = estadoPago.includes('pago pendiente');
                } else if (estadoSeleccionado === 'saldo pendiente') {
                    coincideEstado = estadoPago.includes('saldo pendiente');
                } else if (estadoSeleccionado === 'pago realizado') {
                    coincideEstado = estadoPago.includes('pago realizado');
                } else if (estadoSeleccionado === 'retraso pendiente') {
                    coincideEstado = estadoPago.includes('retraso pendiente') || estadoRenta.includes('retraso pendiente');
                } else if (estadoSeleccionado === 'retraso pagado') {
                    coincideEstado = estadoPago.includes('retraso pagado') || estadoRenta.includes('retraso pagado');
                } else if (estadoSeleccionado === 'extra pendiente') {
                    coincideEstado = estadoPago.includes('extra pendiente') || estadoRenta.includes('extra pendiente');
                } else if (estadoSeleccionado === 'extra pagado') {
                    coincideEstado = estadoPago.includes('extra pagado') || estadoRenta.includes('extra pagado');
                } else if (estadoSeleccionado === 'retrasadas') {
                    // Buscar indicadores de retraso
                    coincideEstado = textoFila.includes('vence hoy') || 
                                   textoFila.includes('días de retraso') ||
                                   textoFila.includes('retraso');
                } else {
                    // Para cualquier otro estado, buscar en ambas columnas de estado
                    coincideEstado = estadoRenta.includes(estadoSeleccionado) || 
                                   estadoPago.includes(estadoSeleccionado);
                }
            }

            // Mostrar/ocultar fila
            if (coincideTexto && coincideEstado) {
                fila.style.display = '';
                filasVisibles++;
            } else {
                fila.style.display = 'none';
            }
        });

        // Actualizar indicador de resultados
        actualizarContadorResultados(filasVisibles, filas.length);
    }

    // Función para actualizar contador de resultados
    function actualizarContadorResultados(visibles, total) {
        let contador = document.getElementById('contadorResultados');
        if (!contador) {
            contador = document.createElement('div');
            contador.id = 'contadorResultados';
            contador.className = 'text-muted mb-2 small';
            if (tablaRentas && tablaRentas.parentNode) {
                tablaRentas.parentNode.insertBefore(contador, tablaRentas);
            }
        }
        
        if (visibles === total) {
            contador.textContent = `Mostrando ${total} renta${total !== 1 ? 's' : ''}`;
        } else {
            contador.textContent = `Mostrando ${visibles} de ${total} renta${total !== 1 ? 's' : ''}`;
        }
    }

    // Event listeners para filtros
    if (buscadorRentas) {
        buscadorRentas.addEventListener('input', filtrarTabla);
        buscadorRentas.addEventListener('keyup', filtrarTabla);
    }

    if (filtroEstado) {
        filtroEstado.addEventListener('change', filtrarTabla);
    }

    // Botón limpiar: recargar página
    if (btnLimpiarFiltros) {
        btnLimpiarFiltros.addEventListener('click', function() {
            window.location.reload();
        });
    }

    // Inicializar contador al cargar
    if (tbodyRentas) {
        const totalFilas = tbodyRentas.querySelectorAll('tr').length;
        actualizarContadorResultados(totalFilas, totalFilas);
    }


})


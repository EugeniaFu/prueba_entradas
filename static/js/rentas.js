document.addEventListener('DOMContentLoaded', function () {

    // ========================================
    // FILTROS DE RENTAS EN TIEMPO REAL
    // ========================================
    
    let filtroTextoActual = '';
    let filtroEstadoActual = '';
    
    // Buscador de texto
    const buscadorRentas = document.getElementById('buscadorRentas');
    if (buscadorRentas) {
        buscadorRentas.addEventListener('keyup', function () {
            filtroTextoActual = this.value.toLowerCase();
            aplicarFiltros();
        });
    }
    
    // Filtro de estado
    const filtroEstado = document.getElementById('filtroEstado');
    if (filtroEstado) {
        filtroEstado.addEventListener('change', function () {
            filtroEstadoActual = this.value.toLowerCase();
            aplicarFiltros();
        });
    }
    
    // Botón limpiar filtros
    const btnLimpiarFiltros = document.getElementById('btnLimpiarFiltros');
    if (btnLimpiarFiltros) {
        btnLimpiarFiltros.addEventListener('click', function () {
            if (buscadorRentas) buscadorRentas.value = '';
            if (filtroEstado) filtroEstado.value = '';
            filtroTextoActual = '';
            filtroEstadoActual = '';
            aplicarFiltros();
        });
    }
    
    function aplicarFiltros() {
        const filas = document.querySelectorAll('#tablaRentas tbody tr');
        
        filas.forEach(function (fila) {
            let mostrar = true;
            
            // Detectar dinámicamente las columnas importantes
            const celdas = fila.cells;
            const tieneColumnasSucursal = document.querySelector('#tablaRentas thead th:nth-child(2)').textContent.includes('Sucursal');
            
            let indiceCliente, indiceEstadoRenta, indiceEstadoPago, indiceFechaEntrada;
            
            if (tieneColumnasSucursal) {
                // Con columna sucursal
                indiceCliente = 3;      // Nombre del cliente
                indiceFechaEntrada = 6; // Fecha de entrada
                indiceEstadoRenta = 8;  // Estado de la renta
                indiceEstadoPago = 9;   // Estado de pago
            } else {
                // Sin columna sucursal
                indiceCliente = 2;      // Nombre del cliente
                indiceFechaEntrada = 5; // Fecha de entrada  
                indiceEstadoRenta = 7;  // Estado de la renta
                indiceEstadoPago = 8;   // Estado de pago
            }
            
            // Filtro por texto (folio y cliente)
            if (filtroTextoActual) {
                const folio = celdas[0].textContent.toLowerCase(); // Folio siempre en primera columna
                const cliente = celdas[indiceCliente].textContent.toLowerCase();
                
                const coincideTexto = folio.includes(filtroTextoActual) || 
                                    cliente.includes(filtroTextoActual);
                
                if (!coincideTexto) {
                    mostrar = false;
                }
            }
            
            // Filtro por estado
            if (filtroEstadoActual && mostrar) {
                const estadoRenta = celdas[indiceEstadoRenta].textContent.toLowerCase();
                const estadoPago = celdas[indiceEstadoPago].textContent.toLowerCase(); 
                const fechaEntrada = celdas[indiceFechaEntrada].innerHTML.toLowerCase();
                
                let coincideEstado = false;
                
                switch (filtroEstadoActual) {
                    case 'activo':
                        coincideEstado = estadoRenta.includes('activo') && !estadoRenta.includes('renovación');
                        break;
                    case 'en curso':
                        coincideEstado = estadoRenta.includes('en curso');
                        break;
                    case 'programada':
                        coincideEstado = estadoRenta.includes('programada');
                        break;
                    case 'finalizadas':
                        coincideEstado = estadoRenta.includes('finalizada');
                        break;
                    case 'cancelada':
                        coincideEstado = estadoRenta.includes('cancelada');
                        break;
                    case 'en recolección':
                        coincideEstado = estadoRenta.includes('en recolección');
                        break;
                    case 'renta parcial':
                        coincideEstado = estadoRenta.includes('renta parcial');
                        break;
                    case 'activa renovación':
                        coincideEstado = estadoRenta.includes('activa renovación');
                        break;
                    case 'piezas pendientes':
                        coincideEstado = estadoRenta.includes('piezas pendientes');
                        break;
                    case 'renta en renovación':
                        coincideEstado = estadoRenta.includes('renta en renovación');
                        break;
                    case 'pago pendiente':
                        coincideEstado = estadoPago.includes('pago pendiente');
                        break;
                    case 'saldo pendiente':
                        coincideEstado = estadoPago.includes('saldo pendiente');
                        break;
                    case 'pago realizado':
                        coincideEstado = estadoPago.includes('pago realizado');
                        break;
                    case 'retraso pendiente':
                        coincideEstado = estadoPago.includes('retraso pendiente');
                        break;
                    case 'retraso pagado':
                        coincideEstado = estadoPago.includes('retraso pagado');
                        break;
                    case 'extra pendiente':
                        coincideEstado = estadoPago.includes('extra pendiente');
                        break;
                    case 'extra pagado':
                        coincideEstado = estadoPago.includes('extra pagado');
                        break;
                    case 'retrasadas':
                        // Buscar badges de retraso en la columna fecha de entrada
                        coincideEstado = fechaEntrada.includes('bg-danger') || 
                                       fechaEntrada.includes('bg-warning') ||
                                       fechaEntrada.includes('vencido') ||
                                       fechaEntrada.includes('retraso');
                        break;
                    default:
                        coincideEstado = true;
                        break;
                }
                
                if (!coincideEstado) {
                    mostrar = false;
                }
            }
            
            // Mostrar u ocultar fila
            fila.style.display = mostrar ? '' : 'none';
        });
        
        // Actualizar contador de resultados
        actualizarContadorResultados();
    }
    
    function actualizarContadorResultados() {
        const filasVisibles = document.querySelectorAll('#tablaRentas tbody tr:not([style*="display: none"])').length;
        const totalFilas = document.querySelectorAll('#tablaRentas tbody tr').length;
        
        // Crear o actualizar contador si no existe
        let contador = document.getElementById('contadorResultados');
        if (!contador) {
            contador = document.createElement('div');
            contador.id = 'contadorResultados';
            contador.className = 'text-muted mt-2';
            const tabla = document.getElementById('tablaRentas');
            tabla.parentNode.insertBefore(contador, tabla.nextSibling);
        }
        
        if (filtroTextoActual || filtroEstadoActual) {
            contador.textContent = `Mostrando ${filasVisibles} de ${totalFilas} rentas`;
            contador.style.display = 'block';
        } else {
            contador.style.display = 'none';
        }
    }

    // ========================================
    // RESTO DE LA FUNCIONALIDAD EXISTENTE
    // ========================================

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
        if (dias <= 2) return precios.precio_dia;
        if (dias >= 3 && dias <= 14) return precios.precio_7dias;
        if (dias >= 15 && dias <= 29) return precios.precio_15dias;
        if (dias >= 30) return precios.precio_30dias;
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



})


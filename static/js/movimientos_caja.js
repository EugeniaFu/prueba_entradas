// ============================================================================
// MOVIMIENTOS DE CAJA - JavaScript
// ============================================================================

$(document).ready(function() {
    // Variables globales
    let currentTab = 'efectivo';
    
    // ========================================================================
    // UTILIDADES DE FECHA PARA ZONA HORARIA LOCAL
    // ========================================================================
    
    function getFechaLocal() {
        // Obtener fecha local de Campeche (GMT-6)
        const ahora = new Date();
        // Ajustar a zona horaria local de Campeche
        const offsetCampeche = -6; // GMT-6
        const offsetLocal = ahora.getTimezoneOffset() / 60; // Offset del navegador en horas
        const ajuste = (offsetCampeche - (-offsetLocal)) * 60 * 60 * 1000;
        const fechaLocal = new Date(ahora.getTime() + ajuste);
        
        return fechaLocal.toISOString().split('T')[0];
    }
    
    // ========================================================================
    // INICIALIZACIÓN
    // ========================================================================
    
    function inicializar() {
        // Configurar fechas por defecto usando zona horaria local de Campeche
        const hoy = getFechaLocal();
        $('#fechaInicioEfectivo, #fechaFinEfectivo, #fechaInicioDigital, #fechaFinDigital').val(hoy);
        $('#fechaCorteCaja').val(hoy);

        // Cargar datos iniciales
        cargarMovimientosEfectivo();
        cargarResumenEfectivo();
        inicializarCorteCaja();

        // Configurar event listeners
        configurarEventListeners();

        console.log('Sistema de caja inicializado correctamente');
    }
    
    function configurarEventListeners() {
        // ====== TABS ======
        $('[data-bs-toggle="tab"]').on('shown.bs.tab', function(e) {
            currentTab = e.target.getAttribute('aria-controls');
            if (currentTab === 'digitales') {
                cargarIngresosDigitales();
            }
        });
        
        // ====== BOTONES PRINCIPALES ======
        $('#btnNuevoMovimiento').click(function() {
            abrirModalMovimiento();
        });
        
        // ====== FILTROS EFECTIVO ======
        $('#btnFiltrarEfectivo').click(function() {
            cargarMovimientosEfectivo();
            cargarResumenEfectivo();
        });
        
        $('#btnLimpiarFiltrosEfectivo').click(function() {
            const hoy = getFechaLocal();
            $('#fechaInicioEfectivo, #fechaFinEfectivo').val(hoy);
            $('#tipoMovimientoEfectivo, #origenMovimientoEfectivo').val('');
            cargarMovimientosEfectivo();
            cargarResumenEfectivo();
        });

        // ====== CORTE DE CAJA ======
        $('#fechaCorteCaja').on('change', cargarCorteCaja);
        $('#filtroSucursalEfectivo').on('change', cargarCorteCaja);
        $('#btnGuardarCorteCaja').click(guardarCorteCaja);
        
        // ====== FILTROS DIGITALES ======
        $('#btnFiltrarDigital').click(function() {
            cargarIngresosDigitales();
        });
        
        $('#btnLimpiarFiltrosDigital').click(function() {
            const hoy = getFechaLocal();
            $('#fechaInicioDigital, #fechaFinDigital').val(hoy);
            cargarIngresosDigitales();
        });
        
        // ====== BOTONES DE ACTUALIZAR ======
        $('#btnActualizarEfectivo').click(function() {
            cargarMovimientosEfectivo();
            cargarResumenEfectivo();
        });
        
        $('#btnActualizarDigital').click(function() {
            cargarIngresosDigitales();
        });
        
        // ====== MODAL MOVIMIENTO ======
        $('#formMovimiento').submit(function(e) {
            e.preventDefault();
            guardarMovimiento();
        });
    }
    
    // ========================================================================
    // FUNCIONES DE CARGA DE DATOS - EFECTIVO
    // ========================================================================
    
    function cargarMovimientosEfectivo() {
        mostrarLoading('efectivo', true);
        
        const filtros = {
            fecha_inicio: $('#fechaInicioEfectivo').val(),
            fecha_fin: $('#fechaFinEfectivo').val(),
            tipo: $('#tipoMovimientoEfectivo').val(),
            tipo_movimiento: $('#origenMovimientoEfectivo').val(),
            sucursal_id: $('#filtroSucursalEfectivo').length ? $('#filtroSucursalEfectivo').val() : ''
        };
        
        $.ajax({
            url: '/caja/api/movimientos',
            method: 'GET',
            data: filtros,
            success: function(response) {
                if (response.success) {
                    renderizarTablaEfectivo(response.movimientos);
                } else {
                    mostrarError('Error al cargar movimientos: ' + response.error);
                }
            },
            error: function(xhr) {
                mostrarError('Error de conexión al cargar movimientos');
                console.error('Error:', xhr);
            },
            complete: function() {
                mostrarLoading('efectivo', false);
            }
        });
    }
    
    function cargarResumenEfectivo() {
        const filtros = {
            fecha_inicio: $('#fechaInicioEfectivo').val(),
            fecha_fin: $('#fechaFinEfectivo').val(),
            sucursal_id: $('#filtroSucursalEfectivo').length ? $('#filtroSucursalEfectivo').val() : ''
        };
        
        $.ajax({
            url: '/caja/api/resumen',
            method: 'GET',
            data: filtros,
            success: function(response) {
                if (response.success) {
                    actualizarResumenEfectivo(response.resumen);
                } else {
                    console.error('Error al cargar resumen:', response.error);
                }
            },
            error: function(xhr) {
                console.error('Error al cargar resumen:', xhr);
            }
        });
    }
    
    function renderizarTablaEfectivo(movimientos) {
        const tbody = $('#tbodyMovimientosEfectivo');
        tbody.empty();
        
        if (movimientos.length === 0) {
            $('#noDataEfectivo').removeClass('d-none');
            return;
        }
        
        $('#noDataEfectivo').addClass('d-none');
        
        movimientos.forEach(function(mov) {
            const badgeTipo = mov.tipo === 'ingreso' 
                ? '<span class="badge bg-success">Ingreso</span>'
                : '<span class="badge bg-danger">Egreso</span>';
                
            const badgeOrigen = mov.tipo_movimiento === 'manual'
                ? '<span class="badge bg-primary">Manual</span>'
                : '<span class="badge bg-info">Automático</span>';
                
            const fila = `
                <tr>
                    <td>${mov.fecha_formateada}</td>
                    <td>${mov.hora_formateada}</td>
                    <td>${badgeTipo}</td>
                    <td class="text-truncate" style="max-width: 200px;" title="${mov.concepto}">
                        ${mov.concepto}
                    </td>
                    <td class="text-end fw-bold ${mov.tipo === 'ingreso' ? 'text-success' : 'text-danger'}">
                        $${mov.monto_formateado}
                    </td>
                    <td>${badgeOrigen}</td>
                    <td>${mov.usuario_nombre || 'Sistema'}</td>
                    <td>
                        <button class="btn btn-outline-primary btn-sm" onclick="verDetalleMovimiento(${mov.id})" title="Ver detalle">
                            <i class="bi bi-eye"></i>
                        </button>
                    </td>
                </tr>
            `;
            tbody.append(fila);
        });
    }
    
    function actualizarResumenEfectivo(resumen) {
        $('#totalIngresosEfectivo').text('$' + resumen.total_ingresos.toLocaleString('es-MX', {minimumFractionDigits: 2}));
        $('#countIngresosEfectivo').text(resumen.count_ingresos + ' movimientos');

        $('#totalEgresosEfectivo').text('$' + resumen.total_egresos.toLocaleString('es-MX', {minimumFractionDigits: 2}));
        $('#countEgresosEfectivo').text(resumen.count_egresos + ' movimientos');

        $('#saldoInicialPeriodo').text('$' + resumen.saldo_inicial_periodo.toLocaleString('es-MX', {minimumFractionDigits: 2}));
        $('#saldoCaja').text('$' + resumen.saldo_final_periodo.toLocaleString('es-MX', {minimumFractionDigits: 2}));

        // Actualizar color del saldo
        const saldoElement = $('#saldoCaja');
        saldoElement.removeClass('text-success text-danger text-primary');
        if (resumen.saldo_final_periodo > 0) {
            saldoElement.addClass('text-success');
        } else if (resumen.saldo_final_periodo < 0) {
            saldoElement.addClass('text-danger');
        } else {
            saldoElement.addClass('text-primary');
        }
        
        // Actualizar fecha del resumen
        const fechaInicio = $('#fechaInicioEfectivo').val();
        const fechaFin = $('#fechaFinEfectivo').val();
        
        if (fechaInicio === fechaFin) {
            const fechaHoy = getFechaLocal();
            const fechaStr = fechaInicio === fechaHoy ? 'Hoy' : fechaInicio;
            $('#fechaResumenEfectivo').text(fechaStr);
        } else {
            $('#fechaResumenEfectivo').text('Período seleccionado');
        }
    }

    // ========================================================================
    // CORTE DE CAJA (billetes y monedas) - solo conteo/auditoría, no afecta
    // el acumulado de ingresos/egresos ni crea movimientos de caja.
    // ========================================================================

    const DENOMINACIONES_BILLETES = [1000, 500, 200, 100, 50, 20];
    const DENOMINACIONES_MONEDAS = [10, 5, 2, 1, 0.50, 0.20, 0.10];

    function formatearDenominacion(valor) {
        return valor < 1 ? '$' + valor.toFixed(2) : '$' + valor.toFixed(0);
    }

    function inicializarCorteCaja() {
        const $billetes = $('#tablaBilletesCorte tbody');
        const $monedas = $('#tablaMonedasCorte tbody');

        DENOMINACIONES_BILLETES.forEach(function(denom) {
            $billetes.append(filaDenominacion('billete', denom));
        });
        DENOMINACIONES_MONEDAS.forEach(function(denom) {
            $monedas.append(filaDenominacion('moneda', denom));
        });

        $('#tablaBilletesCorte, #tablaMonedasCorte').on('input', '.cantidad-denominacion', recalcularTotalContado);

        cargarCorteCaja();
    }

    function filaDenominacion(tipo, denominacion) {
        return `
            <tr>
                <td>${formatearDenominacion(denominacion)}</td>
                <td style="max-width:90px;">
                    <input type="number" min="0" value="0" class="form-control form-control-sm cantidad-denominacion"
                           data-tipo="${tipo}" data-denominacion="${denominacion}">
                </td>
                <td class="text-end subtotal-denominacion" style="min-width:90px;">$0.00</td>
            </tr>
        `;
    }

    function recalcularTotalContado() {
        let total = 0;
        $('.cantidad-denominacion').each(function() {
            const $input = $(this);
            const cantidad = parseInt($input.val()) || 0;
            const denominacion = parseFloat($input.data('denominacion'));
            const subtotal = cantidad * denominacion;
            $input.closest('tr').find('.subtotal-denominacion').text('$' + subtotal.toFixed(2));
            total += subtotal;
        });
        $('#totalContadoCorte').text('$' + total.toLocaleString('es-MX', {minimumFractionDigits: 2}));
        return total;
    }

    function obtenerSucursalIdCorte() {
        return $('#filtroSucursalEfectivo').length ? $('#filtroSucursalEfectivo').val() : null;
    }

    function actualizarIndicadoresCorte(saldoSistema, diferencia) {
        $('#saldoSistemaCorte').text('$' + saldoSistema.toLocaleString('es-MX', {minimumFractionDigits: 2}));

        const $diferencia = $('#diferenciaCorte');
        const $contenedor = $('#contenedorDiferenciaCorte');
        $contenedor.removeClass('bg-success bg-danger bg-secondary bg-opacity-10');
        $diferencia.removeClass('text-success text-danger text-muted');

        const etiqueta = diferencia > 0 ? ' (sobrante)' : (diferencia < 0 ? ' (faltante)' : '');
        $diferencia.text('$' + diferencia.toLocaleString('es-MX', {minimumFractionDigits: 2}) + etiqueta);

        if (diferencia === 0) {
            $contenedor.addClass('bg-secondary bg-opacity-10');
            $diferencia.addClass('text-muted');
        } else if (diferencia > 0) {
            $contenedor.addClass('bg-success bg-opacity-10');
            $diferencia.addClass('text-success');
        } else {
            $contenedor.addClass('bg-danger bg-opacity-10');
            $diferencia.addClass('text-danger');
        }
    }

    function cargarCorteCaja() {
        const fecha = $('#fechaCorteCaja').val();
        const sucursalId = obtenerSucursalIdCorte();

        // Limpiar mientras carga
        $('.cantidad-denominacion').val(0);
        $('#observacionesCorteCaja').val('');
        $('#saldoSistemaCorte').text('--');
        $('#diferenciaCorte').text('--');
        $('#contenedorDiferenciaCorte').removeClass('bg-success bg-danger bg-secondary bg-opacity-10');
        recalcularTotalContado();

        $.ajax({
            url: '/caja/api/corte',
            method: 'GET',
            data: { fecha: fecha, sucursal_id: sucursalId },
            success: function(response) {
                if (!response.success) return;
                const corte = response.corte;
                if (!corte) return;

                corte.detalle.forEach(function(fila) {
                    $(`.cantidad-denominacion[data-tipo="${fila.tipo}"][data-denominacion="${fila.denominacion}"]`)
                        .val(fila.cantidad);
                });
                $('#observacionesCorteCaja').val(corte.observaciones || '');
                recalcularTotalContado();
                actualizarIndicadoresCorte(corte.saldo_sistema, corte.diferencia);
            },
            error: function(xhr) {
                console.error('Error al cargar corte de caja:', xhr);
            }
        });
    }

    function guardarCorteCaja() {
        const fecha = $('#fechaCorteCaja').val();
        const sucursalId = obtenerSucursalIdCorte();

        if (sucursalId !== null && !sucursalId) {
            mostrarError('Debe seleccionar a qué sucursal pertenece el corte');
            return;
        }

        const denominaciones = [];
        $('.cantidad-denominacion').each(function() {
            const cantidad = parseInt($(this).val()) || 0;
            if (cantidad > 0) {
                denominaciones.push({
                    tipo: $(this).data('tipo'),
                    denominacion: parseFloat($(this).data('denominacion')),
                    cantidad: cantidad
                });
            }
        });

        const data = {
            fecha: fecha,
            denominaciones: denominaciones,
            observaciones: $('#observacionesCorteCaja').val().trim()
        };
        if (sucursalId) data.sucursal_id = sucursalId;

        const $btn = $('#btnGuardarCorteCaja');
        const textoOriginal = $btn.html();
        $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm me-1"></span>Guardando...');

        $.ajax({
            url: '/caja/api/corte',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                if (response.success) {
                    mostrarExito(response.message);
                    actualizarIndicadoresCorte(response.saldo_sistema, response.diferencia);
                } else {
                    mostrarError('Error: ' + response.error);
                }
            },
            error: function(xhr) {
                let mensaje = 'Error al guardar el corte de caja';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    mensaje = xhr.responseJSON.error;
                }
                mostrarError(mensaje);
            },
            complete: function() {
                $btn.prop('disabled', false).html(textoOriginal);
            }
        });
    }

    // ========================================================================
    // FUNCIONES DE CARGA DE DATOS - INGRESOS DIGITALES
    // ========================================================================
    
    function cargarIngresosDigitales() {
        mostrarLoading('digital', true);
        
        const filtros = {
            fecha_inicio: $('#fechaInicioDigital').val(),
            fecha_fin: $('#fechaFinDigital').val(),
            sucursal_id: $('#filtroSucursalDigital').length ? $('#filtroSucursalDigital').val() : ''
        };
        
        $.ajax({
            url: '/caja/api/ingresos-digitales',
            method: 'GET',
            data: filtros,
            success: function(response) {
                if (response.success) {
                    renderizarTablaDigitales(response.ingresos_digitales);
                    actualizarResumenDigital(response.resumen_digital);
                } else {
                    mostrarError('Error al cargar ingresos digitales: ' + response.error);
                }
            },
            error: function(xhr) {
                mostrarError('Error de conexión al cargar ingresos digitales');
                console.error('Error:', xhr);
            },
            complete: function() {
                mostrarLoading('digital', false);
            }
        });
    }
    
    function renderizarTablaDigitales(ingresos) {
        const tbody = $('#tbodyIngresosDigitales');
        tbody.empty();
        
        if (ingresos.length === 0) {
            $('#noDataDigital').removeClass('d-none');
            return;
        }
        
        $('#noDataDigital').addClass('d-none');
        
        ingresos.forEach(function(ingreso) {
            const badgeMetodo = {
                'T.DÉBITO': '<span class="badge bg-primary">T. Débito</span>',
                'T.CRÉDITO': '<span class="badge bg-warning">T. Crédito</span>',
                'TRANSFERENCIA': '<span class="badge bg-info">Transferencia</span>'
            }[ingreso.metodo_pago] || '<span class="badge bg-secondary">' + ingreso.metodo_pago + '</span>';
            
            const fila = `
                <tr>
                    <td>${ingreso.fecha_formateada}</td>
                    <td>${ingreso.tipo_documento}</td>
                    <td><strong>${ingreso.folio || 'N/A'}</strong></td>
                    <td>${ingreso.cliente_nombre || 'N/A'}</td>
                    <td>${badgeMetodo}</td>
                    <td class="font-monospace">${ingreso.numero_seguimiento || 'N/A'}</td>
                    <td class="text-end fw-bold text-success">$${ingreso.monto_formateado}</td>
                    <td>${ingreso.usuario_nombre || 'Sistema'}</td>
                </tr>
            `;
            tbody.append(fila);
        });
    }
    
    function actualizarResumenDigital(resumen) {
        const container = $('#resumenMetodosPago');
        container.empty();
        
        if (resumen.length === 0) {
            container.html('<p class="text-muted text-center">No hay ingresos digitales en el período seleccionado</p>');
            return;
        }
        
        let totalGeneral = 0;
        
        resumen.forEach(function(metodo) {
            totalGeneral += parseFloat(metodo.total);
            
            const color = {
                'T.DÉBITO': 'primary',
                'T.CRÉDITO': 'warning', 
                'TRANSFERENCIA': 'info'
            }[metodo.metodo_pago] || 'secondary';
            
            const item = `
                <div class="mb-3">
                    <div class="p-3 bg-${color} bg-opacity-10 rounded">
                        <h6 class="text-${color} mb-1">${metodo.metodo_pago.replace('T.', 'Tarjeta ')}</h6>
                        <h5 class="text-${color} mb-0">$${metodo.total_formateado}</h5>
                        <small class="text-muted">${metodo.cantidad} transacciones</small>
                    </div>
                </div>
            `;
            container.append(item);
        });
        
        // Agregar total general
        const totalItem = `
            <div class="border-top pt-3">
                <div class="p-3 bg-success bg-opacity-10 rounded">
                    <h6 class="text-success mb-1"><strong>Total Digital</strong></h6>
                    <h4 class="text-success mb-0"><strong>$${totalGeneral.toLocaleString('es-MX', {minimumFractionDigits: 2})}</strong></h4>
                </div>
            </div>
        `;
        container.append(totalItem);
    }
    
    // ========================================================================
    // FUNCIONES DE MODALES
    // ========================================================================
    
    function abrirModalMovimiento(tipo = null) {
        // Limpiar formulario
        $('#formMovimiento')[0].reset();
        
        // Configurar modal - título genérico
        $('#modalMovimientoLabel').html('<i class="bi bi-cash-stack me-2"></i>Nuevo Movimiento de Efectivo');
        
        // Si se especifica un tipo, preseleccionarlo
        if (tipo) {
            $('#tipoMovimiento').val(tipo);
        }
        
        // Mostrar modal
        $('#modalMovimiento').modal('show');
        
        // Foco en el primer campo
        setTimeout(function() {
            $('#tipoMovimiento').focus();
        }, 300);
    }
    
    function guardarMovimiento() {
        const form = $('#formMovimiento');
        const data = {
            tipo: $('#tipoMovimiento').val(),
            monto: parseFloat($('#montoMovimiento').val()),
            concepto: $('#conceptoMovimiento').val().trim(),
            observaciones: $('#observacionesMovimiento').val().trim(),
            metodo_pago: 'EFECTIVO' // Siempre efectivo para movimientos de caja
        };
        
        // Si el usuario es admin y tiene selector de sucursal en el modal, enviarlo.
        // Si no lo seleccionó aunque aparezca, validarlo.
        const $sucursalMovimiento = $('#sucursalMovimiento');
        if ($sucursalMovimiento.length) {
            data.sucursal_id = $sucursalMovimiento.val();
            if (!data.sucursal_id) {
                mostrarError('Debe seleccionar a qué sucursal pertenece el movimiento');
                return;
            }
        }
        
        // Validaciones básicas
        if (!data.tipo || !data.monto || !data.concepto) {
            mostrarError('Todos los campos marcados con * son obligatorios');
            return;
        }
        
        if (data.monto <= 0) {
            mostrarError('El monto debe ser mayor a 0');
            return;
        }
        
        // Deshabilitar botón durante el envío
        const btnGuardar = form.find('button[type="submit"]');
        const textoOriginal = btnGuardar.html();
        btnGuardar.prop('disabled', true).html('<i class="spinner-border spinner-border-sm me-1"></i>Guardando...');
        
        $.ajax({
            url: '/caja/api/movimiento',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                if (response.success) {
                    mostrarExito(response.message);
                    $('#modalMovimiento').modal('hide');
                    
                    // Recargar datos
                    cargarMovimientosEfectivo();
                    cargarResumenEfectivo();
                } else {
                    mostrarError('Error: ' + response.error);
                }
            },
            error: function(xhr) {
                let mensaje = 'Error al guardar el movimiento';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    mensaje = xhr.responseJSON.error;
                }
                mostrarError(mensaje);
                console.error('Error:', xhr);
            },
            complete: function() {
                btnGuardar.prop('disabled', false).html(textoOriginal);
            }
        });
    }
    
    // Función global para ver detalle de movimiento
    window.verDetalleMovimiento = function(movimientoId) {
        $.ajax({
            url: '/caja/api/movimiento/' + movimientoId,
            method: 'GET',
            success: function(response) {
                if (response.success) {
                    mostrarDetalleMovimiento(response.movimiento, response.referencia_info);
                } else {
                    mostrarError('Error al cargar detalle: ' + response.error);
                }
            },
            error: function(xhr) {
                mostrarError('Error al cargar detalle del movimiento');
                console.error('Error:', xhr);
            }
        });
    };
    
    function mostrarDetalleMovimiento(movimiento, referencia) {
        const badgeTipo = movimiento.tipo === 'ingreso' 
            ? '<span class="badge bg-success fs-6">Ingreso</span>'
            : '<span class="badge bg-danger fs-6">Egreso</span>';
            
        const badgeOrigen = movimiento.tipo_movimiento === 'manual'
            ? '<span class="badge bg-primary">Manual</span>'
            : '<span class="badge bg-info">Automático</span>';
        
        let contenido = `
            <div class="row g-3">
                <div class="col-md-6">
                    <strong>Fecha:</strong><br>
                    ${movimiento.fecha_formateada}
                </div>
                <div class="col-md-6">
                    <strong>Hora:</strong><br>
                    ${movimiento.hora_formateada}
                </div>
                <div class="col-md-6">
                    <strong>Tipo:</strong><br>
                    ${badgeTipo}
                </div>
                <div class="col-md-6">
                    <strong>Origen:</strong><br>
                    ${badgeOrigen}
                </div>
                <div class="col-md-6">
                    <strong>Monto:</strong><br>
                    <span class="h5 ${movimiento.tipo === 'ingreso' ? 'text-success' : 'text-danger'}">
                        $${movimiento.monto_formateado}
                    </span>
                </div>
                <div class="col-md-6">
                    <strong>Usuario:</strong><br>
                    ${movimiento.usuario_completo || 'Sistema'}
                </div>
                <div class="col-12">
                    <strong>Concepto:</strong><br>
                    ${movimiento.concepto}
                </div>
        `;
        
        if (movimiento.observaciones) {
            contenido += `
                <div class="col-12">
                    <strong>Observaciones:</strong><br>
                    ${movimiento.observaciones}
                </div>
            `;
        }
        
        // Si es movimiento automático, mostrar información de referencia
        if (movimiento.tipo_movimiento === 'automatico' && referencia) {
            contenido += `
                <div class="col-12">
                    <hr>
                    <h6 class="text-primary"><i class="bi bi-link me-1"></i>Información de Referencia</h6>
                    <div class="bg-light p-3 rounded">
                        <strong>Documento:</strong> ${movimiento.referencia_tabla}<br>
                        <strong>ID Referencia:</strong> ${referencia.id}<br>
            `;
            
            if (referencia.cliente_nombre) {
                contenido += `<strong>Cliente:</strong> ${referencia.cliente_nombre}<br>`;
            }
            if (referencia.renta_id) {
                contenido += `<strong>Renta ID:</strong> ${referencia.renta_id}<br>`;
            }
            
            contenido += `
                    </div>
                </div>
            `;
        }
        
        contenido += '</div>';
        
        $('#detalleMovimientoContent').html(contenido);
        $('#modalDetalle').modal('show');
    }
    
    // ========================================================================
    // FUNCIONES AUXILIARES
    // ========================================================================
    
    function mostrarLoading(tipo, mostrar) {
        const loading = tipo === 'efectivo' ? $('#loadingEfectivo') : $('#loadingDigital');
        if (mostrar) {
            loading.removeClass('d-none');
        } else {
            loading.addClass('d-none');
        }
    }
    
    function mostrarError(mensaje) {
        // Crear toast de error
        const toast = $(`
            <div class="toast align-items-center text-white bg-danger border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi bi-exclamation-triangle me-2"></i>${mensaje}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `);
        
        // Agregar al contenedor de toasts (crear si no existe)
        if ($('#toastContainer').length === 0) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }
        
        $('#toastContainer').append(toast);
        
        // Mostrar toast
        toast.toast('show');
        
        // Remover después de ocultarse
        toast.on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }
    
    function mostrarExito(mensaje) {
        // Crear toast de éxito
        const toast = $(`
            <div class="toast align-items-center text-white bg-success border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi bi-check-circle me-2"></i>${mensaje}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `);
        
        // Agregar al contenedor de toasts
        if ($('#toastContainer').length === 0) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }
        
        $('#toastContainer').append(toast);
        
        // Mostrar toast
        toast.toast('show');
        
        // Remover después de ocultarse
        toast.on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }
    
    // ========================================================================
    // FUNCIONES DE EXPORTACIÓN PDF
    // ========================================================================
    
    $('#btnExportarEfectivo').click(function() {
        exportarMovimientosEfectivoPDF();
    });
    
    $('#btnExportarDigital').click(function() {
        exportarIngresosDigitalesPDF();
    });
    
    function exportarMovimientosEfectivoPDF() {
        // Obtener filtros actuales
        const fechaInicio = $('#fechaInicioEfectivo').val();
        const fechaFin = $('#fechaFinEfectivo').val();
        const tipo = $('#tipoMovimientoEfectivo').val();
        const tipoMovimiento = $('#origenMovimientoEfectivo').val();
        
        const sucursalId = $('#filtroSucursalEfectivo').length ? $('#filtroSucursalEfectivo').val() : '';
        
        // Construir URL con parámetros
        let url = `/caja/pdf/movimientos?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`;
        
        if (tipo) {
            url += `&tipo=${tipo}`;
        }
        
        if (tipoMovimiento) {
            url += `&tipo_movimiento=${tipoMovimiento}`;
        }
        
        if (sucursalId) {
            url += `&sucursal_id=${sucursalId}`;
        }
        
        // Abrir PDF en nueva ventana
        window.open(url, '_blank');
        
        mostrarExito('Generando reporte PDF de movimientos en efectivo...');
    }
    
    function exportarIngresosDigitalesPDF() {
        mostrarInfo('Exportación de ingresos digitales en desarrollo. Por ahora usa la exportación de efectivo para movimientos completos.');
    }
    
    function mostrarExito(mensaje) {
        const toast = $(`
            <div class="toast align-items-center text-white bg-success border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi bi-check-circle me-2"></i>${mensaje}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `);
        
        if ($('#toastContainer').length === 0) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }
        
        $('#toastContainer').append(toast);
        toast.toast('show');
        
        toast.on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }
    
    function mostrarInfo(mensaje) {
        const toast = $(`
            <div class="toast align-items-center text-white bg-info border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi bi-info-circle me-2"></i>${mensaje}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `);
        
        if ($('#toastContainer').length === 0) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }
        
        $('#toastContainer').append(toast);
        toast.toast('show');
        
        toast.on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }
    
    // ========================================================================
    // INICIALIZAR CUANDO EL DOM ESTÉ LISTO
    // ========================================================================
    
    inicializar();
});
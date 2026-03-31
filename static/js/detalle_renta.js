document.addEventListener('DOMContentLoaded', function () {
    // Abrir modal de detalle
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-ver-detalle');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalDetalleRenta'));
            modal.show();

            // Debug: Verificar que todos los elementos existan
            console.log('Verificando elementos del modal:');
            console.log('detalle-notas-salida-tabla:', !!document.getElementById('detalle-notas-salida-tabla'));
            console.log('cobros-pendientes-section:', !!document.getElementById('cobros-pendientes-section'));
            console.log('retrasos-pendientes:', !!document.getElementById('retrasos-pendientes'));
            console.log('extras-pendientes:', !!document.getElementById('extras-pendientes'));
            console.log('btn-cobrar-retraso:', !!document.getElementById('btn-cobrar-retraso'));
            console.log('btn-cobrar-extra:', !!document.getElementById('btn-cobrar-extra'));

            // Limpiar datos previos
            document.getElementById('detalle-renta-id').textContent = rentaId;
            document.getElementById('detalle-productos-tabla').innerHTML =
                '<tr><td colspan="5" class="text-center text-muted">Cargando...</td></tr>';

            // Cargar datos
            fetch(`/rentas/detalle/${rentaId}`)
                .then(resp => resp.json())
                .then(data => {
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }

                    cargarDatosRenta(data.renta);
                    cargarDatosCliente(data.cliente);
                    cargarProductos(data.productos);

                    // Cargar historial de pagos/prefacturas
                    const totalConIva = parseFloat(data.renta.total_con_iva) || parseFloat(data.renta.total) || 0;
                    fetch(`/prefactura/api/pagos/${rentaId}`)
                        .then(resp => resp.json())
                        .then(pagos => {
                            cargarHistorialPagos(pagos, totalConIva);
                        })
                        .catch(err => {
                            console.error('Error al cargar pagos:', err);
                            document.getElementById('detalle-pagos-tabla').innerHTML = 
                                '<tr><td colspan="6" class="text-center text-danger">Error al cargar historial de pagos</td></tr>';
                        });

                    fetch(`/notas_entrada/historial/${rentaId}`)
                        .then(resp => resp.json())
                        .then(notas => {
                            const tbody = document.getElementById('detalle-notas-entrada-tabla');
                            if (!notas.length) {
                                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Sin notas de entrada</td></tr>';
                                return;
                            }
                            tbody.innerHTML = notas.map(nota => `
                                <tr>
                                    <td>${nota.folio}</td>
                                    <td>${new Date(nota.fecha_entrada_real).toLocaleString()}</td>
                                    <td>
                                        <a href="/notas_entrada/pdf/${nota.id}" target="_blank" class="btn btn-sm btn-primary">
                                            <i class="bi bi-file-earmark-pdf"></i> PDF
                                        </a>
                                    </td>
                                </tr>
                            `).join('');
                        })
                        .catch(err => {
                            console.error('Error al cargar notas de entrada:', err);
                            document.getElementById('detalle-notas-entrada-tabla').innerHTML = 
                                '<tr><td colspan="3" class="text-center text-danger">Error al cargar notas de entrada</td></tr>';
                        });

                    // Cargar historial de notas de salida
                    fetch(`/notas_salida/historial/${rentaId}`)
                        .then(resp => {
                            console.log('Respuesta notas de salida:', resp.status);
                            if (!resp.ok) {
                                throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
                            }
                            return resp.json();
                        })
                        .then(notas => {
                            console.log('Notas de salida recibidas:', notas);
                            const tbody = document.getElementById('detalle-notas-salida-tabla');
                            if (!tbody) {
                                console.error('Elemento detalle-notas-salida-tabla no encontrado');
                                return;
                            }
                            if (!notas.length) {
                                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Sin notas de salida</td></tr>';
                                return;
                            }
                            tbody.innerHTML = notas.map(nota => `
                                <tr>
                                    <td>${nota.folio}</td>
                                    <td>${new Date(nota.fecha_salida_real).toLocaleString()}</td>
                                    <td>
                                        <a href="/notas_salida/pdf/${nota.id}" target="_blank" class="btn btn-sm btn-success">
                                            <i class="bi bi-file-earmark-pdf"></i> PDF
                                        </a>
                                    </td>
                                </tr>
                            `).join('');
                        })
                        .catch(err => {
                            console.error('Error al cargar notas de salida:', err);
                            const tbody = document.getElementById('detalle-notas-salida-tabla');
                            if (tbody) {
                                tbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">Error: ${err.message}</td></tr>`;
                            }
                        });

                    // Cargar cobros por retraso pendientes
                    fetch(`/cobros_retraso/pendientes/${rentaId}`)
                        .then(resp => {
                            console.log('Respuesta cobros retraso:', resp.status);
                            if (!resp.ok) {
                                throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
                            }
                            return resp.json();
                        })
                        .then(data => {
                            console.log('Cobros retraso recibidos:', data);
                            cargarRetrasosPendientes(data, rentaId);
                        })
                        .catch(err => {
                            console.error('Error al cargar retrasos pendientes:', err);
                            // Mostrar mensaje de error en la sección
                            const tbody = document.getElementById('retrasos-pendientes-tabla');
                            if (tbody) {
                                tbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">Error: ${err.message}</td></tr>`;
                            }
                        });

                    // Cargar cobros extra pendientes
                    fetch(`/cobros_extra/pendientes/${rentaId}`)
                        .then(resp => {
                            console.log('Respuesta cobros extra:', resp.status);
                            if (!resp.ok) {
                                throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
                            }
                            return resp.json();
                        })
                        .then(data => {
                            console.log('Cobros extra recibidos:', data);
                            cargarExtrasPendientes(data, rentaId);
                        })
                        .catch(err => {
                            console.error('Error al cargar cobros extra pendientes:', err);
                            // Mostrar mensaje de error en la sección
                            const tbody = document.getElementById('extras-pendientes-tabla');
                            if (tbody) {
                                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Error: ${err.message}</td></tr>`;
                            }
                        });
                })
                .catch(err => {
                    console.error('Error:', err);
                    alert('Error al cargar los datos');
                });
        }
    });

    function cargarDatosRenta(renta) {
        // Estados con colores
        const estadoRentaClass = {
            'activo': 'bg-success',
            'programada': 'bg-warning',
            'finalizada': 'bg-secondary',
            'cancelada': 'bg-danger'
        };

        const estadoPagoClass = {
            'Pago realizado': 'bg-success',
            'Pago pendiente': 'bg-danger',
            'Parcialmente pagado': 'bg-warning'
        };

        document.getElementById('detalle-estado-renta').textContent = renta.estado_renta;
        document.getElementById('detalle-estado-renta').className =
            `badge ${estadoRentaClass[renta.estado_renta.toLowerCase()] || 'bg-secondary'}`;

        document.getElementById('detalle-estado-pago').textContent = renta.estado_pago;
        document.getElementById('detalle-estado-pago').className =
            `badge ${estadoPagoClass[renta.estado_pago] || 'bg-secondary'}`;

        document.getElementById('detalle-metodo-pago').textContent = renta.metodo_pago;
        document.getElementById('detalle-fecha-registro').textContent = renta.fecha_registro;
        document.getElementById('detalle-direccion-obra').textContent = renta.direccion_obra;
        document.getElementById('detalle-periodo-renta').textContent =
            `${renta.fecha_salida} al ${renta.fecha_entrada}`;
        document.getElementById('detalle-fecha-limite').textContent = renta.fecha_limite;
        document.getElementById('detalle-traslado').textContent = renta.traslado;

        // Totales - Cálculos corregidos siguiendo la lógica del backend
        // Backend: total_sin_iva = subtotal_productos + costo_traslado
        // Backend: total_con_iva = total_sin_iva + iva
        // Despejando: subtotal_productos = total_con_iva - iva - costo_traslado
        
        const totalConIva = parseFloat(renta.total_con_iva) || parseFloat(renta.total) || 0;
        const iva = parseFloat(renta.iva) || 0;
        const costoTraslado = parseFloat(renta.costo_traslado) || 0;
        
        // Subtotal de productos solamente (sin incluir traslado)
        const subtotalProductos = Math.round((totalConIva - iva - costoTraslado) * 100) / 100;
        
        document.getElementById('detalle-subtotal').textContent = `$${subtotalProductos.toFixed(2)}`;
        document.getElementById('detalle-costo-traslado').textContent = `$${costoTraslado.toFixed(2)}`;
        document.getElementById('detalle-iva').textContent = `$${iva.toFixed(2)}`;
        document.getElementById('detalle-total').textContent = `$${totalConIva.toFixed(2)}`;

        // Observaciones
        if (renta.observaciones) {
            document.getElementById('detalle-observaciones').textContent = renta.observaciones;
            document.getElementById('detalle-observaciones-section').style.display = 'block';
        } else {
            document.getElementById('detalle-observaciones-section').style.display = 'none';
        }
    }

    function cargarDatosCliente(cliente) {
        document.getElementById('detalle-codigo-cliente').textContent = cliente.codigo;
        document.getElementById('detalle-nombre-cliente').textContent = cliente.nombre;
        document.getElementById('detalle-telefono-cliente').textContent = cliente.telefono;
        document.getElementById('detalle-email-cliente').textContent = cliente.email;
        document.getElementById('detalle-rfc-cliente').textContent = cliente.rfc;
        document.getElementById('detalle-direccion-cliente').textContent = cliente.direccion;
    }

    function cargarProductos(productos) {
        const tbody = document.getElementById('detalle-productos-tabla');

        if (productos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No hay productos</td></tr>';
            return;
        }

        let html = '';
        productos.forEach(producto => {
            html += `
                <tr>
                    <td>${producto.nombre}</td>
                    <td>${producto.cantidad}</td>
                    <td>${producto.dias_renta || 'N/A'}</td>
                    <td>$${parseFloat(producto.costo_unitario || 0).toFixed(2)}</td>
                    <td>$${parseFloat(producto.subtotal || 0).toFixed(2)}</td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    }

    function cargarHistorialPagos(pagos, totalRenta) {
        const tbody = document.getElementById('detalle-pagos-tabla');
        const resumenDiv = document.getElementById('detalle-resumen-pagos');
        
        if (!pagos || pagos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Sin historial de pagos</td></tr>';
            resumenDiv.innerHTML = '<div class="alert alert-info">No hay pagos registrados para esta renta.</div>';
            return;
        }

        // Calcular totales
        let totalAbonado = 0;
        pagos.forEach(pago => {
            totalAbonado += parseFloat(pago.monto) || 0;
        });
        const saldoPendiente = totalRenta - totalAbonado;

        // Mostrar resumen
        let estadoClass = '';
        let estadoTexto = '';
        if (saldoPendiente <= 0) {
            estadoClass = 'alert-success';
            estadoTexto = 'Renta totalmente pagada';
        } else if (totalAbonado > 0) {
            estadoClass = 'alert-warning';
            estadoTexto = 'Renta parcialmente pagada';
        } else {
            estadoClass = 'alert-danger';
            estadoTexto = 'Renta sin pagos';
        }

        resumenDiv.innerHTML = `
            <div class="${estadoClass}">
                <div class="row">
                    <div class="col-md-3">
                        <strong>Total renta:</strong><br>
                        $${totalRenta.toFixed(2)}
                    </div>
                    <div class="col-md-3">
                        <strong>Total abonado:</strong><br>
                        $${totalAbonado.toFixed(2)}
                    </div>
                    <div class="col-md-3">
                        <strong>Saldo pendiente:</strong><br>
                        $${saldoPendiente.toFixed(2)}
                    </div>
                    <div class="col-md-3">
                        <strong>Estado:</strong><br>
                        ${estadoTexto}
                    </div>
                </div>
            </div>
        `;

        // Mostrar tabla de pagos
        let html = '';
        pagos.forEach(pago => {
            html += `
                <tr>
                    <td>${pago.id}</td>
                    <td><span class="badge ${pago.tipo === 'inicial' ? 'bg-primary' : 'bg-success'}">${pago.tipo}</span></td>
                    <td>${pago.metodo_pago}</td>
                    <td>$${parseFloat(pago.monto).toFixed(2)}</td>
                    <td>${pago.fecha_emision}</td>
                    <td>
                        <a href="/prefactura/pdf/${pago.id}" target="_blank" class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-file-earmark-pdf"></i> PDF
                        </a>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    }

    function cargarRetrasosPendientes(data, rentaId) {
        console.log('Cargando retrasos pendientes:', data);
        const seccionRetrasos = document.getElementById('retrasos-pendientes');
        const tbody = document.getElementById('retrasos-pendientes-tabla');
        const btnCobrarRetraso = document.getElementById('btn-cobrar-retraso');
        const seccionPadre = document.getElementById('cobros-pendientes-section');
        
        if (!seccionRetrasos || !tbody || !btnCobrarRetraso || !seccionPadre) {
            console.error('Elementos de retrasos pendientes no encontrados:', {
                seccionRetrasos: !!seccionRetrasos,
                tbody: !!tbody,
                btnCobrarRetraso: !!btnCobrarRetraso,
                seccionPadre: !!seccionPadre
            });
            return;
        }
        
        if (!data || !data.retrasos || data.retrasos.length === 0) {
            console.log('Sin retrasos pendientes');
            seccionRetrasos.style.display = 'none';
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Sin retrasos pendientes</td></tr>';
            return;
        }
        
        console.log('Mostrando retrasos pendientes:', data.retrasos.length);
        // Mostrar sección
        seccionRetrasos.style.display = 'block';
        seccionPadre.style.display = 'block';
        btnCobrarRetraso.style.display = 'inline-block';
        
        // Configurar botón
        btnCobrarRetraso.onclick = () => {
            console.log('Abriendo modal cobro retraso para renta:', rentaId);
            // Abrir modal de cobro retraso con datos
            if (window.abrirModalCobroRetraso) {
                window.abrirModalCobroRetraso(rentaId);
            } else {
                console.error('Función abrirModalCobroRetraso no disponible');
            }
        };
        
        // Llenar tabla
        tbody.innerHTML = data.retrasos.map(retraso => `
            <tr>
                <td>
                    <span class="badge bg-danger">${retraso.dias_retraso} día${retraso.dias_retraso > 1 ? 's' : ''}</span>
                </td>
                <td>$${parseFloat(retraso.monto_total || 0).toFixed(2)}</td>
                <td>
                    <span class="badge ${retraso.estado === 'pendiente' ? 'bg-warning' : 'bg-success'}">
                        ${retraso.estado === 'pendiente' ? 'Pendiente' : 'Pagado'}
                    </span>
                </td>
            </tr>
        `).join('');
    }
    
    function cargarExtrasPendientes(data, rentaId) {
        console.log('Cargando extras pendientes:', data);
        const seccionExtras = document.getElementById('extras-pendientes');
        const tbody = document.getElementById('extras-pendientes-tabla');
        const btnCobrarExtra = document.getElementById('btn-cobrar-extra');
        const seccionPadre = document.getElementById('cobros-pendientes-section');
        
        if (!seccionExtras || !tbody || !btnCobrarExtra || !seccionPadre) {
            console.error('Elementos de extras pendientes no encontrados:', {
                seccionExtras: !!seccionExtras,
                tbody: !!tbody,
                btnCobrarExtra: !!btnCobrarExtra,
                seccionPadre: !!seccionPadre
            });
            return;
        }
        
        if (!data || !data.extras || data.extras.length === 0) {
            console.log('Sin cobros extra pendientes');
            seccionExtras.style.display = 'none';
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Sin cobros extra pendientes</td></tr>';
            return;
        }
        
        console.log('Mostrando cobros extra pendientes:', data.extras.length);
        // Mostrar sección
        seccionExtras.style.display = 'block';
        seccionPadre.style.display = 'block';
        btnCobrarExtra.style.display = 'inline-block';
        
        // Configurar botón
        btnCobrarExtra.onclick = () => {
            console.log('Abriendo modal cobro extra para renta:', rentaId);
            // Abrir modal de cobro extra con datos
            if (window.abrirModalCobroExtra) {
                window.abrirModalCobroExtra(rentaId);
            } else {
                console.error('Función abrirModalCobroExtra no disponible');
            }
        };
        
        // Llenar tabla
        tbody.innerHTML = data.extras.map(extra => `
            <tr>
                <td>${extra.concepto}</td>
                <td>${extra.descripcion || 'N/A'}</td>
                <td>$${parseFloat(extra.monto_total || 0).toFixed(2)}</td>
                <td>
                    <span class="badge ${extra.estado === 'pendiente' ? 'bg-warning' : 'bg-success'}">
                        ${extra.estado === 'pendiente' ? 'Pendiente' : 'Pagado'}
                    </span>
                </td>
            </tr>
        `).join('');
    }

});